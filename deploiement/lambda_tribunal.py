"""Point d'entrée de la Lambda du Tribunal (#13), derrière une Lambda Function URL.

Cinq routes, en POST, avec un corps JSON :

- ``/tribunal`` ``{"profil": "<id>", "demande": "<texte>"}`` : fait le procès. Champ
  facultatif ``"calibrage": {"reponses": {"<id de question>": "<réponse>"}}`` : les
  réponses du Pacte vécu (#68), datées du jour par la Lambda.
  (``juger_decision``) et renvoie le contrat JSON tel quel. Le contrat est archivé
  dans S3 (``traces/<date>/<id>.json``) et son identifiant est renvoyé dans
  l'en-tête ``X-Proces-Id`` : le format du contrat ne change pas.
- ``/verdict`` ``{"id": "<id>", "verdict": "maintenu" | "modifie" | "pacte_ajuste"}`` :
  archive la décision avec ses pièces et le choix de l'utilisateur
  (``verdicts/<profil>/<id>.json``, relu par l'outil de jurisprudence, #56). Un nouveau
  verdict pour le même procès remplace l'ancien.
- ``/question`` ``{"id": "<id>", "question": "<texte>"}`` : contre-interrogatoire (#55).
  Relit le procès archivé, répond à la question (orchestrateur, Procureur et Avocat,
  Greffier), réarchive le contrat complété au même endroit et renvoie l'échange et
  les pièces ajoutées.
- ``/verifier`` ``{"id": "<id>", "texte": "<argument>", "pieces": ["P2", ...]}`` :
  « Trompez le Greffier » (#69). Vérifie chaque nombre du texte contre les pièces citées
  du procès archivé (``detailler_argument``, outil 6), **sans Bedrock** : réponse
  immédiate et gratuite. Texte et débit limités, car le point d'accès est public.
- ``/proces-verbal`` ``{"id": "<id>"}`` : renvoie le procès-verbal du procès archivé,
  en page HTML imprimable (``pipeline.proces_verbal``, #57). Il relit l'archive du
  verdict si l'utilisateur a déjà tranché, sinon la trace du procès. Aucun appel à
  Bedrock : la page est produite par Python à partir du contrat.

Le pipeline est importé et les CSV sont lus au niveau du module, hors du
handler : une Lambda déjà démarrée les garde en mémoire (caches de
``pipeline/donnees.py``). Le journal CloudWatch le montre : la ligne
« Données chargées » n'apparaît qu'au démarrage.

Dans le zip, ce fichier est à la racine : le handler est ``lambda_tribunal.handler``.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import traceback
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

from pipeline.agent_profil import ProfilInconnu
from pipeline.calibrage import ErreurCalibrage
from pipeline.chiffres import detailler_argument
from pipeline.contre_interrogatoire import QuestionInvalide, interroger, pieces_de_l_echange
from pipeline.donnees import ErreurDonnees, seances_americaines
from pipeline.jurisprudence import cle_verdict
from pipeline.pacte import PacteInvalide
from pipeline.proces_verbal import proces_verbal_html
from pipeline.tribunal import bornes_periode, juger_decision

VERDICTS = ("maintenu", "modifie", "pacte_ajuste")  # CLAUDE.md, section 5
ROUTES = ("/tribunal", "/verdict", "/question", "/verifier", "/proces-verbal")
LONGUEUR_MAX_DEMANDE = 2000  # une demande d'investissement tient en quelques phrases
REPONSES_MAX_CALIBRAGE = 20  # le Pacte vécu pose une dizaine de questions au plus
FORMAT_ID = re.compile(r"\d{4}-\d{2}-\d{2}-[0-9a-f]{12}")
EN_TETE_ID = "X-Proces-Id"

# /verifier (#69) : un argument tient en quelques phrases ; le débit est limité par adresse IP
# et par instance de Lambda (la concurrence réservée de 2 borne le reste).
LONGUEUR_MAX_ARGUMENT = 600
PIECES_MAX_ARGUMENT = 10
FORMAT_PIECE = re.compile(r"P\d{1,3}")
DEBIT_MAX_VERIFIER = 30  # vérifications par minute et par adresse IP
FENETRE_DEBIT_S = 60
ADRESSES_SUIVIES_MAX = 1000
_appels_verifier: dict[str, deque] = {}


class RequeteInvalide(Exception):
    """Corps ou paramètres refusés : la réponse est une erreur 400 avec ce message."""


# --- Démarrage de la Lambda : données chargées une seule fois ----------------

_debut = time.perf_counter()
try:
    seances_americaines()  # lit l'univers et les prix ; les appels suivants les reprennent du cache
    print(f"Données chargées en {time.perf_counter() - _debut:.1f} s (démarrage de la Lambda)")
except ErreurDonnees as erreur:  # chaque procès renverra la même erreur, lisible
    print(f"Données non chargées au démarrage : {erreur}")

_s3 = None


def _client_s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3")
    return _s3


# --- Handler -------------------------------------------------------------------


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Appelé par Lambda pour chaque requête de la Function URL (format d'événement 2.0)."""
    methode = event.get("requestContext", {}).get("http", {}).get("method", "")
    chemin = event.get("rawPath", "")
    if chemin not in ROUTES:
        return _reponse(404, {"erreur": f"Route inconnue : {', '.join(ROUTES)}"})
    if methode != "POST":
        return _reponse(405, {"erreur": "Seule la méthode POST est acceptée"})
    try:
        corps = _lire_corps(event)
        if chemin == "/tribunal":
            return _tribunal(corps)
        if chemin == "/question":
            return _question(corps)
        if chemin == "/verifier":
            adresse = event.get("requestContext", {}).get("http", {}).get("sourceIp", "inconnue")
            return _verifier(corps, adresse)
        if chemin == "/proces-verbal":
            return _proces_verbal(corps)
        return _verdict(corps)
    except RequeteInvalide as erreur:
        return _reponse(400, {"erreur": str(erreur)})
    except (ClientError, ErreurDonnees) as erreur:  # bucket absent ou inaccessible
        print(f"Archive S3 indisponible : {erreur}")
        return _reponse(500, {"erreur": "Archive S3 indisponible"})


