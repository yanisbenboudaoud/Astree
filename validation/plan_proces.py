"""Tient le plan de procès de #167 sur la Lambda déployée (vrais appels Bedrock, payants).

Chaque procès du plan (``validation/jeux/plan_proces.json`` : décisions × profils ×
répétitions) est envoyé à ``POST /tribunal``, un à la fois (concurrence réservée de 2).
La Lambda l'archive dans S3 comme tout procès ; ce script note seulement, dans
``validation/jeux/plan_proces_resultats.json``, quel procès répond à quelle case du plan,
avec le statut HTTP et la durée mesurée côté client. Une case déjà tenue n'est pas
rejouée : relancer le script reprend là où il s'est arrêté, sans payer deux fois.

Usage : ``python -m validation.plan_proces`` (identifiants de ``aws login``), puis
``python -m validation.evaluation orchestrateur`` pour le rapport.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, Iterator

from validation.evaluation import DOSSIER_JEUX

CHEMIN_PLAN = DOSSIER_JEUX / "plan_proces.json"
CHEMIN_RESULTATS = DOSSIER_JEUX / "plan_proces_resultats.json"


def charger_plan() -> dict[str, Any]:
    return json.loads(CHEMIN_PLAN.read_text(encoding="utf-8"))


def charger_resultats() -> list[dict[str, Any]]:
    if not CHEMIN_RESULTATS.exists():
        return []
    return json.loads(CHEMIN_RESULTATS.read_text(encoding="utf-8"))


def cases(plan: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Chaque procès du plan, répétitions comprises, dans un ordre stable."""
    for repetition in range(1, plan["repetitions"] + 1):
        for decision in plan["decisions"]:
            for profil in plan["profils"]:
                yield {"decision": decision["id"], "demande": decision["demande"], "profil": profil,
                       "repetition": repetition}


def cle(case: dict[str, Any]) -> tuple[str, str, int]:
    return case["decision"], case["profil"], case["repetition"]


def tenir_plan(envoyer: Callable[[dict[str, Any]], tuple[int, float, str | None]],
               ecrire: Callable[[list[dict[str, Any]]], None]) -> list[dict[str, Any]]:
    """Envoie chaque case pas encore tenue avec succès ; écrit les résultats après chaque procès."""
    resultats = charger_resultats()  # les échecs restent notés ; leur case est rejouée
    faites = {cle(r) for r in resultats if r["statut"] == 200}
    for case in cases(charger_plan()):
        if cle(case) in faites:
            continue
        statut, duree, identifiant = envoyer({"profil": case["profil"], "demande": case["demande"]})
        resultat = {**case, "proces_id": identifiant, "statut": statut, "duree_s": round(duree, 1)}
        print(f"{case['decision']} · {case['profil']} · répétition {case['repetition']} : "
              f"HTTP {statut} en {duree:.1f} s · {identifiant or 'non archivé'}", flush=True)
        resultats.append(resultat)
        ecrire(resultats)
    return resultats


def _ecrire(resultats: list[dict[str, Any]]) -> None:
    CHEMIN_RESULTATS.write_text(json.dumps(resultats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> int:
    from deploiement.tester_function_url import FONCTION, adresse_function_url, envoyer

    adresse = adresse_function_url(FONCTION)

    def envoyer_proces(corps: dict[str, Any]) -> tuple[int, float, str | None]:
        statut, duree, _, identifiant = envoyer(f"{adresse}/tribunal", corps)
        return statut, duree, identifiant

    resultats = tenir_plan(envoyer_proces, _ecrire)
    tenues = {cle(r) for r in resultats if r["statut"] == 200}
    manquantes = [c for c in cases(charger_plan()) if cle(c) not in tenues]
    print(f"{len(tenues)} procès tenus, {len(manquantes)} à reprendre → {CHEMIN_RESULTATS.name}")
    return 1 if manquantes else 0


if __name__ == "__main__":
    sys.exit(main())
