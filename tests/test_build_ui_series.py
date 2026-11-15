"""Tests des données de l'interface (pipeline/vues_interface.py, utilisé par scripts/build_ui_series.py et la Lambda) :
elles reprennent les calculs du pipeline."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import numpy as np
import pytest

from pipeline import vues_interface as build
from pipeline.categories import charger_categories
from pipeline.pacte import charger_pacte

RACINE = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def robert():
    return charger_pacte(RACINE / "personas" / "robert.json")


@pytest.fixture(scope="module")
def semaines(robert):
    return build.positions_hebdomadaires(build.valeurs_actuelles(robert["portefeuille"]).index)


def test_compositions_couvrent_toutes_les_repartitions():
    repartitions = list(build.compositions(4, 20))
    assert len(repartitions) == 1771  # C(23, 3) : 4 titres, pas de 5 points
    assert all(sum(r) == 20 for r in repartitions)
    assert (5, 5, 5, 5) in repartitions and (20, 0, 0, 0) in repartitions


def test_max_conforme_s_arrete_a_la_premiere_taille_incompatible():
    entrees = [{"taille": t, "compatible": t <= 9 or t == 12} for t in range(15)]
    assert build.max_conforme(entrees) == 9
    assert build.max_conforme([{"taille": 0, "compatible": False}]) is None


def test_encodage_du_recul_en_dixiemes_de_point():
    recul = np.array([0.0, -0.077574, -0.289679])
    entiers = np.frombuffer(base64.b64decode(build.encoder_recul(recul)), dtype="<i2")
    assert entiers.tolist() == [0, -78, -290]


def test_une_semaine_une_seance(robert, semaines):
    index = build.valeurs_actuelles(robert["portefeuille"]).index
    dates = index[semaines]
    assert dates[0] == index[0] and dates[-1] == index[-1]
    assert len(set(zip(dates.isocalendar().year, dates.isocalendar().week))) == len(dates)


def test_robert_actuel_et_trente_pour_cent_de_tsla(robert, semaines):
    profil = build.construire_profil(robert, {t: {"groupe": "x"} for t in ["ZST.TO", "XBB.TO", "XIU.TO", "JNJ", "RY.TO", "FTS.TO"]}, semaines)
    actuel = profil["actuel"]
    assert round(actuel["rendement"] * 100, 1) == 9.3
    assert round(actuel["chuteMax"] * 100, 1) == -7.8
    assert actuel["gain"] == 233034

    decision = {"type": "position", "ticker": "TSLA", "taille": 0.30, "financement": "proportionnel"}
    entree = build.entree_decision(robert["portefeuille"], decision, robert["pacte"]["regles"], semaines)
    assert round(entree["chuteMax"] * 100, 1) == -29.0
    assert round(entree["rejeu2022"] * 100, 1) == -23.7
    assert entree["statuts"]["pire_baisse_max"] == "violation"
    assert entree["seances"] == {"nombre": 278, "du": "2022-02-23", "au": "2025-05-07"}


def test_rendement_reel_identique_a_la_piece_du_tribunal(robert, semaines):
    """#113 : l'écran Décision affiche le rendement après inflation que le Tribunal citerait."""
    from pipeline.simulation import piece_simulation

    decision = {"type": "position", "ticker": "TSLA", "taille": 0.30, "financement": "proportionnel"}
    valeurs = piece_simulation("P1", robert["portefeuille"], decision)["valeurs"]
    profil = build.construire_profil(robert, build.groupes_univers(), semaines)
    entree = build.entree_decision(robert["portefeuille"], decision, robert["pacte"]["regles"], semaines)

    assert profil["inflation"]["annuelle"] == pytest.approx(valeurs["inflation_annuelle"], abs=1e-6)
    assert (profil["inflation"]["moisFin"], profil["inflation"]["publieLe"]) == ("2026-09", "2026-10-31")
    assert profil["actuel"]["rendementReel"] == pytest.approx(valeurs["rendement_reel_annuel_actuel"], abs=1e-6)
    assert entree["rendementReel"] == pytest.approx(valeurs["rendement_reel_annuel"], abs=1e-6)
    assert entree["rendementReel"] < entree["rendement"]


def test_sans_donnees_macro_l_ecran_reste_affichable(robert, semaines, monkeypatch):
    def sans_fichier(*_args, **_kwargs):
        raise build.ErreurDonnees("macro_rates.csv absent")

    monkeypatch.setattr(build.macro, "inflation", sans_fichier)
    profil = build.construire_profil(robert, build.groupes_univers(), semaines)
    assert profil["inflation"] is None and profil["actuel"]["rendementReel"] is None


def test_groupes_deduits_de_l_univers_sans_nom_de_profil():
    univers = build.charger_univers().set_index("ticker", drop=False)
    assert build.groupe_du_titre(univers.loc["XBB.TO"]) == "Revenu fixe"
    assert build.groupe_du_titre(univers.loc["BTC-USD"]) == "Cryptoactifs"
    assert build.groupe_du_titre(univers.loc["ESGV"]) == "Actions filtrées ESG"
    assert build.groupe_du_titre(univers.loc["NVDA"]) == "Technologie"
    assert build.groupe_du_titre(univers.loc["RY.TO"]) == "Actions canadiennes"
    assert build.groupe_du_titre(univers.loc["JNJ"]) == "Actions américaines"
    assert set(charger_categories()) >= {"crypto", "tech"}


def test_vues_d_un_profil_identiques_aux_fichiers_precalcules(robert):
    """La Lambda (/profil, #86) et scripts/build_ui_series.py produisent les mêmes vues."""
    generes = RACINE / "frontend" / "src" / "data" / "generated"
    vues = json.loads(json.dumps(build.vues_profil(robert)))
    assert vues["profil"] == json.loads((generes / "profils" / "robert.json").read_text(encoding="utf-8"))
    assert vues["calibrage"] == json.loads((generes / "calibrage" / "robert.json").read_text(encoding="utf-8"))
