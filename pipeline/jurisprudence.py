"""Jurisprudence : les verdicts passés du même Pacte, versés au dossier (#56).

La route ``/verdict`` de la Lambda (#13) archive chaque procès avec le choix de
l'utilisateur (``maintenu``, ``modifie`` ou ``pacte_ajuste``) dans
``verdicts/<profil>/<id>.json``. Cet outil relit ces archives et compte, règle
par règle, les violations passées et ce que l'utilisateur en a fait. Le système
a ainsi une mémoire : « vous avez déjà maintenu une décision qui violait cette
règle ».

Comme les autres outils, il ne fait que compter : aucun LLM. Les archives
lues sont celles du profil jugé, et de lui seul : le modèle choisit seulement
la règle à examiner. Sans archive, la pièce le dit (« aucun procès archivé ») ;
rien n'est inventé.

Source des archives, par ``SOURCE_DONNEES`` (comme ``pipeline/donnees.py``) :
- ``local`` : dossier ``archives/verdicts/<profil>/`` du dépôt (ignoré par Git) ;
- ``s3`` : préfixe ``verdicts/<profil>/`` du bucket nommé par ``BUCKET_PROJET``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from pipeline.donnees import ErreurDonnees
from pipeline.llm import decrire_outil

NOM_OUTIL = "consulter_jurisprudence"
PREFIXE_VERDICTS = "verdicts/"
DOSSIER_VERDICTS_LOCAL = Path(__file__).resolve().parent.parent / "archives" / "verdicts"
TOUTES = "toutes"  # valeur du paramètre « regle » : toutes les règles du Pacte
VERDICTS = ("maintenu", "modifie", "pacte_ajuste")  # REFERENCE_DU_PROJET.md, section 5
LIMITE_ARCHIVES = 200  # archives lues au plus (les plus récentes) : borne la durée du procès
NB_ANTECEDENTS_MAX = 5  # antécédents détaillés dans la pièce (les plus récents)


def cle_verdict(persona: str, identifiant: str) -> str:
    """Clé S3 de l'archive d'un verdict, rangée par profil pour être relue par profil."""
    return f"{PREFIXE_VERDICTS}{persona}/{identifiant}.json"


# --- Lecture des archives ---------------------------------------------------------


def charger_archives(persona: str) -> list[tuple[str, dict[str, Any]]]:
    """Archives de verdicts du profil, ``(identifiant, contrat)``, les plus récentes d'abord.

    Raises:
        ErreurDonnees: source inconnue ou archive S3 illisible.
    """
    source = os.environ.get("SOURCE_DONNEES", "local")
    if source == "local":
        return _archives_locales(DOSSIER_VERDICTS_LOCAL / persona)
    if source == "s3":
        return _archives_s3(persona)
    raise ErreurDonnees(f"SOURCE_DONNEES doit valoir « local » ou « s3 », pas « {source} »")


def _archives_locales(dossier: Path) -> list[tuple[str, dict[str, Any]]]:
    if not dossier.is_dir():
        return []
    fichiers = sorted(dossier.glob("*.json"), reverse=True)[:LIMITE_ARCHIVES]
    return [(fichier.stem, json.loads(fichier.read_text(encoding="utf-8"))) for fichier in fichiers]


def _archives_s3(persona: str) -> list[tuple[str, dict[str, Any]]]:
    bucket = os.environ.get("BUCKET_PROJET")
    if not bucket:
        raise ErreurDonnees("SOURCE_DONNEES=s3 demande la variable BUCKET_PROJET (nom du bucket)")
    prefixe = f"{PREFIXE_VERDICTS}{persona}/"
    client = boto3.client("s3")
    try:
        cles = [objet["Key"]
                for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefixe)
                for objet in page.get("Contents", [])]
        # L'identifiant commence par la date : l'ordre des clés est l'ordre chronologique.
        cles = sorted(cles, reverse=True)[:LIMITE_ARCHIVES]
        return [(Path(cle).stem, json.loads(client.get_object(Bucket=bucket, Key=cle)["Body"].read()))
                for cle in cles]
    except (ClientError, BotoCoreError) as erreur:
        raise ErreurDonnees(f"Archives de verdicts illisibles dans s3://{bucket}/{prefixe} : {erreur}") from erreur


# --- Calcul de la pièce -----------------------------------------------------------


def resumer_archive(identifiant: str, archive: dict[str, Any]) -> dict[str, Any]:
    """Un antécédent : date du procès, décision, règles du Pacte violées, verdict.

    Seuls les contrôles des règles du Pacte archivé comptent (pas ceux du
    système, comme ``verifier_chiffres``).
    """
    regles = {regle["id"] for regle in archive.get("pacte", {}).get("regles", [])}
    decision = archive.get("decision") or {}
    return {
        "date": identifiant[:10],
        "decision": decision.get("libelle", ""),
        "regles_violees": [controle["regle"] for controle in archive.get("controles", [])
                           if controle.get("statut") == "violation" and controle.get("regle") in regles],
        "verdict": archive.get("verdict"),
    }


def piece_jurisprudence(archives: list[tuple[str, dict[str, Any]]], regle: str = TOUTES) -> dict[str, Any]:
    """Pièce (sans id) : procès archivés, violations de la règle et verdicts choisis.

    Args:
        archives: ``(identifiant, contrat archivé)``, les plus récentes d'abord.
        regle: ``id`` d'une règle du Pacte, ou ``TOUTES`` (toute règle du Pacte).
    """
    antecedents = [resumer_archive(identifiant, archive) for identifiant, archive in archives
                   if archive.get("verdict") in VERDICTS]

    def viole(antecedent: dict[str, Any]) -> bool:
        violees = antecedent["regles_violees"]
        return bool(violees) if regle == TOUTES else regle in violees

    en_violation = [antecedent for antecedent in antecedents if viole(antecedent)]
    detailles = en_violation[:NB_ANTECEDENTS_MAX]
    # Le contrat n'admet que des listes de valeurs simples : un antécédent = même rang dans chaque liste.
    valeurs: dict[str, Any] = {
        "regle": regle,
        "proces_archives": len(antecedents),
        "proces_en_violation": len(en_violation),
        **{verdict: sum(1 for a in en_violation if a["verdict"] == verdict) for verdict in VERDICTS},
        "dates_antecedents": [a["date"] for a in detailles],
        "decisions_antecedents": [a["decision"] for a in detailles],
        "regles_violees_antecedents": [", ".join(a["regles_violees"]) for a in detailles],
        "verdicts_antecedents": [a["verdict"] for a in detailles],
    }
    return {
        "type": "calculee",
        "etiquette": "fait",
        "titre": "Jurisprudence : verdicts passés de ce profil"
        + ("" if regle == TOUTES else f" sur la règle « {regle} »"),
        "outil": NOM_OUTIL,
        "valeurs": valeurs,
        "valeur_affichee": valeur_affichee(valeurs),
        "source": "Archive des verdicts du Tribunal (verdicts/<profil>/), écrite par la route /verdict "
                  "quand l'utilisateur rend son verdict",
        "traitement": "Pour chaque procès archivé de ce profil : règles du Pacte en violation et verdict "
                      f"choisi par l'utilisateur. Au plus les {LIMITE_ARCHIVES} procès les plus récents ; "
                      f"les {NB_ANTECEDENTS_MAX} derniers antécédents en violation sont détaillés.",
        "limites": "Seuls les procès dont l'utilisateur a rendu un verdict sont archivés. Les règles sont "
                   "comparées par identifiant : le Pacte a pu changer depuis. Un verdict passé ne dit rien "
                   "de la qualité de la décision prise.",
    }


def valeur_affichee(valeurs: dict[str, Any]) -> str:
    """« 3 procès archivés · 2 en violation : 1 maintenu, 1 modifié, 0 Pacte ajusté »."""
    total = valeurs["proces_archives"]
    if total == 0:
        return "Aucun procès archivé pour ce profil"
    texte = f"{total} procès archivé{'s' if total > 1 else ''}"
    if valeurs["proces_en_violation"] == 0:
        return texte + " · aucun en violation"
    def compte(nombre: int, mot: str) -> str:
        return f"{nombre} {mot}{'s' if nombre > 1 else ''}"

    return (f"{texte} · {valeurs['proces_en_violation']} en violation : {compte(valeurs['maintenu'], 'maintenu')}, "
            f"{compte(valeurs['modifie'], 'modifié')}, {compte(valeurs['pacte_ajuste'], 'Pacte ajusté')}")


def decrire_consulter_jurisprudence(ids_regles: list[str]) -> dict[str, Any]:
    """Description de l'outil pour l'orchestrateur Bedrock (règles du Pacte jugé)."""
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["regle"],
        "properties": {
            "regle": {
                "type": "string",
                "enum": [*ids_regles, TOUTES],
                "description": f"Identifiant d'une règle du Pacte, ou « {TOUTES} » pour toute règle",
            },
        },
    }
    return decrire_outil(
        NOM_OUTIL,
        "Consulte les procès passés de ce même profil, archivés avec le verdict de l'utilisateur : "
        "combien ont violé une règle du Pacte, et si l'utilisateur a alors maintenu sa décision, l'a "
        "modifiée ou a ajusté son Pacte. Utile quand une règle est probablement violée par la "
        "décision : un antécédent montre si ce conflit se répète. Sans archive, l'outil le dit.",
        schema,
    )
