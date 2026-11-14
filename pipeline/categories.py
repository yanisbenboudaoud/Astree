"""Catégories d'actifs (tech, crypto…) utilisées par les règles « plafond » des Pactes.

Les catégories sont définies une seule fois, pour tous les profils, dans
config/categories.json. Un titre appartient à une catégorie si sa classe
d'actifs (asset_class) ou son secteur (sector) dans assets_universe.csv
figure dans la définition, ou s'il est listé dans « ajouts ».

Un titre absent de l'univers n'est jamais classé au hasard : il est signalé
(dans_univers = False), et le Greffier rendra « a_verifier ».
"""

import csv
import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CHEMIN_CATEGORIES = RACINE / "config" / "categories.json"
CHEMIN_UNIVERS = RACINE / "alphaforge_starter" / "assets_universe.csv"

CHAMPS_CATEGORIE = ("libelle", "classes_actifs", "secteurs", "ajouts", "justification")


class CategoriesInvalides(ValueError):
    """Le fichier des catégories est mal formé."""


def charger_categories(chemin=CHEMIN_CATEGORIES):
    """Lit config/categories.json et renvoie le dictionnaire {nom: définition}."""
    with open(chemin, encoding="utf-8") as fichier:
        contenu = json.load(fichier)
    categories = contenu.get("categories")
    if not isinstance(categories, dict) or not categories:
        raise CategoriesInvalides(f"{chemin} : le champ « categories » est absent ou vide")
    for nom, definition in categories.items():
        manquants = [champ for champ in CHAMPS_CATEGORIE if champ not in definition]
        if manquants:
            raise CategoriesInvalides(f"{chemin} : catégorie « {nom} », champs manquants : {', '.join(manquants)}")
    return categories


def charger_univers(chemin=CHEMIN_UNIVERS):
    """Lit assets_universe.csv et renvoie {ticker: {"asset_class": …, "sector": …}}."""
    with open(chemin, encoding="utf-8", newline="") as fichier:
        return {
            ligne["ticker"]: {"asset_class": ligne["asset_class"], "sector": ligne["sector"]}
            for ligne in csv.DictReader(fichier)
        }


def categories_du_titre(ticker, categories, univers):
    """Catégories d'un titre.

    Renvoie {"ticker", "dans_univers", "categories"} :
    - dans_univers = True : categories est la liste triée des catégories du titre
      (vide si le titre n'est dans aucune) ;
    - dans_univers = False : le titre est inconnu, categories est vide et ne doit
      pas être lu comme « aucune catégorie » : le contrôle rend « a_verifier ».
    """
    actif = univers.get(ticker)
    if actif is None:
        return {"ticker": ticker, "dans_univers": False, "categories": []}

    trouvees = [
        nom
        for nom, definition in categories.items()
        if actif["asset_class"] in definition["classes_actifs"]
        or actif["sector"] in definition["secteurs"]
        or ticker in definition["ajouts"]
    ]
    return {"ticker": ticker, "dans_univers": True, "categories": sorted(trouvees)}
