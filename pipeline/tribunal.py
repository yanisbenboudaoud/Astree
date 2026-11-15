"""Le Tribunal : enchaîne les phases du procès et assemble le contrat (CLAUDE.md, sections 4 et 5).

Phases fixes, imposées par Python : Profil → Orchestrateur → Procureur et
Avocat → Greffier → Verdict.

Toutes les phases sont branchées : le contrat est complet, pour une décision de
type « position » comme pour une « reallocation » vers un panier (#16).

Pacte vécu (#68) : si l'utilisateur a répondu aux jours de marché revécus,
``calibrage`` est vérifié **avant** tout appel Bedrock ; la règle de pire baisse
prend le seuil mesuré, et ses réponses deviennent la pièce P2 (``declaree``).

``taille_max_compatible`` (#21) est toujours calculé par Python, que
l'orchestrateur ait demandé l'outil ou non : le curseur de l'écran Décision
en a besoin dans tous les cas.

Les **points de bascule** (#61) relisent la même recherche : dès qu'une règle
calculable du Pacte est en violation, Python verse d'office leur pièce au
dossier, avant le débat, et remplit le champ ``points_de_bascule`` du contrat
(ce qui rendrait chaque règle conforme : taille maximale ou seuil suffisant).

Le Greffier passe en dernier : ``verifier_pacte`` contrôle chaque règle du
Pacte, puis chaque argument du débat est vérifié : ses chiffres
(``verifier_chiffres``, CLAUDE.md, section 4 ter) et le cadre « simulation
seulement » (``verifier_cadre_simulation`` : aucun conseil, aucune promesse,
#60). Un argument refusé est renvoyé **une fois** à son agent
(``corriger_argument``), puis rangé dans ``arguments_rejetes`` s'il échoue encore.
"""

from __future__ import annotations

from typing import Any, Callable

from pipeline.agent_profil import chemin_profil, lancer_agent_profil
from pipeline.cadre_simulation import controle_cadre_simulation
from pipeline.calibrage import calibrer
from pipeline.chiffres import controle_verifier_chiffres, trier_arguments
from pipeline.debat import corriger_argument, debattre
from pipeline.greffier import controle_biais_survivant, controle_performance_passee, verifier_pacte
from pipeline.donnees import HYPOTHESES_DONNEES, date_extraction, seances_americaines
from pipeline.indicateurs import DECIMALES_VALEURS
from pipeline.llm import converser_avec_outils
from pipeline.orchestrateur import RAISON_D_OFFICE, instruire_dossier
from pipeline.pacte import charger_pacte, pacte_pour_contrat, piece_pacte
from pipeline.points_de_bascule import NOM_OUTIL as OUTIL_POINTS_DE_BASCULE
from pipeline.points_de_bascule import piece_points_de_bascule, pour_contrat
from pipeline.taille_max import ResultatRecherche, rechercher_taille_max
from pipeline.simulation import poids_apres_decision, simuler_portefeuille

ID_PIECE_PACTE = "P1"  # le Pacte est la première pièce ; l'orchestrateur numérote la suite
ID_PIECE_CALIBRAGE = "P2"  # réponses du Pacte vécu, quand il y en a (#68)
RAISON_POINTS_DE_BASCULE = f"{RAISON_D_OFFICE} : une règle calculable du Pacte est en violation"

AVERTISSEMENT = (
    "Simulation éducative. Aucune transaction réelle. Ceci n'est pas un conseil financier personnalisé."
)
HYPOTHESES_PROCES = ["Seuils du Pacte choisis par l'équipe", "Portefeuille et capital fictifs"]
LIMITE_PACTE_VECU = "Une réponse à un jour de marché passé ne garantit pas le comportement futur"
LIMITES = [
    "Les rendements passés ne garantissent pas les rendements futurs",
    "Biais du survivant dans l'univers d'actifs",
    "La pire baisse et la volatilité ne sont que des indicateurs de risque parmi d'autres",
]


