import pandas as pd
import pytest

from pipeline.donnees import (
    HYPOTHESES_DONNEES,
    ErreurDonnees,
    charger_donnees,
    charger_prix,
    charger_univers,
    convertir_en_cad,
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
    assert (prix.index.day_of_week < 5).all()


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
    lundis = [d for d in prix.index if d.day_of_week == 0]
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


# --- Conversion en CAD (issue #5) -------------------------------------------


@pytest.fixture(scope="module")
def prix_cad():
    return charger_donnees(MELANGE)


@pytest.fixture(scope="module")
def taux_usdcad():
    taux = lire_csv("fx_usdcad_daily.csv")
    taux["date"] = pd.to_datetime(taux["date"])
    return taux.set_index("date")["usdcad"]


def test_titre_cad_inchange_apres_conversion(prix, prix_cad):
    for ticker in ["RY.TO", "XBB.TO"]:
        pd.testing.assert_series_equal(prix_cad[ticker], prix[ticker])


def test_titre_usd_multiplie_par_le_taux_du_jour(prix, prix_cad, taux_usdcad):
    jour = pd.Timestamp("2022-06-15")
    for ticker in ["TSLA", "SPY", "BTC-USD"]:
        assert prix_cad.at[jour, ticker] == pytest.approx(prix.at[jour, ticker] * taux_usdcad[jour])


def test_jour_ferie_canadien_reporte_le_dernier_taux(prix, prix_cad, taux_usdcad):
    feries_canadiens = [d for d in prix.index if d not in taux_usdcad.index]
    assert feries_canadiens, "le jeu de données devrait contenir des jours fériés canadiens"
    for jour in feries_canadiens:
        dernier_taux = taux_usdcad[taux_usdcad.index < jour].iloc[-1]
        assert prix_cad.at[jour, "SPY"] == pytest.approx(prix.at[jour, "SPY"] * dernier_taux)


def test_conversion_sans_trou(prix_cad):
    assert list(prix_cad.columns) == MELANGE
    assert not prix_cad.isna().any().any()


def test_devise_non_prise_en_charge_erreur(prix):
    with pytest.raises(ErreurDonnees, match="TSLA \\(EUR\\)"):
        convertir_en_cad(prix[["TSLA"]], {"TSLA": "EUR"})


def test_devise_manquante_erreur(prix):
    with pytest.raises(ErreurDonnees, match="SPY"):
        convertir_en_cad(prix[["SPY"]], {})


def test_hypothese_cad_listee():
    assert "Montants convertis en CAD" in HYPOTHESES_DONNEES


def test_reproduit_la_pire_baisse_de_tsla_en_cad(prix_cad):
    # Valeur de la pièce P4 de docs/exemples/contrat_robert.json (pire_baisse_cad).
    tsla = prix_cad["TSLA"]
    assert round((tsla / tsla.cummax() - 1).min(), 4) == -0.7088


def test_reproduit_le_portefeuille_actuel_de_robert():
    # Portefeuille de personas/robert.json, rééquilibré chaque jour (CLAUDE.md, section 6 bis).
    # Valeurs attendues : « comparaison.actuel » de docs/exemples/contrat_robert.json.
    poids = pd.Series({"ZST.TO": 0.3, "XBB.TO": 0.2, "XIU.TO": 0.2, "JNJ": 0.1, "RY.TO": 0.1, "FTS.TO": 0.1})
    rendements = charger_donnees(list(poids.index)).pct_change().dropna()
    rendement_portefeuille = (rendements * poids).sum(axis=1)
    valeur = (1 + rendement_portefeuille).cumprod()
    annees = (valeur.index[-1] - pd.Timestamp("2021-11-12")).days / 365.25
    assert round(valeur.iloc[-1] ** (1 / annees) - 1, 4) == 0.0929
    assert round(rendement_portefeuille.std() * 252**0.5, 4) == 0.0559
    assert round((valeur / valeur.cummax().clip(lower=1) - 1).min(), 4) == -0.0776
