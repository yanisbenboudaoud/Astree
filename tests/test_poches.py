"""Tests des poches : plusieurs horizons dans un même portefeuille (pipeline/poches.py, #115).

Sans Bedrock : l'Agent Profil, l'orchestrateur et le débat sont remplacés par les faux
de test_orchestrateur. Les simulations utilisent les vraies données du jeu de départ.
Le profil de test à deux poches est ``personas/sofia.json`` (fictif).
"""

import copy
import json

import pytest

from contrat.valider import valider_contrat
from pipeline import agent_profil, contre_interrogatoire, tribunal
from pipeline.agent_profil import (
    REGLE_CONTROLE,
    charger_profil,
    choisir_poche,
    construire_message,
    lancer_agent_profil,
    schema_extraction,
    structurer_decision,
)
from pipeline.calibrage import ErreurCalibrage, reponses_demo
from pipeline.pacte import erreurs_profil, pacte_pour_contrat, piece_pacte
from pipeline.poches import (
    PocheInconnue,
    a_des_poches,
    formater_horizon,
    poche_la_plus_prudente,
    portefeuille_global,
    profil_de_la_poche,
    regles_de_la_poche,
)
from pipeline.profils import appliquer_modifications
from pipeline.questionnaire import ReponsesInvalides, detail_bareme, profil_depuis_reponses
from pipeline.tribunal import LIMITE_POCHE, juger_decision, verifier_avant_proces
from pipeline.univers import charger_univers
from tests.test_orchestrateur import EXTRACTION_TSLA, FauxDebat, FauxModele, demande
from tests.test_route_profil import SAISIE

DEUX_POCHES = charger_profil("sofia")  # court terme −8 %, long terme −40 %
SANS_POCHES = charger_profil("robert")
UNIVERS = charger_univers()
EXTRACTION_TSLA_20 = {**EXTRACTION_TSLA, "taille": 0.20}


def profil_modifie(**modifications):
    profil = copy.deepcopy(DEUX_POCHES)
    for chemin, valeur in modifications.items():
        cible = profil
        *parents, cle = chemin.split("__")
        for parent in parents:
            cible = cible[int(parent)] if parent.isdigit() else cible[parent]
        cible[cle] = valeur
    return profil


# --- Format du profil ---------------------------------------------------------------


def test_le_profil_de_test_a_deux_poches_est_valide():
    assert erreurs_profil(DEUX_POCHES, nom_fichier="sofia") == []
    assert a_des_poches(DEUX_POCHES) and not a_des_poches(SANS_POCHES)


@pytest.mark.parametrize("modifications, message", [
    ({"poches__0__part": 0.4}, "les parts totalisent 1.1000"),
    ({"poches__1__id": "mise_de_fonds"}, "id de poche en double"),
    ({"poches__0__horizon_ans": [5, 3]}, "le minimum 5 dépasse le maximum 3"),
    ({"poches__0__portefeuille": [{"ticker": "ZST.TO", "poids": 0.5}]}, "les poids totalisent 0.5000"),
    ({"portefeuille": [{"ticker": "SPY", "poids": 1.0}]}, "somme des portefeuilles des poches"),
    ({"decision_demo__poche": "vacances"}, "« vacances » n'est pas une poche du profil"),
])
def test_poches_incoherentes_refusees(modifications, message):
    erreurs = erreurs_profil(profil_modifie(**modifications))
    assert any(message in erreur for erreur in erreurs), erreurs


def test_regle_d_une_poche_validee_comme_une_regle_commune():
    profil = copy.deepcopy(DEUX_POCHES)
    profil["poches"][1]["regles"].append({"id": "horizon_ans", "type": "qualitative", "libelle": "x",
                                          "justification": "y"})
    profil["poches"][1]["regles"].append({"id": "plafond_x", "type": "plafond", "categories": ["inconnue"],
                                          "max": 0.1, "libelle": "x", "justification": "y"})
    erreurs = erreurs_profil(profil)
    assert any("poches/1 (poche « retraite »)/regles/1" in e and "id réservé" in e for e in erreurs)
    assert any("catégorie inconnue : inconnue" in e for e in erreurs)


