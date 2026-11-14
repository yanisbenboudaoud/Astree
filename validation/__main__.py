"""``python -m validation`` : joue tous les scénarios et réécrit le rapport."""

import sys

from validation.scenarios import ecrire_rapport, executer_scenarios

resultats = executer_scenarios()
chemin = ecrire_rapport(resultats)
echecs = [r for r in resultats if r.ok is False]
attente = [r for r in resultats if r.ok is None]
print(f"{len(resultats) - len(echecs) - len(attente)} réussis, {len(echecs)} en échec, "
      f"{len(attente)} en attente → {chemin}")
for r in echecs:
    print(f"ÉCHEC  {r.groupe} / {r.scenario} : attendu {r.attendu}, obtenu {r.obtenu}")
sys.exit(1 if echecs else 0)
