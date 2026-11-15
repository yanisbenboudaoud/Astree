"""Tests des scénarios de validation et de sensibilité (validation/scenarios.py, #15)."""

import pytest

from validation.scenarios import (
    CHEMIN_GRAPHIQUE,
    CHEMIN_RAPPORT,
    GROUPES,
    executer_scenarios,
    graphique_svg,
    rapport_markdown,
    sensibilite_seuil,
)


@pytest.mark.parametrize("groupe", GROUPES, ids=lambda g: g.__name__)
def test_aucun_scenario_en_echec(groupe):
    echecs = [r for r in groupe() if r.ok is False]
    assert echecs == [], "\n".join(f"{r.scenario} : attendu {r.attendu}, obtenu {r.obtenu}" for r in echecs)


def test_rapport_a_jour():
    """Le tableau de la documentation correspond aux résultats actuels.

    En cas d'échec : lancer « python -m validation » et committer le rapport.
    """
    assert CHEMIN_RAPPORT.read_text(encoding="utf-8") == rapport_markdown(executer_scenarios())


def test_aucun_scenario_en_attente():
    assert [r.scenario for r in executer_scenarios() if r.ok is None] == []


def test_graphique_a_jour():
    """Le graphique de la documentation correspond aux calculs actuels (« python -m validation »)."""
    assert CHEMIN_GRAPHIQUE.read_text(encoding="utf-8") == graphique_svg(sensibilite_seuil())


def test_taille_max_croit_quand_le_seuil_s_assouplit():
    tailles = [taille for _, taille in sensibilite_seuil()]
    assert all(a <= b for a, b in zip(tailles, tailles[1:]))
    assert dict(sensibilite_seuil())[-0.12] == 0.09  # valeur du faux contrat (P5)