def _tribunal(corps: dict[str, Any]) -> dict[str, Any]:
    profil, demande = corps.get("profil"), corps.get("demande")
    if not isinstance(profil, str) or not profil:
        raise RequeteInvalide("Champ « profil » manquant : identifiant d'un profil, ex. « robert »")
    if not isinstance(demande, str) or not demande.strip():
        raise RequeteInvalide("Champ « demande » manquant : la décision à juger, en une phrase")
    if len(demande) > LONGUEUR_MAX_DEMANDE:
        raise RequeteInvalide(f"Demande trop longue : {LONGUEUR_MAX_DEMANDE} caractères au plus")
    calibrage = _lire_calibrage(corps.get("calibrage"))

    try:
        contrat = juger_decision(profil, demande, calibrage=calibrage)
    except ErreurCalibrage as erreur:
        return _reponse(400, {"erreur": str(erreur)})
    except ProfilInconnu as erreur:
        return _reponse(404, {"erreur": str(erreur)})
    except PacteInvalide as erreur:
        return _reponse(422, {"erreur": "Pacte du profil invalide", "details": erreur.erreurs})
    except ErreurDonnees as erreur:
        return _reponse(422, {"erreur": str(erreur)})
    except Exception:  # noqa: BLE001 - le détail va dans CloudWatch, pas chez l'utilisateur
        traceback.print_exc()
        return _reponse(500, {"erreur": "Erreur interne : le procès n'a pas pu aller au bout"})

    identifiant = nouvel_identifiant()
    en_tetes = {}
    try:
        _ecrire(cle_trace(identifiant), contrat)
        en_tetes[EN_TETE_ID] = identifiant
    except (ClientError, ErreurDonnees) as erreur:
        # Le procès a coûté des appels Bedrock : on le renvoie quand même, sans identifiant.
        print(f"Archivage du procès impossible : {erreur}")
    return _reponse(200, contrat, en_tetes)


def _lire_calibrage(brut: Any) -> dict[str, Any] | None:
    """Réponses du Pacte vécu (#68), datées du jour (UTC) ; None si le champ est absent."""
    if brut is None:
        return None
    reponses = brut.get("reponses") if isinstance(brut, dict) else None
    if (not isinstance(reponses, dict) or not reponses or len(reponses) > REPONSES_MAX_CALIBRAGE
            or not all(isinstance(c, str) and isinstance(v, str) for c, v in reponses.items())):
        raise RequeteInvalide("Champ « calibrage » invalide : {\"reponses\": {\"<id de question>\": \"<réponse>\"}}")
    return {"reponses": reponses, "date": datetime.now(timezone.utc).date().isoformat(), "etiquette": "fait"}


