"""Tests de la composition des FNB et des plafonds par transparence (pipeline/composition.py, #116)."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from contrat.valider import valider_contrat
from pipeline import composition
from pipeline.chiffres import verifier_argument
from pipeline.composition import (
    charger_compositions,
    erreurs_compositions,
    fonds_sans_composition,
    part_dans_le_fonds,
    part_des_categories,
    part_sans_transparence,
    piece_composition,
)
from pipeline.greffier import verifier_pacte
from pipeline.pacte import charger_pacte

RACINE = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((RACINE / "contrat" / "schema_sortie.json").read_text(encoding="utf-8"))
AUDACIEUX = charger_pacte(RACINE / "personas" / "amira.json")
PRUDENT = charger_pacte(RACINE / "personas" / "robert.json")


def regle(id_regle, categories, maximum):
    return {"id": id_regle, "type": "plafond", "categories": categories, "max": maximum, "libelle": id_regle}


@pytest.fixture
def compositions_modifiees(monkeypatch):
    """Remplace le fichier de composition le temps d'un test (le fichier n'est pas modifié)."""
    def remplacer(modifier):
        donnees = copy.deepcopy(charger_compositions())
        modifier(donnees)
        monkeypatch.setattr(composition, "charger_compositions", lambda: donnees)
    return remplacer


# --- Le fichier de composition -------------------------------------------------------------


def test_fichier_coherent_avec_l_univers_et_les_categories():
    assert erreurs_compositions() == []


def test_chaque_fnb_de_l_univers_a_une_composition_relevee():
    assert fonds_sans_composition() == []


def test_chaque_fnb_a_sa_source_et_ses_dates():
    for ticker, fonds in charger_compositions()["fonds"].items():
        assert fonds["url"].startswith("https://"), ticker
        assert fonds["date_consultation"] == "2026-11-15", ticker


def test_repartition_qui_ne_totalise_pas_100_signalee(compositions_modifiees):
    donnees = copy.deepcopy(charger_compositions())
    donnees["fonds"]["SPY"]["secteurs"]["pourcentages"]["Energy"] = 13.58
    donnees["fonds"]["QQQ"]["secteurs"]["classification"] = "NAICS"
    donnees["fonds"]["GME"] = {**donnees["fonds"]["SPY"]}
    assert erreurs_compositions(donnees) == [
        "SPY/secteurs : les pourcentages totalisent 110.00 au lieu de 100",
        "QQQ/secteurs : classification « NAICS » inconnue",
        "GME : absent des FNB de assets_universe.csv",
        "GME/secteurs : les pourcentages totalisent 110.00 au lieu de 100",
    ]


def test_secteur_mal_ecrit_dans_les_categories_signale():
    categories = copy.deepcopy(composition.charger_categories())
    categories["tech"]["transparence"]["par_classification"]["ICB"]["secteurs"] = ["Tech"]
    categories["energie_fossile"]["transparence"]["par_classification"]["GICS"]["secteurs"] = ["energy"]
    assert erreurs_compositions(categories=categories) == [
        "tech/transparence/ICB : secteur « Tech » inconnu",
        "energie_fossile/transparence/GICS : secteur « energy » inconnu",
    ]


# --- Part d'une catégorie dans un FNB ------------------------------------------------------------


def test_qqq_compte_pour_sa_part_reelle_de_tech_pas_100_pour_cent():
    # ICB : Technology 64,4 % (Alphabet compris) + Amazon 4,70 % (Consumer Discretionary en ICB).
    assert part_dans_le_fonds("QQQ", ["tech"]) == pytest.approx(0.644 + 0.047)
    assert part_sans_transparence({"QQQ": 1.0}, ["tech"]) == 1.0  # classement direct : QQQ entier


def test_spy_compte_pour_sa_part_de_tech_avec_alphabet_et_amazon():
    # GICS : Information Technology 36,15 % + Alphabet (classes A et C) 2,68 % + 2,14 % + Amazon 4,01 %.
    assert part_dans_le_fonds("SPY", ["tech"]) == pytest.approx(0.3615 + 0.0268 + 0.0214 + 0.0401)


def test_un_portefeuille_avec_spy_a_une_part_energie_fossile_positive():
    resultat = part_des_categories({"SPY": 0.5, "XBB.TO": 0.5}, ["energie_fossile"])
    assert resultat.part == pytest.approx(0.5 * 0.0358 + 0.5 * 0.0516)  # Energy de SPY et des obligations
    assert resultat.part > 0 and resultat.par_transparence == ["SPY", "XBB.TO"]
    assert part_sans_transparence({"SPY": 0.5, "XBB.TO": 0.5}, ["energie_fossile"]) == 0.0


def test_classification_qui_n_isole_pas_la_categorie_garde_le_classement_direct():
    # AGG range l'énergie dans Industrial : jamais deviné, classement direct (0) et signalé.
    assert part_dans_le_fonds("AGG", ["energie_fossile"]) is None
    resultat = part_des_categories({"AGG": 0.4, "XOM": 0.1, "SPY": 0.5}, ["energie_fossile"])
    assert resultat.part == pytest.approx(0.1 + 0.5 * 0.0358)
    assert resultat.classement_direct == ["AGG"] and resultat.par_transparence == ["SPY"]


def test_fnb_sans_composition_garde_son_classement_et_le_signale(compositions_modifiees):
    compositions_modifiees(lambda d: d["fonds"].pop("QQQ"))
    resultat = part_des_categories({"QQQ": 0.5, "SPY": 0.5}, ["tech"])
    assert resultat.classement_direct == ["QQQ"]
    assert resultat.part == pytest.approx(0.5 * 1.0 + 0.5 * part_dans_le_fonds("SPY", ["tech"]))


def test_or_et_obligations_d_etat_sans_entreprise():
    for ticker in ("GLD", "TLT"):
        assert part_dans_le_fonds(ticker, ["tech"]) == 0
        assert part_dans_le_fonds(ticker, ["energie_fossile"]) == 0


def test_union_sectorielle_et_geographique_non_calculable():
    # Il faudrait la répartition croisée secteur × pays : classement direct.
    assert part_dans_le_fonds("ZST.TO", ["energie_fossile", "canada"]) is None


def test_categorie_sans_transparence_lue_en_classement_direct():
    resultat = part_des_categories({"QQQ": 0.5, "BTC-USD": 0.5}, ["crypto"])
    assert resultat.part == 0.5 and resultat.par_transparence == [] and resultat.classement_direct == []


def test_titre_hors_univers_jamais_devine():
    assert part_des_categories({"XSP.TO": 0.5, "SPY": 0.5}, ["etats_unis"]).hors_univers == ["XSP.TO"]


# --- Plafonds géographiques (#112) par transparence -------------------------------------------------


def test_plafond_etats_unis_par_transparence_pour_un_fnb_mondial(compositions_modifiees):
    """Un FNB d'actions mondiales coté à New York (comme ZEQT ou XSP de l'atelier) n'est pas 100 % américain."""
    mondial = {"date": "2026-11-12", "pourcentages": {"United States": 62.0, "Japan": 6.0, "United Kingdom": 4.0,
                                                       "Canada": 3.0, "Autres pays": 25.0}}
    compositions_modifiees(lambda d: d["fonds"]["ESGV"].update(pays=mondial))
    poids = {"ESGV": 0.5, "XIU.TO": 0.5}
    plafond = regle("plafond_etats_unis", ["etats_unis"], 0.40)
    assert part_sans_transparence(poids, ["etats_unis"]) == 0.5  # classement direct : violation
    [controle] = verifier_pacte([plafond], poids, None, "P1")
    assert controle["statut"] == "conforme"
    assert controle["message"].startswith("États-Unis : 31,0 % du portefeuille après la décision (par transparence : ESGV ;")
    assert part_des_categories(poids, ["hors_canada"]).part == pytest.approx(0.5 * 0.97)


