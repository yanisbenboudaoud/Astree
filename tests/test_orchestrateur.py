"""Tests de l'orchestrateur et du Tribunal (#12).

Le modèle est remplacé par un faux qui rejoue des tours écrits à l'avance : les
tests ne coûtent rien et tournent sans accès AWS. Les tests réels (marqueur
« bedrock ») font de vrais appels payants ; ils ne tournent qu'avec
« pytest -m bedrock ».
"""

import copy
import itertools
import json

import pytest
from jsonschema import Draft202012Validator

from contrat.valider import charger_schema, valider_contrat
from pipeline import agent_profil, tribunal
from pipeline.agent_profil import chemin_profil
from pipeline.donnees import ErreurDonnees
from pipeline.llm import DemandeOutil, TourOutils, decrire_outil
from pipeline.orchestrateur import (
    BUDGET_APPELS,
    RAISON_D_OFFICE,
    RAISON_REFUSEE,
    Outil,
    construire_dossier,
    entree_simulation_obligatoire,
    instruire_dossier,
    raison_valide,
)
from pipeline.pacte import charger_pacte, pacte_pour_contrat, piece_pacte
from pipeline.debat import ResultatDebat as DebatResultat
from pipeline.tribunal import AVERTISSEMENT, juger_decision

PROFIL = charger_pacte(chemin_profil("robert"))
DECISION = {"type": "position", "ticker": "TSLA", "taille": 0.3, "financement": "proportionnel",
            "libelle": "30 % en TSLA"}
RAISON = "Horizon court : mesurer le temps de récupération du titre"
SIMULATION_DECISION = entree_simulation_obligatoire(DECISION)

_identifiants = itertools.count(1)


def demande(nom, raison=RAISON, **entree):
    return DemandeOutil(id=f"u{next(_identifiants)}", nom=nom, entree={**entree, "raison": raison})


class FauxModele:
    """Rejoue des tours écrits à l'avance et garde ce que le modèle a reçu."""

    def __init__(self, *tours):
        self.tours = list(tours)
        self.appels = []

    def __call__(self, systeme, conversation, outils):
        self.appels.append({"systeme": systeme, "conversation": list(conversation), "outils": outils})
        demandes = self.tours.pop(0) if self.tours else []
        return TourOutils(message_assistant={"role": "assistant", "content": []},
                          demandes=demandes, texte="")


def resultats_envoyes(modele, tour):
    """Blocs toolResult renvoyés au modèle après le tour donné (0 = premier)."""
    return [bloc["toolResult"] for bloc in modele.appels[tour + 1]["conversation"][-1]["content"]]


def faux_outil(nom, champs, erreur=None):
    schema = {"type": "object", "properties": {c: {"type": "string"} for c in champs},
              "required": list(champs), "additionalProperties": False}

    def executer(entree, id_piece):
        if erreur:
            raise ErreurDonnees(erreur)
        return {"id": id_piece, "outil": nom, "entree": entree}

    return Outil(nom, decrire_outil(nom, f"Outil {nom}", schema), executer)


INDICATEURS = faux_outil("indicateurs_actif", ["ticker"])
SIMULER = faux_outil("simuler_portefeuille", ["ticker", "taille", "financement", "periode"])
FAUX_OUTILS = [INDICATEURS, SIMULER]


def instruire(modele, outils=FAUX_OUTILS):
    return instruire_dossier(DECISION, PROFIL, premier_numero=2, outils=outils, converser=modele)


# --- Boucle et pièces ---------------------------------------------------------


