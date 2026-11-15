"""Évaluations mesurées (#165) : module commun, jeu « chiffres » et rapport reproductible."""

import pytest

from pipeline.chiffres import extraire_nombres
from validation.evaluation import chemin_rapport, charger_jeu, evaluer_jeu, intervalle_wilson, main, taux
from validation.evaluation_chiffres import jouer_cas

PERIODE = ["2021-11-12", "2026-11-12"]
PROCES_ROBERT_30 = "2026-11-15-fcb6ce39f184"


# --- Intervalle de Wilson -----------------------------------------------------------

def test_wilson_valeur_de_reference():
    bas, haut = intervalle_wilson(5, 10)
    assert bas == pytest.approx(0.2366, abs=1e-4)
    assert haut == pytest.approx(0.7634, abs=1e-4)


def test_wilson_a_100_pourcent_n_atteint_pas_une_largeur_nulle():
    bas, haut = intervalle_wilson(66, 66)
    assert haut == 1.0
    assert bas == pytest.approx(66 / (66 + 1.959964**2))  # forme close quand k = n


def test_wilson_a_0_pourcent():
    bas, haut = intervalle_wilson(0, 6)
    assert bas == 0.0
    assert haut == pytest.approx(0.3903, abs=1e-4)


@pytest.mark.parametrize("k, n", [(0, 0), (-1, 5), (6, 5)])
def test_wilson_refuse_les_entrees_impossibles(k, n):
    with pytest.raises(ValueError):
        intervalle_wilson(k, n)


def test_taux_en_francais():
    assert taux(5, 10) == "5/10 (50,0 % ; IC 95 % : 23,7 % à 76,3 %)"


# --- Jeu « chiffres » ---------------------------------------------------------------

@pytest.fixture(scope="module")
def jeu():
    return charger_jeu("chiffres")


def test_jeu_a_assez_de_pieges_et_d_arguments_valides(jeu):
    familles = jeu["familles"]
    pieges = [c for c in jeu["cas"] if familles[c["famille"]]["attendu"] == "rejete"
              and not familles[c["famille"]].get("hors_promesse")]
    valides = [c for c in jeu["cas"] if familles[c["famille"]]["attendu"] == "accepte"]
    assert len(pieges) >= 60
    assert len(valides) >= 40


def test_familles_de_l_issue_presentes(jeu):
    attendues = {"chiffre_altere", "arrondi_faux", "signe_faux", "nombre_derive", "piece_non_citee", "date_absente"}
    assert attendues <= set(jeu["familles"])


def test_chaque_piege_est_extrait_tel_qu_ecrit(jeu):
    for cas in jeu["cas"]:
        if "piege" in cas:
            assert cas["piege"] in [n.texte for n in extraire_nombres(cas["texte"])], cas["id"]


def test_famille_inconnue_refusee(tmp_path, monkeypatch):
    (tmp_path / "faux.json").write_text(
        '{"evaluation": "chiffres", "familles": {}, "cas": [{"id": "x", "famille": "inconnue"}]}', encoding="utf-8")
    monkeypatch.setattr("validation.evaluation.DOSSIER_JEUX", tmp_path)
    with pytest.raises(ValueError, match="inconnue"):
        charger_jeu("faux")


# --- Jouer un cas -------------------------------------------------------------------

def cas(texte, pieces, piege=None):
    c = {"id": "t", "famille": "f", "proces": PROCES_ROBERT_30, "pieces": pieces, "texte": texte}
    if piege:
        c["piege"] = piege
    return c


def test_piege_detecte():
    r = jouer_cas(cas("La pire baisse atteint −29,03 %.", ["P2"], "−29,03 %"), "rejete", PERIODE)
    assert r.ok and r.obtenu == "rejete"
    assert "« −29,03 % » introuvable dans P2" in r.detail


def test_piege_rejete_pour_un_autre_nombre_est_un_rate():
    r = jouer_cas(cas("La pire baisse atteint −29,03 %, soit −31 %.", ["P2"], "−29,03 %"), "rejete", PERIODE)
    # « −29,03 % » et « −31 % » sont tous deux introuvables : le piège est bien relevé.
    assert r.ok
    r = jouer_cas(cas("La pire baisse atteint −29,0 %, soit −31 %.", ["P2"], "−29,0 %"), "rejete", PERIODE)
    assert not r.ok and r.obtenu == "rejete_autre_motif"


def test_piege_accepte_nomme_le_champ_trouve():
    r = jouer_cas(cas("Sans cette position, la volatilité était de 9,3 %.", ["P2"], "9,3 %"), "rejete", PERIODE)
    assert not r.ok
    assert r.detail == "accepté : « 9,3 % » trouvé dans P2 (rendement_annuel_actuel)"


def test_argument_valide_accepte():
    r = jouer_cas(cas("Avec 30 % en TSLA, la pire baisse atteint −29 %.", ["P2"]), "accepte", PERIODE)
    assert r.ok and r.detail == "accepté"


# --- Rapport ------------------------------------------------------------------------

def test_rapport_se_regenere_a_l_identique():
    _, _, premier = evaluer_jeu("chiffres")
    _, _, second = evaluer_jeu("chiffres")
    assert premier == second
    assert chemin_rapport("chiffres").read_text(encoding="utf-8") == premier, (
        "docs/validation/evaluation_chiffres.md n'est plus à jour : relancer "
        "python -m validation.evaluation chiffres")


def test_rapport_garde_chaque_rate():
    _, resultats, texte = evaluer_jeu("chiffres")
    for r in resultats:
        if not r.ok:
            assert f"`{r.id}`" in texte


def test_commande_sans_argument():
    assert main([]) == 2
