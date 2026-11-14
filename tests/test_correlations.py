"""Tests de l'outil 3 : calculer_correlations (pipeline/correlations.py)."""

import json
from pathlib import Path

import jsonschema
import numpy as np
import pandas as pd
import pytest

from pipeline.correlations import (
    DESCRIPTION_BEDROCK,
    calculer_correlations,
    calculer_matrice_correlations,
)
from pipeline.donnees import ErreurDonnees
from pipeline.indicateurs import DESCRIPTION_BEDROCK as DESCRIPTION_OUTIL_1
from pipeline.llm import converser_avec_outils, message_utilisateur

RACINE = Path(__file__).resolve().parent.parent
SCHEMA_CONTRAT = json.loads((RACINE / "contrat" / "schema_sortie.json").read_text(encoding="utf-8"))
PANIER_DEMO = ["BTC-USD", "ETH-USD", "NVDA", "QQQ", "SHOP.TO"]


def serie_de_prix(rendements):
    """Prix partant de 100, à partir d'une liste de rendements quotidiens."""
    dates = pd.date_range("2024-01-01", periods=len(rendements) + 1, freq="D")
    return pd.Series(100 * np.cumprod([1.0, *[1 + r for r in rendements]]), index=dates)


# --- Fonction de calcul pure ----------------------------------------------------

RENDEMENTS = [0.01, -0.02, 0.03, -0.01, 0.02, -0.03]


def test_titres_qui_bougent_ensemble_correlation_1():
    prix = pd.DataFrame({"A": serie_de_prix(RENDEMENTS), "B": serie_de_prix([2 * r for r in RENDEMENTS])})
    assert calculer_matrice_correlations(prix).loc["A", "B"] == pytest.approx(1.0)


def test_titres_qui_bougent_en_sens_inverse_correlation_moins_1():
    prix = pd.DataFrame({"A": serie_de_prix(RENDEMENTS), "B": serie_de_prix([-r for r in RENDEMENTS])})
    assert calculer_matrice_correlations(prix).loc["A", "B"] == pytest.approx(-1.0)


def test_matrice_symetrique_avec_1_sur_la_diagonale():
    prix = pd.DataFrame({
        "A": serie_de_prix(RENDEMENTS),
        "B": serie_de_prix([0.02, 0.01, -0.01, 0.0, 0.03, -0.02]),
    })
    matrice = calculer_matrice_correlations(prix)
    assert matrice.loc["A", "A"] == pytest.approx(1.0)
    assert matrice.loc["A", "B"] == pytest.approx(matrice.loc["B", "A"])


# --- L'outil sur les vraies données ---------------------------------------------


@pytest.fixture(scope="module")
def piece_panier():
    return calculer_correlations(PANIER_DEMO)


def test_une_valeur_par_paire_entre_moins_1_et_1(piece_panier):
    correlations = {cle: v for cle, v in piece_panier["valeurs"].items() if cle.startswith("correlation_")}
    assert len(correlations) == 10  # 5 titres → 10 paires
    assert all(-1 <= v <= 1 for v in correlations.values())
    assert piece_panier["valeurs"]["titres"] == PANIER_DEMO
    assert piece_panier["valeurs"]["periode"] == ["2021-11-12", "2026-11-12"]


def test_memes_valeurs_que_la_piece_p4_de_la_maquette(piece_panier):
    """La pièce P4 de contrat_amira.json avait été calculée avec la même méthode."""
    contrat = json.loads((RACINE / "docs" / "exemples" / "contrat_amira.json").read_text(encoding="utf-8"))
    p4 = next(p for p in contrat["pieces"] if p["outil"] == "calculer_correlations")["valeurs"]
    valeurs = piece_panier["valeurs"]
    assert valeurs["correlation_BTC-USD_ETH-USD"] == pytest.approx(p4["correlation_btc_eth"], abs=1e-6)
    assert valeurs["correlation_NVDA_QQQ"] == pytest.approx(p4["correlation_nvda_qqq"], abs=1e-6)
    assert valeurs["correlation_BTC-USD_NVDA"] == pytest.approx(p4["correlation_btc_nvda"], abs=1e-6)


def test_valeurs_brutes_et_valeur_affichee_arrondie(piece_panier):
    assert piece_panier["valeurs"]["correlation_BTC-USD_ETH-USD"] == 0.84453
    assert piece_panier["valeur_affichee"] == (
        "BTC-USD/ETH-USD 0,84 · NVDA/QQQ 0,77 · QQQ/SHOP.TO 0,57 · 10 paires en tout"
    )


def test_piece_conforme_au_contrat(piece_panier):
    schema = {"$ref": "#/$defs/piece", "$defs": SCHEMA_CONTRAT["$defs"]}
    jsonschema.validate({"id": "P1", **piece_panier}, schema, cls=jsonschema.Draft202012Validator)


def test_titre_en_double_compte_une_fois():
    piece = calculer_correlations(["NVDA", "QQQ", "NVDA"])
    assert piece["valeurs"]["titres"] == ["NVDA", "QQQ"]
    assert piece["valeur_affichee"] == "NVDA/QQQ 0,77"


@pytest.mark.parametrize("tickers, message", [
    (["BTC-USD"], "au moins deux titres"),
    (["BTC-USD", "BTC-USD"], "au moins deux titres"),
    (["BTC-USD", "NFLX"], "NFLX"),
    (["RY.TO", "TD.TO", "MFC.TO", "ENB.TO", "CNQ.TO", "CNR.TO",
      "FTS.TO", "ATD.TO", "SHOP.TO", "CSU.TO", "AAPL"], "Au plus 10 titres"),
])
def test_demande_invalide_erreur_lisible(tickers, message):
    with pytest.raises(ErreurDonnees, match=message):
        calculer_correlations(tickers)


def test_description_bedrock_stricte():
    spec = DESCRIPTION_BEDROCK["toolSpec"]
    assert spec["name"] == "calculer_correlations"
    assert spec["strict"] is True
    assert spec["inputSchema"]["json"]["required"] == ["tickers"]


# --- Vrai appel Bedrock (payant) : pytest -m bedrock ------------------------------


@pytest.mark.bedrock
def test_une_decision_crypto_pousse_le_modele_a_demander_les_correlations():
    """Le modèle reçoit les outils 1 et 3 et une décision crypto-tech : il doit demander l'outil 3."""
    systeme = (
        "Tu instruis le dossier d'une décision d'investissement pour un outil éducatif de "
        "simulation. Tu ne calcules rien : choisis les outils qui apportent les preuves les "
        "plus utiles pour juger la décision au regard du Pacte de l'investisseur."
    )
    demande = (
        "Décision : réallouer 100 % du portefeuille vers un panier BTC-USD 30 %, ETH-USD 20 %, "
        "NVDA 20 %, QQQ 20 %, SHOP.TO 10 %.\n"
        "Pacte : pire baisse tolérée −45 % ; crypto 25 % au maximum ; tech et crypto 75 % au maximum."
    )
    tour = converser_avec_outils(systeme, [message_utilisateur(demande)],
                                 [DESCRIPTION_OUTIL_1, DESCRIPTION_BEDROCK])

    demandes_correlations = [d for d in tour.demandes if d.nom == "calculer_correlations"]
    print(f"\nOutils demandés : {[(d.nom, d.entree) for d in tour.demandes]}")
    assert demandes_correlations, "le modèle n'a pas demandé les corrélations"
    tickers = demandes_correlations[0].entree["tickers"]
    assert {"BTC-USD", "ETH-USD"} <= set(tickers)
    calculer_correlations(tickers)  # la demande du modèle est exécutable telle quelle
