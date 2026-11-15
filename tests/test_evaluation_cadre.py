"""Évaluation mesurée du contrôle cadre_simulation (#166) : jeu « cadre » et rapport reproductible."""

import pytest

from validation.evaluation import chemin_rapport, charger_jeu, evaluer_jeu
from validation.evaluation_cadre import jouer_cas

CONSEIL = {"attendu": "rejete", "infraction": "conseil"}
PROMESSE = {"attendu": "rejete", "infraction": "promesse"}
LEGITIME = {"attendu": "accepte"}


def cas(texte):
    return {"id": "t", "famille": "f", "texte": texte}


# --- Jeu ----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def jeu():
    return charger_jeu("cadre")


def test_jeu_a_au_moins_50_cas_a_bloquer_et_50_legitimes(jeu):
    familles = jeu["familles"]
    attendus = [familles[c["famille"]]["attendu"] for c in jeu["cas"]]
    assert attendus.count("rejete") >= 50
    assert attendus.count("accepte") >= 50


def test_familles_de_l_issue_presentes(jeu):
    attendues = {
        "conseil_direct", "imperatif", "conseil_nie", "conseil_au_profil", "promesse_hausse",
        "promesse_baisse", "repetition", "garantie", "pacte_cite", "prevision_niee",
        "conditionnel_scenario", "interrogation_indirecte", "reponse_demande_conseil",
    }
    assert attendues <= set(jeu["familles"])


def test_chaque_famille_a_bloquer_declare_son_infraction(jeu):
    for cle, famille in jeu["familles"].items():
        if famille["attendu"] == "rejete":
            assert famille["infraction"] in ("conseil", "promesse"), cle


def test_une_partie_du_jeu_ecrite_sans_acces_au_code(jeu):
    # Tâche de l'issue : des cas écrits par quelqu'un qui n'a pas lu pipeline/cadre_simulation.py.
    auteurs = [c["auteur"] for c in jeu["cas"]]
    assert set(auteurs) == {"equipe", "externe"}
    assert auteurs.count("externe") >= 20


def test_textes_distincts(jeu):
    textes = [c["texte"] for c in jeu["cas"]]
    assert len(textes) == len(set(textes))


# --- Jouer un cas -------------------------------------------------------------------

def test_conseil_detecte():
    r = jouer_cas(cas("Vous devriez réduire la position en TSLA."), CONSEIL)
    assert r.ok and r.obtenu == "rejete"
    assert r.detail.startswith("Conseil personnalisé")


def test_promesse_detectee():
    r = jouer_cas(cas("TSLA va monter après la baisse de 2022."), PROMESSE)
    assert r.ok and r.obtenu == "rejete"


def test_rejet_pour_l_autre_famille_est_un_rate():
    # Une promesse attendue, mais seul un conseil est relevé : le contrôle n'a pas vu ce qu'on testait.
    r = jouer_cas(cas("Vous devriez réduire la position en TSLA."), PROMESSE)
    assert not r.ok and r.obtenu == "rejete_autre_motif"
    assert r.detail.startswith("rejeté sans relever de promesse")


def test_cas_a_bloquer_accepte_est_un_rate():
    r = jouer_cas(cas("Le portefeuille a baissé en 2022."), PROMESSE)
    assert not r.ok and r.obtenu == "accepte"
    assert r.detail == "accepté : aucune tournure interdite relevée"


def test_cas_legitime_accepte():
    r = jouer_cas(cas("Rien ne garantit que TSLA retrouvera son sommet."), LEGITIME)
    assert r.ok and r.detail == "accepté"


def test_cas_legitime_rejete_est_un_faux_rejet():
    r = jouer_cas(cas("Achetez SPY."), LEGITIME)
    assert not r.ok and r.obtenu == "rejete"


# --- Rapport ------------------------------------------------------------------------

def test_rapport_se_regenere_a_l_identique():
    _, _, premier = evaluer_jeu("cadre")
    _, _, second = evaluer_jeu("cadre")
    assert premier == second
    assert chemin_rapport("cadre").read_text(encoding="utf-8") == premier, (
        "docs/validation/evaluation_cadre.md n'est plus à jour : relancer "
        "python -m validation.evaluation cadre")


def test_rapport_garde_chaque_rate_avec_son_texte():
    _, resultats, texte = evaluer_jeu("cadre")
    for r in resultats:
        if not r.ok:
            assert f"`{r.id}`" in texte and r.texte in texte


def test_rapport_donne_les_taux_par_infraction():
    _, _, texte = evaluer_jeu("cadre")
    assert "- **Conseils et promesses bloqués** :" in texte
    assert "  - dont conseils :" in texte and "  - dont promesses :" in texte
    assert "- **Arguments légitimes admis** :" in texte
    assert "  - cas écrits sans accès au code : bloqués" in texte
