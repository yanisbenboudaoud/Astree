"""Validation externe (#168) : nos rendements annuels comparés à ceux publiés par les émetteurs."""

import pandas as pd
import pytest

from pipeline.donnees import ErreurDonnees, charger_adj_close_cotation
from validation.externe import (
    CHEMIN_RAPPORT,
    Comparaison,
    base_de_comparaison,
    charger_releves,
    comparer,
    main,
    points,
    pourcentage,
    rapport,
    rendement_annee_civile,
)


def serie(prix: dict[str, float], nom="TEST") -> pd.Series:
    s = pd.Series(prix, dtype=float)
    s.index = pd.to_datetime(s.index)
    s.name = nom
    return s


def comparaison(notre, emetteur, base="cours", autres=None, seuil=0.25, ticker="AGG", annee=2022):
    return Comparaison(ticker, annee, "2021-12-31", "2022-12-30", notre, emetteur, base, autres or {}, seuil)


# --- Calcul -------------------------------------------------------------------------

def test_rendement_entre_les_dernieres_seances_des_deux_annees():
    # Dernière séance de 2021 : le 30 décembre (100) ; de 2022 : le 29 décembre (110).
    s = serie({"2021-06-01": 90, "2021-12-30": 100, "2022-03-01": 95, "2022-12-29": 110, "2023-01-03": 120})
    rendement, debut, fin = rendement_annee_civile(s, 2022)
    assert rendement == pytest.approx(0.10)
    assert (debut, fin) == ("2021-12-30", "2022-12-29")


def test_annee_sans_seance_signalee_jamais_devinee():
    s = serie({"2022-12-29": 110, "2023-12-28": 120})
    with pytest.raises(ErreurDonnees, match="pas de séance en 2021 ou en 2022"):
        rendement_annee_civile(s, 2022)


def test_base_de_comparaison_cours_puis_valeur_liquidative_puis_fonds():
    assert base_de_comparaison({"annee": 2022, "valeur_liquidative": -0.1306, "cours": -0.1303}) == (
        "cours", -0.1303, {"valeur_liquidative": -0.1306})
    assert base_de_comparaison({"annee": 2022, "valeur_liquidative": 0.012}) == ("valeur_liquidative", 0.012, {})
    assert base_de_comparaison({"annee": 2022, "fonds_base_non_precisee": -0.0636})[0] == "fonds_base_non_precisee"
    with pytest.raises(ValueError):
        base_de_comparaison({"annee": 2022})


def test_ecart_signe_en_points_et_seuil_inclusif():
    c = comparaison(-0.1302, -0.1303)
    assert c.ecart_points == pytest.approx(0.01)
    assert comparaison(0.1025, 0.10).dans_le_seuil          # 0,25 point tout juste
    assert not comparaison(0.1026, 0.10).dans_le_seuil      # 0,26 point
    assert not comparaison(0.0974, 0.10).dans_le_seuil      # −0,26 point : l'écart est absolu


def test_adj_close_de_cotation_sur_le_calendrier_du_titre():
    xiu = charger_adj_close_cotation("XIU.TO")
    assert xiu.notna().all() and xiu.index.is_monotonic_increasing
    assert xiu.name == "XIU.TO"
    with pytest.raises(ErreurDonnees, match="DOGE-USD"):
        charger_adj_close_cotation("DOGE-USD")


def test_formats_francais():
    assert pourcentage(-0.0636) == "−6,36 %"
    assert pourcentage(0.1182) == "+11,82 %"
    assert points(-0.04) == "−0,04"
    assert points(-0.001) == "+0,00"
    assert points(0.0054, 3) == "+0,005"


# --- Relevés ------------------------------------------------------------------------

@pytest.fixture(scope="module")
def releves():
    return charger_releves()


def test_seuil_ecrit_avant_le_calcul(releves):
    seuil = releves["seuil_acceptation"]
    assert seuil["ecart_max_points"] == 0.25
    assert seuil["fixe_avant_calcul"] is True
    assert seuil["regle"] and seuil["justification"]


def test_au_moins_6_fnb_dont_les_fnb_canadiens_des_portefeuilles_de_test(releves):
    tickers = {f["ticker"] for f in releves["fnb"]}
    assert len(tickers) >= 6
    assert {"XIU.TO", "XBB.TO", "ZST.TO"} <= tickers
    assert tickers & {"SPY", "AGG", "ESGV"}


def test_chaque_rendement_a_sa_source_et_sa_citation(releves):
    for fnb in releves["fnb"]:
        assert fnb["devise"] in ("CAD", "USD") and fnb["base_publiee"]
        annees = [r["annee"] for r in fnb["rendements"]]
        assert 2022 in annees, fnb["ticker"]
        assert set(annees) <= {2022, 2023, 2024, 2025}
        for r in fnb["rendements"]:
            assert r["url"].startswith("https://") and r["document"] and r["citation"], (fnb["ticker"], r["annee"])
            base_de_comparaison(r)  # au moins une base publiée


# --- Rapport ------------------------------------------------------------------------

def test_rapport_se_regenere_a_l_identique_et_correspond_au_depot(releves):
    premier = rapport(releves, comparer(releves))
    assert premier == rapport(releves, comparer(releves))
    assert CHEMIN_RAPPORT.read_text(encoding="utf-8") == premier, (
        "docs/validation/validation_externe.md n'est plus à jour : relancer python -m validation.externe")


def test_chaque_ecart_hors_seuil_est_explique(releves):
    texte = rapport(releves, comparer(releves))
    assert "Explication manquante" not in texte


def test_ecart_hors_seuil_sans_explication_signale(releves):
    hors_seuil = comparaison(-0.10, -0.13, ticker="AGG", annee=2022)
    texte = rapport({**releves, "explications": {}}, [hors_seuil])
    assert "- **AGG 2022** (+3,00 point) : **Explication manquante.**" in texte
    texte = rapport({**releves, "explications": {"AGG/2022": "Distribution absente de adj_close."}}, [hors_seuil])
    assert "- **AGG 2022** (+3,00 point) : Distribution absente de adj_close." in texte


def test_rapport_met_2022_en_avant(releves):
    texte = rapport(releves, comparer(releves))
    assert "## 2022, l'année au centre des procès" in texte
    assert "- **2022**, l'année de crise rejouée par chaque procès :" in texte


def test_commande_refuse_un_argument():
    assert main(["inattendu"]) == 2