def test_execute_les_outils_choisis_et_numerote_les_pieces():
    modele = FauxModele([demande("indicateurs_actif", ticker="TSLA"),
                         demande("simuler_portefeuille", **{**SIMULATION_DECISION, "periode": "2022"})])
    resultat = instruire(modele)
    assert [p["id"] for p in resultat.pieces] == ["P2", "P3", "P4"]  # P4 : simulation d'office
    assert resultat.trace[0] == {"etape": "orchestrateur", "outil": "indicateurs_actif",
                                 "raison": RAISON, "entree": {"ticker": "TSLA"}, "sortie": "P2"}
    envoye = resultats_envoyes(modele, 0)[0]
    assert envoye["status"] == "success"
    assert envoye["content"][0]["json"]["id"] == "P2"
    assert "raison" not in envoye["content"][0]["json"]["entree"]  # la raison ne va pas à l'outil


def test_le_modele_recoit_chaque_outil_avec_le_parametre_raison():
    modele = FauxModele()
    instruire(modele)
    schema_envoye = modele.appels[0]["outils"][0]["toolSpec"]["inputSchema"]["json"]
    assert schema_envoye["required"] == ["ticker", "raison"]
    assert INDICATEURS.description_bedrock["toolSpec"]["inputSchema"]["json"]["required"] == ["ticker"]


def test_dossier_sans_justifications_ni_nom():
    dossier = construire_dossier(DECISION, PROFIL)
    assert "justification" not in dossier
    assert PROFIL["nom"] not in dossier
    assert "pire_baisse_max" in dossier and "ZST.TO" in dossier


# --- Garde-fous ---------------------------------------------------------------


def test_budget_maximum_d_appels():
    modele = FauxModele(*[[demande("indicateurs_actif", ticker=f"T{i}")] for i in range(BUDGET_APPELS + 3)])
    resultat = instruire(modele)
    assert resultat.appels == BUDGET_APPELS
    assert len(modele.appels) == BUDGET_APPELS  # plus aucun tour une fois le budget atteint


def test_budget_depasse_dans_un_meme_tour():
    modele = FauxModele([demande("indicateurs_actif", ticker=f"T{i}") for i in range(BUDGET_APPELS + 2)])
    resultat = instruire(modele)
    refusees = [e for e in resultat.trace if e["sortie"] == "Erreur : Budget d'appels atteint"]
    assert len(refusees) == 2
    assert len(resultat.pieces) == BUDGET_APPELS + 1  # 8 demandées + la simulation d'office


def test_outil_hors_liste_blanche_refuse():
    modele = FauxModele([demande("verifier_chiffres", texte="…")])
    resultat = instruire(modele)
    assert resultats_envoyes(modele, 0)[0]["status"] == "error"
    assert resultat.trace[0]["sortie"] == "Erreur : Outil « verifier_chiffres » non autorisé"
    assert resultat.trace[0]["raison"] == RAISON_REFUSEE


@pytest.mark.parametrize("raison, motif", [
    ("La pire baisse dépasse 12 %", "aucun chiffre"),
    ("", "obligatoire"),
    ("   ", "obligatoire"),
    (None, "obligatoire"),
    ("x" * 200, "au plus 160 caractères"),
])
def test_raison_avec_chiffre_vide_ou_trop_longue_refusee(raison, motif):
    assert not raison_valide(raison)
    modele = FauxModele([demande("indicateurs_actif", raison=raison, ticker="TSLA")])
    resultat = instruire(modele)
    envoye = resultats_envoyes(modele, 0)[0]
    assert envoye["status"] == "error"
    assert motif in envoye["content"][0]["json"]["erreur"]  # le modèle sait quoi corriger
    assert resultat.trace[0]["raison"] == RAISON_REFUSEE


def test_erreur_d_outil_renvoyee_au_modele_sans_planter():
    titre_inconnu = faux_outil("indicateurs_actif", ["ticker"],
                               erreur="Titre(s) absent(s) de l'univers d'actifs : ZZZ")
    modele = FauxModele([demande("indicateurs_actif", ticker="ZZZ")])
    resultat = instruire(modele, [titre_inconnu, SIMULER])
    envoye = resultats_envoyes(modele, 0)[0]
    assert envoye["status"] == "error"
    assert "ZZZ" in envoye["content"][0]["json"]["erreur"]
    assert resultat.trace[0]["sortie"].startswith("Erreur : Titre(s) absent(s)")
    assert [e["outil"] for e in resultat.trace] == ["indicateurs_actif", "simuler_portefeuille"]


