"""Tests du Pacte vécu (pipeline/calibrage.py, #68).

Sans Bedrock : le procès complet utilise les faux modèles de test_orchestrateur.
Les épisodes viennent des vraies données du jeu de départ.
"""

import copy

import pytest

from contrat.valider import valider_contrat
from pipeline import agent_profil, tribunal
from pipeline.agent_profil import chemin_profil
from pipeline.calibrage import (
    ASSOUPLIR, ATTENDRE, GARDER, PAS_ATTENDRE, RESTE, VEND,
    ErreurCalibrage, calibrer, episodes_de_baisse, parcours_dichotomie, prochaine_question, reponses_demo,
)
from pipeline.chiffres import verifier_argument
from pipeline.greffier import verifier_pacte
from pipeline.pacte import charger_pacte, pacte_pour_contrat
from pipeline.tribunal import juger_decision
from tests.test_orchestrateur import EXTRACTION_TSLA, FauxDebat, FauxModele

PRUDENT = charger_pacte(chemin_profil("robert"))
AUDACIEUX = charger_pacte(chemin_profil("amira"))
ESG = charger_pacte(chemin_profil("mateo"))
DATE = "2026-11-15"
SIMULATION_TSLA_30 = {"id": "P9", "valeurs": {"pire_baisse": -0.2897}}  # 30 % en TSLA (pièce P1 du contrat type)


def repondre(profil, limite, **autres):
    """Répond « reste » tant que la baisse du jour ne dépasse pas ``limite`` ; puis les autres questions."""
    defaut = {"capacite": ATTENDRE, "crypto": RESTE, "valeurs": GARDER, **autres}
    episodes = episodes_de_baisse(profil["portefeuille"])
    reponses = {}
    while (question := prochaine_question(profil, reponses, episodes)) is not None:
        if question["type"] == "baisse":
            reponses[question["id"]] = RESTE if question["baisse"] >= limite else VEND
        else:
            reponses[question["id"]] = defaut[question["type"]]
    return reponses


def controle_pire_baisse(profil_calibre):
    regles = profil_calibre["pacte"]["regles"]
    poids = {ligne["ticker"]: ligne["poids"] for ligne in profil_calibre["portefeuille"]}
    controles = verifier_pacte(regles, poids, SIMULATION_TSLA_30, "P1")
    return next(c for c in controles if c["regle"] == "pire_baisse_max")


# --- Épisodes : de vrais jours, sans la suite ---------------------------------------


def test_un_vrai_jour_par_niveau_du_moins_au_plus_profond():
    episodes = episodes_de_baisse(PRUDENT["portefeuille"])
    assert [e.id for e in episodes] == [f"baisse_{n}" for n in range(5, 55, 5)]
    for episode in episodes:
        assert episode.baisse <= episode.niveau  # le jour a bien baissé d'au moins ce niveau
        assert episode.date_sommet < episode.date_jour


def test_aucune_donnee_posterieure_au_jour_de_la_question():
    for episode in episodes_de_baisse(PRUDENT["portefeuille"]):
        assert episode.historique.index.max().date().isoformat() == episode.date_jour


def test_le_portefeuille_du_profil_passe_avant_les_references():
    episodes = episodes_de_baisse(PRUDENT["portefeuille"])
    assert episodes[0].serie == "Votre portefeuille"  # Robert baisse de −5 % lui-même…
    assert episodes[1].ticker == "XIU.TO"  # … mais jamais de −10 % : on prend une référence


# --- Dichotomie ---------------------------------------------------------------------


def test_dichotomie_quatre_questions_au_plus():
    for limite in range(-1, 10):
        reponses = {rang: RESTE if rang <= limite else VEND for rang in range(10)}
        poses, reste, vend, prochain = parcours_dichotomie(10, reponses)
        assert prochain is None and len(poses) <= 4
        assert (reste, vend) == (limite, limite + 1)


def test_memes_reponses_meme_seuil():
    reponses = repondre(PRUDENT, -0.12)
    seuils = {calibrer(PRUDENT, dict(reponses), DATE, "P2").seuil for _ in range(3)}
    assert len(seuils) == 1


