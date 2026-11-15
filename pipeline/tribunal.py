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

Progression en direct (#90) : avec ``signaler``, chaque étape réelle est publiée au
moment où elle a lieu (début de chaque phase, chaque appel d'outil de l'orchestrateur,
retour du Procureur et de l'Avocat, chaque renvoi du Greffier ; format dans
``pipeline.progression``). Le contrat est identique avec ou sans ``signaler``.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

from pipeline.agent_profil import charger_profil, lancer_agent_profil
from pipeline.cadre_simulation import controle_cadre_simulation
from pipeline.calibrage import ResultatCalibrage, calibrer
from pipeline.chiffres import controle_verifier_chiffres, trier_arguments
from pipeline.composition import NOM_OUTIL as OUTIL_COMPOSITION
from pipeline.composition import piece_composition
from pipeline.debat import corriger_argument, debattre
from pipeline.greffier import controle_biais_survivant, controle_performance_passee, verifier_pacte
from pipeline.donnees import HYPOTHESES_DONNEES, seances_americaines
from pipeline.frais import HYPOTHESE_FRAIS
from pipeline.macro import HYPOTHESE_TAUX_SANS_RISQUE
from pipeline.sources import VALEURS_FRAIS, sources_du_proces
from pipeline.indicateurs import DECIMALES_VALEURS
from pipeline.llm import converser_avec_outils
from pipeline.orchestrateur import RAISON_D_OFFICE, instruire_dossier
from pipeline.pacte import pacte_pour_contrat, piece_pacte
from pipeline.points_de_bascule import NOM_OUTIL as OUTIL_POINTS_DE_BASCULE
from pipeline.points_de_bascule import piece_points_de_bascule, pour_contrat
from pipeline.progression import Signaler, ne_rien_signaler
from pipeline.questionnaire import NOM_OUTIL_PIECE as OUTIL_QUESTIONNAIRE
from pipeline.questionnaire import controles_questionnaire, piece_questionnaire
from pipeline.taille_max import ResultatRecherche, rechercher_taille_max
from pipeline.simulation import poids_apres_decision, simuler_portefeuille

ID_PIECE_PACTE = "P1"  # le Pacte est la première pièce ; l'orchestrateur numérote la suite
ID_PIECE_CALIBRAGE = "P2"  # réponses du Pacte vécu, quand il y en a (#68)
RAISON_POINTS_DE_BASCULE = f"{RAISON_D_OFFICE} : une règle calculable du Pacte est en violation"
RAISON_COMPOSITION = f"{RAISON_D_OFFICE} : le portefeuille contient des FNB, lus selon leur composition publiée"
HYPOTHESE_COMPOSITION = ("Composition des FNB relevée sur les pages des émetteurs à une date donnée, "
                         "appliquée à toute la période")

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

# Ce que fait le Tribunal au début de chaque phase (progression en direct, #90).
ACTIVITES = {
    "agent_profil": "L'Agent Profil charge le Pacte et structure la demande (Bedrock)",
    "orchestrateur": "L'orchestrateur choisit les preuves à rassembler (Bedrock) ; Python exécute chaque outil",
    "calculs": "Python compare le portefeuille avant et après, et cherche la taille maximale compatible",
    "debat": "Le Procureur et l'Avocat plaident en parallèle, à partir des pièces (Bedrock)",
    "greffier": "Le Greffier contrôle le Pacte, puis les chiffres et le cadre de chaque argument (Python)",
}
DESTINATAIRES = {"procureur": "au Procureur", "avocat": "à l'Avocat"}


def verifier_avant_proces(
    identifiant_profil: str,
    calibrage: dict[str, Any] | None = None,
) -> ResultatCalibrage | None:
    """Contrôles sans Bedrock avant un procès : profil connu et valide, réponses du Pacte vécu complètes.

    La Lambda s'en sert pour refuser tout de suite une demande invalide, avant de lancer
    le procès en arrière-plan (#90).

    Returns:
        Le calibrage du Pacte vécu (#68), ou None sans réponses.

    Raises:
        ProfilInconnu, PacteInvalide: profil introuvable ou invalide (``personas/`` ou profil créé, #87).
        ErreurDonnees: profil créé illisible.
        ErreurCalibrage: réponses du Pacte vécu incomplètes ou invalides.
    """
    profil = charger_profil(identifiant_profil)
    if calibrage is None:
        return None
    return calibrer(profil, calibrage["reponses"], calibrage["date"], ID_PIECE_CALIBRAGE,
                    calibrage.get("etiquette", "fait"))


def juger_decision(
    identifiant_profil: str,
    demande: str,
    converser: Callable[..., Any] = converser_avec_outils,
    calibrage: dict[str, Any] | None = None,
    signaler: Signaler | None = None,
) -> dict[str, Any]:
    """Fait le procès d'une demande pour n'importe quel profil de ``personas/``.

    Args:
        identifiant_profil: ``id`` du profil : un fichier ``personas/<id>.json`` ou un profil créé (#87).
        demande: texte de l'utilisateur (ex. : « Je veux mettre 30 % en Tesla »).
        converser: tour de modèle de l'orchestrateur (remplacé dans les tests).
        calibrage: réponses du Pacte vécu, ou None : ``{"reponses": {id: réponse},
            "date": "AAAA-MM-JJ", "etiquette": "fait" | "fictif"}``.
        signaler: appelée à chaque étape réelle du procès (``pipeline.progression``),
            éventuellement depuis le fil d'exécution du Procureur ou de l'Avocat. None :
            rien n'est signalé.

    Returns:
        Le contrat complet (position ou réallocation). Si
        l'Agent Profil n'a pas pu construire de décision, ``decision`` vaut
        ``None``, aucune pièce n'est calculée et ``controles`` dit quoi préciser.

    Raises:
        ProfilInconnu, PacteInvalide: voir ``lancer_agent_profil``.
        ErreurCalibrage: réponses du Pacte vécu incomplètes ou invalides.
    """
    signaler = signaler or ne_rien_signaler

    def signaler_etape(etape: dict[str, Any]) -> None:
        signaler({"type": "etape", "etape": etape})

    def commencer(phase: str) -> None:
        signaler({"type": "phase", "phase": phase, "activite": ACTIVITES[phase]})

    vecu = None
    if calibrage is not None:  # vérifié avant l'Agent Profil : une erreur ne coûte aucun appel Bedrock
        vecu = verifier_avant_proces(identifiant_profil, calibrage)
    commencer("agent_profil")
    profil = lancer_agent_profil(demande, identifiant_profil, ID_PIECE_PACTE)
    pieces_initiales = [profil.piece_pacte]
    if vecu is not None:
        profil.profil = vecu.profil
        profil.pacte = pacte_pour_contrat(vecu.profil)
        profil.piece_pacte = piece_pacte(vecu.profil, ID_PIECE_PACTE)
        pieces_initiales = [profil.piece_pacte, vecu.piece]
        profil.trace = [profil.trace[0], vecu.trace, *profil.trace[1:]]
    controles_initiaux = list(profil.controles)
    if "questionnaire" in profil.profil:  # Pacte tiré du questionnaire (#84) : réponses et contradictions (#85)
        id_questionnaire = f"P{len(pieces_initiales) + 1}"
        piece_q = piece_questionnaire(profil.profil, id_questionnaire)
        pieces_initiales.append(piece_q)
        controles_q = controles_questionnaire(profil.profil, id_questionnaire, profil.decision,
                                              vecu.piece if vecu is not None else None)
        controles_initiaux += controles_q
        profil.trace.append({
            "etape": "agent_profil",
            "outil": OUTIL_QUESTIONNAIRE,
            "entree": profil.profil["questionnaire"]["date"],
            "sortie": f"{id_questionnaire} : {len(piece_q['valeurs']['contradictions'])} contradiction(s), "
                      f"{len(controles_q)} contrôle(s) à vérifier",
        })
        profil.hypotheses.append("Règles du Pacte tirées du questionnaire : barème de l'équipe (config/questionnaire.json)")
    for etape in profil.trace:  # étapes de l'Agent Profil (et du questionnaire), signalées à la fin de sa phase
        signaler_etape(etape)
    contrat = {
        "persona": identifiant_profil,
        "demande": demande,
        "decision": profil.decision,
        "pacte": profil.pacte,
        "pieces": pieces_initiales,
        "controles": controles_initiaux,
        "verdict": None,
        "hypotheses": [],
        "sources": [],  # rempli à la fin, d'après ce que le procès a réellement utilisé (#111)
        "limites": list(LIMITES),
        "trace": list(profil.trace),
        "avertissement": AVERTISSEMENT,
    }
    if profil.decision is None:
        contrat["sources"] = sources_du_proces(contrat)
        return contrat

    commencer("orchestrateur")
    instruction = instruire_dossier(profil.decision, profil.profil, premier_numero=len(pieces_initiales) + 1,
                                    converser=converser, signaler_etape=signaler_etape)
    signaler({"type": "activite", "activite": ACTIVITES["calculs"]})
    contrat["comparaison"] = comparaison(profil.profil["portefeuille"], profil.decision)
    recherche = rechercher_taille_max(
        profil.profil["portefeuille"], profil.decision, profil.profil["pacte"]["regles"]
    )
    contrat["taille_max_compatible"] = recherche.taille_max
    contrat["pieces"] += instruction.pieces
    contrat["trace"] += instruction.trace
    verser_composition(profil.profil, profil.decision, contrat, signaler_etape)
    contrat["points_de_bascule"] = verser_points_de_bascule(recherche, profil.decision, contrat, signaler_etape)

    # Débat : Procureur et Avocat en parallèle, sur les mêmes pièces.
    commencer("debat")
    dossier = {"decision": profil.decision, "pacte": profil.pacte, "pieces": contrat["pieces"],
               "periode": bornes_periode()}
    debat = debattre(dossier, signaler_etape=signaler_plaidoirie(signaler))
    contrat["trace"] += debat.trace

    # Greffier, en dernier : règles du Pacte, puis chiffres et cadre des arguments.
    commencer("greffier")
    controles_pacte = controler_pacte(profil.profil, profil.decision, instruction, contrat["pieces"])
    tracer(contrat["trace"], signaler_etape, {
        "etape": "greffier",
        "outil": "verifier_pacte",
        "entree": [regle["id"] for regle in profil.profil["pacte"]["regles"]],
        "sortie": resumer_controles(controles_pacte),
    })
    requisitoire = verifier_cote(debat.requisitoire, "requisitoire", "procureur", dossier, contrat["trace"], signaler)
    plaidoirie = verifier_cote(debat.plaidoirie, "plaidoirie", "avocat", dossier, contrat["trace"], signaler)
    controle_chiffres = controle_verifier_chiffres(requisitoire, plaidoirie)
    controle_cadre = controle_cadre_simulation(requisitoire, plaidoirie)
    nombre_arguments = f"{len(debat.requisitoire) + len(debat.plaidoirie)} arguments"
    for outil, controle in (("verifier_chiffres", controle_chiffres), ("verifier_cadre_simulation", controle_cadre)):
        tracer(contrat["trace"], signaler_etape,
               {"etape": "greffier", "outil": outil, "entree": nombre_arguments, "sortie": controle["message"]})

    contrat["requisitoire"] = requisitoire.valides
    contrat["plaidoirie"] = plaidoirie.valides
    contrat["arguments_rejetes"] = requisitoire.rejetes + plaidoirie.rejetes
    performance = controle_performance_passee(requisitoire.valides + plaidoirie.valides)
    contrat["controles"] += [*controles_pacte, controle_chiffres, controle_cadre,
                             *([performance] if performance else []), controle_biais_survivant()]
    contrat["hypotheses"] = [periode_analyse(), *HYPOTHESES_DONNEES, *profil.hypotheses,
                             *hypotheses_proces(vecu.seuil if vecu else None)]
    if any("taux_sans_risque_moyen" in piece["valeurs"] for piece in contrat["pieces"]):
        contrat["hypotheses"].append(HYPOTHESE_TAUX_SANS_RISQUE)
    if any(piece.get("outil") == OUTIL_COMPOSITION for piece in contrat["pieces"]):
        contrat["hypotheses"].append(HYPOTHESE_COMPOSITION)
    if any(cle in piece["valeurs"] for piece in contrat["pieces"] for cle in VALEURS_FRAIS):
        contrat["hypotheses"].append(HYPOTHESE_FRAIS)
    if vecu is not None:
        contrat["limites"].append(LIMITE_PACTE_VECU)
    contrat["sources"] = sources_du_proces(contrat)
    return contrat


def verser_composition(
    profil: dict[str, Any],
    decision: dict[str, Any],
    contrat: dict[str, Any],
    signaler_etape: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    """Verse d'office la pièce de composition des FNB (#116), quand le portefeuille en contient.

    Les plafonds du Greffier sont calculés par transparence : la pièce montre la composition
    utilisée et la part de chaque catégorie, pour que les agents puissent la citer et que le
    contrôle s'y réfère. Sans FNB à lire : ni pièce ni étape de trace.
    """
    id_piece = f"P{prochain_numero(contrat['pieces'])}"
    piece = piece_composition(id_piece, profil["portefeuille"], decision, profil["pacte"]["regles"])
    if piece is None:
        return
    contrat["pieces"].append(piece)
    tracer(contrat["trace"], signaler_etape, {
        "etape": "orchestrateur",
        "outil": OUTIL_COMPOSITION,
        "raison": RAISON_COMPOSITION,
        "entree": {"fonds": piece["valeurs"]["fonds_lus"]},
        "sortie": id_piece,
    })


def verser_points_de_bascule(
    recherche: ResultatRecherche,
    decision: dict[str, Any],
    contrat: dict[str, Any],
    signaler_etape: Callable[[dict[str, Any]], None] | None = None,
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
    tracer(contrat["trace"], signaler_etape, {
        "etape": "orchestrateur",
        "outil": OUTIL_POINTS_DE_BASCULE,
        "raison": RAISON_POINTS_DE_BASCULE,
        "entree": {"regles": piece["valeurs"]["regles_en_violation"]},
        "sortie": id_piece,
    })
    return pour_contrat(recherche, decision, id_piece)


def signaler_plaidoirie(signaler: Signaler) -> Callable[[dict[str, Any]], None]:
    """Signal du débat : chaque plaidoirie dès son retour, puis qui plaide encore (« L'Avocat plaide encore »).

    Appelée depuis les deux fils du débat : un verrou garde le compte des retours.
    """
    verrou, retours = threading.Lock(), []

    def signaler_etape(etape: dict[str, Any]) -> None:
        signaler({"type": "etape", "etape": etape})
        with verrou:
            retours.append(etape["etape"])
            premier = len(retours) == 1
        if premier:
            reste = "L'Avocat" if etape["etape"] == "procureur" else "Le Procureur"
            signaler({"type": "activite", "activite": f"{reste} plaide encore (Bedrock)"})

    return signaler_etape


def tracer(
    trace: list[dict[str, Any]],
    signaler_etape: Callable[[dict[str, Any]], None] | None,
    etape: dict[str, Any],
) -> None:
    """Ajoute une étape à la trace du contrat et la signale aussitôt (progression, #90)."""
    trace.append(etape)
    if signaler_etape is not None:
        signaler_etape(etape)


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


def verifier_cote(arguments, cote, role, dossier, trace, signaler: Signaler | None = None):
    """Chiffres et cadre d'un côté du débat, avec une relance par argument refusé.

    Chaque relance ajoute l'étape de trace de ``corriger_argument``. Avec ``signaler``
    (#90), le renvoi est annoncé avant l'appel à Bedrock, puis l'étape est signalée.
    """
    def corriger(argument, motif):
        if signaler is not None:
            signaler({"type": "activite", "activite": f"Argument renvoyé {DESTINATAIRES[role]} par le Greffier : {motif}"})
        corrige, etape = corriger_argument(role, dossier, argument, motif)
        tracer(trace, None if signaler is None else lambda e: signaler({"type": "etape", "etape": e}), etape)
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

