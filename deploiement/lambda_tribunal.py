"""Point d'entrée de la Lambda du Tribunal (#13), derrière une Lambda Function URL.

Huit routes, en POST, avec un corps JSON :

- ``/tribunal`` ``{"profil": "<id>", "demande": "<texte>"}`` : fait le procès
  (``juger_decision``). ``profil`` est un profil de démonstration (``personas/``) ou un
  profil créé par ``/profil``. Champ facultatif ``"calibrage": {"reponses": {"<id de
  question>": "<réponse>"}}`` : les réponses du Pacte vécu (#68), datées du jour par la
  Lambda. Le contrat est archivé dans S3 (``traces/<date>/<id>.json``) et son identifiant
  est renvoyé dans l'en-tête ``X-Proces-Id`` : le format du contrat ne change pas.
  Champ facultatif ``"poche": "<id>"`` (#115) : pour un profil à poches, la poche où la
  décision est jugée ; sans lui, l'Agent Profil la déduit de la demande. Obligatoire avec
  ``calibrage`` pour un profil à poches. Poche inconnue : 400.

  - Avec ``"progression": true`` (#90, l'interface) : la demande est vérifiée sans
    Bedrock, puis la Lambda **s'invoque elle-même en asynchrone** pour faire le procès
    et répond tout de suite **202** ``{"id": "<id>"}``. Pendant le procès, chaque étape
    réelle est publiée dans ``progression/<id>.json`` (``pipeline.progression``).
  - Sans ce champ : ancien comportement, la réponse est le contrat (200), à la fin du
    procès. Il sert aux scripts et à une interface pas encore à jour.
- ``/progression`` ``{"id": "<id>"}`` (#90) : relit S3 et renvoie la progression du procès
  en cours, ou ``{"id", "statut": "termine", "contrat": {...}}`` quand il est archivé.
  Sans Bedrock ; débit limité par adresse IP.
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
- ``/questionnaire`` ``{}`` : les questions du questionnaire investisseur (#84), avec les
  vrais chiffres des cartes de portefeuilles. Sans Bedrock.
- ``/profil`` ``{"reponses": {...}, "capital": <CAD>, "portefeuille": [{"ticker", "poids"}],
  "nom": "<facultatif>", "modifications": {"<id de règle>": <valeur>}}`` (#87) : Python
  construit le profil à partir des réponses (``profil_depuis_reponses``), applique les seuils
  choisis par l'utilisateur, le valide et le range dans ``profils/<id>.json`` du bucket.
  Champ facultatif ``"objectifs": [{"id", "objectif", "horizon", "part", "portefeuille"}]``
  (#115, au moins deux) : une poche par objectif, avec sa propre pire baisse ; le
  ``portefeuille`` global peut alors être omis, et une règle d'une poche se modifie par
  la clé ``"<id de poche>/<id de règle>"``.
  L'identifiant est généré ici, jamais tiré du nom saisi : un profil créé n'écrase jamais
  un profil de démonstration. Sans Bedrock. Réponse 201 : ``{id, profil, bareme,
  contradictions, archive, vues}`` ; ``vues`` contient ce que les écrans Portefeuille et
  « Revivez 4 jours » affichent (``pipeline.vues_interface``, #86). Avec ``"apercu": true``,
  rien n'est rangé : réponse 200 ``{profil, bareme, contradictions}``, pour l'aperçu du
  Pacte avant signature. Débit limité par adresse IP, car le point d'accès est public.
- ``/table`` ``{"profil": "<id>", "ticker": "<ticker>"}`` (#86) : la table de l'écran
  Décision pour ce titre (position de 0 à 50 %, statut de chaque règle du Pacte), la même
  que celles précalculées pour les profils de démonstration. Sans Bedrock.

Le procès lancé en arrière-plan arrive par un événement interne
``{"action": "juger_en_arriere_plan", "id": …}``, envoyé par la Lambda elle-même. Un
événement de la Function URL ne peut pas lui ressembler : il porte toujours
``requestContext``, et le corps de la requête reste dans ``body``.

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
from concurrent.futures import ThreadPoolExecutor
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
from pipeline.poches import PocheInconnue
from pipeline.proces_verbal import proces_verbal_html
from pipeline.profils import (
    ProfilDejaExistant,
    appliquer_modifications,
    cle_profil,
    enregistrer_profil,
    nouvel_identifiant_profil,
)
from pipeline.agent_profil import charger_profil
from pipeline.questionnaire import (
    ReponsesInvalides,
    contradictions,
    detail_bareme,
    profil_depuis_reponses,
    questions,
    valider_reponses,
)
from pipeline.progression import Progression
from pipeline.tribunal import bornes_periode, juger_decision, verifier_avant_proces
from pipeline.univers import charger_univers
from pipeline.vues_interface import semaines_du_profil, table_position, vues_profil

VERDICTS = ("maintenu", "modifie", "pacte_ajuste")  # CLAUDE.md, section 5
ROUTES = ("/tribunal", "/progression", "/verdict", "/question", "/verifier", "/proces-verbal",
          "/questionnaire", "/profil", "/table")
ACTION_JUGER = "juger_en_arriere_plan"  # événement interne : procès lancé par /tribunal (#90)
DEBIT_MAX_PROGRESSION = 90  # relectures par minute et par adresse IP (l'interface relit toutes les 1,5 s)
_appels_progression: dict[str, deque] = {}
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

# /profil (#87) : chaque appel écrit un objet dans S3. Corps borné (une vingtaine de réponses
# et au plus une ligne par titre de l'univers), débit borné par adresse IP.
TAILLE_MAX_PROFIL = 20_000  # caractères du corps JSON
LIGNES_MAX_PORTEFEUILLE = 31  # titres de assets_universe.csv
OBJECTIFS_MAX = 5  # poches d'un profil créé (#115)
LONGUEUR_MAX_NOM = 40
MODIFICATIONS_MAX = 10
NOM_PAR_DEFAUT = "Investisseur"
DEBIT_MAX_PROFIL = 10  # profils créés ou aperçus par minute et par adresse IP
_appels_profil: dict[str, deque] = {}
FORMAT_ID_PROFIL = re.compile(r"[a-z][a-z0-9_]{0,63}")


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
_lambda = None


def _client_s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3")
    return _s3


def _client_lambda():
    global _lambda
    if _lambda is None:
        _lambda = boto3.client("lambda")
    return _lambda


# --- Handler -------------------------------------------------------------------


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Appelé par Lambda pour chaque requête de la Function URL (format d'événement 2.0).

    Ou pour un procès lancé en arrière-plan par ``/tribunal`` (événement interne, #90).
    """
    if event.get("action") == ACTION_JUGER and "requestContext" not in event:
        return juger_en_arriere_plan(event)
    methode = event.get("requestContext", {}).get("http", {}).get("method", "")
    chemin = event.get("rawPath", "")
    if chemin not in ROUTES:
        return _reponse(404, {"erreur": f"Route inconnue : {', '.join(ROUTES)}"})
    if methode != "POST":
        return _reponse(405, {"erreur": "Seule la méthode POST est acceptée"})
    adresse = event.get("requestContext", {}).get("http", {}).get("sourceIp", "inconnue")
    try:
        corps = _lire_corps(event)
        if chemin == "/tribunal":
            return _tribunal(corps)
        if chemin == "/progression":
            return _progression(corps, adresse)
        if chemin == "/question":
            return _question(corps)
        if chemin == "/verifier":
            return _verifier(corps, adresse)
        if chemin == "/questionnaire":
            return _reponse(200, {"questions": questions()})
        if chemin == "/profil":
            return _profil(corps, adresse)
        if chemin == "/table":
            return _table(corps)
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
    poche = corps.get("poche")
    if poche is not None and (not isinstance(poche, str) or not FORMAT_ID_PROFIL.fullmatch(poche)):
        raise RequeteInvalide("Champ « poche » invalide : l'id d'une poche du profil, ex. « retraite »")
    if corps.get("progression") is True:
        return _demarrer_proces(profil, demande, calibrage, poche)

    try:
        contrat = juger_decision(profil, demande, calibrage=calibrage, poche=poche)
    except (ErreurCalibrage, PocheInconnue) as erreur:
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