# --- Seuil mesuré et Greffier -------------------------------------------------------


def test_profil_prudent_tsla_30_en_violation():
    resultat = calibrer(PRUDENT, repondre(PRUDENT, -0.12), DATE, "P2")
    valeurs = resultat.piece["valeurs"]
    assert valeurs["seuil_mesure"] >= -0.12 > valeurs["baisse_refusee"]  # entre le dernier « reste » et le premier « vend »
    assert resultat.seuil == valeurs["seuil_mesure"]
    controle = controle_pire_baisse(resultat.profil)
    assert controle["statut"] == "violation" and "P2" in controle["pieces"]


def test_profil_qui_reste_jusqu_a_moins_30_tsla_30_conforme():
    resultat = calibrer(PRUDENT, repondre(PRUDENT, -0.32), DATE, "P2")
    assert resultat.seuil <= -0.30
    assert controle_pire_baisse(resultat.profil)["statut"] == "conforme"


def test_regle_du_pacte_porte_sa_provenance():
    resultat = calibrer(PRUDENT, repondre(PRUDENT, -0.12), DATE, "P2", etiquette="fictif")
    regle = next(r for r in pacte_pour_contrat(resultat.profil)["regles"] if r["type"] == "pire_baisse_max")
    assert regle["seuil"] == resultat.seuil and regle["piece"] == "P2" and regle["etiquette"] == "fictif"
    assert DATE in regle["provenance"] and "justification" not in regle
    assert PRUDENT["pacte"]["regles"][0]["seuil"] == -0.12  # le profil d'origine n'est pas modifié


def test_vend_des_le_premier_jour_seuil_conserve():
    resultat = calibrer(PRUDENT, repondre(PRUDENT, 0.0), DATE, "P2")
    assert resultat.seuil is None and resultat.piece["valeurs"]["seuil_mesure"] is None
    assert resultat.profil["pacte"]["regles"] == PRUDENT["pacte"]["regles"]
    assert "non mesurable" in resultat.piece["valeur_affichee"]


# --- Questions propres au profil, sans nom de persona -------------------------------


def test_capacite_comparee_a_l_horizon():
    reponses = repondre(PRUDENT, -0.12, capacite=PAS_ATTENDRE)
    valeurs = calibrer(PRUDENT, reponses, DATE, "P2").piece["valeurs"]
    assert valeurs["horizon_ans"] == [3, 5] and valeurs["capacite_reponse"] == PAS_ATTENDRE
    assert valeurs["capacite_annees_retour"] is None or valeurs["capacite_annees_retour"] > 0


def test_crypto_seulement_si_le_portefeuille_en_contient():
    assert "crypto" not in repondre(PRUDENT, -0.12)
    valeurs = calibrer(AUDACIEUX, repondre(AUDACIEUX, -0.45), DATE, "P2").piece["valeurs"]
    assert valeurs["crypto_baisse"] < -0.5 and valeurs["crypto_reponse"] == RESTE
    assert valeurs["crypto_valeur_sommet"] == round(AUDACIEUX["capital_fictif_cad"] * 0.15)  # BTC 10 % + ETH 5 %


def test_arbitrage_valeurs_pour_chaque_critere_documentaire():
    reponses = repondre(ESG, -0.20, valeurs=ASSOUPLIR)
    assert reponses["valeurs_controverses_esg"] == ASSOUPLIR
    valeurs = calibrer(ESG, reponses, DATE, "P2").piece["valeurs"]
    assert valeurs["valeurs_regles"] == ["controverses_esg"] and valeurs["valeurs_reponses"] == [ASSOUPLIR]


# --- Réponses refusées --------------------------------------------------------------


def test_reponses_incompletes_refusees():
    reponses = repondre(PRUDENT, -0.12)
    del reponses["capacite"]
    with pytest.raises(ErreurCalibrage, match="capacite"):
        calibrer(PRUDENT, reponses, DATE, "P2")
    with pytest.raises(ErreurCalibrage, match="baisse_25"):
        calibrer(PRUDENT, {}, DATE, "P2")


