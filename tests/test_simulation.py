import json
from pathlib import Path

import jsonschema
import pytest

from pipeline.donnees import ErreurDonnees
from pipeline.simulation import (
    ErreurSimulation,
    decrire_simuler_portefeuille,
    formater_pourcentage,
    piece_simulation,
    poids_apres_decision,
    simuler_portefeuille,
)

RACINE = Path(__file__).resolve().parent.parent

# Profil de test du cas 1 et faux contrat de la maquette (valeurs attendues).
ROBERT = json.loads((RACINE / "personas" / "robert.json").read_text(encoding="utf-8"))
CONTRAT = json.loads((RACINE / "docs" / "exemples" / "contrat_robert.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((RACINE / "contrat" / "schema_sortie.json").read_text(encoding="utf-8"))

PORTEFEUILLE = ROBERT["portefeuille"]
DECISION = ROBERT["decision_demo"]  # 30 % en TSLA, financement proportionnel
PIECES = {piece["id"]: piece for piece in CONTRAT["pieces"]}


def position(ticker, taille, financement="proportionnel"):
    return {"type": "position", "ticker": ticker, "taille": taille, "financement": financement}


def arrondi(indicateurs):
    return {nom: round(valeur, 4) for nom, valeur in indicateurs.items()}


# --- Chiffres de la maquette ---------------------------------------------------


def test_reproduit_la_comparaison_de_la_maquette():
    resultat = simuler_portefeuille(PORTEFEUILLE, DECISION)
    assert arrondi(resultat["actuel"]) == CONTRAT["comparaison"]["actuel"]
    assert arrondi(resultat["apres"]) == CONTRAT["comparaison"]["apres"]


def test_taille_zero_apres_egal_actuel():
    resultat = simuler_portefeuille(PORTEFEUILLE, position("TSLA", 0.0))
    assert resultat["apres"] == pytest.approx(resultat["actuel"], abs=1e-12)


def test_pire_baisse_autour_de_la_taille_max_de_la_maquette():
    # Pièce P5 : à 9 %, la pire baisse respecte le seuil de −12 % ; à 10 %, non.
    p5 = PIECES["P5"]["valeurs"]
    a_9 = simuler_portefeuille(PORTEFEUILLE, position("TSLA", 0.09))["apres"]["pire_baisse"]
    a_10 = simuler_portefeuille(PORTEFEUILLE, position("TSLA", 0.10))["apres"]["pire_baisse"]
    assert round(a_9, 4) == p5["pire_baisse_a_taille_max"]
    assert round(a_10, 4) == p5["pire_baisse_a_taille_suivante"]


def test_valeurs_brutes_non_arrondies():
    pire_baisse = simuler_portefeuille(PORTEFEUILLE, DECISION)["apres"]["pire_baisse"]
    assert pire_baisse != round(pire_baisse, 4)


# --- Poids après la décision ---------------------------------------------------


def test_financement_proportionnel_reduit_toutes_les_lignes():
    poids = poids_apres_decision(PORTEFEUILLE, DECISION)
    for ligne in PORTEFEUILLE:
        assert poids[ligne["ticker"]] == pytest.approx(ligne["poids"] * 0.7)
    assert poids["TSLA"] == pytest.approx(0.3)
    assert sum(poids.values()) == pytest.approx(1)


def test_financement_depuis_un_titre_ne_reduit_que_cette_ligne():
    poids = poids_apres_decision(PORTEFEUILLE, position("TSLA", 0.1, "depuis_ZST.TO"))
    attendus = {ligne["ticker"]: ligne["poids"] for ligne in PORTEFEUILLE}
    attendus["ZST.TO"] -= 0.1
    attendus["TSLA"] = 0.1
    assert poids == pytest.approx(attendus)


def test_ligne_videe_par_le_financement_disparait():
    poids = poids_apres_decision(PORTEFEUILLE, position("TSLA", 0.1, "depuis_JNJ"))
    assert "JNJ" not in poids
    assert sum(poids.values()) == pytest.approx(1)


def test_titre_deja_en_portefeuille_s_ajoute_a_sa_ligne():
    poids = poids_apres_decision(PORTEFEUILLE, position("RY.TO", 0.1))
    assert poids["RY.TO"] == pytest.approx(0.1 * 0.9 + 0.1)
    assert len(poids) == len(PORTEFEUILLE)


def test_financement_depuis_change_les_chiffres():
    proportionnel = simuler_portefeuille(PORTEFEUILLE, position("TSLA", 0.1))["apres"]
    depuis_obligations = simuler_portefeuille(PORTEFEUILLE, position("TSLA", 0.1, "depuis_XBB.TO"))["apres"]
    assert depuis_obligations != proportionnel


# --- Erreurs claires -----------------------------------------------------------


@pytest.mark.parametrize("taille", [-0.1, 1.2, "30 %", True])
def test_taille_impossible(taille):
    with pytest.raises(ErreurSimulation, match="Taille"):
        poids_apres_decision(PORTEFEUILLE, position("TSLA", taille))


@pytest.mark.parametrize(
    ("financement", "motif"),
    [
        ("depuis_AAPL", "absent du portefeuille"),
        ("depuis_JNJ", "pèse moins"),
        ("vendre_tout", "inconnu"),
    ],
)
def test_financement_impossible(financement, motif):
    with pytest.raises(ErreurSimulation, match=motif):
        poids_apres_decision(PORTEFEUILLE, position("TSLA", 0.2, financement))


def test_financement_depuis_le_titre_achete():
    with pytest.raises(ErreurSimulation, match="titre acheté"):
        poids_apres_decision(PORTEFEUILLE, position("RY.TO", 0.05, "depuis_RY.TO"))


def test_reallocation_pas_encore_prise_en_charge():
    reallocation = {"type": "reallocation", "panier": [{"ticker": "BTC-USD", "poids": 1.0}], "part_reallouee": 0.5}
    with pytest.raises(ErreurSimulation, match="#16"):
        simuler_portefeuille(PORTEFEUILLE, reallocation)


def test_portefeuille_qui_ne_totalise_pas_1():
    with pytest.raises(ErreurSimulation, match="totalisent"):
        simuler_portefeuille([{"ticker": "SPY", "poids": 0.6}], DECISION)


def test_portefeuille_vide():
    with pytest.raises(ErreurSimulation, match="vide"):
        simuler_portefeuille([], DECISION)


def test_titre_hors_univers():
    with pytest.raises(ErreurDonnees, match="absent"):
        simuler_portefeuille(PORTEFEUILLE, position("GME", 0.1))


def test_periode_inconnue():
    with pytest.raises(ErreurSimulation, match="Période"):
        piece_simulation("P1", PORTEFEUILLE, DECISION, periode="2020")


# --- Pièces au format du contrat ----------------------------------------------


def valider_piece(piece):
    validateur = jsonschema.Draft202012Validator({"$ref": "#/$defs/piece", "$defs": SCHEMA["$defs"]})
    validateur.validate(piece)


def comparer_a_la_maquette(piece, attendue):
    assert {cle: valeur for cle, valeur in piece.items() if cle != "valeurs"} == {
        cle: valeur for cle, valeur in attendue.items() if cle != "valeurs"
    }
    valeurs = {nom: round(v, 4) if isinstance(v, float) else v for nom, v in piece["valeurs"].items()}
    assert valeurs == attendue["valeurs"]


def test_piece_periode_complete_reproduit_p1():
    piece = piece_simulation("P1", PORTEFEUILLE, DECISION)
    valider_piece(piece)
    comparer_a_la_maquette(piece, PIECES["P1"])


def test_piece_rejeu_2022_reproduit_p2():
    piece = piece_simulation("P2", PORTEFEUILLE, DECISION, periode="2022")
    valider_piece(piece)
    comparer_a_la_maquette(piece, PIECES["P2"])


@pytest.mark.parametrize(
    ("valeur", "decimales", "texte"),
    [
        (-0.2897, 1, "−29,0 %"),
        (0.1198, 1, "+12,0 %"),
        (-0.0259, 1, "−2,6 %"),
        (0.00001, 1, "0,0 %"),
        (-0.00001, 1, "0,0 %"),
        (0.0929, 0, "+9 %"),
    ],
)
def test_formater_pourcentage(valeur, decimales, texte):
    assert formater_pourcentage(valeur, decimales) == texte


# --- Description pour Bedrock --------------------------------------------------


def test_description_bedrock():
    description = decrire_simuler_portefeuille(["TSLA", "SPY", "ZST.TO"], PORTEFEUILLE)
    spec = description["toolSpec"]
    schema = spec["inputSchema"]["json"]
    assert spec["name"] == "simuler_portefeuille"
    assert spec["strict"] is True
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False
    assert schema["properties"]["ticker"]["enum"] == ["SPY", "TSLA", "ZST.TO"]
    financements = schema["properties"]["financement"]["enum"]
    assert financements[0] == "proportionnel"
    assert sorted(financements[1:]) == sorted(f"depuis_{ligne['ticker']}" for ligne in PORTEFEUILLE)
    assert schema["properties"]["periode"]["enum"] == ["complete", "2022"]


def test_parametres_de_bedrock_acceptes_tels_quels():
    # Ce que le modèle renverrait pour la décision de démonstration, suivi de l'appel Python.
    parametres = {"ticker": "TSLA", "taille": 0.3, "financement": "proportionnel", "periode": "2022"}
    jsonschema.validate(
        parametres,
        decrire_simuler_portefeuille(["TSLA"], PORTEFEUILLE)["toolSpec"]["inputSchema"]["json"],
    )
    decision = {"type": "position", **{k: parametres[k] for k in ("ticker", "taille", "financement")}}
    piece = piece_simulation("P2", PORTEFEUILLE, decision, periode=parametres["periode"])
    assert piece["valeur_affichee"] == PIECES["P2"]["valeur_affichee"]
