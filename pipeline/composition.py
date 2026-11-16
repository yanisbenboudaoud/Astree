"""Composition des FNB : parts des catégories calculées par transparence (#116).

Un FNB n'est pas un bloc : SPY détient de l'énergie, QQQ n'est pas tout entier
technologique. Atelier Banque Nationale : pour un fonds, il faut regarder sa composition.

Part d'une catégorie = somme, sur les titres du portefeuille, du poids du titre × part
de la catégorie dans le titre :

- **titre individuel** : 0 ou 1, selon son classement direct (``pipeline.categories``) ;
- **FNB** : sa composition publiée par l'émetteur (``donnees_externes/composition_fnb.json``),
  lue selon le bloc « transparence » de la catégorie (``config/categories.json``) :
  répartition par secteur (selon la classification de l'émetteur : GICS, ICB, secteurs
  obligataires) et poids de quelques titres, ou répartition par pays ;
- **FNB dont la composition ne permet pas le calcul** (répartition absente de la page de
  l'émetteur, classification qui n'isole pas la catégorie, union de catégories sectorielle et
  géographique) : classement direct, **signalé** dans le résultat, jamais deviné.

Une catégorie sans bloc « transparence » (``crypto``) se lit toujours en classement direct.
Python seul, sans LLM ; aucun nom de persona.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from pipeline.categories import TitreHorsUnivers, categories_du_titre, charger_categories, nom_categories
from pipeline.donnees import charger_univers
from pipeline.indicateurs import DECIMALES_VALEURS
from pipeline.simulation import ErreurSimulation, poids_apres_decision

NOM_OUTIL = "composition_fnb"
CHEMIN_COMPOSITIONS = Path(__file__).resolve().parent.parent / "donnees_externes" / "composition_fnb.json"

DIMENSIONS = ("secteurs", "pays")
# Écart toléré entre la somme d'une répartition et 100 % (arrondis des émetteurs).
TOLERANCE_SOMME_POURCENTAGES = 0.05
RE_DATE_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")

TITRE_PIECE = "Composition des FNB : part de chaque catégorie par transparence"
TRAITEMENT = (
    "Part d'une catégorie = somme des poids des titres × part de la catégorie dans chaque titre : 0 ou 1 "
    "pour un titre individuel (config/categories.json) ; pour un FNB, sa composition publiée par l'émetteur "
    "(secteurs selon sa classification et poids de quelques titres pour les catégories sectorielles, pays pour "
    "les catégories géographiques). Un FNB dont la composition ne permet pas le calcul garde son classement "
    "direct (fonds_sans_composition, ou part du FNB absente de la pièce)"
)
# Sans chiffre : les agents ne reprennent aucun nombre des limites (REFERENCE_DU_PROJET.md, section 4 ter).
LIMITES = (
    "Composition relevée à la date des fiches des émetteurs, appliquée à toute la période simulée ; "
    "répartitions arrondies par les émetteurs ; classifications différentes selon l'émetteur (GICS, ICB, "
    "secteurs obligataires) ; peu d'émetteurs publient une répartition par pays"
)


# --- Données ----------------------------------------------------------------------


@lru_cache(maxsize=1)
def charger_compositions() -> dict[str, Any]:
    """Contenu de ``donnees_externes/composition_fnb.json``. Mis en cache : ne pas le modifier."""
    with open(CHEMIN_COMPOSITIONS, encoding="utf-8") as fichier:
        return json.load(fichier)


def composition_du_fonds(ticker: str) -> dict[str, Any] | None:
    """Composition relevée d'un FNB, ou None s'il n'est pas dans le fichier."""
    return charger_compositions()["fonds"].get(ticker)


@lru_cache(maxsize=1)
def _fonds_de_l_univers() -> frozenset[str]:
    univers = charger_univers()
    return frozenset(univers.loc[univers["asset_class"].str.startswith("etf"), "ticker"])