def test_une_poche_sans_aucune_regle_est_refusee():
    profil = copy.deepcopy(DEUX_POCHES)
    profil["pacte"]["regles"] = []
    profil["poches"][1]["regles"] = []
    assert any("aucune règle, ni commune" in e for e in erreurs_profil(profil))


def test_sans_poches_le_pacte_doit_avoir_une_regle_et_la_decision_aucune_poche():
    profil = copy.deepcopy(SANS_POCHES)
    profil["pacte"]["regles"] = []
    profil["decision_demo"]["poche"] = "retraite"
    erreurs = erreurs_profil(profil)
    assert "pacte/regles : au moins une règle est nécessaire" in erreurs
    assert any("le profil n'a pas de poches" in e for e in erreurs)


def test_portefeuille_global_somme_des_poches_ponderees():
    assert {l["ticker"]: round(l["poids"], 6) for l in portefeuille_global(DEUX_POCHES["poches"])} == {
        l["ticker"]: l["poids"] for l in DEUX_POCHES["portefeuille"]}


# --- Projection sur une poche -------------------------------------------------------


def test_profil_de_la_poche_a_la_forme_d_un_profil_sans_poches():
    projete = profil_de_la_poche(DEUX_POCHES, "mise_de_fonds")
    poche = DEUX_POCHES["poches"][0]
    assert "poches" not in projete
    assert projete["portefeuille"] == poche["portefeuille"]
    assert projete["horizon_ans"] == [3, 3] and projete["profil_risque"] == "faible"
    assert projete["capital_fictif_cad"] == 30000  # 100 000 $ × 30 %
    assert [r["id"] for r in projete["pacte"]["regles"]] == ["pire_baisse_max", "disponible_a_la_date",
                                                              "plafond_crypto"]
    assert projete["poche"] == {"id": "mise_de_fonds", "objectif": "Mise de fonds d'une maison",
                                "horizon_ans": [3, 3], "part": 0.3}
    assert projete["decision_demo"]["poche"] == "mise_de_fonds"
    assert "decision_demo" not in profil_de_la_poche(DEUX_POCHES, "retraite")  # elle vise l'autre poche
    assert DEUX_POCHES["poches"][0]["portefeuille"] is not projete["portefeuille"]  # copie, original intact


def test_une_regle_de_la_poche_remplace_la_regle_commune_de_meme_id():
    profil = copy.deepcopy(DEUX_POCHES)
    profil["pacte"]["regles"].append({"id": "pire_baisse_max", "type": "pire_baisse_max", "seuil": -0.2,
                                      "libelle": "Commune", "justification": "x"})
    regles = regles_de_la_poche(profil, profil["poches"][1])
    assert [(r["id"], r.get("seuil")) for r in regles] == [("pire_baisse_max", -0.4), ("plafond_crypto", None)]


def test_poche_inconnue_ou_profil_sans_poches():
    with pytest.raises(PocheInconnue, match="Aucune poche « vacances »"):
        profil_de_la_poche(DEUX_POCHES, "vacances")
    with pytest.raises(PocheInconnue, match="n'a pas de poches"):
        profil_de_la_poche(SANS_POCHES, "retraite")


def test_la_poche_la_plus_prudente_est_celle_a_l_horizon_le_plus_court():
    assert poche_la_plus_prudente(DEUX_POCHES)["id"] == "mise_de_fonds"
    inverse = copy.deepcopy(DEUX_POCHES)
    inverse["poches"].reverse()
    assert poche_la_plus_prudente(inverse)["id"] == "mise_de_fonds"


@pytest.mark.parametrize("horizon, texte", [([3, 5], "3 à 5 ans"), ([3, 3], "3 ans"), ([25, None], "25 ans et plus")])
def test_formater_horizon(horizon, texte):
    assert formater_horizon(horizon) == texte


def test_pacte_et_piece_du_contrat_pour_une_poche():
    projete = profil_de_la_poche(DEUX_POCHES, "retraite")
    pacte = pacte_pour_contrat(projete)
    assert pacte["poche"]["id"] == "retraite" and pacte["horizon_ans"] == [25, None]
    assert [r["id"] for r in pacte["regles"]] == ["pire_baisse_max", "plafond_crypto"]
    piece = piece_pacte(projete, "P1")
    assert piece["valeurs"]["part_poche"] == 0.7 and piece["valeurs"]["pire_baisse_max"] == -0.4
    assert piece["titre"] == "Pacte de Sofia : poche « Retraite »"