def _demarrer_proces(profil: str, demande: str, calibrage: dict[str, Any] | None,
                     poche: str | None = None) -> dict[str, Any]:
    """``/tribunal`` avec progression (#90) : vérifie, publie l'état initial, lance le procès et répond 202."""
    try:
        verifier_avant_proces(profil, calibrage, poche)  # sans Bedrock : une demande invalide est refusée tout de suite
    except (ErreurCalibrage, PocheInconnue) as erreur:
        return _reponse(400, {"erreur": str(erreur)})
    except ProfilInconnu as erreur:
        return _reponse(404, {"erreur": str(erreur)})
    except PacteInvalide as erreur:
        return _reponse(422, {"erreur": "Pacte du profil invalide", "details": erreur.erreurs})
    except ErreurDonnees as erreur:
        return _reponse(422, {"erreur": str(erreur)})
    fonction = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    if not fonction:
        return _reponse(500, {"erreur": "Procès en arrière-plan impossible hors de la Lambda"})

    identifiant = nouvel_identifiant()
    progression = Progression(identifiant, lambda document: _ecrire(cle_progression(identifiant), document))
    progression.publier_etat_initial()  # /progression le trouve dès la réponse 202
    evenement = {"action": ACTION_JUGER, "id": identifiant, "profil": profil, "demande": demande,
                 "calibrage": calibrage, "poche": poche}
    try:
        _client_lambda().invoke(FunctionName=fonction, InvocationType="Event",
                                Payload=json.dumps(evenement, ensure_ascii=False).encode("utf-8"))
    except ClientError as erreur:
        print(f"Lancement du procès en arrière-plan impossible : {erreur}")
        progression.echouer("Le procès n'a pas pu démarrer : réessayez dans un instant")
        return _reponse(503, {"erreur": "Le Tribunal n'a pas pu démarrer le procès : réessayez dans un instant"})
    return _reponse(202, {"id": identifiant, "statut": "en_cours"}, {EN_TETE_ID: identifiant})