def est_fonds(ticker: str) -> bool:
    """Vrai pour un FNB de l'univers (classe d'actifs ``etf_…`` de assets_universe.csv)."""
    return ticker in _fonds_de_l_univers()


def _repartition(composition: dict[str, Any], cle: str) -> dict[str, float] | None:
    """Pourcentages d'un bloc (``secteurs``, ``pays`` ou ``titres``), convertis en décimales ; None s'il manque."""
    bloc = composition.get(cle)
    return None if bloc is None else {nom: valeur / 100 for nom, valeur in bloc["pourcentages"].items()}


# --- Part d'une catégorie dans un FNB --------------------------------------------------


def part_dans_le_fonds(ticker: str, categories: Iterable[str]) -> float | None:
    """Part de l'union des catégories dans un FNB, selon sa composition publiée.

    Returns:
        Une part entre 0 et 1, ou None si la composition ne permet pas de la calculer :
        FNB absent du fichier, répartition absente, classification qui n'isole pas une des
        catégories, ou union de catégories de dimensions différentes (secteur et pays : il
        faudrait la répartition croisée). Le FNB garde alors son classement direct.
    """
    composition = composition_du_fonds(ticker)
    if composition is None:
        return None
    categories = list(categories)
    definitions = charger_categories()
    directes = {c for c in categories if not definitions[c].get("transparence")}
    if directes & categories_du_titre(ticker):
        return 1.0  # le FNB entier appartient à une catégorie lue en classement direct
    regles = [definitions[c]["transparence"] for c in categories if definitions[c].get("transparence")]
    dimensions = {regle["dimension"] for regle in regles}
    if len(dimensions) != 1:
        return None
    if dimensions.pop() == "secteurs":
        return _part_par_secteurs(composition, regles)
    return _part_par_pays(composition, regles)


def _part_par_secteurs(composition: dict[str, Any], regles: list[dict[str, Any]]) -> float | None:
    secteurs_du_fonds = _repartition(composition, "secteurs")
    if secteurs_du_fonds is None:
        return None
    classification = composition["secteurs"]["classification"]
    secteurs, titres = set(), set()
    for regle in regles:
        lecture = regle["par_classification"].get(classification)
        if lecture is None:
            return None  # cette classification n'isole pas la catégorie (ex. : énergie dans Industrial)
        secteurs |= set(lecture.get("secteurs", []))
        titres |= set(lecture.get("titres", []))
    part = float(sum(valeur for nom, valeur in secteurs_du_fonds.items() if nom in secteurs))
    if titres:
        poids_titres = _repartition(composition, "titres")
        if poids_titres is None or not titres <= set(poids_titres):
            return None  # un titre à ajouter n'a pas été relevé : la part serait sous-estimée
        part += sum(poids_titres[titre] for titre in titres)
    return min(part, 1.0)


def _part_par_pays(composition: dict[str, Any], regles: list[dict[str, Any]]) -> float | None:
    pays_du_fonds = _repartition(composition, "pays")
    if pays_du_fonds is None:
        return None

    def compte(pays: str) -> bool:
        return any(pays in regle.get("pays", []) or ("pays_sauf" in regle and pays not in regle["pays_sauf"])
                   for regle in regles)

    return min(float(sum(valeur for nom, valeur in pays_du_fonds.items() if compte(nom))), 1.0)


# --- Part d'une catégorie dans un portefeuille -------------------------------------------


@dataclass
class PartCategories:
    """Part de l'union de catégories dans un portefeuille, et comment elle a été obtenue."""

    part: float = 0.0
    hors_univers: list[str] = field(default_factory=list)       # catégories inconnues : jamais devinées
    par_transparence: list[str] = field(default_factory=list)   # FNB lus selon leur composition
    classement_direct: list[str] = field(default_factory=list)  # FNB sans composition utilisable


