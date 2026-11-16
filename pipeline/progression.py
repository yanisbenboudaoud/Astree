"""Progression réelle d'un procès en cours (#90), pour l'écran « Le Tribunal instruit le dossier ».

``juger_decision(..., signaler=...)`` appelle ``signaler(evenement)`` à chaque étape réelle
du procès, au moment où elle a lieu. Trois sortes d'événements :

- ``{"type": "phase", "phase": <id>, "activite": <texte>}`` : une phase commence (la
  précédente est finie). Phases, dans l'ordre fixe de ``PHASES`` : ``agent_profil``,
  ``orchestrateur``, ``debat`` (Procureur et Avocat en parallèle), ``replique`` (chacun
  répond à un argument de l'autre, #189), ``greffier`` ;
- ``{"type": "etape", "etape": <étape de trace>}`` : une étape vient d'être tracée, au
  même format que ``trace`` dans le contrat (un appel d'outil de l'orchestrateur, le
  retour du Procureur ou de l'Avocat, un contrôle du Greffier…) ;
- ``{"type": "activite", "activite": <texte>}`` : ce que le Tribunal fait en ce moment
  (« Argument renvoyé au Procureur… »), écrit juste avant l'appel qu'il annonce.

``Progression`` cumule ces événements dans un document JSON, que la Lambda publie dans
S3 (``progression/<id>.json``) et que l'interface relit (``POST /progression``) ::

    {"id": "…", "statut": "en_cours" | "termine" | "erreur", "phase": "orchestrateur",
     "activite": "…", "etapes": [...], "erreur": "…" (si erreur),
     "debut": "<ISO>", "mise_a_jour": "<ISO>"}

Python seul, sans AWS : la publication est une fonction reçue (``publier``). Les
signaux du Procureur et de l'Avocat arrivent de deux fils d'exécution : le document est
protégé par un verrou, et chaque version est publiée dans l'ordre.
"""

from __future__ import annotations

import copy
import threading
from datetime import datetime, timezone
from typing import Any, Callable

PHASES = ("agent_profil", "orchestrateur", "debat", "replique", "greffier")
STATUTS = ("en_cours", "termine", "erreur")

Signaler = Callable[[dict[str, Any]], None]


def ne_rien_signaler(evenement: dict[str, Any]) -> None:
    """Signal par défaut : le procès ne publie rien (tests, ligne de commande)."""


def maintenant_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def horodater(etape: dict[str, Any]) -> dict[str, Any]:
    """Ajoute à une étape de trace l'heure où elle a eu lieu (UTC, à la milliseconde, #189).

    L'étape garde sa première heure si elle est signalée deux fois.
    """
    etape.setdefault("horodatage", datetime.now(timezone.utc).isoformat(timespec="milliseconds"))
    return etape


class Progression:
    """Document de progression d'un procès, mis à jour à chaque signal (sans verrou à gérer par l'appelant)."""

    def __init__(
        self,
        identifiant: str,
        publier: Callable[[dict[str, Any]], None] = lambda document: None,
        horloge: Callable[[], str] = maintenant_iso,
    ):
        self._verrou = threading.Lock()
        self._publier = publier
        self._horloge = horloge
        debut = horloge()
        self._document: dict[str, Any] = {
            "id": identifiant, "statut": "en_cours", "phase": None, "activite": None,
            "etapes": [], "debut": debut, "mise_a_jour": debut,
        }

    @property
    def document(self) -> dict[str, Any]:
        """Copie de l'état actuel."""
        with self._verrou:
            return copy.deepcopy(self._document)

    def publier_etat_initial(self) -> None:
        """Publie le document avant le premier signal (le procès est accepté, pas encore commencé)."""
        self._modifier(lambda document: None)

    def signaler(self, evenement: dict[str, Any]) -> None:
        """Fonction ``signaler`` à passer à ``juger_decision``.

        Raises:
            ValueError: type d'événement ou phase inconnus (une erreur de code, pas de données).
        """
        type_evenement = evenement.get("type")
        if type_evenement == "phase":
            if evenement.get("phase") not in PHASES:
                raise ValueError(f"Phase inconnue : {evenement.get('phase')!r}")

            def appliquer(document):
                document["phase"] = evenement["phase"]
                document["activite"] = evenement.get("activite")
        elif type_evenement == "etape":
            def appliquer(document):
                document["etapes"].append(copy.deepcopy(evenement["etape"]))
        elif type_evenement == "activite":
            def appliquer(document):
                document["activite"] = evenement.get("activite")
        else:
            raise ValueError(f"Événement de progression inconnu : {type_evenement!r}")
        self._modifier(appliquer)

    def terminer(self) -> None:
        """Le contrat est archivé : l'interface peut le relire."""
        self._modifier(lambda document: document.update(statut="termine", phase=None, activite=None))

    def echouer(self, motif: str) -> None:
        """Le procès s'est arrêté : le motif est affiché au lieu d'un écran figé."""
        self._modifier(lambda document: document.update(statut="erreur", activite=None, erreur=motif))

    def _modifier(self, appliquer: Callable[[dict[str, Any]], None]) -> None:
        with self._verrou:
            appliquer(self._document)
            self._document["mise_a_jour"] = self._horloge()
            self._publier(copy.deepcopy(self._document))  # sous le verrou : versions publiées dans l'ordre
