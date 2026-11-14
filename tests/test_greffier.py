"""Tests du Greffier (pipeline/greffier.py) : outil 5, verifier_pacte."""

import json
from pathlib import Path

import pytest

from contrat.valider import valider_contrat
from pipeline.greffier import (
    controle_biais_survivant,
    controle_performance_passee,
    verifier_pacte,
)
from pipeline.pacte import charger_pacte, pacte_pour_contrat
from pipeline.simulation import piece_simulation, poids_apres_decision

PERSONAS = Path(__file__).resolve().parent.parent / "personas"
TSLA_30 = {"type": "position", "ticker": "TSLA", "taille": 0.30, "financement": "proportionnel"}


def regle(id_regle, type_regle, **parametres):
    return {"id": id_regle, "type": type_regle, "libelle": id_regle, **parametres}


def piece_pire_baisse(valeur, id_piece="P1"):
    return {"id": id_piece, "type": "calculee", "valeurs": {"pire_baisse": valeur}}


def controle_unique(une_regle, poids=None, piece=None, pieces=()):
    poids = poids if poids is not None else {"SPY": 1.0}
    return verifier_pacte([une_regle], poids, piece, "P3", pieces)[0]


def juger(nom_profil, decision):
    """Procès réel (données du dépôt) : contrôles du Pacte pour une décision."""
    profil = charger_pacte(PERSONAS / f"{nom_profil}.json")
    piece = piece_simulation("P1", profil["portefeuille"], decision)
    poids = poids_apres_decision(profil["portefeuille"], decision)
    controles = verifier_pacte(profil["pacte"]["regles"], poids, piece, "P3")
    return {c["regle"]: c for c in controles}, piece


# --- Même décision, deux profils (tests de l'issue #10) ---------------------------

def test_tsla_30_profil_prudent_viole_la_pire_baisse():
    controles, _ = juger("robert", TSLA_30)
    assert controles["pire_baisse_max"]["statut"] == "violation"
    assert controles["pire_baisse_max"]["message"] == "Pire baisse −29,0 % au-delà du seuil −12,0 %"
    assert controles["pire_baisse_max"]["pieces"] == ["P1", "P3"]
    assert controles["plafond_crypto"]["statut"] == "conforme"
    assert controles["preserver_capital"]["statut"] == "a_verifier"


def test_tsla_30_profil_audacieux_respecte_la_pire_baisse():
    controles, piece = juger("amira", TSLA_30)
    assert -0.45 < piece["valeurs"]["pire_baisse"] < -0.42  # −42,6 % : marge faible
    assert controles["pire_baisse_max"]["statut"] == "conforme"
    assert controles["plafond_crypto"]["statut"] == "conforme"
    assert controles["pas_exclusivement_tech"]["statut"] == "conforme"


def test_profil_esg_regle_documentaire_sans_source_a_verifier():
    profil = charger_pacte(PERSONAS / "mateo.json")
    controles, _ = juger("mateo", profil["decision_demo"])  # 10 % en XOM
    assert controles["controverses_esg"]["statut"] == "a_verifier"
    assert "Source manquante" in controles["controverses_esg"]["message"]
    assert all(c["statut"] != "violation" for c in controles.values())


def test_controles_valides_dans_le_contrat_d_exemple():
    """Les contrôles produits passent le validateur du contrat (renvois compris)."""
    chemin = Path(__file__).resolve().parent.parent / "docs" / "exemples" / "contrat_robert.json"
    contrat = json.loads(chemin.read_text(encoding="utf-8"))
    profil = charger_pacte(PERSONAS / "robert.json")
    piece = next(p for p in contrat["pieces"] if p["id"] == "P1")
    poids = poids_apres_decision(profil["portefeuille"], TSLA_30)
    systeme = [c for c in contrat["controles"] if c["regle"] in {"verifier_chiffres"}]
    contrat["controles"] = (
        verifier_pacte(pacte_pour_contrat(profil)["regles"], poids, piece, "P3")
        + systeme + [controle_biais_survivant()]
    )
    assert valider_contrat(contrat) == []


# --- pire_baisse_max --------------------------------------------------------------

def test_pire_baisse_egale_au_seuil_conforme():
    controle = controle_unique(regle("pb", "pire_baisse_max", seuil=-0.12), piece=piece_pire_baisse(-0.12))
    assert controle["statut"] == "conforme"
    assert controle["message"] == "Pire baisse −12,0 % dans la limite du seuil −12,0 %"