def test_zst_publie_sa_repartition_par_pays():
    assert part_dans_le_fonds("ZST.TO", ["canada"]) == 1.0
    assert part_dans_le_fonds("ZST.TO", ["hors_canada"]) == 0.0


# --- La pièce et le Greffier -------------------------------------------------------------------------


def valider_piece(piece):
    jsonschema.Draft202012Validator({"$ref": "#/$defs/piece", "$defs": SCHEMA["$defs"]}).validate(piece)


PANIER = AUDACIEUX["decision_demo"]


def test_piece_part_de_chaque_categorie_avant_et_apres():
    piece = piece_composition("P7", AUDACIEUX["portefeuille"], PANIER, AUDACIEUX["pacte"]["regles"])
    valider_piece(piece)
    v = piece["valeurs"]
    assert piece["outil"] == "composition_fnb" and piece["etiquette"] == "fictif"
    poids = {ligne["ticker"]: ligne["poids"] for ligne in AUDACIEUX["portefeuille"]}
    assert v["part_tech_crypto_actuelle"] == pytest.approx(part_des_categories(poids, ["tech", "crypto"]).part, abs=1e-6)
    assert v["part_tech_crypto"] == pytest.approx(0.8 + 0.2 * 0.691, abs=1e-6)  # tout réalloué au panier
    assert v["part_tech_crypto_sans_transparence"] == 1.0
    assert v["QQQ_part_tech"] == pytest.approx(0.691) and v["QQQ_classification_secteurs"] == "ICB"
    assert v["QQQ_date_secteurs"] == "2026-10-30" and v["QQQ_date_titres"] == "2026-11-11"
    assert "XBB.TO_part_tech" not in v and v["XBB.TO_part_energie_fossile"] == pytest.approx(0.0516)
    assert v["fonds_lus"] == ["GLD", "QQQ", "SPY", "XBB.TO", "XIU.TO"]
    assert piece["valeur_affichee"].startswith("Cryptoactifs 50,0 % · Technologie et cryptoactifs 93,8 % (au lieu de 100,0 %)")
    assert "invesco.com" in piece["source"] and "2026-10-30" in piece["source"]
    assert not any(c.isdigit() for c in piece["limites"])


