"""Tests de verifier_chiffres (pipeline/chiffres.py) : chaque exemple de CLAUDE.md, section 4 ter."""

import json
from pathlib import Path

import pytest

from pipeline.chiffres import (
    controle_verifier_chiffres,
    extraire_nombres,
    trier_arguments,
    verifier_argument,
)

EXEMPLES = Path(__file__).resolve().parent.parent / "docs" / "exemples"
PERIODE = ["2021-11-12", "2026-11-12"]


def piece(id_piece, **valeurs):
    return {"id": id_piece, "type": "calculee", "valeurs": valeurs}


DOSSIER = {
    "decision": {"type": "position", "ticker": "TSLA", "taille": 0.30, "financement": "proportionnel"},
    "periode": PERIODE,
    "pieces": [
        piece("P1", pire_baisse=-0.2897, pire_baisse_actuelle=-0.0776, rendement_annuel=0.1198),
        piece("P2", periode=["2021-12-31", "2022-12-30"], rendement_2022_actuel=-0.0259),
        piece("P3", date_signature="2026-11-14", pire_baisse_max=-0.12, horizon_ans=[3, 5]),
        piece("P4", date_sommet="2022-01-03", date_retour_sommet="2024-12-10",
              pire_baisse_usd=-0.7297, annees_recuperation=2.935),
    ],
}


def passe(texte, *pieces):
    return verifier_argument({"etiquette": "fait", "texte": texte, "pieces": list(pieces)}, DOSSIER).valide


def textes(texte):
    return [n.texte for n in extraire_nombres(texte)]


# --- Règle 1 : ce qui est extrait --------------------------------------------------

def test_virgule_decimale_et_virgule_de_ponctuation():
    assert textes("en 2022, TSLA a perdu 29,0 %") == ["2022", "29,0 %"]


def test_id_de_piece_et_nombres_colles_non_extraits():
    assert textes("voir P1 et P12, le 2e titre, COVID-19") == []


@pytest.mark.parametrize("nom", ["S&P/TSX 60", "Nasdaq-100", "S&P 500"])
def test_noms_d_actifs_non_extraits(nom):
    assert textes(f"comme le {nom}, la pire chute est de 29 %") == ["29 %"]


def test_signes_lus():
    nombres = extraire_nombres("passe de −7,8 % à +12,0 %")
    assert [(n.signe, str(n.valeur)) for n in nombres] == [("-", "7.8"), ("+", "12.0")]


def test_milliers_separes_par_des_espaces():
    assert [str(n.valeur) for n in extraire_nombres("un capital de 650 000 $")] == ["650000"]


# --- Règle 3 : correspondance par arrondi --------------------------------------------

@pytest.mark.parametrize("texte, attendu", [
    ("La pire chute passe à −29,0 %.", True),
    ("La pire chute passe à −29 %.", True),
    ("La pire chute passe à −28 %.", False),
    ("La pire chute passe à −29,03 %.", False),
])
def test_arrondi_a_la_precision_ecrite(texte, attendu):
    assert passe(texte, "P1") is attendu


def test_pres_de_3_ans_passe_pour_2_935():
    assert passe("TSLA a mis près de 3 ans à revenir à son sommet.", "P4")


def test_mot_d_approximation_ne_donne_aucune_tolerance():
    assert not passe("La pire chute serait d'environ −28 %.", "P1")


# --- Règle 4 : signe -------------------------------------------------------------------

def test_chute_de_sans_signe_passe_en_valeur_absolue():
    assert passe("Une chute de 29 % sur la période.", "P1")
    assert passe("Une chute de 73,0 % pour TSLA.", "P4")


def test_sans_signe_ni_mot_de_baisse_lu_comme_positif():
    verification = verifier_argument(
        {"etiquette": "fait", "texte": "En 2022, le portefeuille ferait 2,6 %.", "pieces": ["P2"]}, DOSSIER
    )
    assert not verification.valide
    assert verification.motif == "« 2,6 % » introuvable dans P2 : valeur négative, écrire le signe « − »"


def test_signe_contraire_rejete():
    assert not passe("La pire chute passe à +29,0 %.", "P1")


# --- Règle 2 : contre quoi -----------------------------------------------------------------

def test_chiffre_d_une_piece_non_citee_rejete():
    verification = verifier_argument(
        {"etiquette": "fait", "texte": "La pire chute passe à −29,0 %.", "pieces": ["P3"]}, DOSSIER
    )
    assert not verification.valide
    assert verification.motif == "« −29,0 % » introuvable dans P3 (présent dans P1, pièce non citée)"


def test_decision_et_periode_toujours_admises():
    assert passe("Avec 30 % en TSLA, du 12 novembre 2021 au 2026-11-12.", "P3")