def test_simulation_ajoutee_d_office():
    resultat = instruire(FauxModele([demande("indicateurs_actif", ticker="TSLA")]))
    derniere = resultat.trace[-1]
    assert derniere == {"etape": "orchestrateur", "outil": "simuler_portefeuille",
                        "raison": RAISON_D_OFFICE, "entree": SIMULATION_DECISION, "sortie": "P3"}


def test_simulation_pas_dupliquee_si_deja_demandee():
    resultat = instruire(FauxModele([demande("simuler_portefeuille", **SIMULATION_DECISION)]))
    assert len(resultat.pieces) == 1
    assert RAISON_D_OFFICE not in [e["raison"] for e in resultat.trace]


def test_simulation_d_une_autre_taille_ne_compte_pas():
    resultat = instruire(FauxModele([demande("simuler_portefeuille", **{**SIMULATION_DECISION, "taille": 0.1})]))
    assert [e["raison"] for e in resultat.trace] == [RAISON, RAISON_D_OFFICE]


def test_reallocation_simulation_obligatoire_ajoutee_d_office():
    reallocation = {"type": "reallocation", "panier": [{"ticker": "BTC-USD", "poids": 1.0}],
                    "part_reallouee": 0.2, "libelle": "20 % réalloué vers BTC-USD"}
    resultat = instruire_dossier(reallocation, PROFIL, premier_numero=2, outils=FAUX_OUTILS,
                                 converser=FauxModele())
    assert resultat.pieces == [{"id": "P2", "outil": "simuler_portefeuille",
                                "entree": {"part_reallouee": 0.2, "periode": "complete"}}]
    assert resultat.trace[-1]["raison"] == RAISON_D_OFFICE
    assert resultat.piece_simulation["id"] == "P2"


def test_raisons_de_la_trace_sans_chiffre():
    modele = FauxModele([demande("indicateurs_actif", raison="Il y a 3 risques", ticker="TSLA")],
                        [demande("indicateurs_actif", ticker="TSLA")])
    assert all(raison_valide(e["raison"]) for e in instruire(modele).trace)


# --- Avec les vrais outils (sans Bedrock) ------------------------------------


def valider_piece(piece):
    schema = charger_schema()
    validateur = Draft202012Validator({"$defs": schema["$defs"], "$ref": "#/$defs/piece"})
    assert list(validateur.iter_errors(piece)) == []


def test_vrais_outils_produisent_des_pieces_du_contrat():
    modele = FauxModele([
        demande("indicateurs_actif", ticker="TSLA"),
        demande("simuler_portefeuille", **{**SIMULATION_DECISION, "periode": "2022"}),
    ])
    resultat = instruire_dossier(DECISION, PROFIL, premier_numero=2, converser=modele)
    assert [p["outil"] for p in resultat.pieces] == ["indicateurs_actif", "simuler_portefeuille",
                                                     "simuler_portefeuille"]
    for piece in resultat.pieces:
        valider_piece(piece)
    # Simulation d'office : mêmes chiffres que la pièce P1 de la maquette.
    assert round(resultat.pieces[-1]["valeurs"]["pire_baisse"], 4) == -0.2897


def test_taille_impossible_renvoyee_au_modele():
    modele = FauxModele([demande("simuler_portefeuille", **{**SIMULATION_DECISION, "taille": 1.5})])
    resultat = instruire_dossier(DECISION, PROFIL, premier_numero=2, converser=modele)
    assert resultats_envoyes(modele, 0)[0]["status"] == "error"
    assert "1.5" in resultat.trace[0]["sortie"]


# --- Le Tribunal : toutes les phases ------------------------------------------


def argument(texte, *pieces):
    return {"etiquette": "fait", "texte": texte, "pieces": list(pieces)}