def test_pire_baisse_sans_piece_de_simulation_a_verifier():
    controle = controle_unique(regle("pb", "pire_baisse_max", seuil=-0.12), piece=None)
    assert controle["statut"] == "a_verifier"
    assert controle["pieces"] == ["P3"]


# --- plafond ----------------------------------------------------------------------

def test_plafond_depasse_violation():
    controle = controle_unique(
        regle("crypto", "plafond", categories=["crypto"], max=0.25),
        poids={"BTC-USD": 0.3, "ETH-USD": 0.2, "SPY": 0.5},
    )
    assert controle["statut"] == "violation"
    assert controle["message"] == "Cryptoactifs : 50,0 % du portefeuille après la décision, au-delà du plafond de 25,0 %"


def test_plafond_sur_plusieurs_categories_additionne_les_parts():
    controle = controle_unique(
        regle("tc", "plafond", categories=["tech", "crypto"], max=0.75),
        poids={"BTC-USD": 0.3, "NVDA": 0.3, "QQQ": 0.2, "SPY": 0.2},
    )
    assert controle["statut"] == "violation"
    assert controle["message"].startswith("Technologie et cryptoactifs : 80,0 %")


def test_exclusion_respectee():
    controle = controle_unique(regle("crypto", "plafond", categories=["crypto"], max=0.0))
    assert controle["statut"] == "conforme"
    assert controle["message"].endswith("exclusion respectée")


def test_exclusion_violee():
    controle = controle_unique(
        regle("crypto", "plafond", categories=["crypto"], max=0.0),
        poids={"BTC-USD": 0.05, "SPY": 0.95},
    )
    assert controle["statut"] == "violation"
    assert controle["message"].endswith("alors que cette catégorie est exclue")


def test_plafond_atteint_exactement_conforme():
    controle = controle_unique(
        regle("crypto", "plafond", categories=["crypto"], max=0.25),
        poids={"BTC-USD": 0.15, "ETH-USD": 0.1, "SPY": 0.75},
    )
    assert controle["statut"] == "conforme"


def test_titre_hors_univers_a_verifier_jamais_devine():
    controle = controle_unique(
        regle("crypto", "plafond", categories=["crypto"], max=0.0),
        poids={"DOGE-USD": 0.1, "SPY": 0.9},
    )
    assert controle["statut"] == "a_verifier"
    assert "DOGE-USD" in controle["message"]


# --- critere_documentaire et qualitative ---------------------------------------------

def test_critere_documentaire_selon_la_piece():
    une_regle = regle("esg", "critere_documentaire", critere="controverse_esg_importante")
    piece = {"id": "P6", "type": "documentaire", "valeurs": {"controverse_esg_importante": True}}
    controle = controle_unique(une_regle, pieces=[piece])
    assert controle["statut"] == "violation"
    assert controle["pieces"] == ["P6", "P3"]

    piece["valeurs"]["controverse_esg_importante"] = False
    assert controle_unique(une_regle, pieces=[piece])["statut"] == "conforme"


def test_piece_calculee_ignoree_pour_un_critere_documentaire():
    une_regle = regle("esg", "critere_documentaire", critere="controverse_esg_importante")
    piece = {"id": "P6", "type": "calculee", "valeurs": {"controverse_esg_importante": True}}
    assert controle_unique(une_regle, pieces=[piece])["statut"] == "a_verifier"


def test_qualitative_toujours_a_verifier():
    controle = controle_unique(regle("capital", "qualitative"))
    assert controle == {
        "statut": "a_verifier",
        "regle": "capital",
        "message": "Règle déclarée, non mesurable par calcul : à juger par l'utilisateur",
        "pieces": ["P3"],
    }


def test_type_de_regle_sans_controle_refuse():
    with pytest.raises(ValueError, match="volatilite_max"):
        controle_unique(regle("v", "volatilite_max"))


# --- Contrôles du système -------------------------------------------------------------

def test_biais_survivant_toujours_a_verifier():
    assert controle_biais_survivant()["statut"] == "a_verifier"


def test_performance_passee_detectee():
    arguments = [{"texte": "Le rendement annualisé aurait été de +12,0 %.", "pieces": ["P1"]}]
    assert controle_performance_passee(arguments)["regle"] == "performance_passee"


def test_performance_passee_absente():
    arguments = [{"texte": "La pire chute passe de −7,8 % à −29,0 %.", "pieces": ["P1"]}]
    assert controle_performance_passee(arguments) is None
