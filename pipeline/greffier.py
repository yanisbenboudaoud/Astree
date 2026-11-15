"""Greffier : le point de contrôle du Tribunal, en Python sans LLM (CLAUDE.md, section 4).

Outil 5, ``verifier_pacte`` : compare la décision aux règles du Pacte et rend
un contrôle par règle (``conforme``, ``violation`` ou ``a_verifier``), au
format ``controles`` du contrat. Une fonction par type de règle ; aucun nom de
persona : seules les règles du Pacte sont lues.

Outil 6, ``verifier_chiffres`` : dans ``pipeline.chiffres`` (``trier_arguments``,
``controle_verifier_chiffres``).
"""

from __future__ import annotations

import re
from typing import Any, Callable

from pipeline.categories import TitreHorsUnivers, categories_du_titre, charger_categories
from pipeline.simulation import formater_pourcentage

# Écart toléré sur une part de portefeuille (arrondis des poids).
TOLERANCE_PART = 1e-9

MESSAGE_QUALITATIVE = "Règle déclarée, non mesurable par calcul : à juger par l'utilisateur"
MESSAGE_BIAIS_SURVIVANT = "Biais du survivant : univers choisi en 2026, les résultats passés paraissent meilleurs"
MESSAGE_PERFORMANCE_PASSEE = "Performance passée invoquée : elle ne prédit pas l'avenir"

# Mots qui signalent qu'un argument s'appuie sur la performance passée.
MOTS_PERFORMANCE_PASSEE = re.compile(r"\b(rendements?|performances?|rapport[ée]|gains?)\b", re.IGNORECASE)


# --- Outil 5 : verifier_pacte ---------------------------------------------------

