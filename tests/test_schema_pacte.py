"""Tests du schéma des fichiers profils (personas/schema_pacte.json)."""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_PERSONAS = RACINE / "personas"


def charger_json(chemin):
    with open(chemin, encoding="utf-8") as fichier:
        return json.load(fichier)


VALIDATEUR = Draft202012Validator(charger_json(DOSSIER_PERSONAS / "schema_pacte.json"))


def erreurs(profil):
    return list(VALIDATEUR.iter_errors(profil))


@pytest.fixture
def profil():
    return copy.deepcopy(charger_json(DOSSIER_PERSONAS / "robert.json"))


def test_schema_lui_meme_valide():
    Draft202012Validator.check_schema(charger_json(DOSSIER_PERSONAS / "schema_pacte.json"))


@pytest.mark.parametrize("nom", ["robert.json", "amira.json", "mateo.json"])
def test_profils_de_test_valides(nom):
    assert erreurs(charger_json(DOSSIER_PERSONAS / nom)) == []


def test_type_de_regle_inconnu_rejete(profil):
    profil["pacte"]["regles"][0]["type"] = "volatilite_max"
    assert erreurs(profil)


def test_regle_sans_justification_rejetee(profil):
    del profil["pacte"]["regles"][0]["justification"]
    assert erreurs(profil)


def test_pire_baisse_sans_seuil_rejetee(profil):
    del profil["pacte"]["regles"][0]["seuil"]
    assert erreurs(profil)


def test_seuil_positif_rejete(profil):
    profil["pacte"]["regles"][0]["seuil"] = 0.12
    assert erreurs(profil)


def test_plafond_sans_categories_rejete(profil):
    del profil["pacte"]["regles"][1]["categories"]
    assert erreurs(profil)


def test_plafond_max_superieur_a_un_rejete(profil):
    profil["pacte"]["regles"][1]["max"] = 25
    assert erreurs(profil)


def test_parametre_d_un_autre_type_rejete(profil):
    profil["pacte"]["regles"][0]["max"] = 0.5
    assert erreurs(profil)


def test_qualitative_avec_parametre_rejetee(profil):
    profil["pacte"]["regles"][2]["seuil"] = -0.1
    assert erreurs(profil)


def test_critere_documentaire_sans_critere_rejete(profil):
    profil["pacte"]["regles"].append(
        {"id": "esg", "type": "critere_documentaire", "libelle": "ESG", "justification": "Hypothèse."}
    )
    assert erreurs(profil)


def test_champ_inconnu_rejete(profil):
    profil["recommandation"] = "acheter"
    assert erreurs(profil)


def test_etiquette_autre_que_fictif_rejetee(profil):
    profil["etiquette"] = "fait"
    assert erreurs(profil)


def test_decision_position_sans_taille_rejetee(profil):
    del profil["decision_demo"]["taille"]
    assert erreurs(profil)


def test_decision_type_inconnu_rejete(profil):
    profil["decision_demo"]["type"] = "vente"
    assert erreurs(profil)


def test_financement_depuis_un_titre_accepte(profil):
    profil["decision_demo"]["financement"] = "depuis_ZST.TO"
    assert erreurs(profil) == []


def test_profil_invente_sans_age_ni_metier_valide():
    profil = {
        "id": "nadia",
        "nom": "Nadia",
        "etiquette": "fictif",
        "profil_risque": "modere",
        "horizon_ans": [10, None],
        "capital_fictif_cad": 75000,
        "portefeuille": [{"ticker": "SPY", "poids": 0.6}, {"ticker": "XBB.TO", "poids": 0.4}],
        "decision_demo": {"type": "position", "ticker": "NVDA", "taille": 0.15, "financement": "depuis_SPY"},
        "pacte": {
            "date_signature": "2026-11-14",
            "regles": [
                {"id": "pire_baisse_max", "type": "pire_baisse_max", "seuil": -0.25,
                 "libelle": "Pire baisse tolérée : −25 %", "justification": "Hypothèse de test."},
                {"id": "plafond_tech", "type": "plafond", "categories": ["tech"], "max": 0.4,
                 "libelle": "Tech : 40 % au maximum", "justification": "Hypothèse de test."},
            ],
        },
    }
    assert erreurs(profil) == []
