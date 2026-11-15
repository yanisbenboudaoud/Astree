"""Tests des points de bascule : « Qu'est-ce qui changerait la réponse ? » (pipeline/points_de_bascule.py, #61)."""

import json
from pathlib import Path

import jsonschema
import pytest

from pipeline.agent_profil import chemin_profil
from pipeline.chiffres import verifier_argument
from pipeline.greffier import verifier_pacte
from pipeline.pacte import charger_pacte
from pipeline.points_de_bascule import piece_points_de_bascule, points_de_bascule, pour_contrat, seuil_suffisant
from pipeline.simulation import piece_simulation, poids_apres_decision, simuler_portefeuille
from pipeline.taille_max import EtapeRecherche, ResultatRecherche, rechercher_taille_max

RACINE = Path(__file__).resolve().parent.parent
SCHEMA_CONTRAT = json.loads((RACINE / "contrat" / "schema_sortie.json").read_text(encoding="utf-8"))
PRUDENT = charger_pacte(chemin_profil("robert"))
AUDACIEUX = charger_pacte(chemin_profil("amira"))
TSLA_30 = {"type": "position", "ticker": "TSLA", "taille": 0.30, "financement": "proportionnel"}


def position(ticker, taille, financement="proportionnel"):
    return {"type": "position", "ticker": ticker, "taille": taille, "financement": financement}


def recherche(profil, decision, regles=None):
    return rechercher_taille_max(profil["portefeuille"], decision, regles or profil["pacte"]["regles"])


def par_regle(profil, decision, regles=None):
    return {point.regle["id"]: point for point in points_de_bascule(recherche(profil, decision, regles))}


def statuts_du_greffier(profil, decision, regles):
    """Ce que le Greffier dirait de la décision, avec ces règles (même calcul que tribunal.controler_pacte)."""
    simulation = {"id": "P2", "valeurs": {"pire_baisse": simuler_portefeuille(profil["portefeuille"], decision)["apres"]["pire_baisse"]}}
    controles = verifier_pacte(regles, poids_apres_decision(profil["portefeuille"], decision), simulation, "P1")
    return {controle["regle"]: controle["statut"] for controle in controles}


# --- Tests de l'issue -----------------------------------------------------------------


def test_profil_prudent_30_pour_cent_tsla():
    """pire_baisse_max serait conforme jusqu'à 9 %, ou avec un seuil de −29,0 %."""
    points = par_regle(PRUDENT, TSLA_30)
    assert list(points) == ["pire_baisse_max"]
    point = points["pire_baisse_max"]
    assert point.taille_max == 0.09
    assert point.seuil_actuel == -0.12
    # Le seuil qui suffit est la pire baisse simulée (celle de la pièce de simulation, au millionième près).
    simulee = piece_simulation("P2", PRUDENT["portefeuille"], TSLA_30)["valeurs"]["pire_baisse"]
    assert point.seuil_suffisant == pytest.approx(simulee, abs=1e-6) and point.seuil_suffisant <= simulee
    assert point.seuil_suffisant == pytest.approx(-0.2897, abs=5e-5)
    [champ] = pour_contrat(recherche(PRUDENT, TSLA_30), TSLA_30, "P6")
    assert champ["message"] == "Conforme jusqu'à 9 % en TSLA, ou avec un seuil de −29,0 % au lieu de −12,0 %"


def test_profil_audacieux_panier_crypto_tech_un_point_par_regle_violee():
    decision = AUDACIEUX["decision_demo"]
    points = par_regle(AUDACIEUX, decision)
    assert list(points) == ["pire_baisse_max", "plafond_crypto", "pas_exclusivement_tech"]
    # Chaque règle a sa propre taille : la plus petite est la taille maximale de toutes les règles (28 %).
    # Technologie et crypto : QQQ compte pour sa part réelle de technologie (#116), d'où 55 % et non 50 %.
    assert {regle: point.taille_max for regle, point in points.items()} == {
        "pire_baisse_max": 0.36, "plafond_crypto": 0.28, "pas_exclusivement_tech": 0.55}
    assert recherche(AUDACIEUX, decision).taille_max == 0.28
    # −0,6185554 simulé : arrondi du côté permissif à −0,618556 (au plus proche, −0,618555 ne suffirait pas).
    assert points["pire_baisse_max"].seuil_suffisant == -0.618556
    # Tout réallouer : 0,5 de crypto dans le panier ; tech et crypto : tout le panier sauf la part
    # non technologique de QQQ (20 % du panier × 69,1 % de tech par transparence, #116).
    assert points["plafond_crypto"].seuil_suffisant == pytest.approx(0.5)
    assert points["pas_exclusivement_tech"].seuil_suffisant == pytest.approx(0.8 + 0.2 * 0.691, abs=1e-6)
    messages = [champ["message"] for champ in pour_contrat(recherche(AUDACIEUX, decision), decision, "P6")]
    assert messages[1] == "Conforme jusqu'à 28 % réalloués, ou avec un plafond de 50,0 % au lieu de 25,0 %"