def test_pas_de_piece_sans_plafond_lu_par_transparence():
    # Robert : seulement un plafond crypto ; la composition de ses FNB ne changerait aucun contrôle.
    decision = {"type": "position", "ticker": "TSLA", "taille": 0.3, "financement": "proportionnel"}
    assert piece_composition("P5", PRUDENT["portefeuille"], decision, PRUDENT["pacte"]["regles"]) is None


def test_pas_de_piece_sans_fnb():
    portefeuille = [{"ticker": "RY.TO", "poids": 0.5}, {"ticker": "XOM", "poids": 0.5}]
    decision = {"type": "position", "ticker": "TSLA", "taille": 0.1, "financement": "proportionnel"}
    assert piece_composition("P5", portefeuille, decision, [regle("e", ["energie_fossile"], 0.0)]) is None


def test_le_controle_cite_la_piece_de_composition():
    piece = piece_composition("P7", AUDACIEUX["portefeuille"], PANIER, AUDACIEUX["pacte"]["regles"])
    poids = {"QQQ": 0.5, "BTC-USD": 0.5}
    [controle] = verifier_pacte([regle("tc", ["tech", "crypto"], 0.75)], poids, None, "P1", [piece])
    assert controle["pieces"] == ["P7", "P1"]
    # BTC 50 % + QQQ 50 % × 69,1 % = 84,55 % : au-delà du plafond de 75 % (100 % en classement direct).
    assert controle["statut"] == "violation"
    assert controle["message"].startswith("Technologie et cryptoactifs : 84,5 % du portefeuille après la décision "
                                          "(par transparence : QQQ)")


def test_un_argument_qui_cite_la_part_par_transparence_passe_le_greffier():
    piece = piece_composition("P7", AUDACIEUX["portefeuille"], PANIER, AUDACIEUX["pacte"]["regles"])
    dossier = {"decision": PANIER, "pieces": [piece], "periode": ["2021-11-12", "2026-11-12"]}
    texte = ("QQQ ne compte que pour 69,1 % de technologie selon sa fiche du 30 octobre : après la réallocation, "
             "la technologie et la crypto feraient 93,8 % du portefeuille, au lieu de 100,0 % en comptant QQQ en entier.")
    assert verifier_argument({"texte": texte, "pieces": ["P7"]}, dossier).introuvables == []
    faux = "QQQ ne compte que pour 60 % de technologie."
    assert verifier_argument({"texte": faux, "pieces": ["P7"]}, dossier).introuvables


def test_contrat_d_un_proces_avec_composition_valide():
    """Le contrat d'exemple, complété de la pièce et d'un contrôle qui la cite, passe contrat.valider."""
    contrat = json.loads((RACINE / "docs" / "exemples" / "contrat_amira.json").read_text(encoding="utf-8"))
    numero = max(int(p["id"][1:]) for p in contrat["pieces"]) + 1
    piece = piece_composition(f"P{numero}", AUDACIEUX["portefeuille"], PANIER, AUDACIEUX["pacte"]["regles"])
    contrat["pieces"].append(piece)
    contrat["controles"].append({"statut": "violation", "regle": "pas_exclusivement_tech", "message": "…",
                                 "pieces": [piece["id"], contrat["controles"][0]["pieces"][-1]]})
    assert valider_contrat(contrat) == []
