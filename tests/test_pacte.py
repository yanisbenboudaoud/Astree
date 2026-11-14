import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from contrat.valider import charger_schema as charger_schema_contrat
from pipeline.categories import categories_du_titre, charger_categories, charger_univers
from pipeline.pacte import (
    PacteInvalide,
    charger_pacte,
    charger_profil,
    pacte_du_contrat,
    valider_profil,
)

RACINE = Path(__file__).resolve().parent.parent
PERSONAS = RACINE / "personas"
PROFIL_INVENTE = Path(__file__).resolve().parent / "donnees" / "profil_invente.json"
NOMS_CATEGORIES = set(charger_categories())


def lire(chemin):
    with open(chemin, encoding="utf-8") as fichier:
        return json.load(fichier)


@pytest.fixture
def profil():
    return copy.deepcopy(lire(PROFIL_INVENTE))


# --- Les profils valides ---------------------------------------------------

FICHIERS_PROFILS = [c for c in sorted(PERSONAS.glob("*.json")) if c.name != "schema_pacte.json"]


@pytest.mark.parametrize("chemin", FICHIERS_PROFILS + [PROFIL_INVENTE], ids=lambda c: c.name)
def test_profils_valides(chemin):
    assert valider_profil(lire(chemin), NOMS_CATEGORIES) == []


def test_profil_invente_se_charge_sans_changer_le_code():
    profil = charger_profil(PROFIL_INVENTE)
    assert profil["id"] == "profil_invente"
    assert [r["type"] for r in profil["pacte"]["regles"]] == [
        "pire_baisse_max", "plafond", "critere_documentaire", "qualitative"
    ]


# --- La pièce « Pacte » ----------------------------------------------------

def test_piece_pacte_robert_identique_au_contrat_exemple():
    piece = charger_pacte(PERSONAS / "robert.json", id_piece="P3")
    exemple = next(p for p in lire(RACINE / "docs/exemples/contrat_robert.json")["pieces"] if p["id"] == "P3")
    assert piece["valeurs"] == exemple["valeurs"]
    assert piece["valeur_affichee"] == exemple["valeur_affichee"] == "Signé le 14 nov. 2026"
    assert piece["titre"] == exemple["titre"]
    assert piece["source"] == exemple["source"].replace("persona fictif", "profil fictif")


@pytest.mark.parametrize("chemin", [PERSONAS / "amira.json", PERSONAS / "mateo.json", PROFIL_INVENTE], ids=lambda c: c.name)
def test_piece_pacte_respecte_le_schema_du_contrat(chemin):
    schema = charger_schema_contrat()
    validateur = Draft202012Validator({**schema["$defs"]["piece"], "$defs": schema["$defs"]})
    assert list(validateur.iter_errors(charger_pacte(chemin, id_piece="P1"))) == []


def test_piece_pacte_horizon_sans_borne():
    piece = charger_pacte(PERSONAS / "amira.json")
    assert piece["valeurs"]["horizon_ans"] == [15, None]
    assert piece["valeurs"]["plafond_crypto"] == 0.25
    assert piece["valeurs"]["pas_exclusivement_tech"] == 0.75


def test_pacte_du_contrat_sans_justification():
    pacte = pacte_du_contrat(charger_profil(PERSONAS / "robert.json"))
    exemple = lire(RACINE / "docs/exemples/contrat_robert.json")["pacte"]
    assert all("justification" not in regle for regle in pacte["regles"])
    assert pacte == exemple


# --- Les cas refusés -------------------------------------------------------

def test_type_de_regle_inconnu_refuse(profil):
    profil["pacte"]["regles"][0]["type"] = "risque_max"
    erreurs = valider_profil(profil, NOMS_CATEGORIES)
    assert any("pacte/regles/0/type" in e and "« risque_max » inconnue" in e for e in erreurs)


def test_categorie_inconnue_refusee(profil):
    profil["pacte"]["regles"][1]["categories"] = ["energie"]
    erreurs = valider_profil(profil, NOMS_CATEGORIES)
    assert erreurs == [
        "pacte/regles/1 (tech_limitee) : catégorie « energie » inconnue "
        "(catégories de config/categories.json : crypto, tech)"
    ]


def test_charger_profil_leve_une_erreur_claire(tmp_path, profil):
    profil["pacte"]["regles"][1]["categories"] = ["energie"]
    chemin = tmp_path / "mauvais.json"
    chemin.write_text(json.dumps(profil), encoding="utf-8")
    with pytest.raises(PacteInvalide, match="catégorie « energie » inconnue") as erreur:
        charger_profil(chemin)
    assert len(erreur.value.erreurs) == 1


def test_id_de_regle_en_double_refuse(profil):
    profil["pacte"]["regles"][1]["id"] = "pire_baisse_max"
    assert valider_profil(profil, NOMS_CATEGORIES) == [
        "pacte/regles : identifiant de règle « pire_baisse_max » en double"
    ]


