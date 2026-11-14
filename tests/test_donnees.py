import pandas as pd
import pytest

from pipeline.donnees import (
    ErreurDonnees,
    charger_prix,
    charger_univers,
    lire_csv,
    seances_americaines,
)

# Un mélange d'actions CAD et USD, de FNB (actions et obligations) et de crypto.
MELANGE = ["RY.TO", "TSLA", "SPY", "XBB.TO", "BTC-USD", "ETH-USD"]


@pytest.fixture(scope="module")
def prix_bruts():
    prix = lire_csv("prices_daily.csv")
    prix["date"] = pd.to_datetime(prix["date"])
    return prix


@pytest.fixture(scope="module")
def prix():
    return charger_prix(MELANGE)


def test_melange_complet_sans_trou(prix):
    assert list(prix.columns) == MELANGE
    assert not prix.isna().any().any()


def test_dates_triees_sans_doublon(prix):
    assert prix.index.is_monotonic_increasing
    assert not prix.index.duplicated().any()
    assert prix.index.name == "date"


def test_periode_et_nombre_de_seances(prix):
    assert prix.index[0] == pd.Timestamp("2021-11-12")
    assert prix.index[-1] == pd.Timestamp("2026-11-12")
    assert len(prix) == len(seances_americaines()) == 1255


def test_aucune_seance_le_week_end(prix):
    assert (prix.index.dayofweek < 5).all()


def test_ticker_inconnu_erreur_claire():
    with pytest.raises(ErreurDonnees, match="absent.* de l'univers d'actifs : ZZZ"):
        charger_prix(["SPY", "ZZZ"])


def test_liste_vide_erreur():
    with pytest.raises(ErreurDonnees):
        charger_prix([])


def test_ticker_en_double_garde_une_colonne():
    assert list(charger_prix(["SPY", "SPY", "QQQ"]).columns) == ["SPY", "QQQ"]


def test_valeurs_adj_close_sans_ajustement_supplementaire(prix, prix_bruts):
    # Les jours où le titre a un prix, la valeur est exactement son adj_close :
    # aucun fractionnement n'est réappliqué.
    tsla = prix_bruts[prix_bruts["ticker"] == "TSLA"].set_index("date")["adj_close"]
    pd.testing.assert_series_equal(prix["TSLA"], tsla, check_names=False, check_freq=False)


def test_jour_ferie_tsx_reporte_le_dernier_prix(prix, prix_bruts):
    ry = prix_bruts[prix_bruts["ticker"] == "RY.TO"].set_index("date")["adj_close"]
    feries_tsx = [d for d in prix.index if d not in ry.index]
    assert feries_tsx, "le jeu de données devrait contenir des jours fériés propres à la TSX"
    for jour in feries_tsx:
        # Dernier prix réel de RY.TO avant ce jour, même si c'était un jour où
        # la bourse américaine était fermée (ex. : 24 décembre 2021).
        assert prix.at[jour, "RY.TO"] == ry[ry.index < jour].iloc[-1]


def test_crypto_du_week_end_cumulee_dans_le_lundi(prix, prix_bruts):
    btc = prix_bruts[prix_bruts["ticker"] == "BTC-USD"].set_index("date")["adj_close"]
    lundis = [d for d in prix.index if d.dayofweek == 0]
    for lundi in lundis[:20]:
        # Le prix du lundi est celui du lundi lui-même, pas celui du vendredi :
        # le rendement du lundi couvre donc samedi et dimanche.
        assert prix.at[lundi, "BTC-USD"] == btc[lundi]


def test_reproduit_la_pire_baisse_de_tsla_de_la_maquette(prix):
    # Valeur de la pièce P4 de docs/exemples/contrat_robert.json (pire_baisse_usd).
    tsla = prix["TSLA"]
    assert round((tsla / tsla.cummax() - 1).min(), 4) == -0.7297


def test_univers_contient_les_31_titres():
    assert len(charger_univers()) == 31


def test_source_s3_pas_encore_branchee(monkeypatch):
    monkeypatch.setenv("SOURCE_DONNEES", "s3")
    with pytest.raises(ErreurDonnees, match="#13"):
        lire_csv("assets_universe.csv")


def test_source_inconnue_erreur(monkeypatch):
    monkeypatch.setenv("SOURCE_DONNEES", "ftp")
    with pytest.raises(ErreurDonnees, match="local"):
        lire_csv("assets_universe.csv")
