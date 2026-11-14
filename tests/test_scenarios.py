"""Tests des scénarios de validation et de sensibilité (validation/scenarios.py, #15)."""

import pytest

from validation.scenarios import CHEMIN_RAPPORT, GROUPES, rapport_markdown, executer_scenarios


@pytest.mark.parametrize("groupe", GROUPES, ids=lambda g: g.__name__)
def test_aucun_scenario_en_echec(groupe):
    echecs = [r for r in groupe() if r.ok is False]
    assert echecs == [], "\n".join(f"{r.scenario} : attendu {r.attendu}, obtenu {r.obtenu}" for r in echecs)


def test_rapport_a_jour():
    """Le tableau de la documentation correspond aux résultats actuels.

    En cas d'échec : lancer « python -m validation » et committer le rapport.
    """
    assert CHEMIN_RAPPORT.read_text(encoding="utf-8") == rapport_markdown(executer_scenarios())
