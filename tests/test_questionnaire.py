"""Tests du questionnaire investisseur (#84) : réponses → fichier profil valide, sans LLM."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.categories import categories_du_titre
from pipeline.greffier import verifier_pacte
from pipeline.indicateurs import indicateurs_actif
from pipeline.pacte import erreurs_profil
from pipeline.questionnaire import (
    ReponsesInvalides,
    controle_experience,
    detail_bareme,
    main,
    profil_depuis_reponses,
    questions,
)
from pipeline.simulation import poids_apres_decision, simuler_portefeuille

RACINE = Path(__file__).resolve().parents[1]
DATE = "2026-11-15"


def persona(nom):
    return json.loads((RACINE / "personas" / f"{nom}.json").read_text(encoding="utf-8"))


# Réponses préenregistrées « comme » les trois profils de test (les noms n'apparaissent que dans les tests).
COMME = {
    "robert": {
        "horizon": "3_5", "objectif": "retraite", "retraits": "peu", "coussin": "plus_12",
        "part_patrimoine": "moitie_trois_quarts", "revenu": "assez_stable",
        "reaction": "rien", "vecu_2022": "rien", "regard_proches": "prudent", "experience": ["depots", "fonds", "actions"],
        "quiz_baisse": "100", "crypto": "aucune", "concentration": "sans_limite", "exclusions": ["aucune"],
        "regle_perso": "Entreprises établies, modèle compris",
    },
    "amira": {
        "horizon": "plus_15", "objectif": "croissance", "retraits": "non", "coussin": "6_12",
        "part_patrimoine": "quart_moitie", "revenu": "tres_stable",
        "reaction": "rachete", "vecu_2022": "rachete", "regard_proches": "risques_reflechis",
        "experience": ["fonds", "actions", "crypto"], "quiz_baisse": "100", "crypto": "25",
        "concentration": "trois_quarts", "exclusions": ["aucune"],
    },
    "mateo": {
        "horizon": "5_10", "objectif": "croissance", "retraits": "non", "coussin": "6_12",
        "part_patrimoine": "quart_moitie", "revenu": "tres_stable",
        "reaction": "rien", "vecu_2022": "rien", "regard_proches": "prudent", "experience": ["fonds"],
        "quiz_baisse": "100", "crypto": "aucune", "concentration": "sans_limite",
        "exclusions": ["controverses_esg"], "regle_perso": "Équilibre entre croissance et stabilité",
    },
}


def profil_comme(nom, **modifs):
    reponses = {**COMME[nom], **modifs}
    reponses = {k: v for k, v in reponses.items() if v is not None}
    modele = persona(nom)
    return profil_depuis_reponses(reponses, modele["capital_fictif_cad"], modele["portefeuille"], DATE,
                                  identifiant=f"comme_{nom}", nom=f"Comme {modele['nom']}")


def regle(profil, id_regle):
    return next((r for r in profil["pacte"]["regles"] if r["id"] == id_regle), None)


# --- Profils produits ---------------------------------------------------------------


def test_memes_reponses_meme_profil():
    assert profil_comme("robert") == profil_comme("robert")


@pytest.mark.parametrize("nom", ["robert", "amira", "mateo"])
def test_profil_valide_et_proche_du_profil_de_test(nom):
    profil = profil_comme(nom)
    assert erreurs_profil(profil, nom_fichier=profil["id"]) == []
    assert "decision_demo" not in profil  # facultative : un nouvel utilisateur n'en a pas
    types_persona = {r["type"] for r in persona(nom)["pacte"]["regles"]}
    assert types_persona <= {r["type"] for r in profil["pacte"]["regles"]}
    assert profil["profil_risque"] == persona(nom)["profil_risque"]
    # horizon_ans suit les tranches du questionnaire (Mateo : 5 à 10 ans au lieu de 8 à 12)
    assert profil["horizon_ans"][0] <= persona(nom)["horizon_ans"][0]


def test_seuils_obtenus_pour_les_profils_de_test():
    """Seuils tirés du plafond de capacité (écarts avec personas/ documentés dans la fiche du retrait des cartes)."""
    assert regle(profil_comme("robert"), "pire_baisse_max")["seuil"] == pytest.approx(-0.15)  # Pacte écrit à la main : −12 %
    assert regle(profil_comme("mateo"), "pire_baisse_max")["seuil"] == pytest.approx(-0.25)   # −20 %
    assert regle(profil_comme("amira"), "pire_baisse_max")["seuil"] == pytest.approx(-0.40)   # −45 %


def test_regles_des_preferences():
    amira = profil_comme("amira")
    assert regle(amira, "plafond_crypto")["max"] == 0.25
    assert regle(amira, "plafond_tech") == {**regle(amira, "plafond_tech"), "categories": ["tech"], "max": 0.75}
    mateo = profil_comme("mateo")
    assert regle(mateo, "controverses_esg")["critere"] == "controverse_esg_importante"
    assert regle(mateo, "regle_personnelle")["libelle"] == "Équilibre entre croissance et stabilité"
    assert regle(profil_comme("robert"), "plafond_crypto")["libelle"] == "Crypto : exclue"


def test_justification_cite_les_reponses_decisives():
    justification = regle(profil_comme("robert", horizon="moins_3"), "pire_baisse_max")["justification"]
    assert "horizon : « Moins de 3 ans »" in justification and "capacité à encaisser une baisse" in justification
    assert "Pacte vécu" in justification  # la baisse vraiment acceptée se mesure ensuite


# --- Barème -------------------------------------------------------------------------


def test_horizon_court_le_plafond_de_capacite_fixe_le_seuil():
    profil = profil_comme("amira", horizon="moins_3")  # profil audacieux, mais moins de 3 ans d'horizon
    assert regle(profil, "pire_baisse_max")["seuil"] == pytest.approx(-0.10)
    detail = detail_bareme({**COMME["amira"], "horizon": "moins_3"}, DATE)
    assert detail["capacite"]["plafond"] == -0.10 and detail["seuil_retenu"]["valeur"] == -0.10


def test_le_vecu_2022_l_emporte_sur_la_reaction_imaginee():
    detail = detail_bareme({**COMME["amira"], "vecu_2022": "vendu", "reaction": "rachete"}, DATE)
    assert detail["resserrement"]["resserre"] and detail["resserrement"]["source"] == "vecu_2022"
    assert detail["seuil_retenu"]["valeur"] == pytest.approx(-0.40 * 0.75)  # capacité −40 %, resserrée d'un quart
    garde = detail_bareme({**COMME["amira"], "vecu_2022": "rachete", "reaction": "vend_tout"}, DATE)
    assert not garde["resserrement"]["resserre"] and garde["seuil_retenu"]["valeur"] == pytest.approx(-0.40)


def test_sans_vecu_2022_la_reaction_decide():
    resserrement = detail_bareme({**COMME["amira"], "vecu_2022": "pas_investi", "reaction": "vend_partie"}, DATE)["resserrement"]
    assert resserrement["resserre"] and resserrement["source"] == "reaction"


def test_exclusion_des_energies_fossiles_rend_10_pour_cent_de_xom_en_violation():
    profil = profil_comme("mateo", exclusions=["energies_fossiles"])
    exclusion = regle(profil, "exclusion_energie_fossile")
    assert exclusion["max"] == 0.0 and exclusion["categories"] == ["energie_fossile"]
    decision = {"type": "position", "ticker": "XOM", "taille": 0.10, "financement": "proportionnel"}
    controles = verifier_pacte([exclusion], poids_apres_decision(profil["portefeuille"], decision), None, "P1")
    assert controles[0]["statut"] == "violation"


def test_categorie_energie_fossile():
    assert {"XOM", "CNQ.TO", "ENB.TO"} == {t for t in ("XOM", "CNQ.TO", "ENB.TO", "SPY", "XIU.TO") if "energie_fossile" in categories_du_titre(t)}


# --- Réponses manquantes ou invalides -----------------------------------------------


def test_reponse_manquante_aucune_regle_et_un_controle_a_verifier():
    profil = profil_comme("robert", crypto=None)
    assert regle(profil, "plafond_crypto") is None
    controles = detail_bareme({k: v for k, v in COMME["robert"].items() if k != "crypto"}, DATE)["controles"]
    assert any(c["statut"] == "a_verifier" and "Cryptoactifs" in c["message"] for c in controles)


def test_le_seuil_de_pire_baisse_est_une_hypothese_du_bareme():
    detail = next(r for r in detail_bareme(COMME["robert"], DATE)["regles"] if r["id"] == "pire_baisse_max")
    assert detail["etiquette"] == "hypothese"
    assert {"horizon", "coussin", "reaction", "vecu_2022"} <= set(detail["reponses"])


def test_quiz_faux_signale_sans_penalite():
    detail = detail_bareme({**COMME["robert"], "quiz_baisse": "50"}, DATE)
    assert any("mal comprise" in c["message"] for c in detail["controles"])
    assert regle(profil_comme("robert", quiz_baisse="50"), "pire_baisse_max")["seuil"] == pytest.approx(-0.15)


def test_regle_personnelle_reprise_telle_quelle():
    profil = profil_comme("robert", regle_perso="  Pas de   titres que je ne comprends pas  ")
    assert regle(profil, "regle_personnelle")["libelle"] == "Pas de titres que je ne comprends pas"


@pytest.mark.parametrize("modifs, motif", [
    ({"crypto": "50"}, "inconnue"),
    ({"exclusions": ["aucune", "energies_fossiles"]}, "aucune"),
    ({"regle_perso": "x" * 121}, "120 caractères"),
    ({"horizon": None}, "obligatoire"),
    ({"inconnue": "oui"}, "Question inconnue"),
])
def test_reponses_invalides_refusees(modifs, motif):
    with pytest.raises(ReponsesInvalides, match=motif):
        profil_comme("robert", **modifs)


def test_saisies_invalides_refusees():
    with pytest.raises(ReponsesInvalides, match="hors de l'univers"):
        profil_depuis_reponses(COMME["robert"], 1000, [{"ticker": "DOGE-USD", "poids": 1.0}], DATE)
    with pytest.raises(ReponsesInvalides, match="totalisent"):
        profil_depuis_reponses(COMME["robert"], 1000, [{"ticker": "SPY", "poids": 0.5}], DATE)
    with pytest.raises(ReponsesInvalides, match="Identifiant"):
        profil_depuis_reponses(COMME["robert"], 1000, [{"ticker": "SPY", "poids": 1.0}], DATE, identifiant="Jean Dupont")


def test_decision_de_demonstration_facultative():
    profil = profil_depuis_reponses(COMME["robert"], 1000, [{"ticker": "SPY", "poids": 1.0}], DATE,
                                    decision={"type": "position", "ticker": "TSLA", "taille": 0.1, "financement": "proportionnel"})
    assert erreurs_profil(profil) == [] and profil["decision_demo"]["ticker"] == "TSLA"


# --- Questions et commande ----------------------------------------------------------


def test_questions_pretes_a_afficher():
    liste = questions()
    assert [q["id"] for q in liste][:3] == ["horizon", "objectif", "retraits"]
    assert len(liste) == 15


def test_la_question_des_portefeuilles_n_est_plus_posee():
    """La question « fourchettes » (cartes de portefeuilles réels) est retirée : le Pacte vécu mesure la tolérance."""
    assert all(q["id"] != "fourchettes" and q["type"] != "cartes" for q in questions())
    with pytest.raises(ReponsesInvalides, match="Question inconnue"):
        profil_comme("robert", fourchettes="equilibre")


def test_commande_ecrit_un_profil_valide_et_ne_remplace_rien(tmp_path, capsys):
    reponses = tmp_path / "reponses.json"
    reponses.write_text(json.dumps({"id": "jeanne", "nom": "Jeanne", "date": DATE, "capital_cad": 120000,
                                    "portefeuille": [{"ticker": "XIU.TO", "poids": 0.6}, {"ticker": "XBB.TO", "poids": 0.4}],
                                    "reponses": COMME["mateo"]}), encoding="utf-8")
    sortie = tmp_path / "jeanne.json"
    assert main([str(reponses), "--sortie", str(sortie)]) == 0
    profil = json.loads(sortie.read_text(encoding="utf-8"))
    assert erreurs_profil(profil, nom_fichier="jeanne") == []
    assert "Profil écrit" in capsys.readouterr().out
    assert main([str(reponses), "--sortie", str(sortie)]) == 1  # existe déjà : rien n'est remplacé
    assert main([str(reponses), "--sortie", str(sortie), "--forcer"]) == 0


# --- Expérience ---------------------------------------------------------------------


def test_decision_sur_un_type_de_titre_jamais_detenu_a_verifier():
    tsla = {"type": "position", "ticker": "TSLA", "taille": 0.30, "financement": "proportionnel"}
    controle = controle_experience(["depots", "fonds"], tsla)
    assert controle["statut"] == "a_verifier" and "Actions individuelles" in controle["message"] and "TSLA" in controle["message"]
    assert controle_experience(["fonds", "actions"], tsla) is None


def test_experience_d_un_panier():
    panier = {"type": "reallocation", "part_reallouee": 1.0,
              "panier": [{"ticker": "QQQ", "poids": 0.5}, {"ticker": "BTC-USD", "poids": 0.5}]}
    controle = controle_experience(["fonds", "actions"], panier)
    assert "Cryptoactifs" in controle["message"] and "BTC-USD" in controle["message"] and "QQQ" not in controle["message"]
    assert controle_experience(["fonds", "crypto"], panier) is None
