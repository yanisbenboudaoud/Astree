import json
from pathlib import Path

import jsonschema
import pytest

from pipeline import macro
from pipeline.donnees import ErreurDonnees
from pipeline.simulation import (
    LIMITES_DEVISES,
    LIMITES_MACRO,
    TRAITEMENT_DEVISES,
    ErreurSimulation,
    decrire_simuler_portefeuille,
    exposition_devises,
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


# --- Réallocations vers un panier (#16) ------------------------------------------

AMIRA = json.loads((RACINE / "personas" / "amira.json").read_text(encoding="utf-8"))
CONTRAT_AMIRA = json.loads((RACINE / "docs" / "exemples" / "contrat_amira.json").read_text(encoding="utf-8"))
PIECES_AMIRA = {piece["id"]: piece for piece in CONTRAT_AMIRA["pieces"]}


def reallocation(part, panier):
    return {"type": "reallocation", "panier": panier, "part_reallouee": part}


def test_reallocation_totale_donne_le_panier():
    poids = poids_apres_decision(AMIRA["portefeuille"], AMIRA["decision_demo"])
    assert poids == pytest.approx({ligne["ticker"]: ligne["poids"] for ligne in AMIRA["decision_demo"]["panier"]})


def test_reallocation_partielle_au_prorata():
    poids = poids_apres_decision(PORTEFEUILLE, reallocation(0.2, [{"ticker": "BTC-USD", "poids": 0.5},
                                                                  {"ticker": "ZST.TO", "poids": 0.5}]))
    assert poids["BTC-USD"] == pytest.approx(0.1)
    assert poids["ZST.TO"] == pytest.approx(0.3 * 0.8 + 0.1)  # ligne déjà détenue : renforcée
    assert poids["XBB.TO"] == pytest.approx(0.2 * 0.8)
    assert sum(poids.values()) == pytest.approx(1.0)


def test_reallocation_de_demo_memes_valeurs_que_la_maquette():
    """Pièces P1 et P2 de contrat_amira.json : même méthode, mêmes valeurs."""
    resultat = simuler_portefeuille(AMIRA["portefeuille"], AMIRA["decision_demo"])
    p1, p2 = PIECES_AMIRA["P1"]["valeurs"], PIECES_AMIRA["P2"]["valeurs"]
    assert resultat["apres"]["pire_baisse"] == pytest.approx(p1["pire_baisse"], abs=1e-6)
    assert resultat["apres"]["rendement_annuel"] == pytest.approx(p1["rendement_annuel"], abs=1e-6)
    assert resultat["apres"]["volatilite_annuelle"] == pytest.approx(p1["volatilite_annuelle"], abs=1e-6)
    assert resultat["actuel"]["pire_baisse"] == pytest.approx(p1["pire_baisse_actuelle"], abs=1e-6)
    assert resultat["apres"]["rendement_2022"] == pytest.approx(p2["rendement_2022_apres"], abs=1e-6)


@pytest.mark.parametrize("decision, message", [
    (reallocation(0.5, []), "Panier vide"),
    (reallocation(0.5, [{"ticker": "NVDA", "poids": 0.5}, {"ticker": "NVDA", "poids": 0.5}]), "deux fois"),
    (reallocation(0.5, [{"ticker": "NVDA", "poids": 0.6}, {"ticker": "QQQ", "poids": 0.3}]), "totalisent"),
    (reallocation(0.5, [{"ticker": "NVDA", "poids": 0.0}, {"ticker": "QQQ", "poids": 1.0}]), "poids positif"),
    (reallocation(1.5, [{"ticker": "NVDA", "poids": 1.0}]), "Part réallouée"),
    ({"type": "autre"}, "inconnu"),
])
def test_reallocation_invalide_erreur_lisible(decision, message):
    with pytest.raises(ErreurSimulation, match=message):
        poids_apres_decision(PORTEFEUILLE, decision)


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


def comparer_a_la_maquette(piece, attendue, titre):
    """Mêmes champs et mêmes chiffres que la maquette ; le titre et la taille simulée en plus (#55)."""
    assert piece["titre"] == titre
    assert {cle: valeur for cle, valeur in piece.items() if cle not in ("valeurs", "titre")} == {
        cle: valeur for cle, valeur in attendue.items() if cle not in ("valeurs", "titre")
    }
    valeurs = {nom: round(v, 4) if isinstance(v, float) else v for nom, v in piece["valeurs"].items()}
    assert valeurs.pop("taille") == DECISION["taille"]
    assert valeurs == attendue["valeurs"]


@pytest.fixture
def sans_macro(monkeypatch):
    """Données macro indisponibles (fichier absent du bucket, par exemple)."""
    def absent():
        raise ErreurDonnees("macro_rates.csv absent")
    monkeypatch.setattr(macro, "_series", absent)


def sans_exposition_devises(piece):
    """La pièce sans l'exposition en devise, ajoutée après la maquette (#112)."""
    valeurs = {cle: v for cle, v in piece["valeurs"].items() if not cle.startswith(("part_cad", "part_usd"))}
    return {
        **piece,
        "valeurs": valeurs,
        "traitement": piece["traitement"].removesuffix(f" ; {TRAITEMENT_DEVISES}"),
        "limites": piece["limites"].removesuffix(f" ; {LIMITES_DEVISES}"),
    }


def test_piece_periode_complete_reproduit_p1(sans_macro):
    # Sans données macro, la pièce est exactement celle de la maquette, plus l'exposition en
    # devise : la pièce obligatoire du procès ne dépend pas de macro_rates.csv (#111).
    piece = piece_simulation("P1", PORTEFEUILLE, DECISION)
    valider_piece(piece)
    comparer_a_la_maquette(sans_exposition_devises(piece), PIECES["P1"], "Simulation du portefeuille avec 30 % en TSLA")


def test_piece_rejeu_2022_reproduit_p2(sans_macro):
    piece = piece_simulation("P2", PORTEFEUILLE, DECISION, periode="2022")
    valider_piece(piece)
    comparer_a_la_maquette(piece, PIECES["P2"], "Rejeu de 2022 avec 30 % en TSLA")


@pytest.mark.parametrize(("decision", "titre", "valeur"), [
    ({"type": "position", "ticker": "TSLA", "taille": 0.15, "financement": "proportionnel"},
     "Simulation du portefeuille avec 15 % en TSLA", {"taille": 0.15}),
    ({"type": "position", "ticker": "TSLA", "taille": 0.075, "financement": "depuis_ZST.TO"},
     "Simulation du portefeuille avec 7,5 % en TSLA, financé par ZST.TO", {"taille": 0.075}),
])
def test_la_piece_dit_quelle_taille_a_ete_simulee(decision, titre, valeur):
    # Contre-interrogatoire (#55) : plusieurs simulations au dossier, chacune doit dire sa taille.
    piece = piece_simulation("P6", PORTEFEUILLE, decision)
    assert piece["titre"] == titre
    assert {cle: piece["valeurs"][cle] for cle in valeur} == valeur


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


# --- Comparaisons concrètes calculées en Python (dollars, écarts, rapports) -----------


def test_comparaisons_en_dollars_de_la_periode_complete():
    piece = piece_simulation("P1", PORTEFEUILLE, DECISION, capital=650000)
    valider_piece(piece)
    v = piece["valeurs"]
    assert v["capital"] == 650000
    assert v["perte_au_pire_moment_cad"] == pytest.approx(650000 * abs(v["pire_baisse"]), abs=0.5)
    assert v["perte_au_pire_moment_cad_actuelle"] == pytest.approx(650000 * abs(v["pire_baisse_actuelle"]), abs=0.5)
    assert v["ecart_perte_au_pire_moment_cad"] == pytest.approx(
        v["perte_au_pire_moment_cad"] - v["perte_au_pire_moment_cad_actuelle"], abs=1)
    assert v["ecart_pire_baisse_points"] == pytest.approx(abs(v["pire_baisse"] - v["pire_baisse_actuelle"]) * 100, abs=1e-3)
    assert v["rapport_volatilite"] == pytest.approx(v["volatilite_annuelle"] / v["volatilite_annuelle_actuelle"], abs=1e-3)


def test_comparaisons_du_rejeu_2022():
    v = piece_simulation("P2", PORTEFEUILLE, DECISION, periode="2022", capital=650000)["valeurs"]
    assert v["resultat_2022_cad_apres"] == pytest.approx(650000 * v["rendement_2022_apres"], abs=0.5)
    assert v["resultat_2022_cad_apres"] < 0  # 2022 : une perte garde son signe
    assert v["ecart_2022_cad"] == pytest.approx(abs(v["resultat_2022_cad_apres"] - v["resultat_2022_cad_actuel"]), abs=1)


def test_montants_arrondis_au_dollar():
    v = piece_simulation("P1", PORTEFEUILLE, DECISION, capital=650000)["valeurs"]
    assert all(isinstance(v[cle], int) for cle in ("capital", "perte_au_pire_moment_cad", "ecart_perte_au_pire_moment_cad"))


def test_sans_capital_la_piece_ne_change_pas():
    assert "capital" not in piece_simulation("P1", PORTEFEUILLE, DECISION)["valeurs"]


def _montant(valeur):
    """650000 → « 650 000 » (espace de milliers, comme l'écrit un agent)."""
    return f"{round(valeur):,}".replace(",", " ")


def test_une_comparaison_en_dollars_passe_le_greffier():
    from pipeline.chiffres import verifier_argument

    piece = piece_simulation("P1", PORTEFEUILLE, DECISION, capital=650000)
    v = piece["valeurs"]
    dossier = {"decision": DECISION, "pieces": [piece], "periode": ["2021-11-12", "2026-11-12"]}
    texte = (
        f"Au pire moment, votre portefeuille de {_montant(v['capital'])} $ aurait perdu "
        f"{_montant(v['perte_au_pire_moment_cad'])} $, contre {_montant(v['perte_au_pire_moment_cad_actuelle'])} $ "
        f"sans cette position. Les variations seraient {str(round(v['rapport_volatilite'], 1)).replace('.', ',')} fois plus fortes."
    )
    assert verifier_argument({"texte": texte, "pieces": ["P1"]}, dossier).introuvables == []
    # Un montant inventé reste rejeté.
    faux = f"Au pire moment, votre portefeuille aurait perdu {_montant(v['perte_au_pire_moment_cad'] + 5000)} $."
    assert verifier_argument({"texte": faux, "pieces": ["P1"]}, dossier).introuvables


# --- Exposition en devise : risque de change d'un investisseur en CAD (#112) -------------


def test_exposition_en_devise_avant_et_apres_la_decision():
    # Robert : seul JNJ (10 %) est coté en USD ; 30 % en TSLA, financés au prorata, portent la part à 37 %.
    piece = piece_simulation("P1", PORTEFEUILLE, DECISION)
    v = piece["valeurs"]
    assert (v["part_usd_actuelle"], v["part_cad_actuelle"]) == pytest.approx((0.10, 0.90))
    assert (v["part_usd"], v["part_cad"]) == pytest.approx((0.10 * 0.70 + 0.30, 0.90 * 0.70))
    assert v["part_usd"] + v["part_cad"] == pytest.approx(1)
    assert TRAITEMENT_DEVISES in piece["traitement"] and LIMITES_DEVISES in piece["limites"]


def test_exposition_en_devise_selon_le_financement():
    # 7,5 % de TSLA financés par ZST.TO (CAD) : la part en USD monte de 7,5 points exactement.
    v = piece_simulation("P1", PORTEFEUILLE, position("TSLA", 0.075, "depuis_ZST.TO"))["valeurs"]
    assert v["part_usd"] == pytest.approx(0.175)


def test_exposition_en_devise_d_une_reallocation():
    decision = {"type": "reallocation", "part_reallouee": 0.5,
                "panier": [{"ticker": "BTC-USD", "poids": 0.5}, {"ticker": "XIU.TO", "poids": 0.5}]}
    v = piece_simulation("P1", PORTEFEUILLE, decision)["valeurs"]
    assert v["part_usd"] == pytest.approx(0.10 * 0.5 + 0.25)


def test_toutes_les_devises_de_l_univers_sont_dans_la_piece():
    """Même à 0, pour que la pièce ait toujours les mêmes clés : aucune part à déduire."""
    assert exposition_devises({"XIU.TO": 1.0}) == {"CAD": 1.0, "USD": 0.0}


def test_exposition_d_un_titre_hors_univers_jamais_devinee():
    with pytest.raises(ErreurDonnees, match="« GME » est absent de assets_universe.csv"):
        exposition_devises({"GME": 1.0})


def test_l_exposition_en_usd_passe_le_greffier():
    from pipeline.chiffres import verifier_argument

    piece = piece_simulation("P1", PORTEFEUILLE, DECISION)
    dossier = {"decision": DECISION, "pieces": [piece], "periode": ["2021-11-12", "2026-11-12"]}
    # Une part s'écrit sans signe : le Greffier la lit comme positive (CLAUDE.md, section 4 ter, règle 4).
    texte = ("Avec cette décision, la part de votre portefeuille cotée en dollars américains passerait de "
             "10 % à 37 % : sa valeur en CAD dépendrait davantage du taux de change.")
    assert verifier_argument({"texte": texte, "pieces": ["P1"]}, dossier).introuvables == []
    # Une part inventée, ou dérivée (27 points de plus), reste rejetée.
    for faux in ("La part en dollars américains atteindrait +45 %.", "La part en USD augmenterait de 27 points."):
        assert verifier_argument({"texte": faux, "pieces": ["P1"]}, dossier).introuvables


# --- Données macro : inflation, rendement réel, taux, ratio de Sharpe (#111) -------------


def test_macro_de_la_periode_complete():
    piece = piece_simulation("P1", PORTEFEUILLE, DECISION)
    valider_piece(piece)
    v = piece["valeurs"]
    # IPC du Canada de septembre 2021 à septembre 2026 (dernier mois publié), cinq années entières.
    assert v["inflation_annuelle"] == pytest.approx(0.0354, abs=1e-4)
    assert v["rendement_reel_annuel"] == pytest.approx((1 + v["rendement_annuel"]) / (1 + v["inflation_annuelle"]) - 1, abs=1e-6)
    assert v["rendement_reel_annuel_actuel"] == pytest.approx(
        (1 + v["rendement_annuel_actuel"]) / (1 + v["inflation_annuelle"]) - 1, abs=1e-6)
    # Le ratio de Sharpe se refait avec les valeurs de la pièce.
    assert v["ratio_sharpe"] == pytest.approx((v["rendement_annuel"] - v["taux_sans_risque_moyen"]) / v["volatilite_annuelle"], abs=1e-5)
    assert round(v["ratio_sharpe"], 2) == 0.46
    assert round(v["ratio_sharpe_actuel"], 2) == 1.09
    assert "Banque du Canada, API Valet" in piece["source"]
    assert "2021-09 à 2026-09" in piece["traitement"]
    assert piece["limites"].endswith(LIMITES_MACRO)


def test_macro_du_rejeu_2022():
    piece = piece_simulation("P2", PORTEFEUILLE, DECISION, periode="2022")
    valider_piece(piece)
    v = piece["valeurs"]
    assert v["inflation_2022"] == pytest.approx(0.063)  # IPC de décembre 2022, sur 12 mois
    assert round(v["rendement_reel_2022_actuel"], 3) == -0.084
    assert round(v["rendement_reel_2022_apres"], 3) == -0.282
    assert (v["taux_directeur_debut_2022"], v["taux_directeur_fin_2022"]) == (0.0025, 0.0425)
    assert (v["obligation_10_ans_debut_2022"], v["obligation_10_ans_fin_2022"]) == (0.0142, 0.033)
    assert v["taux_directeur_debut_2022"] < v["taux_directeur_moyen_2022"] < v["taux_directeur_fin_2022"]
    assert "IPC du Canada de 2021-12 à 2022-12" in piece["traitement"]


def test_sans_donnees_macro_la_piece_reste_valide(sans_macro, capsys):
    piece = piece_simulation("P2", PORTEFEUILLE, DECISION, periode="2022")
    valider_piece(piece)
    assert "inflation_2022" not in piece["valeurs"]
    assert "Banque du Canada, API Valet" not in piece["source"]
    assert "Données macro non ajoutées à P2" in capsys.readouterr().out


def test_un_rendement_reel_cite_passe_le_greffier():
    from pipeline.chiffres import verifier_argument

    piece = piece_simulation("P2", PORTEFEUILLE, DECISION, periode="2022")
    v = piece["valeurs"]
    dossier = {"decision": DECISION, "pieces": [piece], "periode": ["2021-11-12", "2026-11-12"]}
    texte = (
        f"En 2022, avec une inflation de {formater_pourcentage(v['inflation_2022'])}, votre portefeuille a fait "
        f"{formater_pourcentage(v['rendement_reel_2022_actuel'])} après inflation, et "
        f"{formater_pourcentage(v['rendement_reel_2022_apres'])} avec 30 % en TSLA. Le taux directeur est "
        "passé de +0,25 % à +4,25 %."
    )
    assert verifier_argument({"texte": texte, "pieces": ["P2"]}, dossier).introuvables == []
    # Le rendement réel calculé par l'agent par simple soustraction (−2,6 − 6,3) est rejeté.
    faux = "En 2022, votre portefeuille a fait −8,9 % après inflation."
    assert verifier_argument({"texte": faux, "pieces": ["P2"]}, dossier).introuvables


def test_rendement_reel_de_la_periode_cite_passe_le_greffier():
    """#113 : le rendement réel avant / après de la pièce principale, tel qu'un agent l'écrirait."""
    from pipeline.chiffres import verifier_argument

    piece = piece_simulation("P1", PORTEFEUILLE, DECISION)
    assert "supposé publié à la fin du mois suivant" in piece["traitement"]
    dossier = {"decision": DECISION, "pieces": [piece], "periode": ["2021-11-12", "2026-11-12"]}
    texte = ("Après inflation, votre portefeuille aurait rapporté +5,5 % par an, et +8,1 % avec 30 % en TSLA. "
             "La hausse des prix a été de +3,5 % par an.")
    assert verifier_argument({"texte": texte, "pieces": ["P1"]}, dossier).introuvables == []
    # Rendement en dollars moins l'inflation (+12,0 − 3,5) : nombre dérivé, rejeté.
    faux = "Avec 30 % en TSLA, votre portefeuille aurait rapporté +8,5 % par an après inflation."
    assert verifier_argument({"texte": faux, "pieces": ["P1"]}, dossier).introuvables