def test_sans_poches_pacte_et_piece_inchanges():
    assert "poche" not in pacte_pour_contrat(SANS_POCHES)
    piece = piece_pacte(SANS_POCHES, "P1")
    assert "part_poche" not in piece["valeurs"] and piece["titre"] == "Pacte de Robert"


# --- Agent Profil : quelle poche ? --------------------------------------------------


def test_poche_imposee_par_l_utilisateur():
    choisie, controles, hypotheses, etape = choisir_poche(DEUX_POCHES, None, "retraite")
    assert choisie == "retraite" and controles == []
    assert etape["outil"] == "choisir_poche" and etape["sortie"].startswith("retraite")
    assert "jugée dans la poche « Retraite » (70 % du portefeuille)" in hypotheses[-1]


def test_poche_deduite_par_le_modele():
    choisie, controles, hypotheses, _ = choisir_poche(DEUX_POCHES, "retraite", None)
    assert choisie == "retraite" and controles == []
    assert any("déduite de la demande" in h for h in hypotheses)


def test_poche_imposee_contredite_par_la_demande_a_verifier():
    choisie, controles, _, _ = choisir_poche(DEUX_POCHES, "retraite", "mise_de_fonds")
    assert choisie == "mise_de_fonds"
    assert [c["regle"] for c in controles] == [REGLE_CONTROLE] and controles[0]["statut"] == "a_verifier"


def test_poche_non_precisee_la_plus_prudente_a_verifier():
    choisie, controles, _, _ = choisir_poche(DEUX_POCHES, None, None)
    assert choisie == "mise_de_fonds"
    assert controles[0]["regle"] == REGLE_CONTROLE and "Poche non précisée" in controles[0]["message"]


def test_sans_poches_ni_champ_ni_consigne_de_poche_pour_le_modele():
    assert "poche" not in schema_extraction(UNIVERS, SANS_POCHES)["properties"]
    assert "poche" not in construire_message("30 % en Tesla", SANS_POCHES, UNIVERS).lower()


def test_avec_poches_le_modele_voit_les_poches_et_ne_choisit_qu_une_poche_connue():
    schema = schema_extraction(UNIVERS, DEUX_POCHES)
    assert schema["properties"]["poche"]["anyOf"][0]["enum"] == ["mise_de_fonds", "retraite"]
    assert "poche" in schema["required"]
    message = construire_message("20 % en Tesla dans ma retraite", DEUX_POCHES, UNIVERS)
    assert "- retraite : Retraite (horizon : 25 ans et plus" in message


def test_un_montant_devient_une_part_de_la_poche(monkeypatch):
    extraction = {**EXTRACTION_TSLA, "taille": None, "montant": 6000, "devise_montant": "CAD", "poche": "mise_de_fonds"}
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: extraction)
    resultat = structurer_decision("6 000 $ en Tesla pour la maison", DEUX_POCHES, UNIVERS)
    assert resultat.decision["taille"] == pytest.approx(0.20)  # 6 000 $ / 30 000 $ de la poche
    assert resultat.decision["poche"] == "mise_de_fonds"
    assert resultat.decision["libelle"] == "20 % en TSLA (poche « Mise de fonds d'une maison »)"
    assert [e["outil"] for e in resultat.trace] == ["bedrock", "choisir_poche", "valider_decision"]


def test_financement_depuis_un_titre_d_une_autre_poche_refuse(monkeypatch):
    extraction = {**EXTRACTION_TSLA_20, "financement_depuis": "SPY", "poche": "mise_de_fonds"}
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: extraction)
    resultat = structurer_decision("20 % en Tesla, financé par SPY", DEUX_POCHES, UNIVERS)
    assert resultat.decision["financement"] == "proportionnel"  # SPY n'est que dans la poche retraite
    assert any("SPY impossible" in c["message"] for c in resultat.controles)


