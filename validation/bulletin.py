"""Le bulletin du Greffier : les taux mesurés, écrits pour l'interface (#172).

Chaque commande d'évaluation (#165, #166, #167, #168) range ses résultats dans
``frontend/src/data/bulletin.json``. L'interface ne calcule rien : elle affiche, à côté
d'un contrôle du Greffier, combien de fois ce contrôle a réussi quand on a essayé de le
tromper, avec le lien vers le rapport complet. Les ratés ne sont jamais cachés : le taux
est écrit tel qu'il est, avec le nombre de cas passés à travers.

Une entrée par mesure (``verifier_chiffres``, ``cadre_simulation``, ``orchestrateur``,
``validation_externe``). Chaque taux : ``k`` réussis sur ``n``, ``taux`` (k/n), ``rates``
(n − k) et ``ic95`` (Wilson à 95 %), arrondis ici pour que l'interface n'ait rien à calculer.
La ``date`` de la mesure ne change que si les chiffres changent : relancer une commande sans
rien modifier laisse le fichier identique.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from validation.evaluation import RACINE, ResultatCas, intervalle_wilson

CHEMIN_BULLETIN = RACINE / "frontend" / "src" / "data" / "bulletin.json"
DEPOT = "https://github.com/yanisbenboudaoud/Datathon2026/blob/main/"
DECIMALES = 4


def mesure_taux(k: int, n: int) -> dict[str, Any]:
    """Un taux prêt à afficher : k, n, k/n, n − k et l'intervalle de Wilson à 95 %."""
    bas, haut = intervalle_wilson(k, n)
    return {"k": k, "n": n, "taux": round(k / n, DECIMALES), "rates": n - k,
            "ic95": [round(bas, DECIMALES), round(haut, DECIMALES)]}


def charger_bulletin(chemin: Path = CHEMIN_BULLETIN) -> dict[str, Any]:
    if chemin.exists():
        return json.loads(chemin.read_text(encoding="utf-8"))
    return {
        "description": (
            "Bulletin du Greffier (#172) : taux mesurés par les évaluations de docs/validation/, écrits par "
            "Python (validation/bulletin.py). L'interface les affiche sans rien calculer. Ne pas modifier à "
            "la main : relancer la commande d'évaluation."
        ),
        "depot": DEPOT,
        "mesures": {},
    }


def ranger_mesure(cle: str, mesure: dict[str, Any], chemin: Path = CHEMIN_BULLETIN,
                  aujourd_hui: str | None = None) -> dict[str, Any]:
    """Range une mesure dans le bulletin ; garde l'ancienne date si les chiffres n'ont pas changé.

    Returns:
        L'entrée écrite (avec sa ``date``).
    """
    bulletin = charger_bulletin(chemin)
    ancienne = bulletin["mesures"].get(cle)
    if ancienne and {k: v for k, v in ancienne.items() if k != "date"} == mesure:
        entree = ancienne
    else:
        entree = {**mesure, "date": aujourd_hui or date.today().isoformat()}
    bulletin["mesures"][cle] = entree
    bulletin["mesures"] = dict(sorted(bulletin["mesures"].items()))
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(bulletin, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return entree


# --- Mesures de chaque évaluation -----------------------------------------------------

def _pieges_et_legitimes(nom: str, jeu: dict[str, Any], resultats: list[ResultatCas],
                         issue: int) -> dict[str, Any]:
    """Jeux « Trompez le Greffier » : pièges détectés et arguments légitimes admis.

    Les familles ``hors_promesse`` (limite connue, mesurée à part) ne comptent pas dans les
    pièges, comme dans le rapport.
    """
    hors_promesse = {cle for cle, f in jeu["familles"].items() if f.get("hors_promesse")}
    pieges = [r for r in resultats if r.attendu == "rejete" and r.famille not in hors_promesse]
    legitimes = [r for r in resultats if r.attendu == "accepte"]
    return {
        "issue": issue,
        "jeu": nom,
        "rapport": f"docs/validation/evaluation_{nom}.md",
        "pieges": mesure_taux(sum(r.ok for r in pieges), len(pieges)),
        "legitimes": mesure_taux(sum(r.ok for r in legitimes), len(legitimes)),
    }


def mesure_chiffres(nom: str, jeu: dict[str, Any], resultats: list[ResultatCas]) -> tuple[str, dict[str, Any]]:
    """#165 : chiffres inventés détectés par ``verifier_chiffres``, arguments valides acceptés."""
    return "verifier_chiffres", _pieges_et_legitimes(nom, jeu, resultats, 165)


def mesure_cadre(nom: str, jeu: dict[str, Any], resultats: list[ResultatCas]) -> tuple[str, dict[str, Any]]:
    """#166 : conseils et promesses bloqués par ``cadre_simulation``, arguments légitimes admis."""
    return "cadre_simulation", _pieges_et_legitimes(nom, jeu, resultats, 166)


def mesure_externe(releves: dict[str, Any], comparaisons: list) -> tuple[str, dict[str, Any]]:
    """#168 : rendements annuels des FNB à moins du seuil de ceux publiés par les émetteurs."""
    annee_cle = [c for c in comparaisons if c.annee == 2022]
    return "validation_externe", {
        "issue": 168,
        "rapport": "docs/validation/validation_externe.md",
        "seuil_points": releves["seuil_acceptation"]["ecart_max_points"],
        "fnb": list(dict.fromkeys(c.ticker for c in comparaisons)),
        "dans_le_seuil": mesure_taux(sum(c.dans_le_seuil for c in comparaisons), len(comparaisons)),
        "annee_2022": mesure_taux(sum(c.dans_le_seuil for c in annee_cle), len(annee_cle)),
        "ecart_max_points": round(max(abs(c.ecart_points) for c in comparaisons), 2),
    }


def mesure_orchestrateur(mesures: Any, date_lecture: str) -> tuple[str, dict[str, Any]]:
    """#167 : garde-fous de l'orchestrateur et corrections du débat, sur les procès tenus."""
    renvoyes = sum(c.renvoyes for c in mesures.cotes.values())
    corriges = sum(c.corriges for c in mesures.cotes.values())
    return "orchestrateur", {
        "issue": 167,
        "rapport": "docs/validation/evaluation_orchestrateur.md",
        "proces": mesures.nb_proces,
        "lu_le": date_lecture,
        "budget_respecte": mesure_taux(mesures.proces_dans_budget, mesures.nb_proces),
        "simulation_demandee": mesure_taux(mesures.simulation_spontanee, mesures.nb_proces),
        "corriges_apres_renvoi": mesure_taux(corriges, renvoyes) if renvoyes else None,
    }
