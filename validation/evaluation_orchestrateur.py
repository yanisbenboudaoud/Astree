"""L'orchestrateur et le débat mesurés sur les procès réellement tenus (#167).

L'orchestrateur Bedrock choisit lui-même ses outils (CLAUDE.md, section 4). Cette
évaluation relit les procès archivés par la Lambda dans S3 (``traces/<date>/<id>.json``)
et ceux de ``frontend/src/data/proces/``, **sans aucun appel à Bedrock**, et mesure :

- les outils demandés selon le profil et la décision ;
- les garde-fous : budget d'appels, simulation obligatoire ajoutée d'office, appels refusés ;
- le débat : arguments du Procureur et de l'Avocat renvoyés par le Greffier, corrigés ou rejetés ;
- les appels Bedrock visibles dans la trace.

Contrairement au jeu de #165, ces procès ne sont pas un échantillon planifié : le
rapport donne le nombre de procès lus et la date de lecture, et il change quand de
nouveaux procès sont archivés.

Usage : ``python -m validation.evaluation orchestrateur`` (S3 et procès locaux, avec les
identifiants de ``aws login``), ``python -m validation.evaluation orchestrateur --archive`` (la
copie de S3 versée au dépôt, ``validation/proces_tenus.tar.gz``, #191 : reproductible sans AWS)
ou ``python -m validation.evaluation orchestrateur --local`` (procès de l'interface seulement).
"""

from __future__ import annotations

import json
import os
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from pipeline.orchestrateur import BUDGET_APPELS, BUDGET_APPELS_QUESTION, PREFIXE_ERREUR, RAISON_D_OFFICE
from pipeline.simulation import NOM_OUTIL as SIMULATION
from validation.evaluation import RACINE, cellule, pourcentage, taux

DOSSIER_PROCES = RACINE / "frontend" / "src" / "data" / "proces"
PREFIXE_TRACES = "traces/"
MOTIF_BUDGET = "Budget d'appels atteint"

# Colonnes du tableau des outils, dans l'ordre de la section 4 bis ; un outil inconnu s'ajoute à la fin.
ORDRE_OUTILS = [
    "simuler_portefeuille", "indicateurs_actif", "calculer_correlations", "taille_max_compatible",
    "consulter_jurisprudence", "rechercher_documents", "mesurer_liquidite",
]
COTES = (("requisitoire", "procureur", "Procureur"), ("plaidoirie", "avocat", "Avocat"))


# --- Lecture ------------------------------------------------------------------------

def lire_proces_locaux() -> dict[str, dict[str, Any]]:
    """Procès rejoués par l'interface (``frontend/src/data/proces/<id>.json``)."""
    return {chemin.stem: json.loads(chemin.read_text(encoding="utf-8"))
            for chemin in sorted(DOSSIER_PROCES.glob("*.json")) if chemin.name != "index.json"}


def nom_bucket_projet(sts=None) -> str:
    """``BUCKET_PROJET`` s'il est défini, sinon ``alphaforge-<compte>`` (même nom que ``deploiement/deployer.py``)."""
    if os.environ.get("BUCKET_PROJET"):
        return os.environ["BUCKET_PROJET"]
    if sts is None:
        import boto3
        sts = boto3.client("sts")
    return f"alphaforge-{sts.get_caller_identity()['Account']}"


def lire_traces_s3(bucket: str, s3=None) -> dict[str, dict[str, Any]]:
    """Contrats archivés par la Lambda, lus dans ``traces/`` (lecture S3 seulement, jamais Bedrock)."""
    if s3 is None:
        import boto3
        s3 = boto3.client("s3")
    contrats = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=PREFIXE_TRACES):
        for objet in page.get("Contents", []):
            if objet["Key"].endswith(".json"):
                corps = s3.get_object(Bucket=bucket, Key=objet["Key"])["Body"].read()
                contrats[objet["Key"].rsplit("/", 1)[-1][:-5]] = json.loads(corps)
    return contrats