def test_poche_inconnue_refusee_avant_bedrock(monkeypatch):
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: pytest.fail("aucun appel Bedrock attendu"))
    with pytest.raises(PocheInconnue):
        lancer_agent_profil("20 % en Tesla", "sofia", "P1", poche="vacances")
    with pytest.raises(PocheInconnue):
        verifier_avant_proces("sofia", poche="vacances")


# --- Le procès dans une poche -------------------------------------------------------


@pytest.fixture
def proces_sans_bedrock(monkeypatch):
    debat = FauxDebat()
    monkeypatch.setattr(tribunal, "debattre", debat.debattre)
    monkeypatch.setattr(tribunal, "corriger_argument", debat.corriger_argument)

    def extraire(poche=None):
        monkeypatch.setattr(agent_profil, "appeler_llm",
                            lambda *args: {**copy.deepcopy(EXTRACTION_TSLA_20), "poche": poche})
    extraire()
    return extraire


def controle(contrat, regle):
    return next(c for c in contrat["controles"] if c["regle"] == regle)


def test_meme_decision_violation_court_terme_et_conforme_long_terme(proces_sans_bedrock):
    """Critère de l'issue #115 : court terme −8 %, long terme −40 %, la même décision (20 % en TSLA)."""
    court = juger_decision("sofia", "Je veux mettre 20 % en Tesla", converser=FauxModele(), poche="mise_de_fonds")
    long = juger_decision("sofia", "Je veux mettre 20 % en Tesla", converser=FauxModele(), poche="retraite")

    assert controle(court, "pire_baisse_max")["statut"] == "violation"
    assert controle(long, "pire_baisse_max")["statut"] == "conforme"
    # Simulation sur la poche, pas sur le portefeuille global : le départ diffère.
    assert court["comparaison"]["actuel"]["pire_baisse"] > -0.08 > court["comparaison"]["apres"]["pire_baisse"]
    assert long["comparaison"]["apres"]["pire_baisse"] > -0.40
    assert court["comparaison"]["actuel"] != long["comparaison"]["actuel"]
    assert court["taille_max_compatible"] < 0.20 and long["taille_max_compatible"] == 0.20
    assert [p["regle"] for p in court["points_de_bascule"]] == ["pire_baisse_max"] and long["points_de_bascule"] == []
    for contrat, poche in ((court, "mise_de_fonds"), (long, "retraite")):
        assert contrat["decision"]["poche"] == contrat["pacte"]["poche"]["id"] == poche
        assert LIMITE_POCHE in contrat["limites"]
        assert valider_contrat(contrat) == []


def test_poche_deduite_de_la_demande(proces_sans_bedrock):
    proces_sans_bedrock("retraite")
    contrat = juger_decision("sofia", "20 % de ma retraite en Tesla", converser=FauxModele())
    assert contrat["decision"]["poche"] == "retraite"
    assert all(c["regle"] != REGLE_CONTROLE for c in contrat["controles"])
    assert valider_contrat(contrat) == []


def test_poche_non_precisee_jugee_dans_la_plus_prudente(proces_sans_bedrock):
    contrat = juger_decision("sofia", "Je veux mettre 20 % en Tesla", converser=FauxModele())
    assert contrat["decision"]["poche"] == "mise_de_fonds"
    assert controle(contrat, REGLE_CONTROLE)["statut"] == "a_verifier"
    assert valider_contrat(contrat) == []


def test_sans_poches_aucune_trace_de_poche_dans_le_contrat(monkeypatch):
    """Un profil sans poches donne le même contrat qu'avant #115 : aucun champ, contrôle, étape ni limite de poche."""
    debat = FauxDebat()
    monkeypatch.setattr(tribunal, "debattre", debat.debattre)
    monkeypatch.setattr(tribunal, "corriger_argument", debat.corriger_argument)
    schemas = []
    monkeypatch.setattr(agent_profil, "appeler_llm",
                        lambda systeme, message, schema: schemas.append(schema) or copy.deepcopy(EXTRACTION_TSLA))
    contrat = juger_decision("robert", "Je veux mettre 30 % en Tesla",
                             converser=FauxModele([demande("indicateurs_actif", ticker="TSLA")]))
    assert "poche" not in contrat["decision"] and "poche" not in contrat["pacte"]
    assert contrat["pacte"] == pacte_pour_contrat(SANS_POCHES)
    assert "part_poche" not in contrat["pieces"][0]["valeurs"]
    assert all(e["outil"] != "choisir_poche" for e in contrat["trace"])
    assert LIMITE_POCHE not in contrat["limites"]
    assert "poche" not in schemas[0]["properties"]
    assert not any("poche" in h for h in contrat["hypotheses"])
    assert valider_contrat(contrat) == []