def _verdict(corps: dict[str, Any]) -> dict[str, Any]:
    identifiant, verdict = corps.get("id"), corps.get("verdict")
    if not isinstance(identifiant, str) or not FORMAT_ID.fullmatch(identifiant):
        raise RequeteInvalide(f"Champ « id » invalide : celui de l'en-tête {EN_TETE_ID} du procès")
    if verdict not in VERDICTS:
        raise RequeteInvalide(f"Champ « verdict » invalide : {', '.join(VERDICTS)}")

    try:
        contrat = _lire(cle_trace(identifiant))
    except ClientError as erreur:
        if erreur.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return _reponse(404, {"erreur": f"Aucun procès archivé avec l'identifiant {identifiant}"})
        raise
    archive = {**contrat, "verdict": verdict}
    cle = cle_verdict(contrat["persona"], identifiant)
    _ecrire(cle, archive)
    return _reponse(200, {"id": identifiant, "verdict": verdict, "archive": cle})


def _proces_verbal(corps: dict[str, Any]) -> dict[str, Any]:
    identifiant = corps.get("id")
    if not isinstance(identifiant, str) or not FORMAT_ID.fullmatch(identifiant):
        raise RequeteInvalide(f"Champ « id » invalide : celui de l'en-tête {EN_TETE_ID} du procès")

    try:
        contrat = _lire(cle_trace(identifiant))
    except ClientError as erreur:
        if _absent(erreur):
            return _reponse(404, {"erreur": f"Aucun procès archivé avec l'identifiant {identifiant}"})
        raise
    try:  # le verdict, s'il est rendu, est archivé à part avec le contrat complet
        contrat = _lire(cle_verdict(contrat["persona"], identifiant))
    except ClientError as erreur:
        if not _absent(erreur):
            raise
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html; charset=utf-8"},
        "body": proces_verbal_html(contrat, identifiant),
    }


def _absent(erreur: ClientError) -> bool:
    return erreur.response.get("Error", {}).get("Code") in ("NoSuchKey", "404")


def _question(corps: dict[str, Any]) -> dict[str, Any]:
    identifiant, question = corps.get("id"), corps.get("question")
    if not isinstance(identifiant, str) or not FORMAT_ID.fullmatch(identifiant):
        raise RequeteInvalide(f"Champ « id » invalide : celui de l'en-tête {EN_TETE_ID} du procès")
    if not isinstance(question, str) or not question.strip():
        raise RequeteInvalide("Champ « question » manquant : votre question sur le procès")

    try:
        contrat = _lire(cle_trace(identifiant))
    except ClientError as erreur:
        if erreur.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return _reponse(404, {"erreur": f"Aucun procès archivé avec l'identifiant {identifiant}"})
        raise

    try:
        complete = interroger(contrat, question)
    except QuestionInvalide as erreur:
        return _reponse(400, {"erreur": str(erreur)})
    except ProfilInconnu as erreur:
        return _reponse(404, {"erreur": str(erreur)})
    except (PacteInvalide, ErreurDonnees) as erreur:
        return _reponse(422, {"erreur": str(erreur)})
    except Exception:  # noqa: BLE001 - le détail va dans CloudWatch, pas chez l'utilisateur
        traceback.print_exc()
        return _reponse(500, {"erreur": "Erreur interne : la question n'a pas pu être instruite"})

    echange = complete["contre_interrogatoire"][-1]
    try:
        _ecrire(cle_trace(identifiant), complete)
    except (ClientError, ErreurDonnees) as erreur:
        # Les appels Bedrock sont déjà faits : on renvoie la réponse, sans l'avoir archivée.
        print(f"Archivage de la question impossible : {erreur}")
    return _reponse(200, {"id": identifiant, "echange": echange,
                          "pieces": pieces_de_l_echange(complete, echange)})


