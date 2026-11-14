"""Tests des catégories d'actifs (pipeline/categories.py)."""

import copy

import pytest

from pipeline.categories import (
    TitreHorsUnivers,
    categories_du_titre,
    charger_categories,
    erreurs_config_categories,
)
from pipeline.donnees import ErreurDonnees


@pytest.mark.parametrize(
    "ticker, attendues",
    [
        ("NVDA", {"tech"}),          # secteur Information Technology
        ("SHOP.TO", {"tech"}),       # idem, titre canadien
        ("GOOGL", {"tech"}),         # ajout (Communication Services)
        ("QQQ", {"tech"}),           # ajout (FNB Nasdaq-100)
        ("BTC-USD", {"crypto"}),     # classe d'actifs crypto
        ("ETH-USD", {"crypto"}),
        ("XOM", set()),              # dans l'univers, dans aucune catégorie
        ("TSLA", set()),             # Consumer Discretionary, pas dans les ajouts
        ("SPY", set()),
    ],
)
def test_categories_du_titre(ticker, attendues):
    assert categories_du_titre(ticker) == attendues


def test_titre_hors_univers_signale_jamais_devine():
    with pytest.raises(TitreHorsUnivers, match="« DOGE-USD » est absent de assets_universe.csv"):
        categories_du_titre("DOGE-USD")


def test_titre_hors_univers_est_une_erreur_de_donnees():
    assert issubclass(TitreHorsUnivers, ErreurDonnees)


def test_config_categories_coherente_avec_l_univers():
    assert erreurs_config_categories() == []


def test_faute_de_frappe_dans_la_config_signalee():
    categories = copy.deepcopy(charger_categories())
    categories["tech"]["secteurs"] = ["Information technology"]
    categories["crypto"]["ajouts"] = ["DOGE-USD"]
    erreurs = erreurs_config_categories(categories)
    assert erreurs == [
        "crypto/ajouts : « DOGE-USD » absent de assets_universe.csv",
        "tech/secteurs : « Information technology » absent de assets_universe.csv",
    ]