class FauxDebat:
    """Remplace le Procureur et l'Avocat (Bedrock) par des arguments écrits à l'avance.

    Le Procureur écrit un argument juste ; l'Avocat un juste et un faux (« 4 fois »,
    absent des pièces), que sa correction ne répare pas : il doit être rejeté.
    """

    def __init__(self):
        self.corrections = []

    def debattre(self, dossier, signaler_etape=None):
        simulation = next((p for p in dossier["pieces"] if "pire_baisse_actuelle" in p.get("valeurs", {})), None)
        if dossier["decision"]["type"] == "reallocation":  # arguments sans chiffre, toujours valides
            requisitoire = [argument("Votre Pacte limite la part des cryptoactifs.", "P1")]
            plaidoirie = [argument("Votre horizon est long.", "P1")]
        else:
            requisitoire = [argument("La pire chute passerait de −7,8 % à −29,0 %.", simulation["id"])]
            plaidoirie = [argument("Le rendement annualisé aurait été de +12,0 % contre +9,3 %.", simulation["id"]),
                          argument("Le portefeuille rapporterait 4 fois plus.", simulation["id"])]
        trace = [{"etape": role, "outil": "bedrock", "entree": [p["id"] for p in dossier["pieces"]],
                  "sortie": arguments} for role, arguments in [("procureur", requisitoire), ("avocat", plaidoirie)]]
        for etape in reversed(trace) if signaler_etape else ():  # l'Avocat répond le premier, comme en vrai parfois
            signaler_etape(etape)
        return DebatResultat(requisitoire, plaidoirie, trace)

    def corriger_argument(self, role, dossier, arg, motif):
        self.corrections.append((role, motif))
        return arg, {"etape": role, "outil": "bedrock_correction",
                     "entree": {"argument": arg["texte"], "motif": motif}, "sortie": arg}


@pytest.fixture(autouse=True)
def faux_debat(monkeypatch):
    """Aucun test unitaire n'appelle le vrai débat (Bedrock, payant)."""
    debat = FauxDebat()
    monkeypatch.setattr(tribunal, "debattre", debat.debattre)
    monkeypatch.setattr(tribunal, "corriger_argument", debat.corriger_argument)
    return debat


EXTRACTION_TSLA = {"type_decision": "position", "actif_mentionne": "Tesla", "ticker": "TSLA", "taille": 0.30,
                   "montant": None, "devise_montant": "non_precisee", "financement_depuis": None,
                   "ambiguites": []}


def test_juger_decision_enchaine_profil_et_orchestrateur(monkeypatch):
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: copy.deepcopy(EXTRACTION_TSLA))
    contrat = juger_decision("robert", "Je veux mettre 30 % en Tesla",
                             converser=FauxModele([demande("indicateurs_actif", ticker="TSLA")]))
    assert contrat["persona"] == "robert"
    assert contrat["decision"]["ticker"] == "TSLA"
    assert [p["id"] for p in contrat["pieces"]] == ["P1", "P2", "P3", "P4"]
    assert contrat["pieces"][0]["outil"] == "charger_pacte"
    assert contrat["pieces"][3]["outil"] == "points_de_bascule"  # ajoutée d'office (#61)
    assert [e["etape"] for e in contrat["trace"]] == (
        ["agent_profil"] * 3 + ["orchestrateur"] * 3 + ["procureur", "avocat"] + ["greffier"]
        + ["avocat"] + ["greffier"] * 2  # verifier_pacte, relance de l'avocat, chiffres et cadre
    )
    assert contrat["comparaison"]["actuel"]["pire_baisse"] == pytest.approx(-0.0776, abs=5e-5)
    assert contrat["comparaison"]["apres"]["pire_baisse"] == pytest.approx(-0.2897, abs=5e-5)
    assert contrat["hypotheses"][0] == "Période : 2021-11-12 au 2026-11-12"
    assert "Montants convertis en CAD" in contrat["hypotheses"]
    assert contrat["verdict"] is None and contrat["avertissement"] == AVERTISSEMENT
    for piece in contrat["pieces"]:
        valider_piece(piece)


