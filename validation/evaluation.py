"""Évaluations mesurées des garde-fous (#165, puis #166 et #167).

Les tests unitaires prouvent qu'une règle marche sur ses exemples ; une évaluation
la **mesure** sur un jeu de cas écrit à l'avance (``validation/jeux/<nom>.json``) et
donne un taux, avec son intervalle de confiance de Wilson à 95 %. Python seul, sans
Bedrock : gratuit et reproductible.

Un jeu déclare son ``evaluation`` (le code qui joue ses cas), ses ``familles``
(fixées avant la mesure, chacune avec le résultat ``attendu``) et ses ``cas``.
Chaque cas joué donne un ``ResultatCas`` ; le rapport Markdown est réécrit dans
``docs/validation/evaluation_<nom>.md``, sans date ni horodatage, pour qu'il se
régénère à l'identique.

Un raté n'est jamais corrigé en silence : il reste dans le rapport. Si une règle est
corrigée, la mesure suivante se fait sur un second jeu, écrit après la correction.

Usage : ``python -m validation.evaluation chiffres`` (#165) ou ``cadre`` (#166) ; pour une évaluation
qui relit les procès tenus au lieu d'un jeu, ``python -m validation.evaluation orchestrateur`` (#167).
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_JEUX = RACINE / "validation" / "jeux"
DOSSIER_RAPPORTS = RACINE / "docs" / "validation"

Z_95 = 1.959964  # quantile de la loi normale pour un intervalle à 95 %


@dataclass(frozen=True)
class ResultatCas:
    """Un cas joué : ce qui était attendu, ce qui a été obtenu, et pourquoi."""

    id: str
    famille: str
    attendu: str   # « rejete » ou « accepte »
    obtenu: str    # idem, ou « rejete_autre_motif » pour un piège rejeté sur un autre nombre
    ok: bool
    texte: str
    detail: str    # motif du vérificateur, ou « accepté »


def intervalle_wilson(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Intervalle de confiance de Wilson d'une proportion k/n (95 % par défaut).

    Préféré à l'intervalle « p ± z·√(p(1−p)/n) », qui donne une largeur nulle à 100 %
    et sort de [0, 1] sur de petits échantillons.
    """
    if n <= 0:
        raise ValueError("intervalle de Wilson : n doit être positif")
    if not 0 <= k <= n:
        raise ValueError(f"intervalle de Wilson : k={k} hors de [0, {n}]")
    p = k / n
    denominateur = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denominateur
    demi_largeur = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominateur
    return max(0.0, centre - demi_largeur), min(1.0, centre + demi_largeur)


def charger_jeu(nom: str) -> dict[str, Any]:
    """Lit ``validation/jeux/<nom>.json`` et vérifie que chaque cas a une famille déclarée."""
    chemin = DOSSIER_JEUX / f"{nom}.json"
    jeu = json.loads(chemin.read_text(encoding="utf-8"))
    inconnues = sorted({cas["famille"] for cas in jeu["cas"]} - set(jeu["familles"]))
    if inconnues:
        raise ValueError(f"{chemin.name} : familles non déclarées : {', '.join(inconnues)}")
    ids = [cas["id"] for cas in jeu["cas"]]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{chemin.name} : identifiants de cas en double")
    return jeu


# --- Rapport Markdown -------------------------------------------------------------

def pourcentage(x: float) -> str:
    """0.9876 → « 98,8 % »."""
    return f"{x * 100:.1f} %".replace(".", ",")


def taux(k: int, n: int) -> str:
    """« 66/66 (100,0 % ; IC 95 % : 94,5 % à 100,0 %) »."""
    bas, haut = intervalle_wilson(k, n)
    return f"{k}/{n} ({pourcentage(k / n)} ; IC 95 % : {pourcentage(bas)} à {pourcentage(haut)})"