def juger_en_arriere_plan(evenement: dict[str, Any]) -> dict[str, Any]:
    """Fait le procès lancé par ``/tribunal`` et publie sa progression réelle dans S3 (#90).

    Le contrat est archivé **avant** que la progression passe à « termine » : quand
    l'interface lit « termine », le contrat est déjà là. Toute erreur est écrite dans
    la progression avec son motif, et la fonction se termine normalement : Lambda ne
    relance donc jamais un procès raté (il coûterait de nouveaux appels Bedrock).
    """
    identifiant = evenement.get("id")
    if not isinstance(identifiant, str) or not FORMAT_ID.fullmatch(identifiant):
        print(f"Procès en arrière-plan ignoré : identifiant invalide {identifiant!r}")
        return {"statut": "ignore"}
    ecrivain = EcrivainProgression(cle_progression(identifiant))
    progression = Progression(identifiant, ecrivain.publier)
    try:
        contrat = juger_decision(evenement.get("profil"), evenement.get("demande"),
                                 calibrage=evenement.get("calibrage"), signaler=progression.signaler,
                                 poche=evenement.get("poche"))
        _ecrire(cle_trace(identifiant), contrat)
        progression.terminer()
    except Exception as erreur:  # noqa: BLE001 - le motif va dans la progression, le détail dans CloudWatch
        progression.echouer(motif_erreur(erreur))
    finally:
        ecrivain.fermer()
    return {"id": identifiant, "statut": progression.document["statut"]}


def motif_erreur(erreur: Exception) -> str:
    """Motif affiché par l'interface quand un procès en arrière-plan s'arrête."""
    if isinstance(erreur, (ErreurCalibrage, ProfilInconnu, ErreurDonnees, PocheInconnue)):
        return str(erreur)
    if isinstance(erreur, PacteInvalide):
        return "Pacte du profil invalide"
    if isinstance(erreur, ClientError):
        print(f"Archive S3 indisponible : {erreur}")
        return "Archive S3 indisponible : le procès n'a pas pu être archivé"
    traceback.print_exc()
    return "Erreur interne : le procès n'a pas pu aller au bout (détail dans le journal CloudWatch)"