def test_justification_obligatoire(profil):
    del profil["pacte"]["regles"][3]["justification"]
    assert valider_profil(profil, NOMS_CATEGORIES) == [
        "pacte/regles/3 : champ obligatoire manquant : justification"
    ]


def test_justification_vide_refusee(profil):
    profil["pacte"]["regles"][3]["justification"] = ""
    assert valider_profil(profil, NOMS_CATEGORIES)


@pytest.mark.parametrize(
    "index, parametre",
    [(0, "seuil"), (1, "categories"), (1, "max"), (2, "critere")],
)
def test_parametre_manquant_refuse(profil, index, parametre):
    del profil["pacte"]["regles"][index][parametre]
    erreurs = valider_profil(profil, NOMS_CATEGORIES)
    assert f"pacte/regles/{index} : champ obligatoire manquant : {parametre}" in erreurs


def test_parametre_d_un_autre_type_refuse(profil):
    profil["pacte"]["regles"][0]["max"] = 0.5
    assert valider_profil(profil, NOMS_CATEGORIES) == [
        "pacte/regles/0 : paramètre « max » non permis pour le type « pire_baisse_max »"
    ]


def test_seuil_positif_refuse(profil):
    profil["pacte"]["regles"][0]["seuil"] = 0.3
    assert valider_profil(profil, NOMS_CATEGORIES)


def test_etiquette_autre_que_fictif_refusee(profil):
    profil["etiquette"] = "reel"
    assert valider_profil(profil, NOMS_CATEGORIES)


def test_poids_du_portefeuille_qui_ne_totalisent_pas_1(profil):
    profil["portefeuille"][0]["poids"] = 0.5
    assert valider_profil(profil, NOMS_CATEGORIES) == ["portefeuille : les poids totalisent 1.1000, pas 1"]


def test_titre_en_double_dans_le_portefeuille(profil):
    profil["portefeuille"][1]["ticker"] = "SPY"
    assert "portefeuille : titre « SPY » en double" in valider_profil(profil, NOMS_CATEGORIES)


def test_panier_de_reallocation_qui_ne_totalise_pas_1(profil):
    profil["decision_demo"] = {
        "type": "reallocation",
        "panier": [{"ticker": "BTC-USD", "poids": 0.5}],
        "part_reallouee": 1.0,
    }
    assert valider_profil(profil, NOMS_CATEGORIES) == ["decision_demo/panier : les poids totalisent 0.5000, pas 1"]


def test_financement_inconnu_refuse(profil):
    profil["decision_demo"]["financement"] = "a_credit"
    assert valider_profil(profil, NOMS_CATEGORIES)


def test_horizon_inverse_refuse(profil):
    profil["horizon_ans"] = [20, 10]
    assert valider_profil(profil, NOMS_CATEGORIES) == [
        "horizon_ans : le maximum (10) est plus petit que le minimum (20)"
    ]


# --- Catégories d'un titre -------------------------------------------------

@pytest.fixture(scope="module")
def categories():
    return charger_categories()


@pytest.fixture(scope="module")
def univers():
    return charger_univers()


@pytest.mark.parametrize(
    "ticker, attendu",
    [
        ("BTC-USD", ["crypto"]),       # classe d'actifs « crypto »
        ("NVDA", ["tech"]),            # secteur « Information Technology »
        ("SHOP.TO", ["tech"]),
        ("GOOGL", ["tech"]),           # ajout justifié dans config/categories.json
        ("QQQ", ["tech"]),
        ("TSLA", []),                  # dans l'univers, mais dans aucune catégorie
        ("XOM", []),
        ("ESGV", []),                  # secteur avec une virgule dans le CSV
    ],
)
def test_categories_du_titre(categories, univers, ticker, attendu):
    assert categories_du_titre(ticker, categories, univers) == {
        "ticker": ticker, "dans_univers": True, "categories": attendu
    }


def test_titre_absent_de_l_univers_signale(categories, univers):
    resultat = categories_du_titre("DOGE-USD", categories, univers)
    assert resultat == {"ticker": "DOGE-USD", "dans_univers": False, "categories": []}


def test_tous_les_titres_des_profils_sont_dans_l_univers(univers):
    for chemin in [PERSONAS / "robert.json", PERSONAS / "amira.json", PERSONAS / "mateo.json", PROFIL_INVENTE]:
        profil = lire(chemin)
        tickers = [ligne["ticker"] for ligne in profil["portefeuille"]]
        decision = profil["decision_demo"]
        tickers += [l["ticker"] for l in decision["panier"]] if decision["type"] == "reallocation" else [decision["ticker"]]
        assert [t for t in tickers if t not in univers] == [], chemin.name
