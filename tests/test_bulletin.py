"""Bulletin du Greffier (#172) : les taux mesurés, écrits par Python pour l'interface."""

import json
from types import SimpleNamespace

import pytest

from validation.bulletin import (
    CHEMIN_BULLETIN,
    charger_bulletin,
    mesure_cadre,
    mesure_chiffres,
    mesure_externe,
    mesure_orchestrateur,
    mesure_taux,
    ranger_mesure,
)
from validation.evaluation import RACINE, evaluer_jeu
from validation.externe import charger_releves, comparer


def test_mesure_taux_prete_a_afficher():
    assert mesure_taux(47, 78) == {"k": 47, "n": 78, "taux": 0.6026, "rates": 31, "ic95": [0.4916, 0.7039]}
    assert mesure_taux(66, 66)["ic95"] == [0.945, 1.0]


def test_ranger_garde_la_date_si_les_chiffres_n_ont_pas_change(tmp_path):
    chemin = tmp_path / "bulletin.json"
    mesure = {"issue": 165, "pieges": mesure_taux(66, 66)}
    assert ranger_mesure("verifier_chiffres", mesure, chemin, aujourd_hui="2026-11-15")["date"] == "2026-11-15"
    # Même mesure relancée plus tard : le fichier ne change pas.
    avant = chemin.read_text(encoding="utf-8")
    ranger_mesure("verifier_chiffres", mesure, chemin, aujourd_hui="2026-11-20")
    assert chemin.read_text(encoding="utf-8") == avant
    # Chiffres différents : nouvelle date.
    nouvelle = {"issue": 165, "pieges": mesure_taux(65, 66)}
    assert ranger_mesure("verifier_chiffres", nouvelle, chemin, aujourd_hui="2026-11-20")["date"] == "2026-11-20"


def test_ranger_garde_les_autres_mesures(tmp_path):
    chemin = tmp_path / "bulletin.json"
    ranger_mesure("verifier_chiffres", {"issue": 165}, chemin, aujourd_hui="2026-11-15")
    ranger_mesure("cadre_simulation", {"issue": 166}, chemin, aujourd_hui="2026-11-15")
    bulletin = charger_bulletin(chemin)
    assert list(bulletin["mesures"]) == ["cadre_simulation", "verifier_chiffres"]
    assert bulletin["depot"].startswith("https://github.com/")


def test_mesure_orchestrateur_additionne_les_deux_cotes():
    mesures = SimpleNamespace(
        nb_proces=201, proces_dans_budget=201, simulation_spontanee=200,
        cotes={"requisitoire": SimpleNamespace(renvoyes=113, corriges=108),
               "plaidoirie": SimpleNamespace(renvoyes=33, corriges=32)})
    cle, mesure = mesure_orchestrateur(mesures, "2026-11-15")
    assert cle == "orchestrateur"
    assert mesure["budget_respecte"]["k"] == 201 and mesure["simulation_demandee"]["rates"] == 1
    assert (mesure["corriges_apres_renvoi"]["k"], mesure["corriges_apres_renvoi"]["n"]) == (140, 146)


# --- Le bulletin du dépôt dit exactement ce que disent les rapports --------------------

@pytest.fixture(scope="module")
def bulletin():
    return json.loads(CHEMIN_BULLETIN.read_text(encoding="utf-8"))


def sans_date(entree):
    return {k: v for k, v in entree.items() if k != "date"}


@pytest.mark.parametrize("nom, mesurer", [("chiffres", mesure_chiffres), ("cadre", mesure_cadre)])
def test_bulletin_des_jeux_a_jour(bulletin, nom, mesurer):
    jeu, resultats, _ = evaluer_jeu(nom)
    cle, mesure = mesurer(nom, jeu, resultats)
    assert sans_date(bulletin["mesures"][cle]) == mesure, (
        f"frontend/src/data/bulletin.json n'est plus à jour : relancer python -m validation.evaluation {nom}")


def test_bulletin_de_la_validation_externe_a_jour(bulletin):
    releves = charger_releves()
    cle, mesure = mesure_externe(releves, comparer(releves))
    assert sans_date(bulletin["mesures"][cle]) == mesure, (
        "frontend/src/data/bulletin.json n'est plus à jour : relancer python -m validation.externe")


@pytest.mark.parametrize("cle, champs, texte", [
    ("verifier_chiffres", ("pieges", "legitimes"), "{k}/{n} ("),
    ("cadre_simulation", ("pieges", "legitimes"), "{k}/{n} ("),
    ("validation_externe", ("dans_le_seuil", "annee_2022"), "{k}/{n} ("),
])
def test_chaque_chiffre_du_bulletin_figure_dans_son_rapport(bulletin, cle, champs, texte):
    entree = bulletin["mesures"][cle]
    rapport = (RACINE / entree["rapport"]).read_text(encoding="utf-8")
    for champ in champs:
        assert texte.format(**entree[champ]) in rapport, (cle, champ)
