"""Tests des catégories d'actifs (pipeline/categories.py)."""

import copy
from unittest import mock

import pytest

from pipeline import categories as module_categories
from pipeline.categories import (
    TitreHorsUnivers,
    categories_du_titre,
    charger_categories,
    erreurs_config_categories,
)
from pipeline.donnees import ErreurDonnees, charger_univers


@pytest.mark.parametrize(
    "ticker, attendues",
    [
        ("NVDA", {"tech", "etats_unis", "hors_canada"}),   # secteur Information Technology
        ("SHOP.TO", {"tech", "canada"}),                   # idem, titre canadien
        ("GOOGL", {"tech", "etats_unis", "hors_canada"}),  # ajout (Communication Services)
        ("QQQ", {"tech", "etats_unis", "hors_canada"}),    # ajout (FNB Nasdaq-100)
        ("BTC-USD", {"crypto", "hors_canada"}),            # classe d'actifs crypto, sans pays (#112)
        ("ETH-USD", {"crypto", "hors_canada"}),
        ("XOM", {"energie_fossile", "etats_unis", "hors_canada"}),  # secteur Energy (#84)
        ("JNJ", {"etats_unis", "hors_canada"}),            # aucune catégorie sectorielle
        ("TSLA", {"etats_unis", "hors_canada"}),           # Consumer Discretionary, pas dans les ajouts
        ("SPY", {"etats_unis", "hors_canada"}),            # FNB coté à New York (NYSE Arca)
        ("ESGV", {"etats_unis", "hors_canada"}),           # FNB coté au Cboe BZX
        ("XIU.TO", {"canada"}),                            # FNB coté à Toronto
        ("XBB.TO", {"canada"}),                            # obligations canadiennes
        ("GLD", {"hors_canada"}),                          # retiré de etats_unis : de l'or, sans pays
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


# --- Catégories géographiques (#112) -------------------------------------------------


def test_canada_et_hors_canada_partagent_l_univers_sans_recouvrement():
    """Chaque titre est soit coté à Toronto, soit hors du Canada : jamais les deux, jamais aucun."""
    for ticker in charger_univers()["ticker"]:
        assert len(categories_du_titre(ticker) & {"canada", "hors_canada"}) == 1, ticker


def test_hors_canada_correspond_aux_titres_en_usd():
    """Dans cet univers, hors du Canada = coté en USD (justification de config/categories.json)."""
    univers = charger_univers()
    en_usd = set(univers.loc[univers["currency"] == "USD", "ticker"])
    assert {t for t in univers["ticker"] if "hors_canada" in categories_du_titre(t)} == en_usd


def test_categories_geographiques_definies_par_le_marche_de_cotation():
    definitions = charger_categories()
    assert definitions["canada"]["marches"] == ["TSX"]
    assert "Crypto (24/7)" not in definitions["etats_unis"]["marches"]  # la crypto n'a pas de pays
    assert "Crypto (24/7)" in definitions["hors_canada"]["marches"]


def test_un_retrait_l_emporte_sur_le_marche():
    """Un FNB coté à Toronto qui détiendrait des actions américaines (ex. : XSP) se règle dans la config."""
    categories = copy.deepcopy(charger_categories())
    categories["canada"]["retraits"] = ["XIU.TO"]
    categories["etats_unis"]["ajouts"] = ["XIU.TO"]
    assert erreurs_config_categories(categories) == []
    module_categories._categories_par_ticker.cache_clear()
    try:
        with mock.patch.object(module_categories, "charger_categories", lambda: categories):
            assert categories_du_titre("XIU.TO") == {"etats_unis"}
    finally:
        module_categories._categories_par_ticker.cache_clear()


def test_marche_inconnu_ou_titre_ajoute_et_retire_signales():
    categories = copy.deepcopy(charger_categories())
    categories["canada"]["marches"] = ["Toronto"]
    categories["etats_unis"]["retraits"] = ["SPY", "DOGE-USD"]
    categories["etats_unis"]["ajouts"] = ["SPY"]
    assert erreurs_config_categories(categories) == [
        "canada/marches : « Toronto » absent de assets_universe.csv",
        "etats_unis/retraits : « DOGE-USD » absent de assets_universe.csv",
        "etats_unis : « SPY » est à la fois dans ajouts et dans retraits",
    ]


def test_marches_et_retraits_facultatifs():
    """Une définition écrite avant #112 (sans marches ni retraits) reste valide."""
    categories = {"crypto": {"libelle": "Cryptoactifs", "classes_actifs": ["crypto"], "secteurs": [], "ajouts": []}}
    assert erreurs_config_categories(categories) == []
