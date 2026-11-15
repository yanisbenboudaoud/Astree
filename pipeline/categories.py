"""Catégories d'actifs utilisées par les règles « plafond » des Pactes (CLAUDE.md, section 3).

Elles sont définies une seule fois, pour tous les profils, dans
``config/categories.json``. Un titre appartient à une catégorie si sa classe
d'actifs (``asset_class``), son secteur (``sector``) ou son marché de cotation
(``market``, pour les catégories géographiques, #112) dans
``assets_universe.csv`` figure dans la définition, ou s'il est listé dans ses
« ajouts ». Un titre listé dans ses « retraits » n'y appartient jamais (ex. :
GLD, coté à New York, détient de l'or, qui n'a pas de pays). Les champs
``marches`` et ``retraits`` sont facultatifs.

Un titre absent de l'univers n'est jamais classé au hasard :
``categories_du_titre`` lève ``TitreHorsUnivers``, que le Greffier traduit en
« a_verifier ».
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

from pipeline.donnees import ErreurDonnees, charger_univers

CHEMIN_CATEGORIES = Path(__file__).resolve().parent.parent / "config" / "categories.json"


class TitreHorsUnivers(ErreurDonnees):
    """Titre absent de assets_universe.csv : ses catégories sont inconnues."""


@lru_cache(maxsize=1)
def charger_categories() -> dict:
    """Définitions des catégories, par nom (ex. : ``{"crypto": {...}, "tech": {...}}``).

    Le résultat est mis en cache : ne pas le modifier.
    """
    with open(CHEMIN_CATEGORIES, encoding="utf-8") as fichier:
        return json.load(fichier)["categories"]


def noms_categories() -> frozenset[str]:
    """Noms des catégories que les règles « plafond » peuvent citer."""
    return frozenset(charger_categories())


def nom_categories(noms: list[str]) -> str:
    """["tech", "crypto"] → « Technologie et cryptoactifs » (libellés de config/categories.json).

    Un libellé seul est repris tel quel : « États-Unis », « Placements hors du Canada » (#112).
    """
    definitions = charger_categories()
    libelles = [definitions[nom]["libelle"] for nom in noms]
    if len(libelles) == 1:
        return libelles[0]
    texte = ", ".join(libelles[:-1]) + " et " + libelles[-1]
    return texte[0].upper() + texte[1:].lower()


def categories_du_titre(ticker: str) -> frozenset[str]:
    """Catégories d'un titre de l'univers (ensemble vide s'il n'est dans aucune).

    Lève ``TitreHorsUnivers`` si le titre n'est pas dans assets_universe.csv.
    """
    index = _categories_par_ticker()
    if ticker not in index:
        raise TitreHorsUnivers(
            f"« {ticker} » est absent de assets_universe.csv : ses catégories sont inconnues"
        )
    return index[ticker]


@lru_cache(maxsize=1)
def _categories_par_ticker() -> dict[str, frozenset[str]]:
    univers = charger_univers()
    categories = charger_categories()
    return {
        ligne.ticker: frozenset(
            nom for nom, definition in categories.items()
            if _appartient(ligne.ticker, ligne.asset_class, ligne.sector, ligne.market, definition)
        )
        for ligne in univers.itertuples()
    }


def _appartient(ticker: str, classe_actifs: str, secteur: str, marche: str, definition: dict) -> bool:
    if ticker in definition.get("retraits", []):
        return False
    return (
        classe_actifs in definition["classes_actifs"]
        or secteur in definition["secteurs"]
        or marche in definition.get("marches", [])
        or ticker in definition["ajouts"]
    )


def erreurs_config_categories(
    categories: dict | None = None, univers: pd.DataFrame | None = None
) -> list[str]:
    """Vérifie que config/categories.json ne cite que des valeurs de l'univers.

    Attrape les fautes de frappe (« Information technology ») qui videraient
    une catégorie sans aucun message, et un titre à la fois ajouté et retiré.
    """
    categories = charger_categories() if categories is None else categories
    univers = charger_univers() if univers is None else univers
    connues = {
        "classes_actifs": set(univers["asset_class"]),
        "secteurs": set(univers["sector"]),
        "marches": set(univers["market"]),
        "ajouts": set(univers["ticker"]),
        "retraits": set(univers["ticker"]),
    }
    erreurs = []
    for nom, definition in categories.items():
        for champ, valeurs_connues in connues.items():
            for valeur in definition.get(champ, []):
                if valeur not in valeurs_connues:
                    erreurs.append(f"{nom}/{champ} : « {valeur} » absent de assets_universe.csv")
        for ticker in sorted(set(definition["ajouts"]) & set(definition.get("retraits", []))):
            erreurs.append(f"{nom} : « {ticker} » est à la fois dans ajouts et dans retraits")
    return erreurs
