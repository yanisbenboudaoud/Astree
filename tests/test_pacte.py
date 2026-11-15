"""Tests du chargement et de la validation des Pactes (pipeline/pacte.py)."""

import copy
import json
from pathlib import Path

import pytest

from pipeline.pacte import PacteInvalide, charger_pacte, pacte_pour_contrat, piece_pacte

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_PERSONAS = RACINE / "personas"
EXEMPLES = RACINE / "docs" / "exemples"


def lire_json(chemin):
    with open(chemin, encoding="utf-8") as fichier:
        return json.load(fichier)


def ecrire_profil(dossier, profil, nom=None):
    chemin = dossier / f"{nom or profil['id']}.json"
    chemin.write_text(json.dumps(profil, ensure_ascii=False), encoding="utf-8")
    return chemin


def erreurs_au_chargement(dossier, profil, nom=None):
    """Charge le profil et renvoie le texte de l'erreur (échoue s'il est accepté)."""
    with pytest.raises(PacteInvalide) as exc:
        charger_pacte(ecrire_profil(dossier, profil, nom))
    return str(exc.value)


@pytest.fixture
def robert():
    return copy.deepcopy(lire_json(DOSSIER_PERSONAS / "robert.json"))


@pytest.fixture
def amira():
    return copy.deepcopy(lire_json(DOSSIER_PERSONAS / "amira.json"))


PROFIL_INVENTE = {
    "id": "nadia",
    "nom": "Nadia",
    "etiquette": "fictif",
    "profil_risque": "modere_a_eleve",
    "horizon_ans": [10, None],
    "capital_fictif_cad": 75000,
    "portefeuille": [{"ticker": "SPY", "poids": 0.6}, {"ticker": "XBB.TO", "poids": 0.4}],
    "decision_demo": {"type": "position", "ticker": "NVDA", "taille": 0.15, "financement": "depuis_SPY"},
    "pacte": {
        "date_signature": "2026-03-02",
        "regles": [
            {"id": "pire_baisse_max", "type": "pire_baisse_max", "seuil": -0.25,
             "libelle": "Pire baisse tolérée : −25 %", "justification": "Hypothèse de test."},
            {"id": "plafond_tech", "type": "plafond", "categories": ["tech"], "max": 0.4,
             "libelle": "Tech : 40 % au maximum", "justification": "Hypothèse de test."},
            {"id": "esg", "type": "critere_documentaire", "critere": "controverse_esg_importante",
             "libelle": "Pas de controverse ESG", "justification": "Hypothèse de test."},
            {"id": "local", "type": "qualitative",
             "libelle": "Favoriser les entreprises canadiennes", "justification": "Hypothèse de test."},
        ],
    },
}


# --- Profils acceptés --------------------------------------------------------

@pytest.mark.parametrize("nom", ["robert", "amira", "mateo"])
def test_profils_de_test_charges(nom):
    profil = charger_pacte(DOSSIER_PERSONAS / f"{nom}.json")
    assert profil["id"] == nom
    assert profil["pacte"]["regles"]


def test_profil_invente_charge_sans_changer_le_code(tmp_path):
    profil = charger_pacte(ecrire_profil(tmp_path, PROFIL_INVENTE))
    assert profil == PROFIL_INVENTE


# --- Profils refusés : schéma ------------------------------------------------

def test_type_de_regle_inconnu_refuse(tmp_path, robert):
    robert["pacte"]["regles"][0]["type"] = "volatilite_max"
    message = erreurs_au_chargement(tmp_path, robert)
    assert "volatilite_max" in message
    assert "règle « pire_baisse_max »" in message
    assert "valeurs permises" in message


def test_parametre_manquant_refuse(tmp_path, robert):
    del robert["pacte"]["regles"][1]["max"]
    message = erreurs_au_chargement(tmp_path, robert)
    assert "champ obligatoire manquant : max" in message


def test_justification_manquante_refusee(tmp_path, robert):
    del robert["pacte"]["regles"][2]["justification"]
    assert "justification" in erreurs_au_chargement(tmp_path, robert)


def test_parametre_d_un_autre_type_refuse(tmp_path, robert):
    robert["pacte"]["regles"][2]["seuil"] = -0.1
    assert "champ non permis ici : seuil" in erreurs_au_chargement(tmp_path, robert)


def test_json_illisible_refuse(tmp_path):
    chemin = tmp_path / "casse.json"
    chemin.write_text("{ pas du json", encoding="utf-8")
    with pytest.raises(PacteInvalide, match="JSON illisible"):
        charger_pacte(chemin)