def tableau_familles(jeu: dict[str, Any], resultats: list[ResultatCas]) -> list[str]:
    """Une ligne par famille, dans l'ordre du jeu : k/N réussis et intervalle de Wilson."""
    lignes = [
        "| Famille | Attendu | Réussis | Taux | IC 95 % (Wilson) |",
        "|---|---|---|---|---|",
    ]
    for cle, famille in jeu["familles"].items():
        cas = [r for r in resultats if r.famille == cle]
        if not cas:
            continue
        k, n = sum(r.ok for r in cas), len(cas)
        bas, haut = intervalle_wilson(k, n)
        attendu = "rejeté" if famille["attendu"] == "rejete" else "accepté"
        lignes.append(f"| {famille['libelle']} (`{cle}`) | {attendu} | {k}/{n} | {pourcentage(k / n)} "
                      f"| {pourcentage(bas)} à {pourcentage(haut)} |")
    return lignes


def cellule(texte: str) -> str:
    """Texte sûr dans une cellule de tableau Markdown."""
    return texte.replace("|", "\\|").replace("\n", " ")


# --- Commande ---------------------------------------------------------------------

def _evaluations() -> dict[str, tuple[Callable, Callable]]:
    from validation import evaluation_cadre, evaluation_chiffres
    return {
        "chiffres": (evaluation_chiffres.evaluer, evaluation_chiffres.rapport),
        "cadre": (evaluation_cadre.evaluer, evaluation_cadre.rapport),
    }


def evaluer_jeu(nom: str) -> tuple[dict[str, Any], list[ResultatCas], str]:
    """Joue le jeu ``nom`` et rend le jeu, les résultats et le rapport Markdown."""
    jeu = charger_jeu(nom)
    evaluer, rapport = _evaluations()[jeu["evaluation"]]
    resultats = evaluer(jeu)
    return jeu, resultats, rapport(nom, jeu, resultats)


def chemin_rapport(nom: str) -> Path:
    return DOSSIER_RAPPORTS / f"evaluation_{nom}.md"


def _evaluations_sans_jeu() -> dict[str, Callable[[list[str]], tuple[str, str]]]:
    """Évaluations qui lisent des procès tenus au lieu d'un jeu écrit à l'avance (#167)."""
    from validation import evaluation_orchestrateur
    return {"orchestrateur": evaluation_orchestrateur.executer}


def _ranger_au_bulletin(nom: str, jeu: dict[str, Any], resultats: list[ResultatCas]) -> None:
    """Range la mesure dans le bulletin du Greffier affiché par l'interface (#172)."""
    from validation import bulletin
    mesures = {"chiffres": bulletin.mesure_chiffres, "cadre": bulletin.mesure_cadre}
    if jeu["evaluation"] in mesures:
        cle, mesure = mesures[jeu["evaluation"]](nom, jeu, resultats)
        bulletin.ranger_mesure(cle, mesure)
        print(f"Bulletin du Greffier : « {cle} » → {bulletin.CHEMIN_BULLETIN.relative_to(RACINE)}")


def main(arguments: list[str]) -> int:
    if not arguments:
        print("Usage : python -m validation.evaluation <jeu>   (ex. : chiffres, cadre, orchestrateur [--local])")
        return 2
    nom, options = arguments[0], arguments[1:]
    sans_jeu = _evaluations_sans_jeu()
    if nom in sans_jeu:
        chemin, resume = sans_jeu[nom](options)
        print(f"{resume} → {chemin}")
        return 0
    if options:
        print(f"Options inconnues pour le jeu « {nom} » : {' '.join(options)}")
        return 2
    jeu, resultats, texte = evaluer_jeu(nom)
    chemin = chemin_rapport(nom)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")
    rates = [r for r in resultats if not r.ok]
    print(f"{len(resultats) - len(rates)}/{len(resultats)} cas conformes à l'attendu → {chemin.relative_to(RACINE)}")
    _ranger_au_bulletin(nom, jeu, resultats)
    for r in rates:
        print(f"RATÉ  {r.id} ({r.famille}) : {r.detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
