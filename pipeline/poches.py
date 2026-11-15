"""Plusieurs horizons dans un même portefeuille : les poches (#115).

Un portefeuille global peut servir plusieurs objectifs : une partie pour la
retraite (horizon long), une autre pour une mise de fonds dans trois ans. Un
seul horizon et un seul seuil de pire baisse pour tout le portefeuille ne
conviennent alors à aucune des deux parties.

Un profil peut donc déclarer des ``poches`` (``personas/schema_pacte.json``) :
chacune a son ``objectif``, son ``horizon_ans``, sa ``part`` du portefeuille,
son ``portefeuille`` (poids à l'intérieur de la poche) et ses propres
``regles``. Les règles du Pacte (``pacte.regles``) sont **communes** à toutes
les poches ; une règle de la poche remplace la règle commune de même ``id``.

Une décision est jugée dans **une seule poche**. ``profil_de_la_poche`` projette
le profil sur cette poche : le résultat a exactement la forme d'un profil sans
poches (portefeuille, horizon, règles, capital de la poche), donc tout l'aval du
procès (orchestrateur, simulation, taille maximale, points de bascule, Greffier,
Pacte vécu) fonctionne sans changement, **sur la poche et non sur le portefeuille
global**. Le champ ``poche`` ajouté au profil projeté (id, objectif, horizon,
part) est repris dans le contrat.

Un profil sans poches n'est jamais projeté : il donne exactement le même contrat
qu'avant. Aucun nom de profil ni de poche dans le code : tout vient du fichier.
"""

from __future__ import annotations

import copy
import math
from typing import Any

# Écart toléré entre le portefeuille global déclaré et la somme des poches pondérées
# par leur part (poids écrits à la main, arrondis à 4 décimales).
TOLERANCE_PORTEFEUILLE_GLOBAL = 1e-4


class PocheInconnue(ValueError):
    """La poche demandée n'existe pas dans ce profil (ou le profil n'a pas de poches)."""


def a_des_poches(profil: dict[str, Any]) -> bool:
    """Le profil déclare-t-il des poches ? (Sans poches : une seule poche, comme avant.)"""
    return bool(profil.get("poches"))


def trouver_poche(profil: dict[str, Any], id_poche: str) -> dict[str, Any]:
    """La poche ``id_poche`` du profil.

    Raises:
        PocheInconnue: profil sans poches, ou aucune poche ne porte cet id.
    """
    if not a_des_poches(profil):
        raise PocheInconnue(f"Le profil « {profil['id']} » n'a pas de poches : « {id_poche} » ne peut pas être jugée")
    for poche in profil["poches"]:
        if poche["id"] == id_poche:
            return poche
    ids = ", ".join(p["id"] for p in profil["poches"])
    raise PocheInconnue(f"Aucune poche « {id_poche} » dans le profil « {profil['id']} » (poches : {ids})")


def poche_la_plus_prudente(profil: dict[str, Any]) -> dict[str, Any]:
    """La poche à l'horizon le plus court (maximum, puis minimum) ; à égalité, la première.

    Sert quand la demande ne dit pas quelle poche elle vise : la décision est jugée
    là où une baisse ferait le plus de tort, et un contrôle « à vérifier » le dit.
    """
    def cle(poche: dict[str, Any]) -> tuple[float, float]:
        minimum, maximum = poche["horizon_ans"]
        return (math.inf if maximum is None else maximum, minimum)

    return min(profil["poches"], key=cle)


def regles_de_la_poche(profil: dict[str, Any], poche: dict[str, Any]) -> list[dict[str, Any]]:
    """Règles propres de la poche, puis règles communes qu'elle ne remplace pas (même id)."""
    propres = poche["regles"]
    ids_propres = {regle["id"] for regle in propres}
    return [*propres, *(regle for regle in profil["pacte"]["regles"] if regle["id"] not in ids_propres)]