def test_aucune_regle_violee_ni_piece_ni_erreur():
    resultat = recherche(PRUDENT, position("TSLA", 0.05))
    assert points_de_bascule(resultat) == []
    assert piece_points_de_bascule("P6", resultat, position("TSLA", 0.05)) is None
    assert pour_contrat(resultat, position("TSLA", 0.05), None) == []


# --- Les points de bascule disent vrai -----------------------------------------------------


@pytest.mark.parametrize("profil, decision", [
    (PRUDENT, TSLA_30),
    (PRUDENT, position("BTC-USD", 0.10)),
    (AUDACIEUX, AUDACIEUX["decision_demo"]),
    (AUDACIEUX, position("BTC-USD", 0.30)),
])
def test_memes_regles_que_les_violations_du_greffier(profil, decision):
    regles = profil["pacte"]["regles"]
    statuts = statuts_du_greffier(profil, decision, regles)
    calculables_en_violation = [r["id"] for r in regles
                                if r["type"] in ("pire_baisse_max", "plafond") and statuts[r["id"]] == "violation"]
    assert list(par_regle(profil, decision)) == calculables_en_violation


@pytest.mark.parametrize("profil, decision", [
    (PRUDENT, TSLA_30),
    (PRUDENT, position("BTC-USD", 0.10)),
    (AUDACIEUX, AUDACIEUX["decision_demo"]),
])
def test_le_seuil_suffisant_rend_la_regle_conforme(profil, decision):
    """Ajuster le Pacte : avec le seuil suffisant à la place du sien, le Greffier rend « conforme »."""
    for id_regle, point in par_regle(profil, decision).items():
        cle = "seuil" if point.regle["type"] == "pire_baisse_max" else "max"
        ajustee = {**point.regle, cle: point.seuil_suffisant}
        assert statuts_du_greffier(profil, decision, [ajustee]) == {id_regle: "conforme"}


@pytest.mark.parametrize("profil, decision", [
    (PRUDENT, TSLA_30),
    (AUDACIEUX, AUDACIEUX["decision_demo"]),
])
def test_la_taille_max_est_le_point_de_bascule_de_la_regle(profil, decision):
    """Modifier la décision : la règle est conforme à taille_max et en violation un point plus haut."""
    cle = "part_reallouee" if decision["type"] == "reallocation" else "taille"
    for id_regle, point in par_regle(profil, decision).items():
        a_taille_max = {**decision, cle: point.taille_max}
        un_point_de_plus = {**decision, cle: round(point.taille_max + 0.01, 2)}
        assert statuts_du_greffier(profil, a_taille_max, [point.regle])[id_regle] == "conforme"
        assert statuts_du_greffier(profil, un_point_de_plus, [point.regle])[id_regle] == "violation"


# --- Cas limites ------------------------------------------------------------------------


@pytest.mark.parametrize("type_regle, valeur, attendu", [
    ("pire_baisse_max", -0.6185554, -0.618556),  # au plus proche : -0.618555, qui laisserait la violation
    ("pire_baisse_max", -0.6185546, -0.618555),
    ("pire_baisse_max", -0.25, -0.25),
    ("plafond", 0.2520004, 0.252001),  # au plus proche : 0.252, qui laisserait la violation
    ("plafond", 0.15 * 0.88 + 0.12, 0.252),  # bruit d'arrondi des flottants : rien à décaler
    ("plafond", 1.0, 1.0),
])
def test_seuil_suffisant_arrondi_du_cote_permissif(type_regle, valeur, attendu):
    assert seuil_suffisant(type_regle, valeur) == attendu


def test_exclusion_conforme_seulement_sans_la_decision():
    decision = position("BTC-USD", 0.10)
    points = par_regle(PRUDENT, decision)
    assert points["plafond_crypto"].taille_max == 0.0
    assert points["plafond_crypto"].seuil_suffisant == pytest.approx(0.10)
    messages = {c["regle"]: c["message"] for c in pour_contrat(recherche(PRUDENT, decision), decision, "P6")}
    assert messages["plafond_crypto"] == "Conforme seulement sans la décision, ou avec un plafond de 10,0 % au lieu de l'exclusion"