def test_greffier_controle_chaque_regle_du_pacte(monkeypatch):
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: copy.deepcopy(EXTRACTION_TSLA))
    contrat = juger_decision("robert", "Je veux mettre 30 % en Tesla", converser=FauxModele())
    controles = {c["regle"]: c for c in contrat["controles"]}
    # Mêmes contrôles que docs/exemples/contrat_robert.json pour les règles calculables.
    assert controles["pire_baisse_max"]["statut"] == "violation"
    assert controles["pire_baisse_max"]["message"] == "Pire baisse −29,0 % au-delà du seuil −12,0 %"
    assert controles["pire_baisse_max"]["pieces"] == ["P2", "P1"]  # simulation d'office, puis Pacte
    assert controles["plafond_crypto"]["statut"] == "conforme"
    assert controles["preserver_capital"]["statut"] == "a_verifier"
    assert controles["entreprises_etablies"]["statut"] == "a_verifier"
    assert controles["biais_survivant"]["statut"] == "a_verifier"
    etape = next(e for e in contrat["trace"] if e["outil"] == "verifier_pacte")
    assert etape["etape"] == "greffier"
    assert etape["sortie"] == "1 violation, 1 conforme, 2 à vérifier"
    # Ordre des contrôles : Pacte, puis système (comme contrat_robert.json).
    assert [c["regle"] for c in contrat["controles"]] == [
        "pire_baisse_max", "plafond_crypto", "preserver_capital", "entreprises_etablies",
        "verifier_chiffres", "cadre_simulation", "performance_passee", "biais_survivant"]


def test_debat_verifie_par_le_greffier_avec_une_relance(monkeypatch, faux_debat):
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: copy.deepcopy(EXTRACTION_TSLA))
    contrat = juger_decision("robert", "Je veux mettre 30 % en Tesla", converser=FauxModele())
    assert [a["texte"] for a in contrat["requisitoire"]] == ["La pire chute passerait de −7,8 % à −29,0 %."]
    assert len(contrat["plaidoirie"]) == 1
    # L'argument faux est renvoyé une fois à l'Avocat, puis rejeté avec le motif du Greffier.
    assert [role for role, _ in faux_debat.corrections] == ["avocat"]
    rejete = contrat["arguments_rejetes"][0]
    assert rejete["cote"] == "plaidoirie" and "4" in rejete["raison"]
    controles = {c["regle"]: c for c in contrat["controles"]}
    assert controles["verifier_chiffres"]["message"] == (
        "Chiffres cités vérifiés contre leurs pièces : 4/4 chiffres, 2 arguments ; "
        "1 argument rejeté après une relance")
    assert controles["performance_passee"]["statut"] == "a_verifier"  # l'Avocat parle de rendement
    assert controles["cadre_simulation"] == {
        "statut": "conforme", "regle": "cadre_simulation",
        "message": "Aucun conseil personnalisé ni promesse sur l'avenir : 2 arguments vérifiés"}
    assert contrat["trace"][-2:] == [
        {"etape": "greffier", "outil": "verifier_chiffres", "entree": "3 arguments",
         "sortie": controles["verifier_chiffres"]["message"]},
        {"etape": "greffier", "outil": "verifier_cadre_simulation", "entree": "3 arguments",
         "sortie": controles["cadre_simulation"]["message"]},
    ]


