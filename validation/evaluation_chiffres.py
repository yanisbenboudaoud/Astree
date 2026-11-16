"""« Trompez le Greffier, 100 fois » : taux de détection de verifier_chiffres (#165).

L'écran « Trompez le Greffier » (#69) laisse l'utilisateur glisser un faux chiffre,
un à la fois. Ici, la même épreuve est jouée sur un jeu de cas écrit à l'avance
(``validation/jeux/chiffres.json``), construit sur les pièces des procès enregistrés
(``frontend/src/data/proces/``) : chaque texte est vérifié contre les pièces qu'il
cite, exactement comme le fait le Greffier (``pipeline.chiffres.verifier_argument``).

- Un **piège** porte un seul nombre fautif (``piege``, écrit tel que le vérificateur
  l'extrait). Il est détecté si l'argument est rejeté **et** que ce nombre est parmi
  les introuvables : un rejet pour un autre nombre est un raté.
- Un **argument valide** doit être accepté ; un rejet est un faux rejet.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pipeline.chiffres import Sources, correspond, detailler_argument, extraire_nombres, verifier_argument
from validation.evaluation import RACINE, ResultatCas, cellule, tableau_familles, taux

DOSSIER_PROCES = RACINE / "frontend" / "src" / "data" / "proces"


@lru_cache(maxsize=None)
def _contrat(proces_id: str) -> dict[str, Any]:
    return json.loads((DOSSIER_PROCES / f"{proces_id}.json").read_text(encoding="utf-8"))


def dossier_du_proces(proces_id: str, periode: list[str]) -> dict[str, Any]:
    """Le dossier tel que le Greffier le voit : décision, pièces et période d'analyse."""
    contrat = _contrat(proces_id)
    return {"decision": contrat["decision"], "pieces": contrat["pieces"], "periode": list(periode)}


def jouer_cas(cas: dict[str, Any], attendu: str, periode: list[str]) -> ResultatCas:
    """Vérifie le texte d'un cas contre ses pièces citées et le compare à l'attendu."""
    dossier = dossier_du_proces(cas["proces"], periode)
    argument = {"texte": cas["texte"], "pieces": cas["pieces"]}
    verification = verifier_argument(argument, dossier)

    if attendu == "accepte":
        obtenu = "accepte" if verification.valide else "rejete"
        detail = verification.motif or "accepté"
    elif verification.valide:
        obtenu = "accepte"
        detail = f"accepté : « {cas['piege']} » trouvé dans {', '.join(ou_est_trouve(cas['piege'], argument, dossier))}"
    elif cas["piege"] in {n.texte for n in verification.introuvables}:
        obtenu = "rejete"
        detail = verification.motif
    else:
        obtenu = "rejete_autre_motif"
        detail = f"rejeté sans relever « {cas['piege']} » : {verification.motif}"
    return ResultatCas(cas["id"], cas["famille"], attendu, obtenu, obtenu == attendu, cas["texte"], detail)


def ou_est_trouve(texte_nombre: str, argument: dict[str, Any], dossier: dict[str, Any]) -> list[str]:
    """Pour un nombre accepté : chaque source qui le contient, avec le champ de la pièce (« P2 (rendement_annuel_actuel) »)."""
    nombre = next(n for n in extraire_nombres(argument["texte"]) if n.texte == texte_nombre)
    trouve = next(n for n in detailler_argument(argument, dossier)["nombres"] if n["texte"] == texte_nombre)
    pieces = {piece["id"]: piece for piece in dossier["pieces"]}
    lieux = []
    for source in trouve["sources"]:
        if source not in pieces:  # « décision » ou « période »
            lieux.append(source)
            continue
        champs = []
        for champ, valeur in pieces[source]["valeurs"].items():
            valeurs = Sources()
            valeurs.ajouter(valeur)
            if correspond(nombre, valeurs):
                champs.append(champ)
        lieux.append(f"{source} ({', '.join(champs)})")
    return lieux


def evaluer(jeu: dict[str, Any]) -> list[ResultatCas]:
    return [jouer_cas(cas, jeu["familles"][cas["famille"]]["attendu"], jeu["periode"]) for cas in jeu["cas"]]


def rapport(nom: str, jeu: dict[str, Any], resultats: list[ResultatCas]) -> str:
    """Rapport Markdown : taux globaux, tableau par famille, chaque raté avec son motif."""
    familles = jeu["familles"]
    hors_promesse = {cle for cle, f in familles.items() if f.get("hors_promesse")}
    pieges = [r for r in resultats if r.attendu == "rejete" and r.famille not in hors_promesse]
    valides = [r for r in resultats if r.attendu == "accepte"]
    limites = [r for r in resultats if r.famille in hors_promesse]
    rates = [r for r in resultats if not r.ok]
    cas_par_id = {cas["id"]: cas for cas in jeu["cas"]}
    nb_proces = len({cas["proces"] for cas in jeu["cas"]})

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
        f"- **Chiffres inventés détectés** : {taux(sum(r.ok for r in pieges), len(pieges))}.",
        f"- **Arguments valides acceptés** : {taux(sum(r.ok for r in valides), len(valides))} ; "
        f"faux rejets : {sum(not r.ok for r in valides)}.",
    ]
    for cle in sorted(hors_promesse):
        cas = [r for r in limites if r.famille == cle]
        lignes.append(f"- **Limite connue, mesurée à part** ({familles[cle]['libelle'].lower()}) : "
                      f"{taux(sum(r.ok for r in cas), len(cas))} détectés.")
    lignes += [
        "",
        f"{len(resultats)} cas sur les pièces de {nb_proces} procès enregistrés. Un taux de 100 % sur "
        f"{len(pieges)} pièges ne prouve pas l'infaillibilité : la borne basse de l'intervalle "
        "de Wilson dit ce que l'échantillon permet d'affirmer.",
        "",
        "## Par famille",
        "",
        *tableau_familles(jeu, resultats),
        "",
        "## Ratés",
        "",
    ]
    if rates:
        lignes += ["| Cas | Famille | Texte | Pièces | Résultat |", "|---|---|---|---|---|"]
        for r in rates:
            pieces = ", ".join(cas_par_id[r.id]["pieces"])
            lignes.append(f"| `{r.id}` | `{r.famille}` | {cellule(r.texte)} | {pieces} | {cellule(r.detail)} |")
    else:
        lignes.append("Aucun raté.")
    lignes += ["", "## Familles", ""]
    for cle, famille in familles.items():
        attendu = "rejet attendu" if famille["attendu"] == "rejete" else "acceptation attendue"
        lignes.append(f"- **{famille['libelle']}** (`{cle}`, {attendu}) : {famille['description']}")
    lignes += [
        "",
        "## Méthode",
        "",
        "- Vérificateur : `pipeline.chiffres.verifier_argument`, le même que le Greffier et l'écran "
        "« Trompez le Greffier » (`REFERENCE_DU_PROJET.md`, section 4 ter).",
        f"- Dossier de chaque cas : décision et pièces du procès enregistré "
        f"(`frontend/src/data/proces/<id>.json`), période {jeu['periode'][0]} → {jeu['periode'][1]}.",
        "- Piège détecté : argument rejeté **et** nombre piège parmi les introuvables. "
        "Argument valide : accepté.",
        "- Intervalle de confiance : Wilson à 95 % (`validation.evaluation.intervalle_wilson`).",
        "- Un raté reste dans ce rapport. Une règle corrigée se mesure sur un second jeu, écrit après "
        "la correction.",
        "",
    ]
    return "\n".join(lignes)