def test_reponse_invalide_ou_a_une_question_non_posee_refusee():
    reponses = repondre(PRUDENT, -0.12)
    with pytest.raises(ErreurCalibrage, match="invalide"):
        calibrer(PRUDENT, {**reponses, "baisse_25": "peut-etre"}, DATE, "P2")
    with pytest.raises(ErreurCalibrage, match="non posée"):
        calibrer(PRUDENT, {**reponses, "baisse_50": VEND}, DATE, "P2")
    with pytest.raises(ErreurCalibrage, match="invalide"):
        calibrer(PRUDENT, {**reponses, "capacite": "oui"}, DATE, "P2")


def test_reponses_preenregistrees_des_profils_de_test():
    for profil in (PRUDENT, AUDACIEUX, ESG):
        reponses, date = reponses_demo(profil)
        resultat = calibrer(profil, reponses, date, "P2", etiquette="fictif")
        assert resultat.piece["etiquette"] == "fictif" and resultat.seuil is not None


# --- Le Greffier vérifie les chiffres de la pièce ------------------------------------


def test_un_argument_qui_cite_une_reponse_passe_verifier_chiffres():
    piece = calibrer(PRUDENT, repondre(PRUDENT, -0.12), DATE, "P2").piece
    valeurs = piece["valeurs"]
    rang = valeurs["reponses_jours"].index(RESTE)
    jour, baisse = valeurs["dates_jours"][rang], valeurs["baisses_jours"][rang]
    assert (jour, round(baisse * 100, 1)) == ("2022-06-13", -10.2)
    dossier = {"decision": {"taille": 0.30}, "periode": ["2021-11-12", "2026-11-12"], "pieces": [piece]}
    juste = {"texte": "Le 13 juin 2022, devant une baisse de −10,2 %, vous avez répondu « je reste ».",
             "pieces": ["P2"]}
    invente = {"texte": "Le 13 juin 2022, devant une baisse de −12,5 %, vous avez répondu « je reste ».",
               "pieces": ["P2"]}
    assert verifier_argument(juste, dossier).valide
    assert not verifier_argument(invente, dossier).valide


# --- Le procès complet --------------------------------------------------------------


@pytest.fixture
def proces_sans_bedrock(monkeypatch):
    debat = FauxDebat()
    monkeypatch.setattr(tribunal, "debattre", debat.debattre)
    monkeypatch.setattr(tribunal, "corriger_argument", debat.corriger_argument)
    monkeypatch.setattr(tribunal, "repliquer_les_deux", debat.repliquer_les_deux)
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: copy.deepcopy(EXTRACTION_TSLA))


def test_proces_avec_pacte_vecu_contrat_valide(proces_sans_bedrock):
    reponses, date = reponses_demo(PRUDENT)
    contrat = juger_decision("robert", "Je veux mettre 30 % en Tesla", converser=FauxModele(),
                             calibrage={"reponses": reponses, "date": date, "etiquette": "fictif"})
    assert valider_contrat(contrat) == []
    assert [p["id"] for p in contrat["pieces"][:3]] == ["P1", "P2", "P3"]
    assert contrat["pieces"][1]["type"] == "declaree"
    assert [e["etape"] for e in contrat["trace"][:2]] == ["agent_profil", "calibrage"]
    regle = next(r for r in contrat["pacte"]["regles"] if r["type"] == "pire_baisse_max")
    assert regle["piece"] == "P2" and contrat["pieces"][0]["valeurs"]["pire_baisse_max"] == regle["seuil"]
    controle = next(c for c in contrat["controles"] if c["regle"] == "pire_baisse_max")
    assert controle["statut"] == "violation" and "P2" in controle["pieces"]
    assert any("mesuré sur les réponses" in h for h in contrat["hypotheses"])


def test_calibrage_invalide_refuse_avant_tout_appel_bedrock(monkeypatch):
    def interdit(*args):
        raise AssertionError("aucun appel Bedrock avant la vérification des réponses")
    monkeypatch.setattr(agent_profil, "appeler_llm", interdit)
    with pytest.raises(ErreurCalibrage):
        juger_decision("robert", "Je veux mettre 30 % en Tesla", converser=interdit,
                       calibrage={"reponses": {"baisse_25": "peut-etre"}, "date": DATE})