def test_portefeuille_deja_hors_pacte_aucune_taille():
    """Seuil plus strict que la pire baisse du portefeuille actuel (−7,76 %) : seul le Pacte peut changer."""
    regles = [{"id": "pire_baisse_max", "type": "pire_baisse_max", "seuil": -0.05, "libelle": "…"}]
    [point] = points_de_bascule(recherche(PRUDENT, TSLA_30, regles))
    assert point.taille_max is None
    [champ] = pour_contrat(recherche(PRUDENT, TSLA_30, regles), TSLA_30, "P6")
    assert champ["message"].startswith("Aucune taille ne suffit, le portefeuille actuel enfreint déjà cette règle, "
                                       "ou avec un seuil de −29,0 %")


def test_regle_a_verifier_sans_point_de_bascule():
    """Titre hors univers : la règle n'est pas mesurable, aucun point de bascule n'est inventé."""
    regle = {"id": "plafond_crypto", "type": "plafond", "categories": ["crypto"], "max": 0.0, "libelle": "…"}
    etapes = [EtapeRecherche(t, -0.05, {"plafond_crypto": 0.0}, ["plafond_crypto"], {"plafond_crypto": "a_verifier"})
              for t in (0.0, 0.01)]
    assert points_de_bascule(ResultatRecherche(0.01, None, etapes, [regle])) == []


def test_champ_du_contrat_exige_la_piece():
    with pytest.raises(ValueError, match="pièce"):
        pour_contrat(recherche(PRUDENT, TSLA_30), TSLA_30, None)


# --- La pièce ------------------------------------------------------------------------------


def test_piece_conforme_au_contrat_et_valeurs_alignees():
    decision = AUDACIEUX["decision_demo"]
    piece = piece_points_de_bascule("P6", recherche(AUDACIEUX, decision), decision)
    schema = {"$ref": "#/$defs/piece", "$defs": SCHEMA_CONTRAT["$defs"]}
    jsonschema.validate(piece, schema, cls=jsonschema.Draft202012Validator)
    valeurs = piece["valeurs"]
    assert valeurs["regles_en_violation"] == ["pire_baisse_max", "plafond_crypto", "pas_exclusivement_tech"]
    assert valeurs["seuils_du_pacte"] == [-0.45, 0.25, 0.75]
    assert valeurs["tailles_max_par_regle"] == [0.36, 0.28, 0.55]  # QQQ par transparence (#116)
    assert valeurs["taille_demandee"] == 1.0 and valeurs["taille_max_toutes_regles"] == 0.28
    assert piece["etiquette"] == "fictif" and piece["outil"] == "points_de_bascule"
    assert piece["valeur_affichee"] == (
        "Pire baisse : 36 % max ou seuil −61,9 % · Cryptoactifs : 28 % max ou plafond 50,0 % · "
        "Technologie et cryptoactifs : 55 % max ou plafond 93,8 %")  # QQQ par transparence (#116)


def test_champ_du_contrat_conforme_au_schema():
    decision = AUDACIEUX["decision_demo"]
    schema = {"type": "array", "items": {"$ref": "#/$defs/point_de_bascule"}, "$defs": SCHEMA_CONTRAT["$defs"]}
    champ = pour_contrat(recherche(AUDACIEUX, decision), decision, "P6")
    jsonschema.validate(champ, schema, cls=jsonschema.Draft202012Validator)
    assert [c["type"] for c in champ] == ["pire_baisse_max", "plafond", "plafond"]
    assert all(c["pieces"] == ["P6"] for c in champ)


# --- Le Greffier vérifie les chiffres qui citent la pièce ----------------------------------


def dossier_audacieux():
    decision = AUDACIEUX["decision_demo"]
    piece = piece_points_de_bascule("P6", recherche(AUDACIEUX, decision), decision)
    simulation = piece_simulation("P2", AUDACIEUX["portefeuille"], decision)
    return {"decision": decision, "pieces": [simulation, piece], "periode": ["2021-11-12", "2026-11-12"]}


def argument(texte, *pieces):
    return {"etiquette": "fait", "texte": texte, "pieces": list(pieces)}


def test_verifier_chiffres_accepte_les_chiffres_de_la_piece():
    texte = ("Votre règle de pire baisse serait respectée jusqu'à 36 % réalloués, "
             "ou avec un seuil de −61,9 % au lieu de −45 %.")
    assert verifier_argument(argument(texte, "P6"), dossier_audacieux()).valide


def test_verifier_chiffres_rejette_un_chiffre_absent_ou_une_piece_non_citee():
    dossier = dossier_audacieux()
    faux = verifier_argument(argument("La règle serait respectée jusqu'à 40 % réalloués.", "P6"), dossier)
    assert not faux.valide and "40 %" in faux.motif
    non_citee = verifier_argument(argument("La règle serait respectée jusqu'à 36 % réalloués.", "P2"), dossier)
    assert not non_citee.valide and "P6" in non_citee.motif