def test_argument_qui_conseille_jamais_affiche_comme_valide(monkeypatch, faux_debat):
    """#60 : un conseil du Procureur est renvoyé une fois, puis rejeté ; le contrat reste valide."""
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: copy.deepcopy(EXTRACTION_TSLA))
    debattre = faux_debat.debattre

    def debat_avec_un_conseil(dossier, signaler_etape=None):
        resultat = debattre(dossier, signaler_etape)
        resultat.requisitoire.append(argument("Vous devriez vendre TSLA.", "P1"))
        return resultat
    monkeypatch.setattr(tribunal, "debattre", debat_avec_un_conseil)

    contrat = juger_decision("robert", "Je veux mettre 30 % en Tesla", converser=FauxModele())

    assert "Vous devriez vendre TSLA." not in [a["texte"] for a in contrat["requisitoire"] + contrat["plaidoirie"]]
    assert [role for role, _ in faux_debat.corrections] == ["procureur", "avocat"]
    rejete = next(a for a in contrat["arguments_rejetes"] if a["cote"] == "requisitoire")
    assert rejete["raison"].startswith("Conseil personnalisé : « Vous devriez »")
    controles = {c["regle"]: c for c in contrat["controles"]}
    assert controles["cadre_simulation"]["message"] == (
        "Aucun conseil personnalisé ni promesse sur l'avenir : 2 arguments vérifiés ; "
        "1 argument rejeté après une relance")
    # Le rejet du conseil n'est pas compté comme un chiffre faux.
    assert controles["verifier_chiffres"]["message"].endswith("; 1 argument rejeté après une relance")
    assert valider_contrat(contrat) == []


def test_contrat_complet_passe_le_schema(monkeypatch):
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: copy.deepcopy(EXTRACTION_TSLA))
    contrat = juger_decision("robert", "Je veux mettre 30 % en Tesla",
                             converser=FauxModele([demande("indicateurs_actif", ticker="TSLA")]))
    # taille_max_compatible (#21) est calculé par Python même si le modèle n'a pas demandé l'outil.
    assert contrat["taille_max_compatible"] == 0.09
    assert valider_contrat(contrat) == []


def test_greffier_lit_la_simulation_demandee_par_le_modele(monkeypatch):
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: copy.deepcopy(EXTRACTION_TSLA))
    modele = FauxModele([demande("indicateurs_actif", ticker="TSLA"),
                         demande("simuler_portefeuille", **SIMULATION_DECISION)])
    contrat = juger_decision("robert", "Je veux mettre 30 % en Tesla", converser=modele)
    controle = next(c for c in contrat["controles"] if c["regle"] == "pire_baisse_max")
    assert controle["pieces"] == ["P3", "P1"]  # la simulation du modèle, pas une copie d'office
    assert len([p for p in contrat["pieces"] if p["outil"] == "simuler_portefeuille"]) == 1


def test_juger_decision_reallocation_contrat_complet(monkeypatch):
    reallocation = {"type": "reallocation", "panier": [{"ticker": "BTC-USD", "poids": 1.0}],
                    "part_reallouee": 0.2, "libelle": "20 % réalloué vers BTC-USD"}

    class ProfilReallocation:
        decision = reallocation
        controles, hypotheses = [], []
        profil = charger_pacte(chemin_profil("amira"))
        pacte = pacte_pour_contrat(profil)
        piece_pacte = piece_pacte(profil, "P1")
        trace = [{"etape": "agent_profil", "outil": "charger_pacte", "entree": "amira", "sortie": "P1"}]

    monkeypatch.setattr(tribunal, "lancer_agent_profil", lambda *args: ProfilReallocation)
    contrat = juger_decision("amira", "Je réalloue 20 % vers le bitcoin", converser=FauxModele())
    # Simulation obligatoire ajoutée d'office, comme pour une position.
    assert next(e for e in contrat["trace"] if e["etape"] == "orchestrateur")["raison"] == RAISON_D_OFFICE
    assert contrat["comparaison"]["apres"]["pire_baisse"] < contrat["comparaison"]["actuel"]["pire_baisse"]
    # Crypto après la décision : 0,15 × (1 − t) + t ≤ 0,25 → au plus 11 % réalloués.
    assert contrat["taille_max_compatible"] == 0.11
    statuts = {c["regle"]: c["statut"] for c in contrat["controles"]}
    assert statuts["plafond_crypto"] == "violation"  # 0,15 × 0,8 + 0,2 = 32 % de crypto
    [point] = contrat["points_de_bascule"]
    assert point["regle"] == "plafond_crypto" and point["taille_max"] == 0.11
    assert point["seuil_suffisant"] == pytest.approx(0.15 * 0.8 + 0.2)
    assert point["message"] == "Conforme jusqu'à 11 % réalloués, ou avec un plafond de 32,0 % au lieu de 25,0 %"
    assert valider_contrat(contrat) == []


