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

Poches (#115) : pour un profil dont le portefeuille a plusieurs horizons, l'Agent
Profil choisit la poche jugée et projette le profil sur elle
(``pipeline.poches.profil_de_la_poche``). Tout le reste du procès lit ce profil
projeté : simulation, taille maximale et règles portent sur la poche. Sans poches,
le contrat est exactement le même qu'avant.

Progression en direct (#90) : avec ``signaler``, chaque étape réelle est publiée au
moment où elle a lieu (début de chaque phase, chaque appel d'outil de l'orchestrateur,
retour du Procureur et de l'Avocat, chaque renvoi du Greffier ; format dans
``pipeline.progression``). Le contrat est identique avec ou sans ``signaler``.

Agents coordonnés et mesurés (#189) :
- **Réplique** : après les plaidoiries, chaque camp répond à l'argument adverse qui pèse
  le plus contre lui (``pipeline.debat.repliquer_les_deux``), en ne visant que des
  arguments que le Greffier accepte tels quels. Le Greffier vérifie les répliques comme
  les autres ; une réplique dont l'argument visé est finalement écarté est rejetée.
- **Mesure** : chaque étape de trace porte son ``horodatage`` ; le champ ``bedrock`` du
  contrat compte les appels Bedrock par agent, les jetons, la durée et le coût estimé.
- **Guardrail Bedrock** (s'il est configuré) : la demande est soumise au Guardrail avant
  tout appel au modèle (``RefusGardeFou`` si elle tente de détourner les consignes), et
  chaque argument qui passe les vérifications Python l'est aussi, en sortie.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from pipeline.agent_profil import charger_profil, lancer_agent_profil
from pipeline.cadre_simulation import controle_cadre_simulation
from pipeline.calibrage import ErreurCalibrage, ResultatCalibrage, calibrer
from pipeline.chiffres import controle_verifier_chiffres, trier_arguments
from pipeline.composition import NOM_OUTIL as OUTIL_COMPOSITION
from pipeline.composition import piece_composition
from pipeline.chiffres import argument_recevable
from pipeline.debat import CHAMP_CONTRAT, ADVERSAIRE, corriger_argument, debattre, repliquer_les_deux
from pipeline.greffier import controle_biais_survivant, controle_performance_passee, verifier_pacte
from pipeline.donnees import HYPOTHESES_DONNEES, seances_americaines
from pipeline.frais import HYPOTHESE_FRAIS
from pipeline.macro import HYPOTHESE_TAUX_SANS_RISQUE
from pipeline.sources import VALEURS_FRAIS, sources_du_proces
from pipeline.indicateurs import DECIMALES_VALEURS
from pipeline.llm import RefusGardeFou, compter_appels, converser_avec_outils, garde_fou_actif, verifier_garde_fou
from pipeline.orchestrateur import RAISON_D_OFFICE, instruire_dossier
from pipeline.pacte import pacte_pour_contrat, piece_pacte
from pipeline.points_de_bascule import NOM_OUTIL as OUTIL_POINTS_DE_BASCULE
from pipeline.points_de_bascule import piece_points_de_bascule, pour_contrat
from pipeline.poches import a_des_poches, profil_de_la_poche
from pipeline.progression import Signaler, horodater, ne_rien_signaler
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
LIMITE_POCHE = ("Seule la poche concernée est simulée : l'effet de la décision sur les autres poches et "
                "sur le portefeuille global n'est pas jugé")
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
    "replique": "Chacun répond à l'argument de l'autre qui pèse le plus contre lui (Bedrock)",
    "greffier": "Le Greffier contrôle le Pacte, puis les chiffres et le cadre de chaque argument (Python)",
}
DESTINATAIRES = {"procureur": "au Procureur", "avocat": "à l'Avocat"}
RAISON_CIBLE_ECARTEE = "L'argument visé par cette réplique a été écarté par le Greffier"


def verifier_avant_proces(
    identifiant_profil: str,
    calibrage: dict[str, Any] | None = None,
    poche: str | None = None,
) -> ResultatCalibrage | None:
    """Contrôles sans Bedrock avant un procès : profil connu et valide, poche existante, réponses du Pacte vécu complètes.

    La Lambda s'en sert pour refuser tout de suite une demande invalide, avant de lancer
    le procès en arrière-plan (#90).

    Profil à poches (#115) : le Pacte vécu calibre la règle de pire baisse **d'une poche**
    (ses questions viennent du portefeuille de la poche). La poche doit donc être donnée
    avec les réponses : le modèle ne la déduit qu'après, et les réponses sont vérifiées avant.

    Returns:
        Le calibrage du Pacte vécu (#68), ou None sans réponses.

    Raises:
        ProfilInconnu, PacteInvalide: profil introuvable ou invalide (``personas/`` ou profil créé, #87).
        ErreurDonnees: profil créé illisible.
        PocheInconnue: ``poche`` donnée, mais absente du profil.
        ErreurCalibrage: réponses du Pacte vécu incomplètes ou invalides, ou sans poche pour un profil à poches.
    """
    profil = charger_profil(identifiant_profil)
    if poche is not None:
        profil = profil_de_la_poche(profil, poche)
    if calibrage is None:
        return None
    if a_des_poches(profil):
        raise ErreurCalibrage("Portefeuille divisé en poches : précisez la poche (champ « poche ») "
                              "dont le Pacte vécu mesure la pire baisse")
    return calibrer(profil, calibrage["reponses"], calibrage["date"], ID_PIECE_CALIBRAGE,
                    calibrage.get("etiquette", "fait"))


def juger_decision(
    identifiant_profil: str,
    demande: str,
    converser: Callable[..., Any] = converser_avec_outils,
    calibrage: dict[str, Any] | None = None,
    signaler: Signaler | None = None,
    poche: str | None = None,
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
        poche: profil à poches (#115) : id de la poche choisie par l'utilisateur. None :
            l'Agent Profil la déduit de la demande (sinon, la plus prudente, à vérifier).
            Tout le procès porte ensuite sur cette poche.

    Returns:
        Le contrat complet (position ou réallocation). Si
        l'Agent Profil n'a pas pu construire de décision, ``decision`` vaut
        ``None``, aucune pièce n'est calculée et ``controles`` dit quoi préciser.

    Raises:
        ProfilInconnu, PacteInvalide, PocheInconnue: voir ``lancer_agent_profil``.
        ErreurCalibrage: réponses du Pacte vécu incomplètes ou invalides.
        RefusGardeFou: le Guardrail Bedrock a refusé la demande (aucun appel au modèle).
    """
    debut = time.monotonic()
    with compter_appels() as compteur:
        contrat = _juger(identifiant_profil, demande, converser, calibrage, signaler, poche)
    contrat["bedrock"] = {**compteur.resume(), "duree_proces_s": round(time.monotonic() - debut, 1)}
    return contrat


def _juger(identifiant_profil, demande, converser, calibrage, signaler, poche) -> dict[str, Any]:
    """Le procès lui-même (voir ``juger_decision``), dont les appels Bedrock sont comptés."""
    signaler = horodater_signaux(signaler or ne_rien_signaler)

    def signaler_etape(etape: dict[str, Any]) -> None:
        signaler({"type": "etape", "etape": etape})

    def commencer(phase: str) -> None:
        signaler({"type": "phase", "phase": phase, "activite": ACTIVITES[phase]})

    vecu = None
    if calibrage is not None:  # vérifié avant l'Agent Profil : une erreur ne coûte aucun appel Bedrock
        vecu = verifier_avant_proces(identifiant_profil, calibrage, poche)
    motif = verifier_garde_fou(demande, "INPUT")  # avant tout appel au modèle (#189)
    if motif:
        raise RefusGardeFou(f"Demande refusée : {motif}")
    commencer("agent_profil")
    profil = lancer_agent_profil(demande, identifiant_profil, ID_PIECE_PACTE, poche)
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

    # Réplique (#189) : chaque camp répond à un argument que le Greffier accepterait tel quel.
    commencer("replique")
    repliques = repliquer_les_deux(dossier,
                                   [a for a in debat.requisitoire if argument_recevable(a, dossier)],
                                   [a for a in debat.plaidoirie if argument_recevable(a, dossier)],
                                   signaler_etape=signaler_etape)
    contrat["trace"] += [replique.etape for replique in repliques]

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
    valides = {"procureur": requisitoire.valides, "avocat": plaidoirie.valides}
    visees, cibles_ecartees = {"procureur": [], "avocat": []}, []
    for replique in repliques:
        numero = numero_cible(replique.cible, valides[ADVERSAIRE[replique.role]])
        repond_a = {"cote": CHAMP_CONTRAT[ADVERSAIRE[replique.role]], "numero": numero}
        if numero is None:  # l'argument visé a été corrigé puis rejeté : la réplique ne répond plus à rien
            cibles_ecartees.append({"cote": CHAMP_CONTRAT[replique.role], **replique.argument,
                                    "raison": RAISON_CIBLE_ECARTEE})
            continue
        visees[replique.role].append({**replique.argument, "repond_a": repond_a})
    repliques_requisitoire = verifier_cote(visees["procureur"], "requisitoire", "procureur", dossier,
                                           contrat["trace"], signaler)
    repliques_plaidoirie = verifier_cote(visees["avocat"], "plaidoirie", "avocat", dossier, contrat["trace"], signaler)
    tris = (requisitoire, plaidoirie, repliques_requisitoire, repliques_plaidoirie)
    controle_chiffres = controle_verifier_chiffres(*tris)
    controle_cadre = controle_cadre_simulation(*tris)
    nombre_arguments = f"{len(debat.requisitoire) + len(debat.plaidoirie) + len(repliques)} arguments"
    for outil, controle in (("verifier_chiffres", controle_chiffres), ("verifier_cadre_simulation", controle_cadre)):
        tracer(contrat["trace"], signaler_etape,
               {"etape": "greffier", "outil": outil, "entree": nombre_arguments, "sortie": controle["message"]})

    contrat["requisitoire"] = requisitoire.valides + repliques_requisitoire.valides
    contrat["plaidoirie"] = plaidoirie.valides + repliques_plaidoirie.valides
    contrat["arguments_rejetes"] = [*requisitoire.rejetes, *plaidoirie.rejetes, *repliques_requisitoire.rejetes,
                                    *repliques_plaidoirie.rejetes, *cibles_ecartees]
    performance = controle_performance_passee(contrat["requisitoire"] + contrat["plaidoirie"])
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
    if "poche" in profil.profil:
        contrat["limites"].append(LIMITE_POCHE)
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

    return trier_arguments(arguments, cote, dossier, corriger,
                           garde_fou=verifier_sortie if garde_fou_actif() else None)


def verifier_sortie(texte: str) -> str | None:
    """Un argument soumis au Guardrail Bedrock, côté sortie (#189)."""
    return verifier_garde_fou(texte, "OUTPUT")


def numero_cible(cible: dict[str, Any], valides: list[dict[str, Any]]) -> int | None:
    """Numéro (1, 2…) de l'argument visé par une réplique dans la liste finale de son camp.

    La réplique ne vise qu'un argument accepté tel quel : c'est le même objet dans la liste
    des arguments valides. None s'il n'y est plus.
    """
    return next((i for i, argument in enumerate(valides, start=1) if argument is cible), None)


def horodater_signaux(signaler: Signaler) -> Signaler:
    """Chaque étape signalée reçoit l'heure où elle a eu lieu, avant d'être publiée (#189).

    L'étape signalée est le même objet que celle de la trace du contrat : le contrat
    garde donc les mêmes heures que la progression en direct.
    """
    def signaler_horodate(evenement: dict[str, Any]) -> None:
        if evenement.get("type") == "etape":
            horodater(evenement["etape"])
        signaler(evenement)

    return signaler_horodate


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

