import copy

import pandas as pd
import pytest
from jsonschema import Draft202012Validator

from contrat.valider import charger_schema
from pipeline.donnees import ErreurDonnees
from pipeline.indicateurs import (
    DESCRIPTION_BEDROCK,
    calculer_pire_baisse,
    calculer_rendement_2022,
    calculer_rendement_annualise,
    calculer_temps_recuperation,
    calculer_volatilite_annuelle,
    indicateurs_actif,
)


def serie(valeurs, debut="2021-12-30"):
    return pd.Series(valeurs, index=pd.bdate_range(debut, periods=len(valeurs)), dtype=float)


# --- Petites séries connues -------------------------------------------------


def test_rendement_annualise_double_en_deux_ans():
    valeurs = pd.Series([100.0, 200.0], index=pd.to_datetime(["2020-01-01", "2021-12-31"]))
    annees = (valeurs.index[1] - valeurs.index[0]).days / 365.25
    assert calculer_rendement_annualise(valeurs) == pytest.approx(2 ** (1 / annees) - 1)


def test_volatilite_nulle_pour_une_croissance_constante():
    assert calculer_volatilite_annuelle(serie([100 * 1.01**i for i in range(10)])) == pytest.approx(0)


def test_volatilite_annualisee_racine_de_252():
    valeurs = serie([100, 110, 99, 108.9])  # rendements : +10 %, −10 %, +10 %
    attendu = pd.Series([0.1, -0.1, 0.1]).std() * 252**0.5
    assert calculer_volatilite_annuelle(valeurs) == pytest.approx(attendu)


def test_pire_baisse_depuis_le_sommet():
    assert calculer_pire_baisse(serie([100, 120, 90, 110, 60, 130])) == pytest.approx(-0.5)


def test_pire_baisse_nulle_sans_baisse():
    assert calculer_pire_baisse(serie([1, 2, 3])) == 0


def test_rendement_2022_derniere_valeur_de_chaque_annee():
    valeurs = pd.Series(
        [100.0, 80.0, 50.0, 60.0, 999.0],
        index=pd.to_datetime(["2021-06-01", "2021-12-31", "2022-06-01", "2022-12-30", "2023-01-03"]),
    )
    assert calculer_rendement_2022(valeurs) == pytest.approx(60 / 80 - 1)


def test_rendement_2022_sans_donnees_erreur():
    with pytest.raises(ErreurDonnees, match="2021"):
        calculer_rendement_2022(serie([1, 2, 3], debut="2023-01-02"))


def test_temps_recuperation_sommet_creux_retour():
    valeurs = pd.Series(
        [100.0, 120.0, 60.0, 119.0, 121.0],
        index=pd.to_datetime(["2022-01-01", "2022-01-03", "2022-06-01", "2023-01-01", "2023-01-03"]),
    )
    assert calculer_temps_recuperation(valeurs) == {
        "date_sommet": "2022-01-03",
        "date_creux": "2022-06-01",
        "date_retour_sommet": "2023-01-03",
        "annees_recuperation": pytest.approx(365 / 365.25),
    }


def test_temps_recuperation_pas_revenu_au_sommet():
    resultat = calculer_temps_recuperation(serie([100, 120, 60, 90]))
    assert resultat["date_creux"] is not None
    assert resultat["date_retour_sommet"] is None
    assert resultat["annees_recuperation"] is None


def test_temps_recuperation_sans_baisse():
    assert set(calculer_temps_recuperation(serie([1, 2, 3])).values()) == {None}


# --- L'outil sur les vraies données ------------------------------------------


@pytest.fixture(scope="module")
def piece_tsla():
    return indicateurs_actif("TSLA")


def test_tsla_correspond_a_la_maquette(piece_tsla):
    # Pièce P4 de docs/exemples/contrat_robert.json.
    valeurs = piece_tsla["valeurs"]
    assert round(valeurs["pire_baisse"], 4) == -0.7088
    assert valeurs["date_sommet"] == "2022-01-03"
    assert valeurs["date_creux"] == "2023-01-03"


def test_tsla_temps_de_recuperation_en_cad(piece_tsla):
    # La maquette calculait le retour au sommet en USD (2024-12-10, 2,935 ans).
    # En CAD, comme tous les chiffres du contrat, TSLA revient à son sommet plus tôt.
    # « près de 3 ans » reste vrai dans les deux cas.
    assert piece_tsla["valeurs"]["date_retour_sommet"] == "2024-12-05"
    assert round(piece_tsla["valeurs"]["annees_recuperation"], 4) == 2.9213
    assert round(piece_tsla["valeurs"]["annees_recuperation"]) == 3


def test_piece_conforme_au_contrat(piece_tsla):
    schema = charger_schema()
    schema_piece = {"$defs": schema["$defs"], "$ref": "#/$defs/piece"}
    piece = copy.deepcopy(piece_tsla)
    piece["id"] = "P4"  # l'orchestrateur numérote les pièces
    assert list(Draft202012Validator(schema_piece).iter_errors(piece)) == []


def test_valeurs_brutes_et_valeur_affichee_arrondie(piece_tsla):
    assert piece_tsla["valeurs"]["pire_baisse"] == -0.708806
    assert piece_tsla["valeur_affichee"].startswith("−70,9 % max")


def test_source_sans_taux_de_change_pour_un_titre_cad():
    piece = indicateurs_actif("RY.TO")
    assert "USD/CAD" not in piece["source"]
    assert "2026-11-13" in piece["source"]


def test_ticker_hors_univers_erreur_lisible():
    with pytest.raises(ErreurDonnees, match="ZZZ"):
        indicateurs_actif("ZZZ")


def test_description_bedrock():
    spec = DESCRIPTION_BEDROCK["toolSpec"]
    assert spec["name"] == "indicateurs_actif"
    assert spec["inputSchema"]["json"]["required"] == ["ticker"]