class EcrivainProgression:
    """Publie la progression dans S3 depuis un fil à part : le procès n'attend jamais S3.

    Les versions partent dans l'ordre ; si plusieurs attendent (rafale d'étapes), seule
    la plus récente est écrite. Une écriture ratée est journalisée, sans arrêter le procès.
    """

    def __init__(self, cle: str):
        self.cle = cle
        self._executeur = ThreadPoolExecutor(max_workers=1)
        self._derniere = 0

    def publier(self, document: dict[str, Any]) -> None:
        self._derniere += 1  # appelé sous le verrou de Progression : versions numérotées dans l'ordre
        self._executeur.submit(self._ecrire, self._derniere, document)

    def _ecrire(self, version: int, document: dict[str, Any]) -> None:
        if version < self._derniere:
            return  # une version plus récente est déjà en attente
        try:
            _ecrire(self.cle, document)
        except Exception as erreur:  # noqa: BLE001 - la progression est un affichage : le procès continue
            print(f"Progression non publiée : {erreur}")

    def fermer(self) -> None:
        """Attend la dernière écriture (la Lambda est figée dès que le handler rend la main)."""
        self._executeur.shutdown(wait=True)


def _progression(corps: dict[str, Any], adresse: str) -> dict[str, Any]:
    """Progression d'un procès lancé par ``/tribunal`` (#90), ou son contrat s'il est archivé."""
    if trop_d_appels(_appels_progression, DEBIT_MAX_PROGRESSION, adresse):
        return _reponse(429, {"erreur": f"Trop de relectures : {DEBIT_MAX_PROGRESSION} par minute au plus"})
    identifiant = corps.get("id")
    if not isinstance(identifiant, str) or not FORMAT_ID.fullmatch(identifiant):
        raise RequeteInvalide(f"Champ « id » invalide : celui de l'en-tête {EN_TETE_ID} du procès")
    try:
        document = _lire(cle_progression(identifiant))
    except ClientError as erreur:
        if _absent(erreur):
            return _reponse(404, {"erreur": f"Aucun procès en cours avec l'identifiant {identifiant}"})
        raise
    if document.get("statut") == "termine":
        contrat = _lire(cle_trace(identifiant))
        return _reponse(200, {"id": identifiant, "statut": "termine", "contrat": contrat}, {EN_TETE_ID: identifiant})
    return _reponse(200, document, {EN_TETE_ID: identifiant})


def _lire_calibrage(brut: Any) -> dict[str, Any] | None:
    """Réponses du Pacte vécu (#68), datées du jour (UTC) ; None si le champ est absent."""
    if brut is None:
        return None
    reponses = brut.get("reponses") if isinstance(brut, dict) else None
    if (not isinstance(reponses, dict) or not reponses or len(reponses) > REPONSES_MAX_CALIBRAGE
            or not all(isinstance(c, str) and isinstance(v, str) for c, v in reponses.items())):
        raise RequeteInvalide("Champ « calibrage » invalide : {\"reponses\": {\"<id de question>\": \"<réponse>\"}}")
    return {"reponses": reponses, "date": datetime.now(timezone.utc).date().isoformat(), "etiquette": "fait"}