# --- Règle 5 : dates ---------------------------------------------------------------------

@pytest.mark.parametrize("texte", [
    "Après sa chute de 2022.",
    "Sommet en janv. 2022, retour en déc. 2024.",
    "Le 14 novembre, vous avez signé.",
])
def test_dates_presentes_dans_les_pieces_citees(texte):
    assert passe(texte, "P3", "P4")


def test_date_absente_rejetee():
    assert not passe("Retour au sommet en mars 2025.", "P4")


# --- Règle 6 : aucun nombre dérivé ------------------------------------------------------------

@pytest.mark.parametrize("texte", [
    "La pire chute est 21 points de plus.",
    "Le risque est 4 fois plus élevé.",
])
def test_nombre_derive_rejete(texte):
    assert not passe(texte, "P1")


# --- Règle 7 : plages et listes ------------------------------------------------------------------

def test_plage_verifiee_nombre_par_nombre():
    assert passe("Votre horizon de 3 à 5 ans.", "P3")
    assert not passe("Votre horizon de 3 à 6 ans.", "P3")


# --- Règles 8 et 9 : renvoi, rejet et compte rendu ------------------------------------------------

def argument(texte, *pieces):
    return {"etiquette": "fait", "texte": texte, "pieces": list(pieces)}


def test_argument_corrige_apres_une_relance_accepte():
    appels = []

    def corriger(arg, motif):
        appels.append(motif)
        return argument("La pire chute passe à −29,0 %.", "P1")

    tri = trier_arguments([argument("La pire chute passe à −31 %.", "P1")], "requisitoire", DOSSIER, corriger)
    assert appels == ["« −31 % » introuvable dans P1"]
    assert len(tri.valides) == 1 and tri.rejetes == []


def test_argument_encore_faux_apres_la_relance_rejete():
    appels = []

    def corriger(arg, motif):
        appels.append(motif)
        return argument("La pire chute passe à −30 %.", "P1")

    tri = trier_arguments([argument("La pire chute passe à −31 %.", "P1")], "plaidoirie", DOSSIER, corriger)
    assert len(appels) == 1  # renvoyé une seule fois
    assert tri.valides == []
    assert tri.rejetes == [{
        "cote": "plaidoirie", "etiquette": "fait", "texte": "La pire chute passe à −30 %.",
        "pieces": ["P1"], "raison": "« −30 % » introuvable dans P1",
    }]


def test_sans_correcteur_rejete_directement():
    tri = trier_arguments([argument("Il ferait 2,6 %.", "P2")], "requisitoire", DOSSIER)
    assert tri.relances == 0 and len(tri.rejetes) == 1


def test_compte_rendu_avec_rejet():
    requisitoire = trier_arguments([argument("Pire chute de −29,0 % contre −7,8 %.", "P1")], "requisitoire", DOSSIER)
    plaidoirie = trier_arguments([argument("Il ferait 4 fois mieux.", "P1")], "plaidoirie", DOSSIER,
                                 lambda arg, motif: arg)
    controle = controle_verifier_chiffres(requisitoire, plaidoirie)
    assert controle == {
        "statut": "conforme",
        "regle": "verifier_chiffres",
        "message": "Chiffres cités vérifiés contre leurs pièces : 2/2 chiffres, 1 argument ; "
                   "1 argument rejeté après une relance",
    }


# --- Faux contrats de la maquette ---------------------------------------------------------------

@pytest.mark.parametrize("nom, arguments", [("contrat_robert.json", 7), ("contrat_amira.json", 8)])
def test_faux_contrats_17_sur_17(nom, arguments):
    contrat = json.loads((EXEMPLES / nom).read_text(encoding="utf-8"))
    dossier = {"decision": contrat["decision"], "pieces": contrat["pieces"], "periode": PERIODE}
    tris = [trier_arguments(contrat[cote], cote, dossier) for cote in ("requisitoire", "plaidoirie")]
    assert all(t.rejetes == [] for t in tris)
    message = controle_verifier_chiffres(*tris)["message"]
    assert message == f"Chiffres cités vérifiés contre leurs pièces : 17/17 chiffres, {arguments} arguments"


def test_argument_rejete_du_faux_contrat_amira_reste_rejete():
    contrat = json.loads((EXEMPLES / "contrat_amira.json").read_text(encoding="utf-8"))
    dossier = {"decision": contrat["decision"], "pieces": contrat["pieces"], "periode": PERIODE}
    rejete = contrat["arguments_rejetes"][0]
    verification = verifier_argument(rejete, dossier)
    assert verification.motif == "« 4 » introuvable dans P1"
