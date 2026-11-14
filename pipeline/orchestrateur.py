"""Orchestrateur : instruit le dossier en choisissant les outils Python à appeler.

Deuxième phase du Tribunal (CLAUDE.md, section 4). Un modèle Bedrock lit la
décision et le Pacte, choisit lui-même les outils et leurs paramètres, et donne
une raison courte pour chaque appel. Python exécute chaque appel ; chaque
résultat devient une pièce numérotée (P1, P2…).

Garde-fous, tous appliqués par Python :
- **liste blanche** : seuls les outils passés dans ``outils`` sont décrits au
  modèle et exécutés (outils 1 à 4 ; jamais ceux du Greffier) ;
- **budget** : ``BUDGET_APPELS`` appels au plus, puis on passe au débat ;
- **raison** : obligatoire, une phrase, sans chiffre ; sinon l'appel est refusé ;
- **pièce obligatoire** : si le modèle n'a pas demandé ``OUTIL_OBLIGATOIRE``,
  Python l'ajoute d'office et le note dans la trace ;
- **erreur d'outil** (ex. : titre hors univers) : renvoyée au modèle comme
  résultat en erreur, sans planter et sans créer de pièce.

L'orchestrateur ne calcule rien et ne rend aucun verdict.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from pipeline import indicateurs
from pipeline.donnees import ErreurDonnees
from pipeline.llm import (
    DemandeOutil,
    converser_avec_outils,
    message_resultats,
    message_utilisateur,
    resultat_outil,
)

BUDGET_APPELS = 8  # hypothèse de l'équipe (CLAUDE.md, section 4)
OUTIL_OBLIGATOIRE = "simuler_portefeuille"
LONGUEUR_MAX_RAISON = 160

RAISON_D_OFFICE = "Pièce obligatoire ajoutée d'office"
RAISON_INDISPONIBLE = "Pièce obligatoire indisponible : outil pas encore construit"
RAISON_REFUSEE = "Raison refusée par le garde-fou"


@dataclass(frozen=True)
class Outil:
    """Un outil que l'orchestrateur peut appeler."""

    nom: str
    description_bedrock: dict[str, Any]  # créée avec llm.decrire_outil
    executer: Callable[..., dict[str, Any]]  # paramètres du schéma → pièce sans « id »


# Outils construits à ce jour. simuler_portefeuille (#9) et
# taille_max_compatible (#21) s'ajouteront ici.
OUTILS_DISPONIBLES = [
    Outil("indicateurs_actif", indicateurs.DESCRIPTION_BEDROCK, indicateurs.indicateurs_actif),
]


@dataclass
class ResultatInstruction:
    """Ce que l'orchestrateur transmet au Procureur, à l'Avocat et au Greffier."""

    pieces: list[dict[str, Any]] = field(default_factory=list)  # pièces numérotées
    trace: list[dict[str, Any]] = field(default_factory=list)  # étapes « orchestrateur »
    appels: int = 0  # appels d'outils demandés par le modèle, refusés compris


CONSIGNES = """Tu es l'orchestrateur d'un outil éducatif de simulation d'investissement.
Un investisseur propose une décision. Avant qu'elle soit débattue, tu instruis le dossier :
tu choisis quels outils de calcul appeler pour rassembler les preuves utiles.

Règles :
- Tu ne calcules rien toi-même : tous les chiffres viennent des outils.
- Appelle seulement les outils utiles pour juger CETTE décision au regard de CE Pacte.
  Par exemple : un horizon court rend le temps de récupération d'un titre important.
- Chaque appel a un paramètre « raison » : une phrase courte, en français, qui dit pourquoi
  cette preuve est utile. La raison ne contient AUCUN chiffre.
- Tu as au plus {budget} appels d'outils. Tu peux demander plusieurs outils à la fois.
- Si un outil renvoie une erreur, ne réessaie pas à l'identique.
- Quand le dossier est suffisant, réponds en une phrase, sans appeler d'outil.
- Tu ne donnes ni avis ni verdict : d'autres agents débattront à partir des pièces."""


def instruire_dossier(
    decision: dict[str, Any],
    profil: dict[str, Any],
    outils: list[Outil] | None = None,
    converser: Callable[..., Any] = converser_avec_outils,
    premier_numero: int = 1,
) -> ResultatInstruction:
    """Laisse le modèle choisir les outils, exécute ses appels et numérote les pièces.

    Args:
        decision: décision structurée (format « decision » du contrat).
        profil: profil chargé (personas/<id>.json) ; le code ne lit que ses
            règles, son horizon, son profil de risque et son portefeuille.
        outils: liste blanche des outils permis (par défaut ``OUTILS_DISPONIBLES``).
        converser: fonction qui fait jouer un tour au modèle (remplacée dans les tests).
        premier_numero: numéro de la première pièce créée ici (P1 par défaut).
    """
    outils = OUTILS_DISPONIBLES if outils is None else outils
    par_nom = {outil.nom: outil for outil in outils}
    instruction = _Instruction(par_nom, premier_numero)

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

    instruction.ajouter_piece_obligatoire(decision)
    return instruction.resultat


