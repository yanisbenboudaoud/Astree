"""Tests des routes /questionnaire et /profil de la Lambda (#87).

Ni AWS ni Bedrock : les profils sont rangés dans un dossier temporaire
(``SOURCE_DONNEES=local``), comme en développement.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from deploiement import lambda_tribunal
from pipeline import profils
from pipeline.agent_profil import charger_profil

RACINE = Path(__file__).resolve().parents[1]
SAISIE = json.loads((RACINE / "docs" / "exemples" / "reponses_questionnaire.json").read_text(encoding="utf-8"))
CORPS = {"reponses": SAISIE["reponses"], "capital": SAISIE["capital_cad"],
         "portefeuille": SAISIE["portefeuille"], "nom": "Investisseur exemple"}


@pytest.fixture(autouse=True)
def local(monkeypatch, tmp_path):
    monkeypatch.setenv("SOURCE_DONNEES", "local")
    monkeypatch.setattr(profils, "DOSSIER_PROFILS_LOCAL", tmp_path / "profils")
    monkeypatch.setattr(lambda_tribunal, "_appels_profil", {})
    return tmp_path / "profils"


def appeler(chemin, corps, ip="203.0.113.7"):
    resultat = lambda_tribunal.handler({
        "rawPath": chemin, "body": json.dumps(corps), "isBase64Encoded": False,
        "requestContext": {"http": {"method": "POST", "sourceIp": ip}},
    })
    return resultat["statusCode"], json.loads(resultat["body"])


# --- /questionnaire ---------------------------------------------------------------------


def test_questionnaire_renvoie_les_questions_avec_les_vrais_chiffres_des_cartes():
    statut, corps = appeler("/questionnaire", {})
    assert statut == 200
    par_id = {q["id"]: q for q in corps["questions"]}
    assert {"horizon", "coussin", "fourchettes", "crypto"} <= set(par_id)
    for carte in par_id["fourchettes"]["cartes"]:
        assert carte["pire_baisse"] < 0 and carte["valeur_finale"] > 0


# --- /profil -------------------------------------------------------------------------------


def test_profil_cree_range_et_relu_par_le_tribunal(local):
    statut, corps = appeler("/profil", CORPS)
    assert statut == 201
    identifiant = corps["id"]
    assert identifiant.startswith("investisseur_") and identifiant != SAISIE["id"]
    assert corps["archive"] == f"profils/{identifiant}.json"
    assert (local / f"{identifiant}.json").is_file()
    assert corps["profil"]["nom"] == "Investisseur exemple"
    assert corps["profil"]["etiquette"] == "fictif"
    assert corps["bareme"]["regles"] and isinstance(corps["contradictions"], list)
    assert charger_profil(identifiant) == corps["profil"]  # ce que /tribunal chargera


def test_deux_profils_identiques_ont_deux_identifiants(local):
    premier = appeler("/profil", CORPS)[1]["id"]
    second = appeler("/profil", CORPS)[1]["id"]
    assert premier != second and len(list(local.iterdir())) == 2


def test_profil_avec_seuil_choisi_par_l_utilisateur():
    statut, corps = appeler("/profil", {**CORPS, "modifications": {"pire_baisse_max": -0.15}})
    assert statut == 201
    regle = next(r for r in corps["profil"]["pacte"]["regles"] if r["id"] == "pire_baisse_max")
    assert regle["seuil"] == -0.15 and "Choisi par vous" in regle["justification"]


def test_reponse_inconnue_400_avec_le_motif_et_rien_n_est_range(local):
    statut, corps = appeler("/profil", {**CORPS, "reponses": {**CORPS["reponses"], "horizon": "demain"}})
    assert statut == 400
    assert corps["erreur"] == "Réponses refusées" and any("horizon" in d for d in corps["details"])
    assert not local.exists()


def test_titre_hors_univers_400():
    portefeuille = [{"ticker": "INCONNU", "poids": 1.0}]
    statut, corps = appeler("/profil", {**CORPS, "portefeuille": portefeuille})
    assert statut == 400 and any("INCONNU" in d for d in corps["details"])


def test_modification_refusee_400(local):
    statut, corps = appeler("/profil", {**CORPS, "modifications": {"pire_baisse_max": 0.3}})
    assert statut == 400 and any("entre −1 et 0" in d for d in corps["details"])
    assert not local.exists()


@pytest.mark.parametrize("champs, motif", [
    ({"reponses": {}}, "reponses"),
    ({"reponses": None}, "reponses"),
    ({"portefeuille": [{"ticker": "SPY", "poids": 0.01}] * 32}, "portefeuille"),
    ({"nom": "x" * 41}, "nom"),
    ({"nom": "   "}, "nom"),
    ({"modifications": ["pire_baisse_max"]}, "modifications"),
    ({"reponses": {**CORPS["reponses"], "regle_perso": "x" * 30_000}}, "trop long"),
])
def test_corps_invalide_400(champs, motif, local):
    statut, corps = appeler("/profil", {**CORPS, **champs})
    assert statut == 400 and motif in corps["erreur"]
    assert not local.exists()


def test_le_nom_saisi_ne_choisit_jamais_le_fichier(local):
    statut, corps = appeler("/profil", {**CORPS, "nom": "robert"})
    assert statut == 201 and corps["id"] != "robert"
    assert charger_profil("robert")["nom"] == "Robert"  # le profil de démonstration est intact


def test_debit_limite_par_adresse_ip():
    for _ in range(lambda_tribunal.DEBIT_MAX_PROFIL):
        assert appeler("/profil", CORPS)[0] == 201
    statut, corps = appeler("/profil", CORPS)
    assert statut == 429 and "Trop de profils" in corps["erreur"]
    assert appeler("/profil", CORPS, ip="198.51.100.1")[0] == 201  # une autre adresse passe


def test_s3_indisponible_500(monkeypatch):
    monkeypatch.setenv("SOURCE_DONNEES", "s3")
    monkeypatch.delenv("BUCKET_PROJET", raising=False)
    statut, corps = appeler("/profil", CORPS)
    assert statut == 500 and corps["erreur"] == "Archive S3 indisponible"