@dataclass
class Lecture:
    """Les procès lus, chacun une fois, et d'où ils viennent."""

    contrats: dict[str, dict[str, Any]]
    origines: dict[str, list[str]]  # id → ["S3", "interface"]
    date_lecture: str
    bucket: str | None
    archive: bool = False  # traces relues dans validation/proces_tenus.tar.gz, pas dans S3 (#191)


def rassembler(s3: dict[str, dict[str, Any]], locaux: dict[str, dict[str, Any]], date_lecture: str,
               bucket: str | None, archive: bool = False) -> Lecture:
    """Union des deux sources : un procès de l'interface est souvent une copie d'une trace S3."""
    contrats, origines = {}, {}
    for origine, source in (("S3", s3), ("interface", locaux)):
        for identifiant, contrat in source.items():
            contrats.setdefault(identifiant, contrat)
            origines.setdefault(identifiant, []).append(origine)
    ordre = sorted(contrats)
    return Lecture({i: contrats[i] for i in ordre}, {i: origines[i] for i in ordre}, date_lecture, bucket, archive)


# --- Lecture d'une trace ---------------------------------------------------------------

def est_d_office(etape: dict[str, Any]) -> bool:
    """Pièce ajoutée par Python (simulation obligatoire, points de bascule, composition) et non par le modèle."""
    return (etape.get("raison") or "").startswith(RAISON_D_OFFICE)


def est_refus(etape: dict[str, Any]) -> bool:
    sortie = etape.get("sortie")
    return isinstance(sortie, str) and sortie.startswith(PREFIXE_ERREUR)


def appels_orchestrateur(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in trace if e.get("etape") == "orchestrateur"]


