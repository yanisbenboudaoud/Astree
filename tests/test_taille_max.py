"""Tests de l'outil 4 : taille_max_compatible (pipeline/taille_max.py)."""

import json
from pathlib import Path

import jsonschema
import pytest

from pipeline import taille_max
from pipeline.agent_profil import chemin_profil
from pipeline.orchestrateur import outils_du_profil
from pipeline.pacte import charger_pacte
from pipeline.simulation import ErreurSimulation
from pipeline.taille_max import (
    EtapeRecherche,
    piece_taille_max,
    rechercher_taille_max,
    tailles_a_tester,
)

RACINE = Path(__file__).resolve().parent.parent
SCHEMA_CONTRAT = json.loads((RACINE / "contrat" / "schema_sortie.json").read_text(encoding="utf-8"))
PRUDENT = charger_pacte(chemin_profil("robert"))
AUDACIEUX = charger_pacte(chemin_profil("amira"))


def position(ticker, taille, financement="proportionnel"):
    return {"type": "position", "ticker": ticker, "taille": taille, "financement": financement}


def recherche(profil, decision):
    return rechercher_taille_max(profil["portefeuille"], decision, profil["pacte"]["regles"])


def piece(profil, decision):
    return piece_taille_max("P5", profil["portefeuille"], decision, profil["pacte"]["regles"])


# --- Tailles testées ---------------------------------------------------------------


def test_un_point_par_pas_de_0_a_la_taille_demandee():
    tailles = tailles_a_tester(0.30)
    assert len(tailles) == 31
    assert tailles[0] == 0 and tailles[1] == 0.01 and tailles[-1] == 0.30


def test_taille_demandee_hors_grille_incluse():
    assert tailles_a_tester(0.0769)[-3:] == [0.06, 0.07, 0.0769]


# --- Cas de démo : profil prudent, 30 % en TSLA ------------------------------------


def test_cas_de_demo_9_pour_cent():
    piece_demo = piece(PRUDENT, position("TSLA", 0.30))
    valeurs = piece_demo["valeurs"]
    assert valeurs["taille_max_compatible"] == 0.09
    # Valeurs recalculées depuis les CSV (issue #21) : −11,22 % à 9 %, −12,09 % à 10 %.
    assert valeurs["pire_baisse_a_taille_max"] == pytest.approx(-0.1122, abs=5e-5)
    assert valeurs["pire_baisse_a_taille_suivante"] == pytest.approx(-0.1209, abs=5e-5)
    assert valeurs["regle_limitante"] == "pire_baisse_max"
    assert valeurs["regles_verifiees"] == ["pire_baisse_max", "plafond_crypto"]
    assert valeurs["pas_de_recherche"] == 0.01
    assert piece_demo["valeur_affichee"] == "9 % au maximum"


def test_memes_valeurs_que_la_piece_p5_de_la_maquette():
    contrat = json.loads((RACINE / "docs" / "exemples" / "contrat_robert.json").read_text(encoding="utf-8"))
    p5 = next(p for p in contrat["pieces"] if p["outil"] == "taille_max_compatible")["valeurs"]
    valeurs = piece(PRUDENT, position("TSLA", 0.30))["valeurs"]
    for cle in ("taille_max_compatible", "pire_baisse_a_taille_max", "pire_baisse_a_taille_suivante"):
        assert valeurs[cle] == pytest.approx(p5[cle], abs=5e-5)


def test_piece_conforme_au_contrat():
    schema = {"$ref": "#/$defs/piece", "$defs": SCHEMA_CONTRAT["$defs"]}
    jsonschema.validate(piece(PRUDENT, position("TSLA", 0.30)), schema, cls=jsonschema.Draft202012Validator)


# --- Autres situations ---------------------------------------------------------------


def test_plafond_limitant():
    """Profil audacieux (15 % de crypto) + Bitcoin : le plafond crypto de 25 % limite."""
    valeurs = piece(AUDACIEUX, position("BTC-USD", 0.30))["valeurs"]
    # Part crypto après la décision : 0,15 × (1 − t) + t ≤ 0,25 → t ≤ 11,76 %.
    assert valeurs["taille_max_compatible"] == 0.11
    assert valeurs["regle_limitante"] == "plafond_crypto"
    assert valeurs["part_crypto_a_taille_max"] == pytest.approx(0.15 * 0.89 + 0.11)
    assert valeurs["part_crypto_a_taille_suivante"] == pytest.approx(0.15 * 0.88 + 0.12)
    assert valeurs["part_tech_crypto_a_taille_max"] == pytest.approx(0.5 * 0.89 + 0.11)


def test_taille_demandee_deja_compatible():
    resultat = piece(PRUDENT, position("TSLA", 0.05))
    assert resultat["valeurs"]["taille_max_compatible"] == 0.05
    assert resultat["valeurs"]["pire_baisse_a_taille_suivante"] is None
    assert resultat["valeurs"]["regle_limitante"] is None
    assert resultat["valeur_affichee"] == "5 % : la taille demandée respecte les règles calculables"


def test_portefeuille_deja_hors_pacte_aucune_taille():
    """Seuil plus strict que la pire baisse du portefeuille actuel (−7,76 %) : même 0 % viole."""
    regles = [{"id": "pire_baisse_max", "type": "pire_baisse_max", "seuil": -0.05, "libelle": "…"}]
    resultat = piece_taille_max("P5", PRUDENT["portefeuille"], position("TSLA", 0.30), regles)
    assert resultat["valeurs"]["taille_max_compatible"] is None
    assert resultat["valeurs"]["pire_baisse_a_taille_max"] is None
    assert resultat["valeurs"]["regle_limitante"] == "pire_baisse_max"
    assert resultat["valeur_affichee"].startswith("Aucune taille compatible")