def formater_horizon(horizon_ans: list) -> str:
    """[3, 5] → « 3 à 5 ans » ; [3, 3] → « 3 ans » ; [15, None] → « 15 ans et plus »."""
    minimum, maximum = (f"{borne:g}" if borne is not None else None for borne in horizon_ans)
    if maximum is None:
        return f"{minimum} ans et plus"
    if minimum == maximum:
        return f"{minimum} ans"
    return f"{minimum} à {maximum} ans"


def resume_poche(poche: dict[str, Any]) -> dict[str, Any]:
    """Champ ``pacte.poche`` du contrat : ce qui identifie la poche jugée."""
    return {"id": poche["id"], "objectif": poche["objectif"], "horizon_ans": list(poche["horizon_ans"]),
            "part": poche["part"]}


def profil_de_la_poche(profil: dict[str, Any], id_poche: str) -> dict[str, Any]:
    """Copie du profil réduite à une poche, de la même forme qu'un profil sans poches.

    - ``portefeuille`` : celui de la poche (poids à l'intérieur de la poche) ;
    - ``horizon_ans`` et ``profil_risque`` : ceux de la poche (profil de risque global
      si la poche n'en déclare pas) ;
    - ``pacte.regles`` : règles de la poche, puis règles communes non remplacées ;
    - ``capital_fictif_cad`` : capital × part de la poche (un montant en dollars devient
      une part de la poche) ;
    - ``questionnaire`` (profil tiré du questionnaire) : la réponse « horizon » devient
      celle de la poche, pour que la pièce du questionnaire et ses contrôles portent sur elle ;
    - ``decision_demo`` : gardée seulement si elle vise cette poche ;
    - ``poche`` : résumé de la poche, repris dans le contrat ; ``poches`` est retiré.

    Raises:
        PocheInconnue: voir ``trouver_poche``.
    """
    poche = trouver_poche(profil, id_poche)
    projete = copy.deepcopy({cle: valeur for cle, valeur in profil.items() if cle != "poches"})
    projete["portefeuille"] = copy.deepcopy(poche["portefeuille"])
    projete["horizon_ans"] = list(poche["horizon_ans"])
    projete["profil_risque"] = poche.get("profil_risque", profil["profil_risque"])
    projete["capital_fictif_cad"] = round(profil["capital_fictif_cad"] * poche["part"], 2)
    projete["pacte"]["regles"] = copy.deepcopy(regles_de_la_poche(profil, poche))
    if "questionnaire" in projete and "reponse_horizon" in poche:
        projete["questionnaire"]["reponses"]["horizon"] = poche["reponse_horizon"]
    if projete.get("decision_demo", {}).get("poche") != id_poche:
        projete.pop("decision_demo", None)
    projete["poche"] = resume_poche(poche)
    return projete


def portefeuille_global(poches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Somme des portefeuilles des poches pondérés par leur part (ordre de première apparition)."""
    totaux: dict[str, float] = {}
    for poche in poches:
        for ligne in poche["portefeuille"]:
            totaux[ligne["ticker"]] = totaux.get(ligne["ticker"], 0.0) + poche["part"] * ligne["poids"]
    return [{"ticker": ticker, "poids": round(poids, 10)} for ticker, poids in totaux.items()]


def ecarts_portefeuille_global(profil: dict[str, Any]) -> list[str]:
    """Titres dont le poids global diffère de la somme des poches (liste vide si cohérent)."""
    attendu = {ligne["ticker"]: ligne["poids"] for ligne in portefeuille_global(profil["poches"])}
    declare = {ligne["ticker"]: ligne["poids"] for ligne in profil["portefeuille"]}
    ecarts = []
    for ticker in [*attendu, *(t for t in declare if t not in attendu)]:
        poids_attendu, poids_declare = attendu.get(ticker, 0.0), declare.get(ticker, 0.0)
        if abs(poids_attendu - poids_declare) > TOLERANCE_PORTEFEUILLE_GLOBAL:
            ecarts.append(f"{ticker} {poids_declare:.4f} au lieu de {poids_attendu:.4f}")
    return ecarts
