"""Points de bascule : « Qu'est-ce qui changerait la réponse ? » (#61).

Une explication crédible répond aussi à cette question (atelier de la Banque
Nationale, « Comprendre l'investisseur », diapo 12). Pour chaque règle
**calculable** du Pacte en violation (``pire_baisse_max`` et ``plafond``),
l'outil dit ce qui la rendrait conforme, des deux côtés du verdict :

- **modifier la décision** : la plus grande taille (ou part réallouée) à
  laquelle *cette règle* est respectée, avec le même financement ;
- **ajuster le Pacte** : le seuil qui suffirait, c'est-à-dire la valeur simulée
  après la décision (pire baisse, ou part des catégories du plafond), arrondie du
  côté permissif. Un seuil égal ou plus permissif rend la règle conforme.

Python seul, sans LLM. L'outil ne refait aucun calcul : il relit la recherche
de ``taille_max_compatible`` (#21), où chaque taille testée a été jugée par les
contrôles du Greffier (``verifier_pacte``). La dernière taille testée est la
taille demandée : son statut dit quelles règles sont en violation.

La pièce est **ajoutée d'office** par le Tribunal (``pipeline.tribunal``) dès
qu'une règle calculable est en violation, avant le débat : le Procureur et
l'Avocat peuvent la citer, et ``verifier_chiffres`` la vérifie comme les autres.
Sans violation, il n'y a ni pièce ni point de bascule.

Le code ne connaît aucun persona : il lit seulement les règles du Pacte.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pipeline.greffier import TOLERANCE_PART, nom_categories
from pipeline.indicateurs import DECIMALES_VALEURS
from pipeline.simulation import formater_pourcentage, source_des_prix
from pipeline.taille_max import PAS_DE_RECHERCHE, TYPES_CALCULABLES, ResultatRecherche

NOM_OUTIL = "points_de_bascule"


@dataclass(frozen=True)
class PointDeBascule:
    """Ce qui rendrait conforme une règle calculable en violation."""

    regle: dict[str, Any]  # la règle du Pacte (id, type, seuil ou max, libellé)
    seuil_suffisant: float  # valeur simulée après la décision : pire baisse ou part des catégories
    taille_max: float | None  # plus grande taille où cette règle est conforme ; None : même 0 % la viole

    @property
    def seuil_actuel(self) -> float:
        """Seuil inscrit au Pacte : ``seuil`` (pire baisse) ou ``max`` (plafond)."""
        return self.regle["seuil"] if self.regle["type"] == "pire_baisse_max" else self.regle["max"]


# --- Calcul -----------------------------------------------------------------------


def points_de_bascule(recherche: ResultatRecherche) -> list[PointDeBascule]:
    """Un point de bascule par règle calculable en violation à la taille demandée, dans l'ordre du Pacte.

    Args:
        recherche: résultat de ``rechercher_taille_max`` pour la décision jugée
            (sa dernière étape est la taille demandée).

    Returns:
        Liste vide si aucune règle calculable n'est en violation. Une règle
        « à vérifier » (titre hors univers) n'a pas de point de bascule : rien
        ne permet de la mesurer.
    """
    demandee = recherche.etapes[-1]
    points = []
    for regle in recherche.regles:
        if regle["type"] not in TYPES_CALCULABLES or demandee.statuts.get(regle["id"]) != "violation":
            continue
        conformes = [etape.taille for etape in recherche.etapes
                     if etape.statuts.get(regle["id"]) == "conforme"]
        valeur = demandee.pire_baisse if regle["type"] == "pire_baisse_max" else demandee.parts[regle["id"]]
        points.append(PointDeBascule(
            regle=regle,
            seuil_suffisant=seuil_suffisant(regle["type"], valeur),
            taille_max=max(conformes) if conformes else None,
        ))
    return points


def seuil_suffisant(type_regle: str, valeur: float) -> float:
    """La valeur simulée, arrondie à ``DECIMALES_VALEURS`` du côté **permissif**.

    Arrondie au plus proche, elle pourrait tomber un millionième du mauvais côté
    et laisser la règle en violation. On la décale donc d'un pas si besoin, avec
    les comparaisons du Greffier : pire baisse conforme si ``valeur >= seuil`` ;
    plafond conforme si ``valeur <= max + TOLERANCE_PART``.
    """
    pas = 10 ** -DECIMALES_VALEURS
    seuil = round(valeur, DECIMALES_VALEURS)
    if type_regle == "pire_baisse_max":
        while valeur < seuil:
            seuil = round(seuil - pas, DECIMALES_VALEURS)
    else:
        while valeur > seuil + TOLERANCE_PART:
            seuil = round(seuil + pas, DECIMALES_VALEURS)
    return seuil


# --- La pièce et le champ du contrat ----------------------------------------------


def piece_points_de_bascule(
    id_piece: str,
    recherche: ResultatRecherche,
    decision: dict[str, Any],
) -> dict[str, Any] | None:
    """Pièce « Ce qui changerait la réponse », au format du contrat (étiquette « fictif »).

    Valeurs brutes, en listes parallèles (le contrat n'admet que des listes de
    valeurs simples dans une pièce) : le rang i de chaque liste décrit la règle
    ``regles_en_violation[i]``.

    Returns:
        None si aucune règle calculable n'est en violation : pas de pièce.
    """
    points = points_de_bascule(recherche)
    if not points:
        return None
    reallocation = decision.get("type") == "reallocation"
    valeurs = {
        "regles_en_violation": [point.regle["id"] for point in points],
        "seuils_du_pacte": [point.seuil_actuel for point in points],
        "seuils_suffisants": [point.seuil_suffisant for point in points],
        "tailles_max_par_regle": [point.taille_max for point in points],
        "taille_demandee": recherche.taille_demandee,
        "taille_max_toutes_regles": recherche.taille_max,
        "pas_de_recherche": PAS_DE_RECHERCHE,
    }
    return {
        "id": id_piece,
        "type": "calculee",
        "etiquette": "fictif",
        "titre": "Ce qui changerait la réponse : points de bascule des règles en violation",
        "outil": NOM_OUTIL,
        "valeurs": valeurs,
        "valeur_affichee": " · ".join(_resume(point) for point in points),
        "source": source_des_prix(),
        "traitement": (
            f"Pour chaque règle calculable en violation : plus grande {'part réallouée' if reallocation else 'taille'} "
            "où elle est conforme (simulation de 0 à la taille demandée par pas de 1 point, même financement, "
            "contrôles du Greffier à chaque taille), et seuil qui suffirait : la valeur simulée après la "
            "décision (pire baisse, ou part des catégories du plafond)"
        ),
        "limites": (
            "Une seule période passée ; un seuil qui suffit sur cette période ne protège pas d'une baisse "
            "future plus forte ; seules les règles calculables (pire baisse, plafonds) ont un point de "
            "bascule, pas les règles qualitatives ni documentaires ; ajuster le Pacte reste un choix de "
            "l'utilisateur, pas une recommandation"
        ),
    }


def pour_contrat(
    recherche: ResultatRecherche,
    decision: dict[str, Any],
    id_piece: str | None,
) -> list[dict[str, Any]]:
    """Champ ``points_de_bascule`` du contrat : un objet par règle en violation, ``message`` écrit par Python.

    Args:
        id_piece: pièce des points de bascule (``piece_points_de_bascule``), citée
            par chaque objet ; None seulement s'il n'y a aucun point de bascule.
    """
    points = points_de_bascule(recherche)
    if points and id_piece is None:
        raise ValueError("Des points de bascule existent : la pièce qui les prouve est obligatoire")
    return [{
        "regle": point.regle["id"],
        "type": point.regle["type"],
        "seuil_actuel": point.seuil_actuel,
        "seuil_suffisant": point.seuil_suffisant,
        "taille_max": point.taille_max,
        "message": message(point, decision),
        "pieces": [id_piece],
    } for point in points]


# --- Mise en forme ------------------------------------------------------------------


def message(point: PointDeBascule, decision: dict[str, Any]) -> str:
    """Les deux façons de rendre la règle conforme, en une phrase.

    Ex. : « Conforme jusqu'à 9 % en TSLA, ou avec un seuil de −29,0 % au lieu de −12,0 % ».
    """
    return f"{_cote_decision(point, decision)}, ou {_cote_pacte(point)}"


def _cote_decision(point: PointDeBascule, decision: dict[str, Any]) -> str:
    if point.taille_max is None:
        return "Aucune taille ne suffit, le portefeuille actuel enfreint déjà cette règle"
    if point.taille_max == 0:
        return "Conforme seulement sans la décision"
    objet = "réalloués" if decision.get("type") == "reallocation" else f"en {decision['ticker']}"
    return f"Conforme jusqu'à {_taille(point.taille_max)} {objet}"


def _cote_pacte(point: PointDeBascule) -> str:
    if point.regle["type"] == "pire_baisse_max":
        return (f"avec un seuil de {formater_pourcentage(point.seuil_suffisant)} "
                f"au lieu de {formater_pourcentage(point.seuil_actuel)}")
    if point.seuil_actuel == 0:
        return f"avec un plafond de {_part(point.seuil_suffisant)} au lieu de l'exclusion"
    return f"avec un plafond de {_part(point.seuil_suffisant)} au lieu de {_part(point.seuil_actuel)}"


def _resume(point: PointDeBascule) -> str:
    """Résumé court pour ``valeur_affichee`` : « Pire baisse : 9 % max ou seuil −29,0 % »."""
    if point.regle["type"] == "pire_baisse_max":
        nom, seuil = "Pire baisse", f"seuil {formater_pourcentage(point.seuil_suffisant)}"
    else:
        nom, seuil = nom_categories(point.regle["categories"]), f"plafond {_part(point.seuil_suffisant)}"
    taille = "aucune taille" if point.taille_max is None else f"{_taille(point.taille_max)} max"
    return f"{nom} : {taille} ou {seuil}"


def _taille(taille: float) -> str:
    """0.09 → « 9 % » ; 0.0769 → « 7,7 % » (même format que la pièce de taille maximale)."""
    texte = f"{taille * 100:.1f}".rstrip("0").rstrip(".")
    return f"{texte.replace('.', ',')} %"


def _part(part: float) -> str:
    """0.5 → « 50,0 % » (part de portefeuille, comme les messages du Greffier)."""
    return f"{part * 100:.1f}".replace(".", ",") + " %"
