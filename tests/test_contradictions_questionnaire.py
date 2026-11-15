"""Tests des contradictions du questionnaire et de sa pièce dans le procès (#85)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from contrat.valider import valider_contrat
from pipeline import agent_profil, tribunal
from pipeline.chiffres import verifier_argument
from pipeline.questionnaire import (
    CONTROLE_COHERENCE,
    contradictions,
    controles_questionnaire,
    piece_questionnaire,
    profil_depuis_reponses,
)
from pipeline.tribunal import juger_decision
from tests.test_orchestrateur import EXTRACTION_TSLA, FauxDebat, FauxModele, demande
from tests.test_questionnaire import COMME, DATE, persona

RACINE = Path(__file__).resolve().parents[1]
EXEMPLE = json.loads((RACINE / "docs" / "exemples" / "reponses_questionnaire.json").read_text(encoding="utf-8"))

# Les trois exemples de l'issue #85, chacun à partir de réponses par ailleurs cohérentes.
EXEMPLES_ISSUE = {
    # « Je rachète quand ça baisse » mais « en 2022, j'ai vendu ».
    "reaction_contre_vecu_2022": {"reaction": "rachete", "vecu_2022": "vendu"},
    # Carte Nasdaq-100 (tolérance élevée) mais moins de 3 mois de coussin et horizon de moins de 3 ans.
    "tolerance_contre_capacite": {"fourchettes": "croissance", "coussin": "moins_3", "horizon": "moins_3"},
    # « Mes proches me disent très prudent » mais crypto jusqu'à 25 %.
    "proches_prudents_contre_crypto": {"regard_proches": "tres_prudent", "crypto": "25"},
}


def reponses(**modifs):
    return {**COMME["robert"], **modifs}


def profil(identifiant="investisseur_test", **modifs):
    robert = persona("robert")
    return profil_depuis_reponses(reponses(**modifs), robert["capital_fictif_cad"], robert["portefeuille"], DATE,
                                  identifiant=identifiant, nom="Investisseur test")


# --- Contradictions -------------------------------------------------------------------


@pytest.mark.parametrize("id_attendu, modifs", EXEMPLES_ISSUE.items())
def test_chaque_exemple_de_l_issue_donne_exactement_une_contradiction(id_attendu, modifs):
    trouvees = contradictions(reponses(**modifs))
    assert [c["id"] for c in trouvees] == [id_attendu]
    assert set(modifs) <= set(trouvees[0]["questions"])  # la contradiction nomme les réponses en cause


@pytest.mark.parametrize("nom", sorted(COMME))
def test_reponses_coherentes_sans_contradiction(nom):
    assert contradictions(COMME[nom]) == []


def test_exemple_de_la_documentation_sans_contradiction():
    assert contradictions(EXEMPLE["reponses"]) == []


def test_message_cite_les_reponses_telles_qu_affichees():
    message = contradictions(reponses(reaction="rachete", vecu_2022="vendu"))[0]["message"]
    assert "« J'en rachète »" in message and "« J'ai vendu »" in message


def test_ecart_tolerance_capacite_cite_les_chiffres_et_les_raisons():
    trouvee = contradictions(reponses(fourchettes="croissance", coussin="moins_3", horizon="moins_3"))[0]
    assert "−32,1 %" in trouvee["message"] and "−10,0 %" in trouvee["message"]
    assert "coussin de sécurité" in trouvee["message"].lower() and "horizon" in trouvee["message"].lower()
    assert trouvee["questions"][0] == "fourchettes"


def test_un_seul_cran_d_ecart_n_est_pas_une_contradiction():
    # Carte S&P 500 (−22,2 %, « modéré ») et coussin de 3 à 6 mois (−20 %, « modéré ») : aucun écart.
    assert contradictions(reponses(fourchettes="actions", coussin="3_6", horizon="5_10", retraits="non",
                                   part_patrimoine="quart_moitie", revenu="tres_stable")) == []


def test_capacite_plus_large_que_la_tolerance_n_est_pas_une_contradiction():
    # Être plus prudent que sa situation ne l'exige n'est pas incohérent.
    assert contradictions(reponses(fourchettes="tres_prudent", horizon="plus_15", coussin="plus_12")) == []


# --- Profil et pièce ---------------------------------------------------------------------


def test_le_profil_garde_ses_reponses():
    genere = profil()
    assert genere["questionnaire"]["date"] == DATE
    assert genere["questionnaire"]["etiquette"] == "fait"
    assert genere["questionnaire"]["reponses"]["fourchettes"] == "equilibre"


def test_piece_declaree_du_questionnaire():
    piece = piece_questionnaire(profil(fourchettes="croissance", coussin="moins_3", horizon="moins_3"), "P2")
    assert piece["type"] == "declaree" and piece["etiquette"] == "fait" and piece["id"] == "P2"
    valeurs = piece["valeurs"]
    assert valeurs["date_reponses"] == DATE
    assert valeurs["tolerance_declaree"] == pytest.approx(-0.320501)
    assert valeurs["capacite_plafond"] == -0.1
    assert valeurs["seuil_retenu"] == -0.1
    assert valeurs["contradictions"] == ["tolerance_contre_capacite"]
    assert len(valeurs["questions"]) == len(valeurs["reponses"])
    assert piece["valeur_affichee"] == "Tolérance −32,1 % · capacité −10,0 % · seuil retenu −10,0 % · 1 contradiction"


def test_argument_qui_cite_la_piece_passe_verifier_chiffres():
    piece = piece_questionnaire(profil(fourchettes="croissance", coussin="moins_3", horizon="moins_3"), "P2")
    dossier = {"decision": {"type": "position", "ticker": "TSLA", "taille": 0.3, "financement": "proportionnel"},
               "pieces": [piece], "periode": ["2021-11-12", "2026-11-12"]}
    argument = {"etiquette": "fait", "pieces": ["P2"],
                "texte": "Le 15 novembre, vous avez déclaré accepter −32,1 %, mais votre capacité est de −10,0 %."}
    assert verifier_argument(argument, dossier).valide
    faux = {**argument, "texte": "Vous avez déclaré accepter −35,0 %."}
    assert not verifier_argument(faux, dossier).valide


# --- Contrôles ------------------------------------------------------------------------


def test_une_contradiction_donne_un_controle_a_verifier():
    controles = controles_questionnaire(profil(reaction="rachete", vecu_2022="vendu"), "P2")
    assert len(controles) == 1
    assert controles[0]["statut"] == "a_verifier" and controles[0]["regle"] == CONTROLE_COHERENCE
    assert controles[0]["pieces"] == ["P2"]


def test_seuil_mesure_different_du_seuil_declare():
    genere = profil(fourchettes="actions", coussin="plus_12", horizon="10_15", retraits="non",
                    part_patrimoine="quart_moitie", revenu="tres_stable")  # seuil déclaré −22,3 %
    calibrage = {"id": "P2", "valeurs": {"seuil_mesure": -0.151}}
    controles = controles_questionnaire(genere, "P3", piece_calibrage=calibrage)
    assert len(controles) == 1
    assert "−15,1 %" in controles[0]["message"] and "Le seuil mesuré l'emporte" in controles[0]["message"]
    assert controles[0]["pieces"] == ["P3", "P2"]


def test_meme_seuil_mesure_et_declare_rien_a_dire():
    genere = profil()
    seuil = next(r["seuil"] for r in genere["pacte"]["regles"] if r["type"] == "pire_baisse_max")
    assert controles_questionnaire(genere, "P3", piece_calibrage={"id": "P2", "valeurs": {"seuil_mesure": seuil}}) == []


def test_type_de_titre_jamais_detenu():
    genere = profil(experience=["depots", "fonds", "actions"])
    decision = {"type": "position", "ticker": "BTC-USD", "taille": 0.05, "financement": "proportionnel"}
    controles = controles_questionnaire(genere, "P2", decision=decision)
    assert [c["regle"] for c in controles] == ["questionnaire"]
    assert controles[0]["pieces"] == ["P2"]


# --- Procès complet (sans Bedrock) ------------------------------------------------------------


@pytest.fixture
def profil_du_questionnaire(tmp_path, monkeypatch):
    """Un profil tiré du questionnaire, avec une contradiction, rangé dans un dossier de profils temporaire."""
    genere = profil(reaction="rachete", vecu_2022="vendu")
    (tmp_path / "investisseur_test.json").write_text(json.dumps(genere, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(agent_profil, "DOSSIER_PERSONAS", tmp_path)
    debat = FauxDebat()
    monkeypatch.setattr(tribunal, "debattre", debat.debattre)
    monkeypatch.setattr(tribunal, "corriger_argument", debat.corriger_argument)
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: copy.deepcopy(EXTRACTION_TSLA))
    return genere


def test_proces_d_un_profil_du_questionnaire(profil_du_questionnaire):
    contrat = juger_decision("investisseur_test", "Je veux mettre 30 % en Tesla",
                             converser=FauxModele([demande("indicateurs_actif", ticker="TSLA")]))
    pieces = {p["id"]: p for p in contrat["pieces"]}
    assert pieces["P1"]["outil"] == "charger_pacte"
    assert pieces["P2"]["type"] == "declaree" and pieces["P2"]["outil"] == "lire_questionnaire"
    coherence = [c for c in contrat["controles"] if c["regle"] == CONTROLE_COHERENCE]
    assert len(coherence) == 1 and coherence[0]["statut"] == "a_verifier" and coherence[0]["pieces"] == ["P2"]
    assert any(e["outil"] == "lire_questionnaire" for e in contrat["trace"])
    assert any("questionnaire" in h for h in contrat["hypotheses"])
    assert valider_contrat(contrat) == []


def test_profil_ecrit_a_la_main_sans_piece_du_questionnaire(monkeypatch):
    debat = FauxDebat()
    monkeypatch.setattr(tribunal, "debattre", debat.debattre)
    monkeypatch.setattr(tribunal, "corriger_argument", debat.corriger_argument)
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: copy.deepcopy(EXTRACTION_TSLA))
    contrat = juger_decision("robert", "Je veux mettre 30 % en Tesla",
                             converser=FauxModele([demande("indicateurs_actif", ticker="TSLA")]))
    assert all(p["outil"] != "lire_questionnaire" for p in contrat["pieces"])
    assert all(c["regle"] != CONTROLE_COHERENCE for c in contrat["controles"])