def _profil(corps: dict[str, Any], adresse: str) -> dict[str, Any]:
    """Questionnaire → profil validé, rangé dans S3 sous un identifiant neuf (#87)."""
    if trop_d_appels(_appels_profil, DEBIT_MAX_PROFIL, adresse):
        return _reponse(429, {"erreur": f"Trop de profils créés : {DEBIT_MAX_PROFIL} par minute au plus, "
                                        "réessayez dans un instant"})
    if len(json.dumps(corps, ensure_ascii=False)) > TAILLE_MAX_PROFIL:
        raise RequeteInvalide(f"Corps trop long : {TAILLE_MAX_PROFIL} caractères au plus")
    reponses, capital, portefeuille = corps.get("reponses"), corps.get("capital"), corps.get("portefeuille")
    nom, modifications = corps.get("nom", NOM_PAR_DEFAUT), corps.get("modifications", {})
    objectifs = corps.get("objectifs")
    if not isinstance(reponses, dict) or not reponses:
        raise RequeteInvalide("Champ « reponses » manquant : {\"<id de question>\": <réponse>}")
    if objectifs is not None and (not isinstance(objectifs, list) or len(objectifs) > OBJECTIFS_MAX):
        raise RequeteInvalide(f"Champ « objectifs » invalide : une liste de {OBJECTIFS_MAX} objectifs au plus "
                              "{objectif, horizon, part, portefeuille}")
    if (portefeuille is not None or objectifs is None) and (
            not isinstance(portefeuille, list) or len(portefeuille) > LIGNES_MAX_PORTEFEUILLE):
        raise RequeteInvalide(f"Champ « portefeuille » invalide : une liste de lignes {{ticker, poids}} "
                              f"({LIGNES_MAX_PORTEFEUILLE} au plus)")
    if not isinstance(nom, str) or not nom.strip() or len(nom) > LONGUEUR_MAX_NOM:
        raise RequeteInvalide(f"Champ « nom » invalide : {LONGUEUR_MAX_NOM} caractères au plus")
    if not isinstance(modifications, dict) or len(modifications) > MODIFICATIONS_MAX:
        raise RequeteInvalide("Champ « modifications » invalide : {\"<id de règle>\": <nouvelle valeur>}")
    apercu = corps.get("apercu", False)
    if not isinstance(apercu, bool):
        raise RequeteInvalide("Champ « apercu » invalide : true ou false")

    date_reponses = datetime.now(timezone.utc).date().isoformat()
    identifiant = nouvel_identifiant_profil()
    try:
        profil = profil_depuis_reponses(reponses, capital, portefeuille, date_reponses,
                                        identifiant=identifiant, nom=nom.strip(), objectifs=objectifs)
        if modifications:
            profil = appliquer_modifications(profil, modifications, date_reponses)
        if not apercu:
            enregistrer_profil(profil)
    except ReponsesInvalides as erreur:
        return _reponse(400, {"erreur": "Réponses refusées", "details": erreur.erreurs})
    except ProfilDejaExistant as erreur:  # identifiant aléatoire : en pratique, jamais
        return _reponse(409, {"erreur": str(erreur)})
    contenu = {
        "profil": profil,
        "bareme": detail_bareme(reponses, date_reponses, objectifs),
        "contradictions": contradictions(valider_reponses(reponses)),
    }
    if apercu:
        return _reponse(200, contenu)
    return _reponse(201, {"id": identifiant, **contenu, "archive": cle_profil(identifiant),
                          "vues": vues_profil(profil)})


def _table(corps: dict[str, Any]) -> dict[str, Any]:
    """Table de l'écran Décision d'un titre, pour un profil créé (ou de démonstration)."""
    identifiant, ticker = corps.get("profil"), corps.get("ticker")
    if not isinstance(identifiant, str) or not FORMAT_ID_PROFIL.fullmatch(identifiant):
        raise RequeteInvalide("Champ « profil » invalide : l'identifiant renvoyé par /profil")
    if ticker not in {titre["ticker"] for titre in charger_univers()}:
        raise RequeteInvalide("Champ « ticker » invalide : un titre de l'univers, ex. « TSLA »")
    try:
        profil = charger_profil(identifiant)
    except ProfilInconnu as erreur:
        return _reponse(404, {"erreur": str(erreur)})
    except PacteInvalide as erreur:
        return _reponse(422, {"erreur": "Pacte du profil invalide", "details": erreur.erreurs})
    return _reponse(200, table_position(profil, ticker, semaines_du_profil(profil)))


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
    """Limite de débit de /verifier (voir ``trop_d_appels``)."""
    return trop_d_appels(_appels_verifier, DEBIT_MAX_VERIFIER, adresse, maintenant)


def trop_d_appels(journal: dict[str, deque], maximum: int, adresse: str, maintenant: float | None = None) -> bool:
    """Limite de débit d'une route : fenêtre glissante d'une minute, par adresse IP.

    En mémoire de l'instance : elle repart de zéro à chaque démarrage de la Lambda. C'est
    un garde-fou contre une boucle ou un abus, pas une protection complète.
    """
    maintenant = time.monotonic() if maintenant is None else maintenant
    if adresse not in journal and len(journal) >= ADRESSES_SUIVIES_MAX:
        journal.clear()
    appels = journal.setdefault(adresse, deque())
    while appels and maintenant - appels[0] >= FENETRE_DEBIT_S:
        appels.popleft()
    if len(appels) >= maximum:
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


def cle_progression(identifiant: str) -> str:
    return f"progression/{identifiant}.json"


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