def juger_decision(
    identifiant_profil: str,
    demande: str,
    converser: Callable[..., Any] = converser_avec_outils,
    calibrage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fait le procès d'une demande pour n'importe quel profil de ``personas/``.

    Args:
        identifiant_profil: ``id`` du profil (nom du fichier ``personas/<id>.json``).
        demande: texte de l'utilisateur (ex. : « Je veux mettre 30 % en Tesla »).
        converser: tour de modèle de l'orchestrateur (remplacé dans les tests).
        calibrage: réponses du Pacte vécu, ou None : ``{"reponses": {id: réponse},
            "date": "AAAA-MM-JJ", "etiquette": "fait" | "fictif"}``.

    Returns:
        Le contrat complet (position ou réallocation). Si
        l'Agent Profil n'a pas pu construire de décision, ``decision`` vaut
        ``None``, aucune pièce n'est calculée et ``controles`` dit quoi préciser.

    Raises:
        ProfilInconnu, PacteInvalide: voir ``lancer_agent_profil``.
        ErreurCalibrage: réponses du Pacte vécu incomplètes ou invalides.
    """
    vecu = None
    if calibrage is not None:  # vérifié avant l'Agent Profil : une erreur ne coûte aucun appel Bedrock
        vecu = calibrer(charger_pacte(chemin_profil(identifiant_profil)), calibrage["reponses"],
                        calibrage["date"], ID_PIECE_CALIBRAGE, calibrage.get("etiquette", "fait"))
    profil = lancer_agent_profil(demande, identifiant_profil, ID_PIECE_PACTE)
    pieces_initiales = [profil.piece_pacte]
    if vecu is not None:
        profil.profil = vecu.profil
        profil.pacte = pacte_pour_contrat(vecu.profil)
        profil.piece_pacte = piece_pacte(vecu.profil, ID_PIECE_PACTE)
        pieces_initiales = [profil.piece_pacte, vecu.piece]
        profil.trace = [profil.trace[0], vecu.trace, *profil.trace[1:]]
    contrat = {
        "persona": identifiant_profil,
        "demande": demande,
        "decision": profil.decision,
        "pacte": profil.pacte,
        "pieces": pieces_initiales,
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

    instruction = instruire_dossier(profil.decision, profil.profil, premier_numero=len(pieces_initiales) + 1,
                                    converser=converser)
    contrat["comparaison"] = comparaison(profil.profil["portefeuille"], profil.decision)
    recherche = rechercher_taille_max(
        profil.profil["portefeuille"], profil.decision, profil.profil["pacte"]["regles"]
    )
    contrat["taille_max_compatible"] = recherche.taille_max
    contrat["pieces"] += instruction.pieces
    contrat["trace"] += instruction.trace
    contrat["points_de_bascule"] = verser_points_de_bascule(recherche, profil.decision, contrat)

    # Débat : Procureur et Avocat en parallèle, sur les mêmes pièces.
    dossier = {"decision": profil.decision, "pacte": profil.pacte, "pieces": contrat["pieces"],
               "periode": bornes_periode()}
    debat = debattre(dossier)
    contrat["trace"] += debat.trace

    # Greffier, en dernier : règles du Pacte, puis chiffres et cadre des arguments.
    controles_pacte = controler_pacte(profil.profil, profil.decision, instruction, contrat["pieces"])
    contrat["trace"].append({
        "etape": "greffier",
        "outil": "verifier_pacte",
        "entree": [regle["id"] for regle in profil.profil["pacte"]["regles"]],
        "sortie": resumer_controles(controles_pacte),
    })
    requisitoire = verifier_cote(debat.requisitoire, "requisitoire", "procureur", dossier, contrat["trace"])
    plaidoirie = verifier_cote(debat.plaidoirie, "plaidoirie", "avocat", dossier, contrat["trace"])
    controle_chiffres = controle_verifier_chiffres(requisitoire, plaidoirie)
    controle_cadre = controle_cadre_simulation(requisitoire, plaidoirie)
    nombre_arguments = f"{len(debat.requisitoire) + len(debat.plaidoirie)} arguments"
    for outil, controle in (("verifier_chiffres", controle_chiffres), ("verifier_cadre_simulation", controle_cadre)):
        contrat["trace"].append(
            {"etape": "greffier", "outil": outil, "entree": nombre_arguments, "sortie": controle["message"]}
        )

    contrat["requisitoire"] = requisitoire.valides
    contrat["plaidoirie"] = plaidoirie.valides
    contrat["arguments_rejetes"] = requisitoire.rejetes + plaidoirie.rejetes
    performance = controle_performance_passee(requisitoire.valides + plaidoirie.valides)
    contrat["controles"] += [*controles_pacte, controle_chiffres, controle_cadre,
                             *([performance] if performance else []), controle_biais_survivant()]
    contrat["hypotheses"] = [periode_analyse(), *HYPOTHESES_DONNEES, *profil.hypotheses,
                             *hypotheses_proces(vecu.seuil if vecu else None)]
    if vecu is not None:
        contrat["limites"].append(LIMITE_PACTE_VECU)
    return contrat


def verser_points_de_bascule(
    recherche: ResultatRecherche,
    decision: dict[str, Any],
    contrat: dict[str, Any],
) -> list[dict[str, Any]]:
    """Verse d'office la pièce des points de bascule (#61) et renvoie le champ du contrat.

    Sans règle calculable en violation : ni pièce ni étape de trace, champ vide.
    Sinon, la pièce prend le numéro suivant et l'étape de trace porte la raison
    d'office, comme la simulation obligatoire.
    """
    id_piece = f"P{prochain_numero(contrat['pieces'])}"
    piece = piece_points_de_bascule(id_piece, recherche, decision)
    if piece is None:
        return []
    contrat["pieces"].append(piece)
    contrat["trace"].append({
        "etape": "orchestrateur",
        "outil": OUTIL_POINTS_DE_BASCULE,
        "raison": RAISON_POINTS_DE_BASCULE,
        "entree": {"regles": piece["valeurs"]["regles_en_violation"]},
        "sortie": id_piece,
    })
    return pour_contrat(recherche, decision, id_piece)


def prochain_numero(pieces: list[dict[str, Any]]) -> int:
    """Numéro de la prochaine pièce : celui qui suit la plus grande pièce « P<n> » du dossier.

    Sert aussi au contre-interrogatoire (#55), qui numérote ses pièces à la suite.
    """
    numeros = [int(piece["id"][1:]) for piece in pieces if piece["id"][1:].isdigit()]
    return max(numeros, default=0) + 1


def hypotheses_proces(seuil_mesure: float | None) -> list[str]:
    """Les seuils sont des hypothèses de l'équipe, sauf la pire baisse si le Pacte vécu l'a mesurée."""
    if seuil_mesure is None:
        return list(HYPOTHESES_PROCES)
    return [f"Seuil de pire baisse mesuré sur les réponses de l'utilisateur ({ID_PIECE_CALIBRAGE}) ; "
            "autres seuils choisis par l'équipe", *HYPOTHESES_PROCES[1:]]


def verifier_cote(arguments, cote, role, dossier, trace):
    """Chiffres et cadre d'un côté du débat, avec une relance par argument refusé.

    Chaque relance ajoute l'étape de trace de ``corriger_argument``.
    """
    def corriger(argument, motif):
        corrige, etape = corriger_argument(role, dossier, argument, motif)
        trace.append(etape)
        return corrige

    return trier_arguments(arguments, cote, dossier, corriger)


def controler_pacte(profil, decision, instruction, pieces) -> list[dict[str, Any]]:
    """Un contrôle par règle du Pacte (outil 5 du Greffier)."""
    regles = profil["pacte"]["regles"]
    poids_apres = poids_apres_decision(profil["portefeuille"], decision)
    return verifier_pacte(regles, poids_apres, instruction.piece_simulation, ID_PIECE_PACTE, pieces)


def resumer_controles(controles: list[dict[str, Any]]) -> str:
    """« 1 violation, 1 conforme, 2 à vérifier » (statuts absents omis)."""
    noms = {"violation": ("violation", "violations"), "conforme": ("conforme", "conformes"),
            "a_verifier": ("à vérifier", "à vérifier")}
    parties = []
    for statut, (singulier, pluriel) in noms.items():
        nombre = sum(1 for controle in controles if controle["statut"] == statut)
        if nombre:
            parties.append(f"{nombre} {singulier if nombre == 1 else pluriel}")
    return ", ".join(parties)


def comparaison(portefeuille: list[dict[str, Any]], decision: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Champ « comparaison » du contrat : indicateurs avant et après, valeurs brutes."""
    return {
        cote: {nom: round(valeur, DECIMALES_VALEURS) for nom, valeur in indicateurs.items()}
        for cote, indicateurs in simuler_portefeuille(portefeuille, decision).items()
    }


def bornes_periode() -> list[str]:
    """Première et dernière séance de la période d'analyse (dates ISO)."""
    seances = seances_americaines()
    return [seances[0].date().isoformat(), seances[-1].date().isoformat()]


def periode_analyse() -> str:
    debut, fin = bornes_periode()
    return f"Période : {debut} au {fin}"


def sources() -> list[dict[str, str]]:
    return [
        {"nom": "Yahoo Finance via yfinance", "fichier": "prices_daily.csv",
         "date_extraction": date_extraction("prices_daily.csv")},
        {"nom": "Banque du Canada (API Valet)", "fichier": "fx_usdcad_daily.csv",
         "date_extraction": date_extraction("fx_usdcad_daily.csv")},
    ]