def part_des_categories(poids: dict[str, float], categories: Iterable[str]) -> PartCategories:
    """Part des catégories (leur union) dans un portefeuille, FNB lus par transparence.

    Args:
        poids: un poids par titre (portefeuille de départ ou ``poids_apres_decision``).
        categories: noms de ``config/categories.json`` (ceux d'une règle « plafond »).
    """
    categories = list(categories)
    definitions = charger_categories()
    lues_par_transparence = any(definitions[c].get("transparence") for c in categories)
    resultat = PartCategories()
    for ticker, poids_titre in poids.items():
        try:
            part_titre = 1.0 if categories_du_titre(ticker) & set(categories) else 0.0
        except TitreHorsUnivers:
            resultat.hors_univers.append(ticker)
            continue
        if lues_par_transparence and est_fonds(ticker):
            transparence = part_dans_le_fonds(ticker, categories)
            if transparence is None:
                resultat.classement_direct.append(ticker)
            else:
                part_titre = transparence
                resultat.par_transparence.append(ticker)
        resultat.part += poids_titre * part_titre
    for liste in (resultat.hors_univers, resultat.par_transparence, resultat.classement_direct):
        liste.sort()
    return resultat


def part_sans_transparence(poids: dict[str, float], categories: Iterable[str]) -> float:
    """Part en classement direct seulement (avant #116) : un FNB compte en entier ou pas du tout."""
    categories = set(categories)
    part = 0.0
    for ticker, poids_titre in poids.items():
        try:
            if categories_du_titre(ticker) & categories:
                part += poids_titre
        except TitreHorsUnivers:
            pass
    return part


# --- La pièce ---------------------------------------------------------------------------


