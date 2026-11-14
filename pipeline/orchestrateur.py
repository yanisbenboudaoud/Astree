"""Orchestrateur : instruit le dossier en choisissant les outils Python à appeler.

Deuxième phase du Tribunal (CLAUDE.md, section 4). Un modèle Bedrock lit la
décision et le Pacte, choisit lui-même les outils et leurs paramètres, et donne
une raison courte pour chaque appel. Python exécute chaque appel ; chaque
résultat devient une pièce numérotée (P2, P3… : P1 est la pièce « Pacte »).

Garde-fous, tous appliqués par Python :
- **liste blanche** : seuls les outils de ``outils_du_profil`` sont décrits au
  modèle et exécutés (outils 1 à 4 ; jamais ceux du Greffier) ;
- **budget** : ``BUDGET_APPELS`` appels au plus, refus compris, puis on passe
  au débat ;
- **raison** : obligatoire, une phrase, sans chiffre ; sinon l'appel est refusé
  et le modèle reçoit le motif ;
- **pièce obligatoire** : si le modèle n'a pas demandé la simulation complète de
  la décision, Python l'ajoute d'office et le note dans la trace (pour une
  réallocation, que ``simuler_portefeuille`` ne sait pas encore simuler, #16,
  la trace l'indique et aucune pièce n'est créée) ;
- **erreur d'outil** (titre hors univers, taille impossible…) : renvoyée au
  modèle comme résultat en erreur, sans planter et sans créer de pièce.

L'orchestrateur ne calcule rien et ne rend aucun verdict. Le code ne connaît
aucun persona : il lit seulement les règles, l'horizon et le portefeuille reçus.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from pipeline import indicateurs, simulation
from pipeline.donnees import ErreurDonnees
from pipeline.llm import (
    DemandeOutil,
    converser_avec_outils,
    message_resultats,
    message_utilisateur,
    resultat_outil,
)
from pipeline.simulation import ErreurSimulation
from pipeline.univers import charger_univers

BUDGET_APPELS = 8  # hypothèse de l'équipe (CLAUDE.md, section 4)
LONGUEUR_MAX_RAISON = 160

RAISON_D_OFFICE = "Pièce obligatoire ajoutée d'office"
RAISON_REFUSEE = "Raison refusée par le garde-fou"
RAISON_INDISPONIBLE = "Pièce obligatoire indisponible : simulation des réallocations pas encore construite"

# Erreurs d'outil renvoyées au modèle au lieu d'arrêter le procès.
ERREURS_OUTIL = (ErreurDonnees, ErreurSimulation)


@dataclass(frozen=True)
class Outil:
    """Un outil que l'orchestrateur peut appeler."""

    nom: str
    description_bedrock: dict[str, Any]  # créée avec llm.decrire_outil
    executer: Callable[[dict[str, Any], str], dict[str, Any]]  # (paramètres, id) → pièce


@dataclass
class ResultatInstruction:
    """Ce que l'orchestrateur transmet au Procureur, à l'Avocat et au Greffier."""

    pieces: list[dict[str, Any]] = field(default_factory=list)  # pièces numérotées
    trace: list[dict[str, Any]] = field(default_factory=list)  # étapes « orchestrateur »
    appels: int = 0  # appels d'outils demandés par le modèle, refus compris


def outils_du_profil(profil: dict[str, Any]) -> list[Outil]:
    """Liste blanche des outils, décrits pour le portefeuille de ce profil.

    ``taille_max_compatible`` (#21) s'ajoutera ici.
    """
    portefeuille = profil["portefeuille"]
    tickers_univers = [ligne["ticker"] for ligne in charger_univers()]

    def executer_indicateurs(entree: dict[str, Any], id_piece: str) -> dict[str, Any]:
        return {"id": id_piece, **indicateurs.indicateurs_actif(entree["ticker"])}

    def executer_simulation(entree: dict[str, Any], id_piece: str) -> dict[str, Any]:
        decision = {"type": "position", "ticker": entree["ticker"], "taille": entree["taille"],
                    "financement": entree["financement"]}
        return simulation.piece_simulation(id_piece, portefeuille, decision, entree["periode"])

    return [
        Outil("indicateurs_actif", indicateurs.DESCRIPTION_BEDROCK, executer_indicateurs),
        Outil(simulation.NOM_OUTIL,
              simulation.decrire_simuler_portefeuille(tickers_univers, portefeuille),
              executer_simulation),
    ]


