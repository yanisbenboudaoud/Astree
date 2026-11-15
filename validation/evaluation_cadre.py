"""« Trompez le Greffier », côté cadre : conseils et promesses bloqués, arguments légitimes admis (#166).

Le Greffier refuse tout argument qui conseille une transaction ou promet quelque chose
sur l'avenir (``CLAUDE.md``, section 4 quater). Ici, ce contrôle est joué sur un jeu
écrit à l'avance (``validation/jeux/cadre.json``), avec la fonction du Greffier
(``pipeline.cadre_simulation.verifier_cadre_simulation``), dans les deux sens :

- Un cas **à bloquer** porte une tournure d'une seule famille d'infraction
  (``conseil`` ou ``promesse``, déclarée par sa famille de cas). Il est détecté si
  l'argument est rejeté **et** qu'une infraction de cette famille est relevée : un
  rejet pour l'autre famille seulement est un raté (``rejete_autre_motif``).
- Un cas **légitime** (citation, négation, conditionnel, interrogation indirecte…)
  doit être accepté ; un rejet est un faux rejet.
"""

from __future__ import annotations

from typing import Any

from pipeline.cadre_simulation import verifier_cadre_simulation
from validation.evaluation import ResultatCas, cellule, tableau_familles, taux


def jouer_cas(cas: dict[str, Any], famille: dict[str, Any]) -> ResultatCas:
    """Vérifie le texte d'un cas avec le contrôle du Greffier et le compare à l'attendu."""
    verification = verifier_cadre_simulation({"texte": cas["texte"]})
    attendu = famille["attendu"]

    if attendu == "accepte":
        obtenu = "accepte" if verification.valide else "rejete"
        detail = verification.motif or "accepté"
    elif verification.valide:
        obtenu = "accepte"
        detail = "accepté : aucune tournure interdite relevée"
    elif any(i.famille == famille["infraction"] for i in verification.infractions):
        obtenu = "rejete"
        detail = verification.motif
    else:
        obtenu = "rejete_autre_motif"
        detail = f"rejeté sans relever de {famille['infraction']} : {verification.motif}"
    return ResultatCas(cas["id"], cas["famille"], attendu, obtenu, obtenu == attendu, cas["texte"], detail)


def evaluer(jeu: dict[str, Any]) -> list[ResultatCas]:
    return [jouer_cas(cas, jeu["familles"][cas["famille"]]) for cas in jeu["cas"]]


AUTEURS = {
    "equipe": "cas de l'équipe",
    "externe": "cas écrits sans accès au code",
}


def _lignes_par_auteur(jeu: dict[str, Any], resultats: list[ResultatCas]) -> list[str]:
    """Taux de chaque groupe d'auteurs (``auteur`` d'un cas), s'il y en a plusieurs.

    Les cas écrits sans accès au code disent si le contrôle tient face à des tournures
    que ses auteurs n'ont pas anticipées.
    """
    auteurs = {cas["id"]: cas.get("auteur") for cas in jeu["cas"]}
    groupes = [a for a in AUTEURS if any(auteurs[r.id] == a for r in resultats)]
    if len(groupes) < 2:
        return []
    lignes = ["- **Par auteur** :"]
    for auteur in groupes:
        cas = [r for r in resultats if auteurs[r.id] == auteur]
        a_bloquer = [r for r in cas if r.attendu == "rejete"]
        legitimes = [r for r in cas if r.attendu == "accepte"]
        lignes.append(f"  - {AUTEURS[auteur]} : bloqués {taux(sum(r.ok for r in a_bloquer), len(a_bloquer))} ; "
                      f"légitimes admis {taux(sum(r.ok for r in legitimes), len(legitimes))}.")
    return lignes


def rapport(nom: str, jeu: dict[str, Any], resultats: list[ResultatCas]) -> str:
    """Rapport Markdown : taux globaux, par infraction, par famille, et chaque raté avec son texte."""
    familles = jeu["familles"]
    a_bloquer = [r for r in resultats if r.attendu == "rejete"]
    legitimes = [r for r in resultats if r.attendu == "accepte"]
    rates = [r for r in resultats if not r.ok]

    lignes = [
        f"# Évaluation : {jeu['titre']}",
        "",
        f"> Généré par `python -m validation.evaluation {nom}` à partir de `validation/jeux/{nom}.json` "
        f"(issue #{jeu['issue']}, jeu rédigé le {jeu['redige_le']}). Ne pas modifier à la main : "
        "relancer la commande.",
        "",
        jeu["description"],
        "",
        "## Résultat",
        "",
        f"- **Conseils et promesses bloqués** : {taux(sum(r.ok for r in a_bloquer), len(a_bloquer))}.",
    ]
    for infraction, nom_infraction in (("conseil", "conseils"), ("promesse", "promesses")):
        cas = [r for r in a_bloquer if familles[r.famille]["infraction"] == infraction]
        if cas:
            lignes.append(f"  - dont {nom_infraction} : {taux(sum(r.ok for r in cas), len(cas))}.")
    lignes += [
        f"- **Arguments légitimes admis** : {taux(sum(r.ok for r in legitimes), len(legitimes))} ; "
        f"faux rejets : {sum(not r.ok for r in legitimes)}.",
        *_lignes_par_auteur(jeu, resultats),
        "",
        f"{len(resultats)} cas. La borne basse de l'intervalle de Wilson dit ce que l'échantillon permet "
        "d'affirmer ; un taux de 100 % ne prouve pas l'infaillibilité.",
        "",
        "## Par famille",
        "",
        *tableau_familles(jeu, resultats),
        "",
        "## Ratés",
        "",
    ]
    if rates:
        lignes += ["| Cas | Famille | Texte | Résultat |", "|---|---|---|---|"]
        for r in rates:
            lignes.append(f"| `{r.id}` | `{r.famille}` | {cellule(r.texte)} | {cellule(r.detail)} |")
    else:
        lignes.append("Aucun raté.")
    lignes += ["", "## Familles", ""]
    for cle, famille in familles.items():
        if famille["attendu"] == "rejete":
            attendu = f"rejet attendu, infraction « {famille['infraction']} »"
        else:
            attendu = "acceptation attendue"
        lignes.append(f"- **{famille['libelle']}** (`{cle}`, {attendu}) : {famille['description']}")
    lignes += [
        "",
        "## Méthode",
        "",
        "- Contrôle : `pipeline.cadre_simulation.verifier_cadre_simulation`, le même que le Greffier "
        "applique aux arguments du Procureur, de l'Avocat et du contre-interrogatoire (`CLAUDE.md`, "
        "section 4 quater). Python seul, sans Bedrock.",
        "- Cas à bloquer détecté : argument rejeté **et** infraction de la famille attendue relevée. "
        "Cas légitime : accepté.",
        "- Intervalle de confiance : Wilson à 95 % (`validation.evaluation.intervalle_wilson`).",
        "- Un raté reste dans ce rapport. Une règle corrigée se mesure sur un second jeu, écrit après "
        "la correction.",
        "",
    ]
    return "\n".join(lignes)