def test_pacte_vecu_d_un_profil_a_poches_demande_la_poche(proces_sans_bedrock, monkeypatch):
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: pytest.fail("aucun appel Bedrock attendu"))
    with pytest.raises(ErreurCalibrage, match="précisez la poche"):
        juger_decision("sofia", "20 % en Tesla", converser=FauxModele(),
                       calibrage={"reponses": {"baisse_25": "reste"}, "date": "2026-11-15"})


def test_pacte_vecu_mesure_la_pire_baisse_de_la_poche(proces_sans_bedrock):
    poche = profil_de_la_poche(DEUX_POCHES, "retraite")
    reponses = reponses_demo({**poche, "calibrage_demo": {"date": "2026-11-15", "reste_jusqu_a": -0.25,
                                                          "capacite": "attendre", "justification": "test"}})[0]
    contrat = juger_decision("sofia", "20 % en Tesla", converser=FauxModele(), poche="retraite",
                             calibrage={"reponses": reponses, "date": "2026-11-15", "etiquette": "fictif"})
    regle = next(r for r in contrat["pacte"]["regles"] if r["type"] == "pire_baisse_max")
    assert regle["piece"] == "P2" and regle["seuil"] != -0.40  # seuil de la poche remplacé par le seuil mesuré
    assert contrat["pacte"]["poche"]["id"] == "retraite"
    assert valider_contrat(contrat) == []


# --- Contrat et contre-interrogatoire ----------------------------------------------


def test_valider_refuse_une_decision_hors_de_la_poche_du_pacte(proces_sans_bedrock):
    contrat = juger_decision("sofia", "20 % en Tesla", converser=FauxModele(), poche="retraite")
    contrat["decision"]["poche"] = "mise_de_fonds"
    assert any("decision/poche" in e for e in valider_contrat(contrat))
    del contrat["decision"]["poche"]
    assert any("decision/poche" in e for e in valider_contrat(contrat))


def test_contre_interrogatoire_porte_sur_la_poche_jugee(proces_sans_bedrock, monkeypatch):
    contrat = juger_decision("sofia", "20 % en Tesla", converser=FauxModele(), poche="mise_de_fonds")
    vus = []

    def instruire(decision, profil, *args, **kwargs):
        vus.append(profil)
        raise RuntimeError("arrêt après l'instruction")
    monkeypatch.setattr(contre_interrogatoire, "instruire_question", instruire)
    with pytest.raises(RuntimeError):
        contre_interrogatoire.interroger(contrat, "Et sur le portefeuille global ?")
    assert vus[0]["poche"]["id"] == "mise_de_fonds"
    assert vus[0]["portefeuille"] == DEUX_POCHES["poches"][0]["portefeuille"]


# --- Questionnaire : plusieurs objectifs --------------------------------------------

OBJECTIFS = [
    {"id": "maison", "objectif": "Mise de fonds", "horizon": "moins_3", "part": 0.4,
     "portefeuille": [{"ticker": "ZST.TO", "poids": 0.8}, {"ticker": "XBB.TO", "poids": 0.2}]},
    {"id": "retraite", "objectif": "Retraite", "horizon": "plus_15", "part": 0.6,
     "portefeuille": [{"ticker": "XIU.TO", "poids": 0.5}, {"ticker": "SPY", "poids": 0.5}]},
]


def profil_du_questionnaire(objectifs=OBJECTIFS, **options):
    return profil_depuis_reponses(SAISIE["reponses"], SAISIE["capital_cad"], None, SAISIE["date"],
                                  identifiant="investisseur_poches", objectifs=objectifs, **options)


