"""Le Tribunal : enchaîne les phases du procès et assemble le contrat (CLAUDE.md, sections 4 et 5).

Phases fixes, imposées par Python : Profil → Orchestrateur → Procureur et
Avocat → Greffier → Verdict.

État actuel (#12 en cours) : les phases **Profil** et **Orchestrateur** sont
branchées. Le débat (#11), le Greffier (#10) et ``taille_max_compatible`` (#21)
s'ajouteront ici ; d'ici là, ``juger_decision`` renvoie un contrat **partiel** :
les champs ``taille_max_compatible``, ``requisitoire``, ``plaidoirie`` et
``arguments_rejetes`` sont absents, et ``controles`` ne contient que ceux de
l'Agent Profil.
"""

from __future__ import annotations

from typing import Any, Callable

from pipeline.agent_profil import lancer_agent_profil
from pipeline.donnees import HYPOTHESES_DONNEES, date_extraction, seances_americaines
from pipeline.indicateurs import DECIMALES_VALEURS
from pipeline.llm import converser_avec_outils
from pipeline.orchestrateur import instruire_dossier
from pipeline.simulation import simuler_portefeuille

ID_PIECE_PACTE = "P1"  # le Pacte est la première pièce ; l'orchestrateur numérote la suite

AVERTISSEMENT = (
    "Simulation éducative. Aucune transaction réelle. Ceci n'est pas un conseil financier personnalisé."
)
HYPOTHESES_PROCES = ["Seuils du Pacte choisis par l'équipe", "Portefeuille et capital fictifs"]
LIMITES = [
    "Les rendements passés ne garantissent pas les rendements futurs",
    "Biais du survivant dans l'univers d'actifs",
    "La pire baisse et la volatilité ne sont que des indicateurs de risque parmi d'autres",
]


def juger_decision(
    identifiant_profil: str,
    demande: str,
    converser: Callable[..., Any] = converser_avec_outils,
) -> dict[str, Any]:
    """Fait le procès d'une demande pour n'importe quel profil de ``personas/``.

    Args:
        identifiant_profil: ``id`` du profil (nom du fichier ``personas/<id>.json``).
        demande: texte de l'utilisateur (ex. : « Je veux mettre 30 % en Tesla »).
        converser: tour de modèle de l'orchestrateur (remplacé dans les tests).

    Returns:
        Le contrat (partiel tant que #10, #11 et #21 ne sont pas branchés). Si
        l'Agent Profil n'a pas pu construire de décision, ``decision`` vaut
        ``None``, aucune pièce n'est calculée et ``controles`` dit quoi préciser.

    Raises:
        ProfilInconnu, PacteInvalide: voir ``lancer_agent_profil``.
    """
    profil = lancer_agent_profil(demande, identifiant_profil, ID_PIECE_PACTE)
    contrat = {
        "persona": identifiant_profil,
        "demande": demande,
        "decision": profil.decision,
        "pacte": profil.pacte,
        "pieces": [profil.piece_pacte],
        "controles": list(profil.controles),
        "verdict": None,
        "hypotheses": [],
        "sources": sources(),
        "limites": list(LIMITES),
        "trace": list(profil.trace),
        "avertissement": AVERTISSEMENT,
    }
    if profil.decision is None:
        return contrat

    instruction = instruire_dossier(profil.decision, profil.profil, premier_numero=2, converser=converser)
    contrat["comparaison"] = comparaison(profil.profil["portefeuille"], profil.decision)
    contrat["pieces"] += instruction.pieces
    contrat["trace"] += instruction.trace
    contrat["hypotheses"] = [periode_analyse(), *HYPOTHESES_DONNEES, *profil.hypotheses, *HYPOTHESES_PROCES]
    return contrat


def comparaison(portefeuille: list[dict[str, Any]], decision: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Champ « comparaison » du contrat : indicateurs avant et après, valeurs brutes."""
    return {
        cote: {nom: round(valeur, DECIMALES_VALEURS) for nom, valeur in indicateurs.items()}
        for cote, indicateurs in simuler_portefeuille(portefeuille, decision).items()
    }


def periode_analyse() -> str:
    seances = seances_americaines()
    return f"Période : {seances[0].date().isoformat()} au {seances[-1].date().isoformat()}"


def sources() -> list[dict[str, str]]:
    return [
        {"nom": "Yahoo Finance via yfinance", "fichier": "prices_daily.csv",
         "date_extraction": date_extraction("prices_daily.csv")},
        {"nom": "Banque du Canada (API Valet)", "fichier": "fx_usdcad_daily.csv",
         "date_extraction": date_extraction("fx_usdcad_daily.csv")},
    ]
