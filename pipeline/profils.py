"""Profils créés par les utilisateurs (#87) : rangement, relecture et signature.

Les profils de démonstration sont des fichiers ``personas/<id>.json`` versionnés.
Un profil construit par le questionnaire (#84) n'est pas versionné : il est
rangé à part, sous un identifiant généré ici (jamais tiré d'un nom saisi), pour
que le procès, le contre-interrogatoire, la jurisprudence et le procès-verbal le
retrouvent. Il ne peut donc jamais écraser un profil de démonstration.

Emplacement, par ``SOURCE_DONNEES`` (comme ``pipeline/donnees.py`` et la
jurisprudence) :
- ``local`` : dossier ``archives/profils/`` du dépôt (ignoré par Git) ;
- ``s3`` : préfixe ``profils/`` du bucket nommé par ``BUCKET_PROJET``.

Avant de signer, l'utilisateur peut changer un seuil calculé par le barème
(``appliquer_modifications``) : la règle garde son type, et sa justification dit
« Choisi par vous » avec la valeur que le barème avait proposée. Aucun LLM.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from pipeline.donnees import ErreurDonnees
from pipeline.pacte import DOSSIER_PERSONAS, erreurs_profil
from pipeline.questionnaire import ReponsesInvalides
from pipeline.simulation import formater_pourcentage

PREFIXE_PROFILS = "profils/"
DOSSIER_PROFILS_LOCAL = Path(__file__).resolve().parent.parent / "archives" / "profils"
PREFIXE_IDENTIFIANT = "investisseur_"
# Seuls les seuils calculés peuvent être changés : une règle documentaire ou qualitative
# n'a pas de nombre à choisir.
CHAMP_MODIFIABLE = {"pire_baisse_max": "seuil", "plafond": "max"}


class ProfilDejaExistant(Exception):
    """L'identifiant est déjà pris (profil de démonstration ou profil déjà rangé)."""


def nouvel_identifiant_profil() -> str:
    """« investisseur_3f9a0c1b2d4e » : même format que l'« id » d'un profil, et unique."""
    return f"{PREFIXE_IDENTIFIANT}{uuid.uuid4().hex[:12]}"


def cle_profil(identifiant: str) -> str:
    return f"{PREFIXE_PROFILS}{identifiant}.json"


# --- Lecture et écriture --------------------------------------------------------------


def lire_profil_cree(identifiant: str) -> dict[str, Any] | None:
    """Le profil rangé sous cet identifiant, tel quel (non validé), ou None s'il n'existe pas.

    Raises:
        ErreurDonnees: source inconnue, bucket absent ou profil illisible.
    """
    source = _source()
    if source == "local":
        chemin = DOSSIER_PROFILS_LOCAL / f"{identifiant}.json"
        return json.loads(chemin.read_text(encoding="utf-8")) if chemin.is_file() else None
    bucket = _bucket()
    try:
        objet = boto3.client("s3").get_object(Bucket=bucket, Key=cle_profil(identifiant))
        return json.loads(objet["Body"].read())
    except ClientError as erreur:
        if erreur.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return None
        raise ErreurDonnees(f"Profil illisible dans s3://{bucket}/{cle_profil(identifiant)} : {erreur}") from erreur
    except (BotoCoreError, json.JSONDecodeError) as erreur:
        raise ErreurDonnees(f"Profil illisible dans s3://{bucket}/{cle_profil(identifiant)} : {erreur}") from erreur


def enregistrer_profil(profil: dict[str, Any]) -> str:
    """Range un profil créé ; renvoie son emplacement (chemin local ou URI S3).

    Le profil doit être valide (``erreurs_profil``). Il n'écrase jamais rien : ni un
    profil de ``personas/``, ni un profil déjà rangé sous le même identifiant.

    Raises:
        ReponsesInvalides: profil refusé par ``erreurs_profil``.
        ProfilDejaExistant: identifiant déjà pris.
        ErreurDonnees: source inconnue, bucket absent ou écriture impossible.
    """
    identifiant = profil.get("id")
    erreurs = erreurs_profil(profil, nom_fichier=identifiant)
    if erreurs:
        raise ReponsesInvalides(erreurs)
    if (DOSSIER_PERSONAS / f"{identifiant}.json").exists():
        raise ProfilDejaExistant(f"« {identifiant} » est un profil de démonstration")
    contenu = json.dumps(profil, ensure_ascii=False, indent=2) + "\n"

    if _source() == "local":
        DOSSIER_PROFILS_LOCAL.mkdir(parents=True, exist_ok=True)
        chemin = DOSSIER_PROFILS_LOCAL / f"{identifiant}.json"
        try:
            with open(chemin, "x", encoding="utf-8") as fichier:
                fichier.write(contenu)
        except FileExistsError as erreur:
            raise ProfilDejaExistant(f"Un profil « {identifiant} » existe déjà") from erreur
        return str(chemin)

    bucket, cle = _bucket(), cle_profil(identifiant)
    try:
        boto3.client("s3").put_object(Bucket=bucket, Key=cle, Body=contenu.encode("utf-8"),
                                      ContentType="application/json; charset=utf-8", IfNoneMatch="*")
    except ClientError as erreur:
        if erreur.response.get("Error", {}).get("Code") in ("PreconditionFailed", "412"):
            raise ProfilDejaExistant(f"Un profil « {identifiant} » existe déjà") from erreur
        raise ErreurDonnees(f"Profil non enregistré dans s3://{bucket}/{cle} : {erreur}") from erreur
    except BotoCoreError as erreur:
        raise ErreurDonnees(f"Profil non enregistré dans s3://{bucket}/{cle} : {erreur}") from erreur
    return f"s3://{bucket}/{cle}"