def test_points_de_bascule_verses_d_office_avant_le_debat(monkeypatch, faux_debat):
    """Profil prudent + 30 % TSLA : conforme jusqu'à 9 %, ou avec un seuil de −29,0 % (#61)."""
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: copy.deepcopy(EXTRACTION_TSLA))
    vues = []
    monkeypatch.setattr(tribunal, "debattre",
                        lambda dossier, signaler_etape=None: vues.append([p["outil"] for p in dossier["pieces"]])
                        or faux_debat.debattre(dossier, signaler_etape))
    contrat = juger_decision("robert", "Je veux mettre 30 % en Tesla", converser=FauxModele())

    piece = next(p for p in contrat["pieces"] if p["outil"] == "points_de_bascule")
    assert "points_de_bascule" in vues[0]  # le Procureur et l'Avocat peuvent la citer
    etape = next(e for e in contrat["trace"] if e["outil"] == "points_de_bascule")
    assert etape == {"etape": "orchestrateur", "outil": "points_de_bascule", "raison": tribunal.RAISON_POINTS_DE_BASCULE,
                     "entree": {"regles": ["pire_baisse_max"]}, "sortie": piece["id"]}
    assert raison_valide(etape["raison"]) and RAISON_D_OFFICE in etape["raison"]

    [point] = contrat["points_de_bascule"]
    assert point["regle"] == "pire_baisse_max" and point["taille_max"] == 0.09
    assert point["seuil_suffisant"] == pytest.approx(contrat["comparaison"]["apres"]["pire_baisse"], abs=1e-6)
    assert point["message"] == "Conforme jusqu'à 9 % en TSLA, ou avec un seuil de −29,0 % au lieu de −12,0 %"
    assert point["pieces"] == [piece["id"]]
    assert valider_contrat(contrat) == []


def test_sans_violation_ni_piece_ni_point_de_bascule(monkeypatch):
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: {**EXTRACTION_TSLA, "taille": 0.05})
    contrat = juger_decision("robert", "Je veux mettre 5 % en Tesla", converser=FauxModele())
    assert contrat["points_de_bascule"] == []
    assert all(p["outil"] != "points_de_bascule" for p in contrat["pieces"])
    assert all(e["outil"] != "points_de_bascule" for e in contrat["trace"])
    assert valider_contrat(contrat) == []


def test_juger_decision_sans_decision_ne_calcule_rien(monkeypatch):
    monkeypatch.setattr(agent_profil, "appeler_llm",
                        lambda *args: {**EXTRACTION_TSLA, "taille": None})

    def modele_interdit(*args):
        raise AssertionError("l'orchestrateur ne doit pas être appelé sans décision")

    contrat = juger_decision("robert", "Je veux de la Tesla", converser=modele_interdit)
    assert contrat["decision"] is None
    assert [p["id"] for p in contrat["pieces"]] == ["P1"]
    assert contrat["controles"] and all(c["statut"] == "a_verifier" for c in contrat["controles"])


# --- Progression en direct (#90) --------------------------------------------------


def test_orchestrateur_signale_chaque_appel_au_moment_ou_il_est_fait():
    signalees, deja_signalees = [], []
    modele = FauxModele([demande("indicateurs_actif", ticker="TSLA")],
                        [demande("simuler_portefeuille", **SIMULATION_DECISION)])

    def converser(*args):
        deja_signalees.append(len(signalees))
        return modele(*args)

    resultat = instruire_dossier(DECISION, PROFIL, premier_numero=2, converser=converser,
                                 signaler_etape=signalees.append)
    assert signalees == resultat.trace  # une fois par appel, dans l'ordre
    assert deja_signalees == [0, 1, 2]  # chaque appel est signalé avant le tour suivant du modèle