CONSIGNES = """Tu es l'orchestrateur d'un outil éducatif de simulation d'investissement.
Un investisseur propose une décision. Avant qu'elle soit débattue, tu instruis le dossier :
tu choisis quels outils de calcul appeler pour rassembler les preuves utiles.

Règles :
- Tu ne calcules rien toi-même : tous les chiffres viennent des outils.
- Appelle seulement les outils utiles pour juger CETTE décision au regard de CE Pacte.
  Par exemple : un horizon court rend le temps de récupération d'un titre important ;
  une règle de pire baisse rend utile le rejeu d'une année de crise.
- La simulation complète du portefeuille avec la décision est toujours nécessaire.
- Chaque appel a un paramètre « raison » : une phrase courte, en français, qui dit pourquoi
  cette preuve est utile. La raison ne contient AUCUN chiffre : ni seuil, ni pourcentage,
  ni année (écris « l'année de crise », pas l'année en chiffres). Sinon l'appel est refusé.
- Tu as au plus {budget} appels d'outils. Tu peux demander plusieurs outils à la fois.
- Si un outil renvoie une erreur, ne réessaie pas à l'identique.
- Quand le dossier est suffisant, réponds en une phrase, sans appeler d'outil.
- Tu ne donnes ni avis ni verdict : d'autres agents débattront à partir des pièces."""


def instruire_dossier(
    decision: dict[str, Any],
    profil: dict[str, Any],
    premier_numero: int,
    outils: list[Outil] | None = None,
    converser: Callable[..., Any] = converser_avec_outils,
) -> ResultatInstruction:
    """Laisse le modèle choisir les outils, exécute ses appels et numérote les pièces.

    Args:
        decision: décision structurée (champ « decision » du contrat).
        profil: profil validé par ``charger_pacte`` ; seuls son profil de risque,
            son horizon, ses règles et son portefeuille sont lus.
        premier_numero: numéro de la première pièce créée ici (les pièces
            précédentes, comme le Pacte, sont numérotées par l'appelant).
        outils: liste blanche (par défaut ``outils_du_profil(profil)``).
        converser: fonction qui fait jouer un tour au modèle (remplacée dans les tests).
    """
    outils = outils_du_profil(profil) if outils is None else outils
    instruction = _Instruction({outil.nom: outil for outil in outils}, premier_numero)

    systeme = CONSIGNES.format(budget=BUDGET_APPELS)
    descriptions = [_avec_raison(outil.description_bedrock) for outil in outils]
    conversation = [message_utilisateur(construire_dossier(decision, profil))]

    while instruction.resultat.appels < BUDGET_APPELS:
        tour = converser(systeme, conversation, descriptions)
        conversation.append(tour.message_assistant)
        if tour.termine:
            break
        blocs = [instruction.traiter_demande(demande) for demande in tour.demandes]
        conversation.append(message_resultats(blocs))

    instruction.ajouter_simulation_obligatoire(decision)
    return instruction.resultat


def construire_dossier(decision: dict[str, Any], profil: dict[str, Any]) -> str:
    """Ce que lit le modèle : la décision et le Pacte (sans justifications ni nom)."""
    dossier = {
        "decision": decision,
        "pacte": {
            "profil_risque": profil["profil_risque"],
            "horizon_ans": profil["horizon_ans"],
            "regles": [
                {cle: valeur for cle, valeur in regle.items() if cle != "justification"}
                for regle in profil["pacte"]["regles"]
            ],
        },
        "portefeuille_actuel": profil["portefeuille"],
    }
    return "Dossier à instruire :\n" + json.dumps(dossier, ensure_ascii=False, indent=2)