def verifier_pacte(
    regles: list[dict[str, Any]],
    poids_apres: dict[str, float],
    piece_simulation: dict[str, Any] | None,
    id_piece_pacte: str,
    pieces: list[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Un contrôle par règle du Pacte, dans l'ordre des règles.

    Args:
        regles: règles du Pacte (``pacte.regles`` du contrat ou du fichier profil).
        poids_apres: poids du portefeuille après la décision
            (``pipeline.simulation.poids_apres_decision``).
        piece_simulation: pièce obligatoire de ``simuler_portefeuille`` sur la
            période complète (contient ``pire_baisse``), ou None si elle manque.
        id_piece_pacte: id de la pièce « Pacte » (``pipeline.pacte.piece_pacte``).
        pieces: toutes les pièces du dossier (pour les pièces documentaires).

    Raises:
        ValueError: type de règle sans fonction de contrôle.
    """
    contexte = {
        "poids_apres": poids_apres,
        "piece_simulation": piece_simulation,
        "id_piece_pacte": id_piece_pacte,
        "pieces": list(pieces),
    }
    controles = []
    for regle in regles:
        verifier = CONTROLES_PAR_TYPE.get(regle["type"])
        if verifier is None:
            raise ValueError(f"Type de règle « {regle['type']} » sans contrôle dans le Greffier")
        controles.append(verifier(regle, contexte))
    return controles


def controler_pire_baisse_max(regle: dict[str, Any], contexte: dict[str, Any]) -> dict[str, Any]:
    """``violation`` si la pire baisse après la décision est plus basse que le seuil."""
    piece = contexte["piece_simulation"]
    if piece is None or "pire_baisse" not in piece["valeurs"]:
        return _controle(
            "a_verifier", regle,
            "Pièce de simulation absente : pire baisse après la décision inconnue",
            [contexte["id_piece_pacte"]],
        )
    pire_baisse, seuil = piece["valeurs"]["pire_baisse"], regle["seuil"]
    texte = f"Pire baisse {formater_pourcentage(pire_baisse)}"
    if pire_baisse < seuil:
        statut, message = "violation", f"{texte} au-delà du seuil {formater_pourcentage(seuil)}"
    else:
        statut, message = "conforme", f"{texte} dans la limite du seuil {formater_pourcentage(seuil)}"
    pieces = [piece["id"], contexte["id_piece_pacte"]]
    if regle.get("piece"):  # seuil mesuré par le Pacte vécu (#68) : sa pièce le prouve
        pieces.append(regle["piece"])
    return _controle(statut, regle, message, pieces)


def controler_plafond(regle: dict[str, Any], contexte: dict[str, Any]) -> dict[str, Any]:
    """``violation`` si la part des titres de ces catégories dépasse ``max`` (0 = exclusion).

    Un titre hors de l'univers rend ``a_verifier`` : sa catégorie n'est jamais devinée.
    """
    categories = set(regle["categories"])
    pieces = [contexte["id_piece_pacte"]]
    part, hors_univers = 0.0, []
    for ticker, poids in contexte["poids_apres"].items():
        try:
            if categories_du_titre(ticker) & categories:
                part += poids
        except TitreHorsUnivers:
            hors_univers.append(ticker)

    nom = nom_categories(regle["categories"])
    if hors_univers:
        return _controle(
            "a_verifier", regle,
            f"{nom} : part inconnue, titre absent de l'univers ({', '.join(sorted(hors_univers))})",
            pieces,
        )

    texte = f"{nom} : {_part(part)} du portefeuille après la décision"
    maximum = regle["max"]
    if part > maximum + TOLERANCE_PART:
        limite = "alors que cette catégorie est exclue" if maximum == 0 else f"au-delà du plafond de {_part(maximum)}"
        return _controle("violation", regle, f"{texte}, {limite}", pieces)
    limite = "exclusion respectée" if maximum == 0 else f"dans la limite du plafond de {_part(maximum)}"
    return _controle("conforme", regle, f"{texte}, {limite}", pieces)


def controler_critere_documentaire(regle: dict[str, Any], contexte: dict[str, Any]) -> dict[str, Any]:
    """Selon une pièce documentaire sur le critère ; ``a_verifier`` sans pièce.

    Format attendu : pièce de type ``documentaire`` dont ``valeurs`` contient le
    critère, à ``true`` si le titre le remplit (ex. :
    ``{"ticker": "XOM", "controverse_esg_importante": true}`` → violation). Une
    pièce qui nomme un titre (``ticker``) ne compte que si ce titre est dans le
    portefeuille après la décision (outil ``rechercher_documents``, #17).
    """
    critere = regle["critere"]
    for piece in contexte["pieces"]:
        valeurs = piece["valeurs"]
        if piece["type"] != "documentaire" or not isinstance(valeurs.get(critere), bool):
            continue
        if "ticker" in valeurs and valeurs["ticker"] not in contexte["poids_apres"]:
            continue  # document sur un titre absent du portefeuille après la décision
        pieces = [piece["id"], contexte["id_piece_pacte"]]
        sujet = f" pour {valeurs['ticker']}" if "ticker" in valeurs else ""
        if valeurs[critere]:
            return _controle("violation", regle, f"Critère « {critere} » rempli{sujet} selon {piece['id']}", pieces)
        return _controle("conforme", regle, f"Critère « {critere} » non rempli{sujet} selon {piece['id']}", pieces)
    return _controle(
        "a_verifier", regle,
        f"Source manquante : aucune pièce documentaire sur le critère « {critere} »",
        [contexte["id_piece_pacte"]],
    )


def controler_qualitative(regle: dict[str, Any], contexte: dict[str, Any]) -> dict[str, Any]:
    """Toujours ``a_verifier`` : la règle est déclarée, mais aucun calcul ne la mesure."""
    return _controle("a_verifier", regle, MESSAGE_QUALITATIVE, [contexte["id_piece_pacte"]])


# Ajouter un type de règle = une fonction ci-dessus + une ligne ici (CLAUDE.md, section 3).
CONTROLES_PAR_TYPE: dict[str, Callable[[dict, dict], dict]] = {
    "pire_baisse_max": controler_pire_baisse_max,
    "plafond": controler_plafond,
    "critere_documentaire": controler_critere_documentaire,
    "qualitative": controler_qualitative,
}


# --- Contrôles du système --------------------------------------------------------

def controle_biais_survivant() -> dict[str, Any]:
    """Toujours ``a_verifier`` : l'univers d'actifs a été choisi en 2026."""
    return {"statut": "a_verifier", "regle": "biais_survivant", "message": MESSAGE_BIAIS_SURVIVANT}


def controle_performance_passee(arguments: list[dict[str, Any]]) -> dict[str, Any] | None:
    """``a_verifier`` si un argument invoque la performance passée, sinon None."""
    if any(MOTS_PERFORMANCE_PASSEE.search(argument["texte"]) for argument in arguments):
        return {"statut": "a_verifier", "regle": "performance_passee", "message": MESSAGE_PERFORMANCE_PASSEE}
    return None


# --- Outils de mise en forme -----------------------------------------------------

def _controle(statut: str, regle: dict[str, Any], message: str, pieces: list[str]) -> dict[str, Any]:
    return {"statut": statut, "regle": regle["id"], "message": message, "pieces": pieces}


def _part(valeur: float) -> str:
    """0.5 → « 50,0 % » (part de portefeuille, sans signe)."""
    return f"{valeur * 100:.1f}".replace(".", ",") + " %"


def nom_categories(noms: list[str]) -> str:
    """["tech", "crypto"] → « Technologie et cryptoactifs » (libellés de config/categories.json)."""
    definitions = charger_categories()
    libelles = [definitions[nom]["libelle"] for nom in noms]
    texte = libelles[0] if len(libelles) == 1 else ", ".join(libelles[:-1]) + " et " + libelles[-1]
    return texte[0].upper() + texte[1:].lower()
