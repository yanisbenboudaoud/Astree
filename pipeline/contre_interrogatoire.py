"""Contre-interrogatoire (#55) : une question libre de l'utilisateur après le procès.

``CLAUDE.md``, section 4 : « La question va à l'orchestrateur, qui choisit les
outils ; les nouvelles pièces vont au Procureur et à l'Avocat, puis au Greffier. »
C'est donc la même boucle que le procès, sur le dossier existant :

1. **Orchestrateur** (``instruire_question``) : il lit la question et les pièces
   déjà au dossier, et choisit les outils utiles, avec les mêmes garde-fous
   (liste blanche, raison sans chiffre) et un budget plus petit. Les nouvelles
   pièces sont numérotées à la suite (P7, P8…).
2. **Procureur et Avocat**, en parallèle : chacun répond à la question de son
   point de vue, en citant uniquement des pièces.
3. **Greffier** : ``verifier_chiffres`` et le cadre « simulation seulement »
   (aucun conseil, aucune promesse, #60) sur chaque réponse ; un argument non
   prouvé ou hors cadre est renvoyé une fois à son agent, puis rejeté.

Le système ne recommande toujours rien : une demande de conseil reçoit une
réponse qui le dit, et l'utilisateur garde le verdict.

Format (champ ``contre_interrogatoire`` du contrat, une entrée par question) ::

    {"question": "…", "pieces_ajoutees": ["P7"], "requisitoire": [...],
     "plaidoirie": [...], "arguments_rejetes": [...],
     "controle_chiffres": {...}, "trace": [...]}

Les pièces ajoutées rejoignent le champ ``pieces`` du contrat : une question
suivante, ou le verdict, peut les citer.
"""

from __future__ import annotations

import copy
from typing import Any, Callable

from pipeline.agent_profil import chemin_profil
from pipeline.cadre_simulation import controle_cadre_simulation
from pipeline.chiffres import controle_verifier_chiffres
from pipeline.debat import debattre
from pipeline.llm import converser_avec_outils
from pipeline.orchestrateur import instruire_question
from pipeline.pacte import charger_pacte
from pipeline.tribunal import bornes_periode, prochain_numero, verifier_cote

LONGUEUR_MAX_QUESTION = 500  # une question tient en une ou deux phrases


class QuestionInvalide(ValueError):
    """Question refusée avant tout appel au modèle (vide, trop longue, procès sans décision)."""


def interroger(
    contrat: dict[str, Any],
    question: str,
    converser: Callable[..., Any] = converser_avec_outils,
) -> dict[str, Any]:
    """Répond à une question posée après le procès et renvoie le contrat complété.

    Args:
        contrat: le contrat du procès (éventuellement déjà complété par des questions).
        question: la question de l'utilisateur.
        converser: tour de modèle de l'orchestrateur (remplacé dans les tests).

    Returns:
        Une copie du contrat : les nouvelles pièces ajoutées à ``pieces`` et un
        échange ajouté à ``contre_interrogatoire``. Le contrat reçu n'est pas modifié.

    Raises:
        QuestionInvalide: question vide ou trop longue, ou procès sans décision.
        ProfilInconnu, PacteInvalide: profil du contrat introuvable ou invalide.
    """
    question = verifier_question(question)
    if not contrat.get("decision"):
        raise QuestionInvalide("Ce procès n'a pas de décision : il n'y a rien à contre-interroger")

    profil = charger_pacte(chemin_profil(contrat["persona"]))
    instruction = instruire_question(contrat["decision"], profil, question, contrat["pieces"],
                                     prochain_numero(contrat["pieces"]), converser=converser)
    pieces = [*contrat["pieces"], *instruction.pieces]
    dossier = {"decision": contrat["decision"], "pacte": contrat["pacte"], "pieces": pieces,
               "periode": bornes_periode(), "question": question}

    debat = debattre(dossier)
    trace = [*instruction.trace, *debat.trace]
    requisitoire = verifier_cote(debat.requisitoire, "requisitoire", "procureur", dossier, trace)
    plaidoirie = verifier_cote(debat.plaidoirie, "plaidoirie", "avocat", dossier, trace)
    controle = controle_verifier_chiffres(requisitoire, plaidoirie)
    # Le cadre (#60) est déjà appliqué par verifier_cote ; son compte rendu va dans la trace,
    # le format de l'échange ne change pas.
    cadre = controle_cadre_simulation(requisitoire, plaidoirie)
    nombre_arguments = f"{len(debat.requisitoire) + len(debat.plaidoirie)} arguments"
    for outil, compte_rendu in (("verifier_chiffres", controle), ("verifier_cadre_simulation", cadre)):
        trace.append({"etape": "greffier", "outil": outil, "entree": nombre_arguments,
                      "sortie": compte_rendu["message"]})

    echange = {
        "question": question,
        "pieces_ajoutees": [piece["id"] for piece in instruction.pieces],
        "requisitoire": requisitoire.valides,
        "plaidoirie": plaidoirie.valides,
        "arguments_rejetes": requisitoire.rejetes + plaidoirie.rejetes,
        "controle_chiffres": controle,
        "trace": trace,
    }
    complete = copy.deepcopy(contrat)
    complete["pieces"] = copy.deepcopy(pieces)
    complete["contre_interrogatoire"] = [*contrat.get("contre_interrogatoire", []), echange]
    return complete


def verifier_question(question: Any) -> str:
    """La question, sans espaces superflus ; ``QuestionInvalide`` si elle est vide ou trop longue."""
    if not isinstance(question, str) or not question.strip():
        raise QuestionInvalide("Question vide : posez une question sur le procès")
    question = " ".join(question.split())
    if len(question) > LONGUEUR_MAX_QUESTION:
        raise QuestionInvalide(f"Question trop longue : {LONGUEUR_MAX_QUESTION} caractères au plus")
    return question


def pieces_de_l_echange(contrat: dict[str, Any], echange: dict[str, Any]) -> list[dict[str, Any]]:
    """Les pièces ajoutées par un échange, dans l'ordre (pour les renvoyer à l'interface)."""
    ajoutees = set(echange["pieces_ajoutees"])
    return [piece for piece in contrat["pieces"] if piece["id"] in ajoutees]