# --- Profils refusés : cohérence ---------------------------------------------

def test_categorie_inconnue_refusee(tmp_path, robert):
    robert["pacte"]["regles"][1]["categories"] = ["crypto", "energie"]
    message = erreurs_au_chargement(tmp_path, robert)
    assert "catégorie inconnue : energie" in message
    assert "config/categories.json" in message


def test_id_de_regle_en_double_refuse(tmp_path, robert):
    robert["pacte"]["regles"][3]["id"] = "preserver_capital"
    assert "id de règle en double : preserver_capital" in erreurs_au_chargement(tmp_path, robert)


@pytest.mark.parametrize("id_reserve", ["verifier_chiffres", "cadre_simulation", "horizon_ans"])
def test_id_de_regle_reserve_refuse(tmp_path, robert, id_reserve):
    robert["pacte"]["regles"][2]["id"] = id_reserve
    assert "id réservé" in erreurs_au_chargement(tmp_path, robert)


def test_poids_du_portefeuille_qui_ne_totalisent_pas_un_refuses(tmp_path, robert):
    robert["portefeuille"][0]["poids"] = 0.5
    assert "portefeuille : les poids totalisent 1.2000" in erreurs_au_chargement(tmp_path, robert)


def test_ticker_en_double_refuse(tmp_path, robert):
    robert["portefeuille"][1]["ticker"] = "ZST.TO"
    assert "ticker en double : ZST.TO" in erreurs_au_chargement(tmp_path, robert)


def test_poids_du_panier_qui_ne_totalisent_pas_un_refuses(tmp_path, amira):
    amira["decision_demo"]["panier"][0]["poids"] = 0.5
    assert "decision_demo/panier : les poids totalisent" in erreurs_au_chargement(tmp_path, amira)


def test_financement_depuis_un_titre_absent_refuse(tmp_path, robert):
    robert["decision_demo"]["financement"] = "depuis_AAPL"
    assert "« AAPL » n'est pas dans le portefeuille" in erreurs_au_chargement(tmp_path, robert)


def test_horizon_inverse_refuse(tmp_path, robert):
    robert["horizon_ans"] = [5, 3]
    assert "le minimum 5 dépasse le maximum 3" in erreurs_au_chargement(tmp_path, robert)


def test_date_impossible_refusee(tmp_path, robert):
    robert["pacte"]["date_signature"] = "2026-13-40"
    assert "n'est pas une date réelle" in erreurs_au_chargement(tmp_path, robert)


def test_id_different_du_nom_de_fichier_refuse(tmp_path, robert):
    message = erreurs_au_chargement(tmp_path, robert, nom="robert_v2")
    assert "diffère du nom du fichier « robert_v2.json »" in message


def test_toutes_les_erreurs_listees_d_un_coup(tmp_path, robert):
    robert["horizon_ans"] = [5, 3]
    robert["pacte"]["regles"][1]["categories"] = ["energie"]
    with pytest.raises(PacteInvalide) as exc:
        charger_pacte(ecrire_profil(tmp_path, robert))
    assert len(exc.value.erreurs) == 2


# --- Sorties pour le contrat -------------------------------------------------

@pytest.mark.parametrize("nom", ["robert", "amira"])
def test_pacte_pour_contrat_identique_a_l_exemple(nom):
    profil = charger_pacte(DOSSIER_PERSONAS / f"{nom}.json")
    assert pacte_pour_contrat(profil) == lire_json(EXEMPLES / f"contrat_{nom}.json")["pacte"]


@pytest.mark.parametrize("nom", ["robert", "amira"])
def test_piece_pacte_identique_a_l_exemple(nom):
    profil = charger_pacte(DOSSIER_PERSONAS / f"{nom}.json")
    pieces = lire_json(EXEMPLES / f"contrat_{nom}.json")["pieces"]
    attendue = next(p for p in pieces if p["outil"] == "charger_pacte")
    assert piece_pacte(profil, attendue["id"]) == attendue


def test_piece_pacte_sans_regle_chiffree_garde_date_et_horizon(tmp_path):
    profil = copy.deepcopy(PROFIL_INVENTE)
    profil["pacte"]["regles"] = profil["pacte"]["regles"][3:]
    piece = piece_pacte(charger_pacte(ecrire_profil(tmp_path, profil)), "P7")
    assert piece["valeurs"] == {"date_signature": "2026-03-02", "horizon_ans": [10, None]}
    assert piece["titre"] == "Pacte de Nadia"
    assert piece["valeur_affichee"] == "Signé le 2 mars 2026"