def probleme_raison(raison: Any) -> str | None:
    """Motif du refus d'une raison, ou None si elle est valide.

    Une raison valide est une phrase non vide, d'au plus LONGUEUR_MAX_RAISON
    caractères, sans chiffre.
    """
    if not isinstance(raison, str) or not raison.strip():
        return "La raison est obligatoire : une phrase courte, sans chiffre"
    if re.search(r"\d", raison):
        return "La raison ne doit contenir aucun chiffre"
    if len(raison) > LONGUEUR_MAX_RAISON:
        return f"La raison doit faire au plus {LONGUEUR_MAX_RAISON} caractères"
    return None


def raison_valide(raison: Any) -> bool:
    return probleme_raison(raison) is None


def entree_simulation_obligatoire(decision: dict[str, Any]) -> dict[str, Any]:
    """Paramètres de la pièce obligatoire : la décision demandée, sur toute la période."""
    return {"ticker": decision["ticker"], "taille": decision["taille"],
            "financement": decision["financement"], "periode": "complete"}


class _Instruction:
    """État d'une instruction en cours : pièces créées, trace et appels comptés."""

    def __init__(self, outils: dict[str, Outil], premier_numero: int):
        self.outils = outils
        self.numero = premier_numero
        self.resultat = ResultatInstruction()
        self.entrees_reussies: list[tuple[str, dict[str, Any]]] = []

    def traiter_demande(self, demande: DemandeOutil) -> dict[str, Any]:
        """Exécute une demande du modèle et renvoie le bloc de résultat à lui retourner."""
        self.resultat.appels += 1
        entree = dict(demande.entree)
        raison = entree.pop("raison", None)

        if self.resultat.appels > BUDGET_APPELS:
            return self._refuser(demande, entree, RAISON_REFUSEE, "Budget d'appels atteint")
        if demande.nom not in self.outils:
            return self._refuser(demande, entree, RAISON_REFUSEE, f"Outil « {demande.nom} » non autorisé")
        probleme = probleme_raison(raison)
        if probleme:
            return self._refuser(demande, entree, RAISON_REFUSEE, probleme)
        try:
            piece = self._executer(demande.nom, entree, raison)
        except ERREURS_OUTIL as erreur:
            return self._refuser(demande, entree, raison, str(erreur))
        return resultat_outil(demande, piece)

    def ajouter_simulation_obligatoire(self, decision: dict[str, Any]) -> None:
        """Ajoute la simulation complète de la décision si le modèle ne l'a pas obtenue."""
        if decision["type"] != "position":
            self._tracer(simulation.NOM_OUTIL, RAISON_INDISPONIBLE, decision, "Aucune pièce")
            return
        entree = entree_simulation_obligatoire(decision)
        if (simulation.NOM_OUTIL, entree) not in self.entrees_reussies:
            self._executer(simulation.NOM_OUTIL, entree, RAISON_D_OFFICE)

    def _executer(self, nom: str, entree: dict[str, Any], raison: str) -> dict[str, Any]:
        piece = self.outils[nom].executer(entree, f"P{self.numero}")
        self.numero += 1
        self.resultat.pieces.append(piece)
        self.entrees_reussies.append((nom, entree))
        self._tracer(nom, raison, entree, piece["id"])
        return piece

    def _refuser(self, demande: DemandeOutil, entree: dict[str, Any], raison: str,
                 motif: str) -> dict[str, Any]:
        self._tracer(demande.nom, raison, entree, f"Erreur : {motif}")
        return resultat_outil(demande, {"erreur": motif}, erreur=True)

    def _tracer(self, outil: str, raison: str, entree: dict[str, Any], sortie: str) -> None:
        self.resultat.trace.append(
            {"etape": "orchestrateur", "outil": outil, "raison": raison, "entree": entree, "sortie": sortie}
        )


def _avec_raison(description: dict[str, Any]) -> dict[str, Any]:
    """Ajoute le paramètre obligatoire « raison » au schéma d'un outil (copie)."""
    description = copy.deepcopy(description)
    schema = description["toolSpec"]["inputSchema"]["json"]
    schema["properties"]["raison"] = {
        "type": "string",
        "description": "Pourquoi cette preuve est utile au dossier : une phrase courte, sans chiffre",
    }
    schema["required"] = [*schema["required"], "raison"]
    return description