def appels_du_modele(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Appels demandés par le modèle, refus compris (ils comptent dans le budget)."""
    return [e for e in appels_orchestrateur(trace) if not est_d_office(e)]


def simulation_complete_demandee(trace: list[dict[str, Any]]) -> bool:
    """Le modèle a-t-il obtenu lui-même la simulation complète de la décision ?"""
    return any(e["outil"] == SIMULATION and not est_refus(e) and (e.get("entree") or {}).get("periode") == "complete"
               for e in appels_du_modele(trace))


def simulation_ajoutee_d_office(trace: list[dict[str, Any]]) -> bool:
    return any(e["outil"] == SIMULATION and est_d_office(e) for e in appels_orchestrateur(trace))


def motif_general(sortie: str) -> str:
    """Motif d'un refus sans le titre (« Aucun document sur <titre> pour le critère … »)."""
    motif = sortie.removeprefix(PREFIXE_ERREUR)
    motif = re.sub(r"\bsur \S+ pour\b", "sur <titre> pour", motif)
    return re.sub(r"Outil « [^»]+ »", "Outil « <outil> »", motif)


def genre_motif(motif: str) -> str:
    """Pourquoi le Greffier renvoie un argument : chiffres, cadre (conseil ou promesse), ou les deux."""
    chiffres = "introuvable" in motif or "Pièce citée" in motif or "Aucune pièce citée" in motif
    cadre = "Conseil personnalisé" in motif or "Promesse ou prévision" in motif
    return "chiffres et cadre" if chiffres and cadre else "cadre" if cadre else "chiffres" if chiffres else "autre"


def groupe_profil(persona: str) -> str:
    """Les profils créés par le questionnaire (``investisseur_…``) sont regroupés."""
    return "questionnaire" if persona.startswith("investisseur_") else persona


def groupe_decision(decision: dict[str, Any]) -> str:
    """« position TSLA » (toutes tailles) ou « réallocation BTC-USD, ETH-USD, NVDA, QQQ »."""
    if decision.get("type") == "reallocation":
        return "réallocation " + ", ".join(sorted(ligne["ticker"] for ligne in decision["panier"]))
    return f"position {decision.get('ticker')}"


# --- Mesures ------------------------------------------------------------------------

@dataclass
class Cote:
    """Le débat d'un côté (Procureur ou Avocat), sur tous les procès."""

    proposes: int = 0
    renvoyes: int = 0
    corriges: int = 0       # renvoyés puis acceptés après la relance
    rejetes: int = 0        # dans ``arguments_rejetes``
    affiches: int = 0
    motifs: Counter = field(default_factory=Counter)


@dataclass
class Mesures:
    nb_proces: int
    outils_par_groupe: dict[tuple[str, str], tuple[int, Counter]]  # (profil, décision) → (N, procès par outil)
    outils_par_profil: dict[str, tuple[int, Counter]]
    outils: list[str]
    appels_par_proces: list[int]
    depassements_budget: int          # refus « Budget d'appels atteint »
    proces_dans_budget: int           # au plus BUDGET_APPELS appels demandés, aucun refus de budget
    simulation_spontanee: int
    simulation_d_office: int
    d_office: Counter                 # outil → pièces ajoutées d'office
    refus: Counter                    # motif général → nombre d'appels refusés
    appels_executes: int
    cotes: dict[str, Cote]
    questions: int
    questions_dans_budget: int
    appels_bedrock: list[int]
    calibrage: int


def mesurer(contrats: Iterable[dict[str, Any]]) -> Mesures:
    contrats = list(contrats)
    par_groupe: dict[tuple[str, str], list] = defaultdict(lambda: [0, Counter()])
    par_profil: dict[str, list] = defaultdict(lambda: [0, Counter()])
    vus: Counter = Counter()
    appels, d_office, refus = [], Counter(), Counter()
    depassements = dans_budget = spontanee = ajoutee = executes = 0
    cotes = {cote: Cote() for cote, _, _ in COTES}
    questions = questions_ok = calibrage = 0
    appels_bedrock = []

    for contrat in contrats:
        trace = contrat["trace"]
        du_modele = appels_du_modele(trace)
        outils = {e["outil"] for e in du_modele if not est_refus(e)}
        vus.update(e["outil"] for e in du_modele)
        for compteur in (par_groupe[(groupe_profil(contrat["persona"]), groupe_decision(contrat["decision"]))],
                         par_profil[groupe_profil(contrat["persona"])]):
            compteur[0] += 1
            compteur[1].update(outils)

        appels.append(len(du_modele))
        refus_budget = sum(1 for e in du_modele if est_refus(e) and e["sortie"].endswith(MOTIF_BUDGET))
        depassements += refus_budget
        dans_budget += len(du_modele) <= BUDGET_APPELS and refus_budget == 0
        spontanee += simulation_complete_demandee(trace)
        ajoutee += simulation_ajoutee_d_office(trace)
        d_office.update(e["outil"] for e in appels_orchestrateur(trace) if est_d_office(e))
        refus.update(motif_general(e["sortie"]) for e in du_modele if est_refus(e))
        executes += sum(1 for e in du_modele if not est_refus(e))
        calibrage += any(e.get("etape") == "calibrage" for e in trace)

        for cote, etape, _ in COTES:
            mesure = cotes[cote]
            initiaux = [e for e in trace if e.get("etape") == etape and e.get("outil") == "bedrock"]
            relances = [e for e in trace if e.get("etape") == etape and e.get("outil") == "bedrock_correction"]
            rejetes = sum(1 for a in contrat.get("arguments_rejetes", []) if a.get("cote") == cote)
            mesure.proposes += sum(len(e["sortie"]) for e in initiaux if isinstance(e["sortie"], list))
            mesure.renvoyes += len(relances)
            mesure.rejetes += rejetes
            mesure.corriges += len(relances) - rejetes
            mesure.affiches += len(contrat.get(cote, []))
            mesure.motifs.update(genre_motif(e["entree"]["motif"]) for e in relances)

        for question in contrat.get("contre_interrogatoire", []):
            questions += 1
            questions_ok += len(appels_du_modele(question.get("trace", []))) <= BUDGET_APPELS_QUESTION
        appels_bedrock.append(sum(1 for e in trace if str(e.get("outil", "")).startswith("bedrock")))

    outils = [o for o in ORDRE_OUTILS if o in vus] + sorted(set(vus) - set(ORDRE_OUTILS))
    return Mesures(
        nb_proces=len(contrats),
        outils_par_groupe={k: (v[0], v[1]) for k, v in par_groupe.items()},
        outils_par_profil={k: (v[0], v[1]) for k, v in par_profil.items()},
        outils=outils, appels_par_proces=appels, depassements_budget=depassements,
        proces_dans_budget=dans_budget, simulation_spontanee=spontanee, simulation_d_office=ajoutee,
        d_office=d_office, refus=refus, appels_executes=executes, cotes=cotes, questions=questions,
        questions_dans_budget=questions_ok, appels_bedrock=appels_bedrock, calibrage=calibrage,
    )


# --- Rapport --------------------------------------------------------------------------

def _tableau_outils(titre_ligne: str, lignes: list[tuple[str, int, Counter]], outils: list[str]) -> list[str]:
    entete = [f"| {titre_ligne} | Procès | " + " | ".join(f"`{o}`" for o in outils) + " |",
              "|---|---|" + "---|" * len(outils)]
    corps = [f"| {cellule(nom)} | {n} | " + " | ".join(_part(compteur[o], n) for o in outils) + " |"
             for nom, n, compteur in lignes]
    return entete + corps


def outils_reserves(mesures: Mesures) -> dict[str, list[str]]:
    """Outils que le modèle n'a demandés que pour certains profils : outil → ces profils."""
    profils = mesures.outils_par_profil
    reserves = {}
    for outil in mesures.outils:
        avec = sorted(p for p, (_, compteur) in profils.items() if compteur[outil])
        if 0 < len(avec) < len(profils):
            reserves[outil] = avec
    return reserves


def _outils_reserves(mesures: Mesures) -> list[str]:
    reserves = outils_reserves(mesures)
    if not reserves:
        return []
    return ["Demandés pour certains profils seulement : "
            + " ; ".join(f"`{o}` ({', '.join(p)})" for o, p in reserves.items()) + ".", ""]


def _part(k: int, n: int) -> str:
    return "—" if k == 0 else f"{k}/{n} ({pourcentage(k / n)})"


def _repartition(valeurs: list[int]) -> str:
    mediane = f"{statistics.median(valeurs):g}".replace(".", ",")
    return f"min. {min(valeurs)}, médiane {mediane}, max. {max(valeurs)}"


def outils_obtenus(contrat: dict[str, Any]) -> list[str]:
    """Outils dont le modèle a obtenu une pièce, dans l'ordre de la section 4 bis."""
    obtenus = {e["outil"] for e in appels_du_modele(contrat["trace"]) if not est_refus(e)}
    return [o for o in ORDRE_OUTILS if o in obtenus] + sorted(obtenus - set(ORDRE_OUTILS))


def section_plan(lecture: Lecture, plan: dict[str, Any], resultats: list[dict[str, Any]]) -> list[str]:
    """Le plan de procès (même décision pour chaque profil, répétée) : outils, stabilité, durée."""
    tenus = [r for r in resultats if r["statut"] == 200 and r.get("proces_id") in lecture.contrats]
    echecs = [r for r in resultats if r["statut"] != 200]
    nb_cases = len(plan["decisions"]) * len(plan["profils"]) * plan["repetitions"]
    lignes = [
        "## Plan de procès : même décision, profils différents",
        "",
        f"{plan['description']} Plan : `validation/jeux/plan_proces.json` ; tenu par `python -m validation.plan_proces`. "
        f"Coût estimé avant de le tenir : {plan['cout_estime']}"
        + (f" Coût mesuré, {plan['cout_mesure']}" if plan.get("cout_mesure") else ""),
        "",
        f"{len(tenus)} procès sur {nb_cases} lus ; envois en échec : {len(echecs)}"
        + (f" ({', '.join(sorted({str(r['statut']) for r in echecs}))})" if echecs else "") + ".",
        "",
    ]
    if not tenus:
        return lignes + ["Aucun procès du plan n'a pu être lu (S3 non lu, ou plan pas encore tenu).", ""]

    par_case: dict[tuple[str, str], dict[int, dict[str, Any]]] = defaultdict(dict)
    for r in tenus:
        par_case[(r["decision"], r["profil"])][r["repetition"]] = r
    demandes = {d["id"]: d["demande"] for d in plan["decisions"]}
    repetitions = range(1, plan["repetitions"] + 1)
    lignes += [
        "| Décision | Profil | " + " | ".join(f"Outils, répétition {k}" for k in repetitions) + " | Mêmes outils | Durée (s) |",
        "|---|---|" + "---|" * plan["repetitions"] + "---|---|",
    ]
    stables = comparables = 0
    for decision in plan["decisions"]:
        for profil in plan["profils"]:
            essais = par_case.get((decision["id"], profil), {})
            ensembles = {k: outils_obtenus(lecture.contrats[r["proces_id"]]) for k, r in essais.items()}
            cellules = [", ".join(f"`{o}`" for o in ensembles[k]) if k in ensembles else "non tenu" for k in repetitions]
            if len(ensembles) == plan["repetitions"]:
                comparables += 1
                identiques = len({tuple(e) for e in ensembles.values()}) == 1
                stables += identiques
                meme = "oui" if identiques else "non"
            else:
                meme = "—"
            durees = " ; ".join(f"{essais[k]['duree_s']:g}".replace(".", ",") for k in repetitions if k in essais)
            lignes.append(f"| {cellule(demandes[decision['id']])} | {profil} | " + " | ".join(cellules)
                          + f" | {meme} | {durees} |")
    durees = [r["duree_s"] for r in tenus]
    lignes += [
        "",
        f"- Mêmes outils d'une répétition à l'autre : " + (taux(stables, comparables) if comparables else "sans objet") + ".",
        f"- Durée d'un procès, mesurée côté client (envoi → contrat) : {_repartition_durees(durees)} s.",
        "- Ces procès sont aussi comptés dans les tableaux ci-dessus, avec les procès archivés.",
        "",
    ]
    return lignes


def _repartition_durees(durees: list[float]) -> str:
    def nombre(x: float) -> str:
        return f"{x:.1f}".replace(".", ",")
    return f"min. {nombre(min(durees))}, médiane {nombre(statistics.median(durees))}, max. {nombre(max(durees))}"


def rapport(lecture: Lecture, mesures: Mesures, plan: dict[str, Any] | None = None,
            resultats_plan: list[dict[str, Any]] | None = None) -> str:
    m = mesures
    n = m.nb_proces
    depuis_s3 = sum("S3" in o for o in lecture.origines.values())
    locaux = sum("interface" in o for o in lecture.origines.values())
    dates = sorted(i[:10] for i in lecture.contrats)
    commande = "python -m validation.evaluation orchestrateur" + (
        " --archive" if lecture.archive else "" if lecture.bucket else " --local")
    lieu_s3 = (f"`validation/proces_tenus.tar.gz`, copie de `s3://{lecture.bucket}/{PREFIXE_TRACES}`"
               if lecture.archive else f"`s3://{lecture.bucket}/{PREFIXE_TRACES}`")
    source = (f"{lieu_s3} ({depuis_s3} procès) et `frontend/src/data/proces/` "
              f"({locaux} procès, dont {sum(o == ['interface'] for o in lecture.origines.values())} absents de S3)"
              if lecture.bucket else f"`frontend/src/data/proces/` seulement ({locaux} procès ; S3 non lu)")

    lignes = [
        "# Évaluation : l'orchestrateur et le débat mesurés sur les procès tenus",
        "",
        f"> Généré par `{commande}` (issue #167). **Lu le {lecture.date_lecture}** : {n} procès distincts, "
        f"tenus du {dates[0]} au {dates[-1]}, lus dans {source}. Aucun appel à Bedrock : les traces "
        "sont relues telles qu'archivées. Le rapport change quand de nouveaux procès sont archivés.",
        "",
        "**Limite** : ces procès ne sont pas un échantillon planifié. Ce sont les procès lancés pendant le "
        "développement et les démonstrations, dominés par quelques décisions répétées (voir le tableau "
        "profil × décision). Les taux décrivent ces procès, pas le comportement du modèle sur toutes les "
        "décisions possibles. Le plan de procès, plus bas, est un petit échantillon planifié : la même "
        "décision jugée pour chaque profil.",
        "",
        "## En bref",
        "",
        f"- **Budget de {BUDGET_APPELS} appels respecté** : {taux(m.proces_dans_budget, n)} ; "
        f"refus pour budget dépassé : {m.depassements_budget}. Appels demandés par procès : "
        f"{_repartition(m.appels_par_proces)}.",
        f"- **Simulation obligatoire demandée par le modèle lui-même** : {taux(m.simulation_spontanee, n)} ; "
        f"oubliée puis ajoutée d'office par Python : {m.simulation_d_office}/{n}.",
        f"- **Appels refusés** : {sum(m.refus.values())} sur {sum(m.appels_par_proces)} appels demandés "
        "(détail plus bas).",
    ]
    for cote, _, nom in COTES:
        c = m.cotes[cote]
        lignes.append(
            f"- **{nom}** : {c.proposes} arguments proposés ; renvoyés par le Greffier : {taux(c.renvoyes, c.proposes)} ; "
            f"corrigés après renvoi : " + (taux(c.corriges, c.renvoyes) if c.renvoyes else "aucun renvoi")
            + f" ; rejetés : {c.rejetes}.")
    lignes += [
        "",
        "## Les outils changent avec le Pacte et la décision",
        "",
        "Part des procès où le modèle a obtenu au moins une pièce de chaque outil (appels refusés exclus ; "
        "pièces ajoutées d'office par Python exclues). « — » : jamais demandé.",
        "",
        "### Par profil (Pacte)",
        "",
        *_tableau_outils("Profil", [(p, k, c) for p, (k, c) in sorted(m.outils_par_profil.items(),
                                                                         key=lambda t: (-t[1][0], t[0]))],
                         m.outils),
        "",
        *_outils_reserves(m),
        "### Par profil et par décision",
        "",
        *_tableau_outils("Profil · décision",
                         [(f"{p} · {d}", k, c) for (p, d), (k, c) in sorted(m.outils_par_groupe.items(),
                                                                              key=lambda t: (-t[1][0], t[0]))],
                         m.outils),
        "",
        *(section_plan(lecture, plan, resultats_plan or []) if plan else []),
        "## Garde-fous de l'orchestrateur",
        "",
        f"- Appels exécutés : {m.appels_executes} ; refusés : {sum(m.refus.values())}.",
        f"- Pièces ajoutées d'office par Python : "
        + (", ".join(f"`{o}` {k}" for o, k in sorted(m.d_office.items())) or "aucune")
        + ". `points_de_bascule` est ajoutée dès qu'une règle calculable est en violation (#61), "
        "`composition_fnb` quand un plafond porte sur une catégorie lue par transparence (#116).",
        f"- Procès avec Pacte vécu (étape `calibrage`) : {m.calibrage}/{n}.",
        f"- Contre-interrogatoire : {m.questions} questions ; budget de {BUDGET_APPELS_QUESTION} appels respecté : "
        + (f"{m.questions_dans_budget}/{m.questions}." if m.questions else "sans objet."),
        "",
        "### Appels refusés, par motif",
        "",
    ]
    if m.refus:
        lignes += ["| Motif | Appels |", "|---|---|"]
        lignes += [f"| {cellule(motif)} | {k} |" for motif, k in sorted(m.refus.items(), key=lambda t: (-t[1], t[0]))]
    else:
        lignes.append("Aucun appel refusé.")
    lignes += [
        "",
        "## Le débat",
        "",
        "Un argument renvoyé l'est une fois à son agent avec le motif exact (`CLAUDE.md`, sections 4 ter et "
        "4 quater) ; s'il échoue encore, il va dans `arguments_rejetes`.",
        "",
        "| Côté | Proposés | Renvoyés | Corrigés après renvoi | Rejetés | Affichés | Motifs des renvois |",
        "|---|---|---|---|---|---|---|",
    ]
    for cote, _, nom in COTES:
        c = m.cotes[cote]
        motifs = ", ".join(f"{g} {k}" for g, k in sorted(c.motifs.items())) or "—"
        corriges = taux(c.corriges, c.renvoyes) if c.renvoyes else "—"
        lignes.append(f"| {nom} | {c.proposes} | {taux(c.renvoyes, c.proposes)} | {corriges} | {c.rejetes} "
                      f"| {c.affiches} | {motifs} |")
    lignes += [
        "",
        "## Appels Bedrock et durée",
        "",
        f"- Appels Bedrock visibles dans la trace (Agent Profil, Procureur, Avocat et leurs relances) : "
        f"{_repartition(m.appels_bedrock)} par procès, {sum(m.appels_bedrock)} en tout.",
        "- Non mesurables ici : les tours de conversation de l'orchestrateur (la trace garde les appels "
        "d'outils, pas les tours Bedrock, et un tour peut demander plusieurs outils) et les jetons consommés. "
        "La trace archivée ne contient ni horodatage ni compteur de jetons : la durée n'est mesurée que pour "
        "les procès du plan, côté client.",
        "",
        "## Méthode",
        "",
        "- Un appel « demandé par le modèle » est une étape `orchestrateur` de la trace dont la raison ne "
        f"commence pas par « {RAISON_D_OFFICE} » ; les refus en font partie, car ils comptent dans le budget.",
        "- Simulation obligatoire : `simuler_portefeuille` sur la période complète, réussie.",
        "- Débat : arguments proposés = sortie du premier appel Bedrock de chaque côté ; renvoyés = étapes "
        "`bedrock_correction` ; corrigés = renvoyés moins rejetés.",
        "- Intervalles : Wilson à 95 % (`validation.evaluation.intervalle_wilson`).",
        "",
        "<details><summary>Procès lus</summary>",
        "",
        *[f"- `{i}` ({', '.join(o)}) : {cellule(lecture.contrats[i]['persona'])}, "
          f"{cellule(lecture.contrats[i]['decision'].get('libelle', ''))}" for i, o in lecture.origines.items()],
        "",
        "</details>",
        "",
    ]
    return "\n".join(lignes)


# --- Commande ---------------------------------------------------------------------------

def lire(local_seulement: bool = False, archive: bool = False) -> Lecture:
    locaux = lire_proces_locaux()
    if local_seulement:
        return rassembler({}, locaux, date.today().isoformat(), None)
    if archive:
        # La date de lecture est celle de la copie : le rapport se régénère à l'identique (#191).
        from validation.archive_proces import traces_archivees
        traces, manifeste = traces_archivees()
        return rassembler(traces, locaux, manifeste["lu_le"][:10], manifeste["bucket"], archive=True)
    bucket = nom_bucket_projet()
    return rassembler(lire_traces_s3(bucket), locaux, date.today().isoformat(), bucket)


def executer(arguments: list[str]) -> tuple[str, str]:
    """Lit les procès, écrit le rapport ; rend le chemin et un résumé d'une ligne."""
    from validation.plan_proces import charger_plan, charger_resultats

    lecture = lire(local_seulement="--local" in arguments, archive="--archive" in arguments)
    mesures = mesurer(lecture.contrats.values())
    chemin = RACINE / "docs" / "validation" / "evaluation_orchestrateur.md"
    chemin.write_text(rapport(lecture, mesures, charger_plan(), charger_resultats()), encoding="utf-8")
    if "--local" not in arguments:
        # Bulletin du Greffier (#172) : seulement sur une lecture complète (S3 ou sa copie archivée),
        # pour qu'une lecture locale de quelques procès n'écrase pas la mesure faite sur tous les procès.
        from validation.bulletin import mesure_orchestrateur, ranger_mesure
        ranger_mesure(*mesure_orchestrateur(mesures, lecture.date_lecture))
    return str(chemin.relative_to(RACINE)), f"{mesures.nb_proces} procès lus le {lecture.date_lecture}"