RANG_DE_L_ETAPE = {"agent_profil": 0, "calibrage": 0, "orchestrateur": 1, "procureur": 2, "avocat": 2, "greffier": 3}


def test_juger_decision_signale_les_phases_dans_l_ordre_sans_changer_le_contrat(monkeypatch):
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: copy.deepcopy(EXTRACTION_TSLA))

    def juger(signaler=None):
        return juger_decision("robert", "Je veux mettre 30 % en Tesla", signaler=signaler,
                              converser=FauxModele([demande("indicateurs_actif", ticker="TSLA")]))

    evenements = []
    avec = juger(evenements.append)
    assert avec == juger()  # le contrat est identique avec ou sans signaler

    phases = [e["phase"] for e in evenements if e["type"] == "phase"]
    assert phases == ["agent_profil", "orchestrateur", "debat", "greffier"]
    etapes = [e["etape"] for e in evenements if e["type"] == "etape"]
    # Chaque étape du contrat est signalée une seule fois (le Procureur et l'Avocat dans l'ordre de leur réponse).
    assert sorted(map(json.dumps, etapes)) == sorted(map(json.dumps, avec["trace"]))
    assert [e for e in etapes if e["etape"] == "orchestrateur"] == [
        e for e in avec["trace"] if e["etape"] == "orchestrateur"]  # un signal par appel d'outil, dans l'ordre
    # Chaque étape arrive pendant sa phase (une correction du Greffier, pendant la phase du Greffier).
    phase_courante = None
    for evenement in evenements:
        if evenement["type"] == "phase":
            phase_courante = phases.index(evenement["phase"])
        elif evenement["type"] == "etape":
            etape = evenement["etape"]
            rang = 3 if etape["outil"] == "bedrock_correction" else RANG_DE_L_ETAPE[etape["etape"]]
            assert rang == phase_courante, etape
    # Après la première plaidoirie (ici l'Avocat, dans le faux débat), on dit qui plaide encore.
    activites = [e["activite"] for e in evenements if e["type"] == "activite"]
    assert "Le Procureur plaide encore (Bedrock)" in activites
    # Le renvoi à l'Avocat est annoncé avant sa correction.
    renvoi = next(i for i, e in enumerate(evenements) if e["type"] == "activite" and "renvoyé à l'Avocat" in e["activite"])
    correction = next(i for i, e in enumerate(evenements)
                      if e["type"] == "etape" and e["etape"]["outil"] == "bedrock_correction")
    assert renvoi < correction


# --- Vrais appels à Bedrock (payants) ----------------------------------------


@pytest.mark.bedrock
def test_bedrock_instruit_le_dossier_tsla():
    resultat = instruire_dossier(DECISION, PROFIL, premier_numero=2)
    assert resultat.appels >= 1, "le modèle aurait dû demander au moins un outil"
    assert all(raison_valide(e["raison"]) for e in resultat.trace)
    # La simulation obligatoire est présente, que le modèle l'ait demandée ou non.
    assert any(e["outil"] == "simuler_portefeuille" and e["entree"] == SIMULATION_DECISION
               and e["sortie"].startswith("P") for e in resultat.trace)
    print(json.dumps(resultat.trace, ensure_ascii=False, indent=2))


@pytest.mark.bedrock
def test_bedrock_meme_decision_deux_profils():
    # La même décision, instruite pour deux Pactes différents.
    for identifiant in ["robert", "amira"]:
        profil = charger_pacte(chemin_profil(identifiant))
        resultat = instruire_dossier(DECISION, profil, premier_numero=2)
        print(identifiant, json.dumps(resultat.trace, ensure_ascii=False, indent=2))
        assert any(p["outil"] == "simuler_portefeuille" for p in resultat.pieces)