# --- Signature : seuils choisis par l'utilisateur ------------------------------------------


def appliquer_modifications(profil: dict[str, Any], modifications: dict[str, Any], date_signature: str) -> dict[str, Any]:
    """Copie du profil où l'utilisateur a choisi lui-même certains seuils du Pacte.

    Args:
        profil: profil produit par ``profil_depuis_reponses``.
        modifications: ``{"<id de règle>": <nouvelle valeur>}`` ; seuil négatif pour
            ``pire_baisse_max`` (−0.2 = −20 %), part entre 0 et 1 pour ``plafond``.
        date_signature: date du choix (AAAA-MM-JJ), citée dans la justification.

    Raises:
        ReponsesInvalides: règle inconnue, règle sans seuil à choisir, ou valeur hors bornes.
    """
    regles = {regle["id"]: regle for regle in profil["pacte"]["regles"]}
    erreurs = []
    for id_regle, valeur in modifications.items():
        regle = regles.get(id_regle)
        if regle is None:
            erreurs.append(f"Règle inconnue : « {id_regle} »")
        elif regle["type"] not in CHAMP_MODIFIABLE:
            erreurs.append(f"La règle « {id_regle} » n'a pas de seuil à choisir")
        elif isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
            erreurs.append(f"Valeur invalide pour « {id_regle} » : un nombre décimal")
        elif regle["type"] == "pire_baisse_max" and not -1 <= valeur < 0:
            erreurs.append(f"Seuil invalide pour « {id_regle} » : entre −1 et 0 (−0.2 = −20 %)")
        elif regle["type"] == "plafond" and not 0 <= valeur <= 1:
            erreurs.append(f"Plafond invalide pour « {id_regle} » : entre 0 et 1 (0.25 = 25 %)")
    if erreurs:
        raise ReponsesInvalides(erreurs)

    modifie = json.loads(json.dumps(profil))
    for regle in modifie["pacte"]["regles"]:
        if regle["id"] not in modifications:
            continue
        champ = CHAMP_MODIFIABLE[regle["type"]]
        avant, apres = regle[champ], float(modifications[regle["id"]])
        if apres == avant:
            continue
        regle[champ] = apres
        regle["libelle"] = _libelle_modifie(regle, apres)
        regle["justification"] = (
            f"Choisi par vous le {date_signature} : {_texte_valeur(regle['type'], apres)} au lieu de "
            f"{_texte_valeur(regle['type'], avant)} proposé par le barème. Barème : {regle['justification']}"
        )
    return modifie


def _texte_valeur(type_regle: str, valeur: float) -> str:
    return formater_pourcentage(valeur) if type_regle == "pire_baisse_max" else f"{valeur * 100:.0f} %"


def _libelle_modifie(regle: dict[str, Any], valeur: float) -> str:
    if regle["type"] == "pire_baisse_max":
        return f"Pire baisse tolérée : {formater_pourcentage(valeur)}"
    sujet = regle["libelle"].split(" : ")[0]
    return f"{sujet} : exclusion" if valeur == 0 else f"{sujet} : {valeur * 100:.0f} % du portefeuille au maximum"


# --- Source -----------------------------------------------------------------------


def _source() -> str:
    source = os.environ.get("SOURCE_DONNEES", "local")
    if source not in ("local", "s3"):
        raise ErreurDonnees(f"SOURCE_DONNEES doit valoir « local » ou « s3 », pas « {source} »")
    return source


def _bucket() -> str:
    bucket = os.environ.get("BUCKET_PROJET")
    if not bucket:
        raise ErreurDonnees("SOURCE_DONNEES=s3 demande la variable BUCKET_PROJET (nom du bucket)")
    return bucket