def test_questionnaire_a_plusieurs_objectifs_donne_un_profil_a_poches():
    profil = profil_du_questionnaire()
    assert erreurs_profil(profil, nom_fichier="investisseur_poches") == []
    maison, retraite = profil["poches"]
    seuil = {p["id"]: next(r["seuil"] for r in p["regles"] if r["id"] == "pire_baisse_max") for p in profil["poches"]}
    assert seuil["maison"] == -0.10  # horizon de moins de 3 ans : le plus contraignant
    assert seuil["retraite"] == -0.20  # coussin de 3 à 6 mois : commun, plus contraignant que l'horizon
    assert maison["reponse_horizon"] == "moins_3" and maison["horizon_ans"] == [0, 3]
    assert profil["horizon_ans"] == [0, None]
    assert all(r["id"] != "pire_baisse_max" for r in profil["pacte"]["regles"])  # préférences communes seulement
    assert {l["ticker"]: round(l["poids"], 6) for l in profil["portefeuille"]} == {
        "ZST.TO": 0.32, "XBB.TO": 0.08, "XIU.TO": 0.3, "SPY": 0.3}
    assert "Poche « Mise de fonds »" in maison["regles"][0]["justification"]


def test_piece_du_questionnaire_d_une_poche_part_de_son_horizon(monkeypatch, tmp_path):
    profil = profil_du_questionnaire()
    projete = profil_de_la_poche(profil, "maison")
    assert projete["questionnaire"]["reponses"]["horizon"] == "moins_3"
    assert profil["questionnaire"]["reponses"]["horizon"] == SAISIE["reponses"]["horizon"]  # original intact


def test_detail_du_bareme_par_poche():
    detail = detail_bareme(SAISIE["reponses"], SAISIE["date"], OBJECTIFS)
    assert [(p["id"], p["seuil_retenu"]["valeur"]) for p in detail["poches"]] == [("maison", -0.1), ("retraite", -0.2)]


@pytest.mark.parametrize("objectifs, message", [
    (OBJECTIFS[:1], "au moins deux objectifs"),
    ([{**OBJECTIFS[0], "horizon": "demain"}, OBJECTIFS[1]], "horizon « demain » inconnu"),
    ([{**OBJECTIFS[0], "part": 0}, OBJECTIFS[1]], "part invalide"),
    ([{**OBJECTIFS[0], "portefeuille": [{"ticker": "INCONNU", "poids": 1}]}, OBJECTIFS[1]], "hors de l'univers"),
    ([{**OBJECTIFS[0], "part": 0.5}, OBJECTIFS[1]], "les parts totalisent 1.1000"),
])
def test_objectifs_invalides_refuses(objectifs, message):
    with pytest.raises(ReponsesInvalides) as erreur:
        profil_du_questionnaire(objectifs)
    assert any(message in e for e in erreur.value.erreurs), erreur.value.erreurs


def test_seuil_d_une_poche_choisi_par_l_utilisateur():
    profil = appliquer_modifications(profil_du_questionnaire(), {"retraite/pire_baisse_max": -0.3}, "2026-11-15")
    retraite = profil["poches"][1]["regles"][0]
    assert retraite["seuil"] == -0.3 and "Choisi par vous" in retraite["justification"]
    assert profil["poches"][0]["regles"][0]["seuil"] == -0.10  # l'autre poche ne change pas
    with pytest.raises(ReponsesInvalides, match="Règle inconnue"):
        appliquer_modifications(profil, {"pire_baisse_max": -0.3}, "2026-11-15")  # pas de règle commune de ce nom


def test_proces_d_un_profil_a_poches_tire_du_questionnaire(proces_sans_bedrock, tmp_path, monkeypatch):
    profil = profil_du_questionnaire()
    (tmp_path / "investisseur_poches.json").write_text(json.dumps(profil, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(agent_profil, "DOSSIER_PERSONAS", tmp_path)
    contrat = juger_decision("investisseur_poches", "20 % en Tesla", converser=FauxModele(), poche="maison")
    piece_q = next(p for p in contrat["pieces"] if p["outil"] == "lire_questionnaire")
    assert piece_q["valeurs"]["horizon_ans"] == [0, 3] and piece_q["valeurs"]["seuil_retenu"] == -0.10
    assert controle(contrat, "pire_baisse_max")["statut"] == "violation"
    assert valider_contrat(contrat) == []