def construire_dossier(decision: dict[str, Any], profil: dict[str, Any]) -> str:
    """Ce que le modèle lit : la décision et le Pacte, sans les justifications des règles."""
    regles = [
        {cle: valeur for cle, valeur in regle.items() if cle != "justification"}
        for regle in profil["pacte"]["regles"]
    ]
    dossier = {
        "decision": decision,
        "pacte": {
            "profil_risque": profil["profil_risque"],
            "horizon_ans": profil["horizon_ans"],
            "regles": regles,
        },
        "portefeuille_actuel": profil["portefeuille"],
    }
    return "Dossier à instruire :\n" + json.dumps(dossier, ensure_ascii=False, indent=2)


def raison_valide(raison: Any) -> bool:
    """Une phrase courte, non vide, sans chiffre."""
    return (
        isinstance(raison, str)
        and 0 < len(raison.strip()) <= LONGUEUR_MAX_RAISON
        and not re.search(r"\d", raison)
    )


class _Instruction:
    """État d'une instruction en cours : pièces créées, trace et appels comptés."""

    def __init__(self, outils: dict[str, Outil], premier_numero: int):
        self.outils = outils
        self.numero = premier_numero
        self.resultat = ResultatInstruction()

    def traiter_demande(self, demande: DemandeOutil) -> dict[str, Any]:
        """Exécute une demande du modèle et renvoie le bloc de résultat à lui retourner."""
        self.resultat.appels += 1
        entree = dict(demande.entree)
        raison = entree.pop("raison", None)

        if self.resultat.appels > BUDGET_APPELS:
            return self._refuser(demande, entree, RAISON_REFUSEE, "Budget d'appels atteint")
        if demande.nom not in self.outils:
            return self._refuser(demande, entree, RAISON_REFUSEE,
                                 f"Outil « {demande.nom} » non autorisé")
        if not raison_valide(raison):
            return self._refuser(demande, entree, RAISON_REFUSEE,
                                 "La raison doit être une phrase courte, sans chiffre")

        try:
            piece = self._executer(demande.nom, entree, raison)
        except ErreurDonnees as erreur:
            return self._refuser(demande, entree, raison, str(erreur))
        return resultat_outil(demande, piece)

    def ajouter_piece_obligatoire(self, decision: dict[str, Any]) -> None:
        deja_demandee = any(
            etape["outil"] == OUTIL_OBLIGATOIRE and etape["sortie"].startswith("P")
            for etape in self.resultat.trace
        )
        if deja_demandee:
            return
        entree = {cle: valeur for cle, valeur in decision.items() if cle != "libelle"}
        if OUTIL_OBLIGATOIRE not in self.outils:
            self._tracer(OUTIL_OBLIGATOIRE, RAISON_INDISPONIBLE, entree, "Aucune pièce")
            return
        self._executer(OUTIL_OBLIGATOIRE, entree, RAISON_D_OFFICE)

    def _executer(self, nom: str, entree: dict[str, Any], raison: str) -> dict[str, Any]:
        piece = {"id": f"P{self.numero}", **self.outils[nom].executer(**entree)}
        self.numero += 1
        self.resultat.pieces.append(piece)
        self._tracer(nom, raison, entree, piece["id"])
        return piece

    def _refuser(self, demande: DemandeOutil, entree: dict[str, Any], raison: str,
                 motif: str) -> dict[str, Any]:
        self._tracer(demande.nom, raison, entree, f"Erreur : {motif}")
        return resultat_outil(demande, {"erreur": motif}, erreur=True)

    def _tracer(self, outil: str, raison: str, entree: dict[str, Any], sortie: str) -> None:
        self.resultat.trace.append({
            "etape": "orchestrateur",
            "outil": outil,
            "raison": raison,
            "entree": entree,
            "sortie": sortie,
        })


def _avec_raison(description: dict[str, Any]) -> dict[str, Any]:
    """Ajoute le paramètre obligatoire « raison » au schéma d'un outil."""
    description = copy.deepcopy(description)
    schema = description["toolSpec"]["inputSchema"]["json"]
    schema["properties"]["raison"] = {
        "type": "string",
        "description": "Pourquoi cette preuve est utile au dossier : une phrase courte, sans chiffre",
    }
    schema["required"] = [*schema["required"], "raison"]
    return description