def _verifier(corps: dict[str, Any], adresse: str) -> dict[str, Any]:
    """« Trompez le Greffier » : un texte tapé à la main, vérifié contre les pièces du procès."""
    if trop_de_verifications(adresse):
        return _reponse(429, {"erreur": f"Trop de vérifications : {DEBIT_MAX_VERIFIER} par minute au plus, "
                                        "réessayez dans un instant"})
    identifiant, texte, pieces = corps.get("id"), corps.get("texte"), corps.get("pieces", [])
    if not isinstance(identifiant, str) or not FORMAT_ID.fullmatch(identifiant):
        raise RequeteInvalide(f"Champ « id » invalide : celui de l'en-tête {EN_TETE_ID} du procès")
    if not isinstance(texte, str) or not texte.strip():
        raise RequeteInvalide("Champ « texte » manquant : l'argument à vérifier")
    if len(texte) > LONGUEUR_MAX_ARGUMENT:
        raise RequeteInvalide(f"Texte trop long : {LONGUEUR_MAX_ARGUMENT} caractères au plus")
    if (not isinstance(pieces, list) or len(pieces) > PIECES_MAX_ARGUMENT
            or not all(isinstance(p, str) and FORMAT_PIECE.fullmatch(p) for p in pieces)):
        raise RequeteInvalide(f"Champ « pieces » invalide : une liste d'identifiants « P1 », « P2 »… "
                              f"({PIECES_MAX_ARGUMENT} au plus)")

    try:
        contrat = _lire(cle_trace(identifiant))
    except ClientError as erreur:
        if erreur.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return _reponse(404, {"erreur": f"Aucun procès archivé avec l'identifiant {identifiant}"})
        raise
    dossier = {"decision": contrat["decision"], "pieces": contrat["pieces"], "periode": bornes_periode()}
    resultat = detailler_argument({"texte": texte, "pieces": pieces}, dossier)
    return _reponse(200, {"id": identifiant, "texte": texte, "pieces": pieces, **resultat})


def trop_de_verifications(adresse: str, maintenant: float | None = None) -> bool:
    """Limite de débit de /verifier : fenêtre glissante d'une minute, par adresse IP.

    En mémoire de l'instance : elle repart de zéro à chaque démarrage de la Lambda. C'est
    un garde-fou contre une boucle ou un abus, pas une protection complète.
    """
    maintenant = time.monotonic() if maintenant is None else maintenant
    if adresse not in _appels_verifier and len(_appels_verifier) >= ADRESSES_SUIVIES_MAX:
        _appels_verifier.clear()
    appels = _appels_verifier.setdefault(adresse, deque())
    while appels and maintenant - appels[0] >= FENETRE_DEBIT_S:
        appels.popleft()
    if len(appels) >= DEBIT_MAX_VERIFIER:
        return True
    appels.append(maintenant)
    return False


# --- S3 ------------------------------------------------------------------------


def nouvel_identifiant(maintenant: datetime | None = None) -> str:
    """« 2026-11-14-3f9a0c1b2d4e » : la date (UTC) donne le dossier de la trace."""
    maintenant = maintenant or datetime.now(timezone.utc)
    return f"{maintenant:%Y-%m-%d}-{uuid.uuid4().hex[:12]}"


def cle_trace(identifiant: str) -> str:
    return f"traces/{identifiant[:10]}/{identifiant}.json"


def _bucket() -> str:
    bucket = os.environ.get("BUCKET_PROJET")
    if not bucket:
        raise ErreurDonnees("Variable BUCKET_PROJET absente : impossible d'archiver dans S3")
    return bucket


def _ecrire(cle: str, contenu: dict[str, Any]) -> None:
    _client_s3().put_object(
        Bucket=_bucket(),
        Key=cle,
        Body=json.dumps(contenu, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )


def _lire(cle: str) -> dict[str, Any]:
    objet = _client_s3().get_object(Bucket=_bucket(), Key=cle)
    return json.loads(objet["Body"].read())


# --- HTTP ----------------------------------------------------------------------


def _lire_corps(event: dict[str, Any]) -> dict[str, Any]:
    brut = event.get("body") or ""
    if event.get("isBase64Encoded"):
        brut = base64.b64decode(brut).decode("utf-8")
    try:
        corps = json.loads(brut)
    except json.JSONDecodeError as erreur:
        raise RequeteInvalide(f"Corps JSON illisible : {erreur.msg}") from erreur
    if not isinstance(corps, dict):
        raise RequeteInvalide("Le corps doit être un objet JSON")
    return corps


def _reponse(statut: int, contenu: Any, en_tetes: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "statusCode": statut,
        "headers": {"Content-Type": "application/json; charset=utf-8", **(en_tetes or {})},
        "body": json.dumps(contenu, ensure_ascii=False),
    }
