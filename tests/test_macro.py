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


def test_date_de_publication_supposee_de_l_ipc():
    # Le dernier jour du mois suivant (#113), y compris en février bissextile.
    assert macro.date_publication_ipc(pd.Timestamp("2026-09-01")) == pd.Timestamp("2026-10-31")
    assert macro.date_publication_ipc(pd.Timestamp("2022-12-01")) == pd.Timestamp("2023-01-31")
    assert macro.date_publication_ipc(pd.Timestamp("2024-01-01")) == pd.Timestamp("2024-02-29")


def test_aucun_ipc_utilise_avant_sa_publication(monkeypatch):
    # Un IPC d'octobre 2026 présent dans le fichier, mais publié seulement fin novembre :
    # une mesure faite le 13 novembre (extraction) ne doit pas l'utiliser.
    reelles = macro._series()
    ipc = reelles[macro.SERIE_INFLATION].copy()
    ipc[pd.Timestamp("2026-10-01")] = 0.50
    monkeypatch.setattr(macro, "_series", lambda: {**reelles, macro.SERIE_INFLATION: ipc.sort_index()})

    mesure = macro.inflation(pd.Timestamp("2021-11-12"), pd.Timestamp("2026-11-12"))
    assert (mesure.mois_fin, mesure.publie_le) == ("2026-09", "2026-10-31")
    assert pd.Timestamp(mesure.publie_le) <= pd.Timestamp(macro.date_extraction(macro.FICHIER_MACRO))
    # Un mois plus tard, octobre est publié et devient le dernier mois utilisé.
    plus_tard = macro.inflation(pd.Timestamp("2021-11-12"), pd.Timestamp("2026-11-12"),
                                connu_le=pd.Timestamp("2026-11-30"))
    assert plus_tard.mois_fin == "2026-10"


def test_ipc_publie_le_jour_meme_de_la_mesure():
    debut, fin = pd.Timestamp("2021-11-12"), pd.Timestamp("2026-11-12")
    assert macro.inflation(debut, fin, connu_le=pd.Timestamp("2026-10-30")).mois_fin == "2026-08"
    assert macro.inflation(debut, fin, connu_le=pd.Timestamp("2026-10-31")).mois_fin == "2026-09"


def test_inflation_de_2022_publiee_avant_l_extraction():
    # Mesure faite après coup : décembre 2022, publié fin janvier 2023, est utilisable.
    mesure = macro.inflation(pd.Timestamp("2021-12-31"), pd.Timestamp("2022-12-30"))
    assert mesure.publie_le == "2023-01-31"
    assert pd.Timestamp(mesure.publie_le) <= pd.Timestamp(macro.date_extraction(macro.FICHIER_MACRO))


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


def test_rendement_reel_calcule_a_la_main():
    # 10 % en dollars avec 3 % d'inflation : 1,10 ÷ 1,03 = 1,067961… soit +6,80 % réel,
    # et non 10 − 3 = 7 %. Placement à 0 % en 2022 (inflation 6,3 %) : 1 ÷ 1,063 = 0,940734…
    assert macro.rendement_reel(0.10, 0.03) == pytest.approx(0.067961, abs=1e-6)
    assert macro.rendement_reel(0.0, 0.063) == pytest.approx(-0.059266, abs=1e-6)


def test_source_avec_date_d_extraction():
    assert macro.source_macro().endswith("extrait le 2026-11-13")


def test_les_vrais_proces_de_demo_contiennent_le_rendement_reel():
    """#113, « terminé quand » : un contrat réel (Bedrock) a le rendement réel dans une pièce et passe le validateur."""
    import json
    from pathlib import Path

    from contrat.valider import valider_contrat

    dossier = Path(__file__).resolve().parents[1] / "frontend" / "src" / "data" / "proces"
    index = json.loads((dossier / "index.json").read_text(encoding="utf-8"))["proces"]
    assert index
    for entree in index:
        contrat = json.loads((dossier / f"{entree['procesId']}.json").read_text(encoding="utf-8"))
        assert valider_contrat(contrat) == [], entree["procesId"]
        simulations = [p["valeurs"] for p in contrat["pieces"] if "rendement_reel_annuel" in p["valeurs"]]
        assert simulations, f"{entree['procesId']} : aucune pièce avec le rendement réel"
        for valeurs in simulations:
            attendu = macro.rendement_reel(valeurs["rendement_annuel"], valeurs["inflation_annuelle"])
            assert valeurs["rendement_reel_annuel"] == pytest.approx(attendu, abs=1e-6)