def piece_composition(
    id_piece: str,
    portefeuille: list[dict[str, Any]],
    decision: dict[str, Any],
    regles: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Pièce « composition des FNB » : la part de chaque catégorie avant et après la décision.

    Ajoutée d'office au dossier quand un plafond du Pacte porte sur une catégorie lue par
    transparence et que le portefeuille (avant ou après la décision) contient un FNB dont la
    composition est relevée. Valeurs brutes :

    - ``part_<catégorie>`` (après la décision), ``part_<catégorie>_actuelle`` et, quand elle
      diffère, ``part_<catégorie>_sans_transparence`` (FNB comptés en entier ou pas du tout),
      pour chaque catégorie et pour chaque union de catégories d'une règle « plafond » du Pacte ;
    - ``fonds_lus`` et, pour chacun, ``<ticker>_date_secteurs`` (et ``_titres``, ``_pays``),
      ``<ticker>_classification_secteurs`` et ``<ticker>_part_<catégorie>`` (part de la
      catégorie dans le FNB, quand sa composition permet de la calculer) ;
      ``fonds_sans_composition`` : les FNB absents du fichier, qui gardent leur classement direct.

    Returns:
        La pièce au format du contrat, ou None si elle n'apporte rien au procès : aucune règle
        « plafond » du Pacte ne porte sur une catégorie lue par transparence (ex. : seulement un
        plafond crypto), aucun FNB à lire, ou décision impossible à simuler.
    """
    definitions = charger_categories()
    if not any(regle["type"] == "plafond" and any(definitions[c].get("transparence") for c in regle["categories"])
               for regle in regles):
        return None
    try:
        poids_apres = poids_apres_decision(portefeuille, decision)
    except (ErreurSimulation, KeyError):
        return None
    poids_actuels = {ligne["ticker"]: float(ligne["poids"]) for ligne in portefeuille}
    fonds = sorted(t for t in poids_actuels.keys() | poids_apres.keys() if est_fonds(t))
    lus = [t for t in fonds if composition_du_fonds(t) is not None]
    if not lus:
        return None

    valeurs: dict[str, Any] = {}
    for categories in _ensembles_de_categories(regles):
        apres, actuel = part_des_categories(poids_apres, categories), part_des_categories(poids_actuels, categories)
        if apres.hors_univers or actuel.hors_univers:
            continue  # part inconnue : le Greffier rend « a_verifier »
        nom = "part_" + "_".join(categories)
        valeurs[nom] = apres.part
        valeurs[f"{nom}_actuelle"] = actuel.part
        directe = part_sans_transparence(poids_apres, categories)
        if abs(directe - apres.part) > 10 ** -DECIMALES_VALEURS:
            valeurs[f"{nom}_sans_transparence"] = directe
    valeurs = {cle: round(valeur, DECIMALES_VALEURS) for cle, valeur in valeurs.items()}
    valeurs["fonds_lus"] = lus
    for ticker in lus:  # à plat : le contrat n'admet pas d'objet dans les valeurs d'une pièce
        valeurs.update({f"{ticker}_{cle}": valeur for cle, valeur in composition_utilisee(ticker).items()})
    sans = [t for t in fonds if t not in lus]
    if sans:
        valeurs["fonds_sans_composition"] = sans

    return {
        "id": id_piece,
        "type": "calculee",
        "etiquette": "fictif",
        "titre": TITRE_PIECE,
        "outil": NOM_OUTIL,
        "valeurs": valeurs,
        "valeur_affichee": _valeur_affichee(valeurs, regles),
        "source": source_compositions(lus),
        "traitement": TRAITEMENT,
        "limites": LIMITES,
    }


def composition_utilisee(ticker: str) -> dict[str, Any]:
    """Ce que la pièce dit d'un FNB : dates des répartitions et part de chaque catégorie lisible."""
    composition = composition_du_fonds(ticker)
    utilisee: dict[str, Any] = {}
    for cle in ("secteurs", "titres", "pays"):
        if composition.get(cle) is not None:
            utilisee[f"date_{cle}"] = composition[cle]["date"]
    if composition.get("secteurs") is not None:
        utilisee["classification_secteurs"] = composition["secteurs"]["classification"]
    for nom, definition in charger_categories().items():
        if definition.get("transparence"):
            part = part_dans_le_fonds(ticker, [nom])
            if part is not None:
                utilisee[f"part_{nom}"] = round(part, DECIMALES_VALEURS)
    return utilisee


def _ensembles_de_categories(regles: list[dict[str, Any]]) -> list[list[str]]:
    """Chaque catégorie seule, puis chaque union de catégories d'une règle « plafond » du Pacte."""
    ensembles = [[nom] for nom in charger_categories()]
    for regle in regles:
        if regle["type"] == "plafond" and list(regle["categories"]) not in ensembles:
            ensembles.append(list(regle["categories"]))
    return ensembles


def _valeur_affichee(valeurs: dict[str, Any], regles: list[dict[str, Any]]) -> str:
    """Parts après la décision des catégories plafonnées par le Pacte (sinon : technologie et énergie)."""
    ensembles = [list(r["categories"]) for r in regles if r["type"] == "plafond"] or [["tech"], ["energie_fossile"]]
    morceaux = []
    for categories in ensembles:
        nom = "part_" + "_".join(categories)
        if nom in valeurs and f"{nom}_sans_transparence" in valeurs:
            morceaux.append(f"{nom_categories(categories)} {_part(valeurs[nom])} "
                            f"(au lieu de {_part(valeurs[nom + '_sans_transparence'])})")
        elif nom in valeurs:
            morceaux.append(f"{nom_categories(categories)} {_part(valeurs[nom])}")
    return " · ".join(dict.fromkeys(morceaux)) or "Aucune catégorie calculable"


def _part(valeur: float) -> str:
    """0.4732 → « 47,3 % » (part de portefeuille, sans signe)."""
    return f"{valeur * 100:.1f}".replace(".", ",") + " %"


def source_compositions(tickers: Iterable[str]) -> str:
    """Pages des émetteurs utilisées, avec la date de chaque répartition."""
    morceaux = []
    for ticker in tickers:
        composition = composition_du_fonds(ticker)
        dates = sorted({composition[cle]["date"] for cle in ("secteurs", "titres", "pays") if composition.get(cle)})
        morceaux.append(f"{composition['emetteur']} ({ticker}, {', '.join(dates)}) {composition['url']}")
    return ("Pages publiques des émetteurs, consultées le "
            f"{charger_compositions()['date_constitution']} : " + " ; ".join(morceaux))


# --- Vérification du fichier -------------------------------------------------------------


def erreurs_compositions(
    compositions: dict[str, Any] | None = None,
    categories: dict[str, Any] | None = None,
    univers: pd.DataFrame | None = None,
) -> list[str]:
    """Vérifie le fichier de composition et les blocs « transparence » des catégories.

    Attrape ce qui fausserait un calcul sans message : FNB hors de l'univers, répartition qui
    ne totalise pas 100 %, classification inconnue, nom de secteur mal écrit dans
    ``config/categories.json`` (une catégorie vide en silence), date mal formée.
    """
    compositions = charger_compositions() if compositions is None else compositions
    categories = charger_categories() if categories is None else categories
    univers = charger_univers() if univers is None else univers
    erreurs: list[str] = []
    fonds_univers = set(univers.loc[univers["asset_class"].str.startswith("etf"), "ticker"])
    classifications = set(compositions["classifications"])
    secteurs_par_classification: dict[str, set[str]] = {c: set() for c in classifications}

    for ticker, composition in compositions["fonds"].items():
        if ticker not in fonds_univers:
            erreurs.append(f"{ticker} : absent des FNB de assets_universe.csv")
        for champ in ("nom", "emetteur", "url", "date_consultation"):
            if not composition.get(champ):
                erreurs.append(f"{ticker} : champ « {champ} » manquant")
        for cle in ("secteurs", "titres", "pays"):
            bloc = composition.get(cle)
            if bloc is None:
                continue
            if not RE_DATE_ISO.fullmatch(str(bloc.get("date", ""))):
                erreurs.append(f"{ticker}/{cle} : date « {bloc.get('date')} » au format AAAA-MM-JJ attendue")
            valeurs = bloc["pourcentages"].values()
            if any(not 0 <= v <= 100 for v in valeurs):
                erreurs.append(f"{ticker}/{cle} : pourcentage hors de 0 à 100")
            if cle != "titres" and abs(sum(valeurs) - 100) > TOLERANCE_SOMME_POURCENTAGES:
                erreurs.append(f"{ticker}/{cle} : les pourcentages totalisent {sum(valeurs):.2f} au lieu de 100")
        if composition.get("secteurs") is not None:
            classification = composition["secteurs"]["classification"]
            if classification not in classifications:
                erreurs.append(f"{ticker}/secteurs : classification « {classification} » inconnue")
            else:
                secteurs_par_classification[classification] |= set(composition["secteurs"]["pourcentages"])

    secteurs_gics = set(univers["sector"])
    for nom, definition in categories.items():
        regle = definition.get("transparence")
        if not regle:
            continue
        if regle.get("dimension") not in DIMENSIONS:
            erreurs.append(f"{nom}/transparence : dimension « {regle.get('dimension')} » inconnue")
        elif regle["dimension"] == "pays" and ("pays" in regle) == ("pays_sauf" in regle):
            erreurs.append(f"{nom}/transparence : « pays » ou « pays_sauf » attendu, pas les deux")
        elif regle["dimension"] == "secteurs":
            for classification, lecture in regle.get("par_classification", {}).items():
                if classification not in classifications:
                    erreurs.append(f"{nom}/transparence : classification « {classification} » inconnue")
                    continue
                connus = secteurs_gics if classification == "GICS" else secteurs_par_classification[classification]
                for secteur in lecture.get("secteurs", []):
                    if secteur not in connus:
                        erreurs.append(f"{nom}/transparence/{classification} : secteur « {secteur} » inconnu")
    return erreurs


def fonds_sans_composition() -> list[str]:
    """FNB de l'univers absents du fichier de composition (ils gardent leur classement direct)."""
    return sorted(_fonds_de_l_univers() - set(charger_compositions()["fonds"]))