def test_regles_non_calculables_ignorees():
    resultat = recherche(PRUDENT, position("TSLA", 0.30))
    assert [r["type"] for r in resultat.regles] == ["pire_baisse_max", "plafond"]  # pas les qualitatives


def test_plus_grande_taille_compatible_meme_apres_un_trou(monkeypatch):
    """Pas de dichotomie : une taille compatible au-delà d'une zone en violation est retenue."""
    def faux_evaluer(portefeuille, decision, taille, regles):
        en_violation = 0.03 <= taille <= 0.05
        return EtapeRecherche(taille, -0.1, {}, ["pire_baisse_max"] if en_violation else [])
    monkeypatch.setattr(taille_max, "_evaluer", faux_evaluer)
    assert recherche(PRUDENT, position("TSLA", 0.08)).taille_max == 0.08


def test_meme_financement_a_chaque_taille(monkeypatch):
    vues = []

    def faux_evaluer(portefeuille, decision, taille, regles):
        vues.append(decision["financement"])
        return EtapeRecherche(taille, -0.1, {}, [])
    monkeypatch.setattr(taille_max, "_evaluer", faux_evaluer)
    recherche(PRUDENT, position("TSLA", 0.10, "depuis_ZST.TO"))
    assert set(vues) == {"depuis_ZST.TO"}


def test_reallocation_de_demo_28_pour_cent():
    """Profil audacieux, tout réallouer vers le panier crypto-tech : pièce P5 de contrat_amira.json."""
    resultat = piece(AUDACIEUX, AUDACIEUX["decision_demo"])
    contrat = json.loads((RACINE / "docs" / "exemples" / "contrat_amira.json").read_text(encoding="utf-8"))
    p5 = next(p for p in contrat["pieces"] if p["outil"] == "taille_max_compatible")["valeurs"]
    valeurs = resultat["valeurs"]
    assert resultat["titre"] == "Part maximale réallouable compatible avec le Pacte"
    assert valeurs["taille_max_compatible"] == p5["taille_max_compatible"] == 0.28
    assert valeurs["regle_limitante"] == p5["regle_limitante"] == "plafond_crypto"
    for cle in ("part_crypto_a_taille_max", "part_crypto_a_taille_suivante", "pire_baisse_a_taille_max"):
        assert valeurs[cle] == pytest.approx(p5[cle], abs=1e-6)


def test_panier_invalide_erreur_lisible():
    panier_faux = {"type": "reallocation", "panier": [{"ticker": "BTC-USD", "poids": 0.5}], "part_reallouee": 0.2}
    with pytest.raises(ErreurSimulation, match="totalisent"):
        recherche(AUDACIEUX, panier_faux)


# --- Orchestrateur ---------------------------------------------------------------


def test_outil_dans_la_liste_blanche_de_l_orchestrateur():
    outils = {outil.nom: outil for outil in outils_du_profil(PRUDENT)}
    assert "taille_max_compatible" in outils
    spec = outils["taille_max_compatible"].description_bedrock["toolSpec"]
    assert spec["strict"] is True
    assert spec["inputSchema"]["json"]["required"] == ["ticker", "taille", "financement"]

    resultat = outils["taille_max_compatible"].executer(
        {"ticker": "TSLA", "taille": 0.30, "financement": "proportionnel"}, "P6")
    assert resultat["id"] == "P6"
    assert resultat["valeurs"]["taille_max_compatible"] == 0.09


def test_outils_d_une_reallocation_portent_sur_le_panier_de_la_decision():
    """Pour une réallocation, le modèle ne choisit que la part réallouée (et la période)."""
    decision = AUDACIEUX["decision_demo"]
    outils = {outil.nom: outil for outil in outils_du_profil(AUDACIEUX, decision)}
    assert set(outils) == {"indicateurs_actif", "simuler_portefeuille", "calculer_correlations",
                           "taille_max_compatible", "rechercher_documents", "consulter_jurisprudence"}

    def requis(nom):
        return outils[nom].description_bedrock["toolSpec"]["inputSchema"]["json"]["required"]
    assert requis("simuler_portefeuille") == ["part_reallouee", "periode"]
    assert requis("taille_max_compatible") == ["part_reallouee"]

    simulation = outils["simuler_portefeuille"].executer({"part_reallouee": 1.0, "periode": "complete"}, "P2")
    assert simulation["valeurs"]["pire_baisse"] == pytest.approx(-0.618555, abs=1e-6)
    taille = outils["taille_max_compatible"].executer({"part_reallouee": 1.0}, "P3")
    assert taille["valeurs"]["taille_max_compatible"] == 0.28


def test_outil_3_correlations_dans_la_liste_blanche():
    outils = {outil.nom: outil for outil in outils_du_profil(PRUDENT)}
    resultat = outils["calculer_correlations"].executer({"tickers": ["BTC-USD", "ETH-USD"]}, "P4")
    assert resultat["id"] == "P4"
    assert resultat["valeurs"]["correlation_BTC-USD_ETH-USD"] == pytest.approx(0.84453, abs=1e-6)
