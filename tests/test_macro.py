"""Données macro du Canada : inflation, taux, rendement réel (#111)."""

import pandas as pd
import pytest

from pipeline import macro
from pipeline.donnees import ErreurDonnees


def test_inflation_d_une_annee_civile():
    mesure = macro.inflation(pd.Timestamp("2021-12-31"), pd.Timestamp("2022-12-30"))
    assert (mesure.annees, mesure.mois_debut, mesure.mois_fin) == (1, "2021-12", "2022-12")
    assert mesure.cumulee == pytest.approx(0.063)
    assert mesure.annuelle == pytest.approx(mesure.cumulee)


def test_inflation_s_arrete_au_dernier_mois_publie():
    # La période finit en novembre 2026, mais le dernier IPC publié est celui de septembre.
    mesure = macro.inflation(pd.Timestamp("2021-11-12"), pd.Timestamp("2026-11-12"))
    assert (mesure.annees, mesure.mois_debut, mesure.mois_fin) == (5, "2021-09", "2026-09")
    ipc = macro._series()[macro.SERIE_INFLATION]
    produit = 1.0
    for annee in range(2022, 2027):
        produit *= 1 + ipc[pd.Timestamp(f"{annee}-09-01")]
    assert mesure.cumulee == pytest.approx(produit - 1)
    assert mesure.annuelle == pytest.approx(produit ** (1 / 5) - 1)


def test_inflation_demande_au_moins_un_an():
    with pytest.raises(ErreurDonnees, match="au moins un an"):
        macro.inflation(pd.Timestamp("2022-01-03"), pd.Timestamp("2022-06-30"))


def test_inflation_sans_ipc_publie():
    with pytest.raises(ErreurDonnees, match="aucun IPC"):
        macro.inflation(pd.Timestamp("2019-01-01"), pd.Timestamp("2020-06-30"))


def test_valeurs_en_decimales():
    assert macro.taux_au(macro.SERIE_TAUX_DIRECTEUR, pd.Timestamp("2021-12-31")) == pytest.approx(0.0025)
    assert macro.taux_au(macro.SERIE_TAUX_DIRECTEUR, pd.Timestamp("2022-12-30")) == pytest.approx(0.0425)


def test_taux_au_reprend_la_derniere_valeur_connue():
    # Un samedi n'a pas de valeur : c'est celle du vendredi.
    assert macro.taux_au(macro.SERIE_OBLIGATION_10_ANS, pd.Timestamp("2022-12-31")) == \
        macro.taux_au(macro.SERIE_OBLIGATION_10_ANS, pd.Timestamp("2022-12-30"))


def test_taux_moyen_entre_ses_bornes():
    moyen = macro.taux_moyen(macro.SERIE_TAUX_DIRECTEUR, pd.Timestamp("2022-01-01"), pd.Timestamp("2022-12-30"))
    assert 0.0025 < moyen < 0.0425


def test_taux_sans_valeur():
    with pytest.raises(ErreurDonnees, match="aucune valeur"):
        macro.taux_au(macro.SERIE_TAUX_DIRECTEUR, pd.Timestamp("2010-01-01"))


def test_relation_de_fisher():
    assert macro.rendement_reel(-0.026, 0.063) == pytest.approx(0.974 / 1.063 - 1)
    assert macro.rendement_reel(0.03, 0.03) == pytest.approx(0.0)


def test_source_avec_date_d_extraction():
    assert macro.source_macro().endswith("extrait le 2026-11-13")
