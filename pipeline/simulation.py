"""Outil 2 : simuler_portefeuille — le portefeuille du profil avant et après la décision.

C'est la pièce principale du procès (CLAUDE.md, sections 4 bis et 6 bis) : que
serait devenu le portefeuille sur la période d'analyse, avec et sans la
décision ? Elle remplit ``comparaison.actuel`` et ``comparaison.apres`` du
contrat, et c'est la seule pièce obligatoire de l'orchestrateur.
``taille_max_compatible`` (#21) l'appelle en boucle : les rendements quotidiens
sont donc chargés une seule fois par ensemble de titres.

Méthode (CLAUDE.md, section 6 bis) :

- **Prix** : ``charger_donnees`` (``adj_close`` en CAD, séances américaines).
- **Rééquilibrage quotidien** aux poids cibles : le rendement du portefeuille un
  jour donné est la moyenne pondérée des rendements des titres ce jour-là.
- **Financement** ``proportionnel`` (toutes les lignes réduites au prorata) ou
  ``depuis_<ticker>`` (une seule ligne réduite).
- **Indicateurs** : les fonctions de calcul de ``pipeline.indicateurs`` (#6),
  appliquées à la série de valeurs du portefeuille.

Le code ne connaît aucun persona : il lit seulement le portefeuille reçu.
V1 : décisions de type « position ». Les réallocations vers un panier arrivent
avec #16.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import pandas as pd

from pipeline.donnees import ErreurDonnees, charger_donnees, date_extraction
from pipeline.indicateurs import (
    DECIMALES_VALEURS,
    calculer_pire_baisse,
    calculer_rendement_2022,
    calculer_rendement_annualise,
    calculer_volatilite_annuelle,
)
from pipeline.llm import decrire_outil

NOM_OUTIL = "simuler_portefeuille"

# Écart toléré sur la somme des poids d'un portefeuille (arrondis des fichiers JSON).
TOLERANCE_POIDS = 1e-6

LIMITES_PERIODE_COMPLETE = "Une seule période de {annees} ans ; biais du survivant ; le passé ne prédit pas l'avenir"
LIMITES_REJEU = "Une seule année de crise ; la suivante peut être différente"


class ErreurSimulation(ValueError):
    """Décision ou portefeuille impossible à simuler : l'outil le signale au lieu de deviner.

    Les données absentes (titre hors de l'univers, titre sans prix au début de
    la période) lèvent ``pipeline.donnees.ErreurDonnees``.
    """


# --- Poids après la décision --------------------------------------------------


def poids_apres_decision(portefeuille: list[dict[str, Any]], decision: dict[str, Any]) -> dict[str, float]:
    """Poids cibles du portefeuille une fois la décision appliquée.

    Args:
        portefeuille: lignes ``{"ticker", "poids"}`` du profil (poids totalisant 1).
        decision: décision du contrat (section 5), de l'un des deux types :
            - « position » : ``ticker``, ``taille`` (part du portefeuille, entre
              0 et 1) et ``financement`` (``proportionnel`` ou ``depuis_<ticker>``) ;
            - « reallocation » : ``panier`` (lignes ``{"ticker", "poids"}``
              totalisant 1) et ``part_reallouee`` (entre 0 et 1), prise au
              prorata de toutes les lignes du portefeuille (#16).

    Returns:
        Un poids par titre, totalisant 1. Une ligne vidée (financement
        ``depuis_<ticker>``, ou réallocation de 100 %) disparaît.

    Raises:
        ErreurSimulation: portefeuille ou panier mal formé, type de décision
            inconnu, taille hors de [0, 1], financement inconnu ou impossible.
    """
    poids = _poids_actuels(portefeuille)

    if decision.get("type") == "reallocation":
        return _poids_apres_reallocation(poids, decision)
    if decision.get("type") != "position":
        raise ErreurSimulation(
            f"Type de décision « {decision.get('type')} » inconnu : « position » ou « reallocation » attendu"
        )
    ticker = decision["ticker"]
    taille = decision["taille"]
    if isinstance(taille, bool) or not isinstance(taille, (int, float)) or not 0 <= taille <= 1:
        raise ErreurSimulation(f"Taille « {taille} » impossible : elle doit être comprise entre 0 et 1")
    financement = decision["financement"]

    if financement == "proportionnel":
        apres = {t: p * (1 - taille) for t, p in poids.items()}
    elif financement.startswith("depuis_"):
        source = financement.removeprefix("depuis_")
        if source == ticker:
            raise ErreurSimulation(f"Financement depuis {source} impossible : c'est le titre acheté")
        if source not in poids:
            raise ErreurSimulation(f"Financement depuis {source} impossible : titre absent du portefeuille")
        if poids[source] < taille - TOLERANCE_POIDS:
            raise ErreurSimulation(
                f"Financement depuis {source} impossible : la ligne pèse moins que la taille demandée"
            )
        apres = dict(poids)
        apres[source] = max(poids[source] - taille, 0.0)
        if apres[source] <= TOLERANCE_POIDS:
            del apres[source]
    else:
        raise ErreurSimulation(
            f"Financement « {financement} » inconnu : « proportionnel » ou « depuis_<ticker> » attendu"
        )

    apres[ticker] = apres.get(ticker, 0.0) + taille
    return apres


def _poids_apres_reallocation(poids: dict[str, float], decision: dict[str, Any]) -> dict[str, float]:
    """Retire la part réallouée de chaque ligne au prorata, puis la répartit selon le panier."""
    part = decision["part_reallouee"]
    if isinstance(part, bool) or not isinstance(part, (int, float)) or not 0 <= part <= 1:
        raise ErreurSimulation(f"Part réallouée « {part} » impossible : elle doit être comprise entre 0 et 1")
    panier = decision["panier"]
    if not panier:
        raise ErreurSimulation("Panier vide : rien à réallouer")
    tickers = [ligne["ticker"] for ligne in panier]
    if len(set(tickers)) != len(tickers):
        raise ErreurSimulation("Un titre apparaît deux fois dans le panier")
    if any(isinstance(ligne["poids"], bool) or not ligne["poids"] > 0 for ligne in panier):
        raise ErreurSimulation("Chaque titre du panier doit avoir un poids positif")
    total = sum(ligne["poids"] for ligne in panier)
    if abs(total - 1) > TOLERANCE_POIDS:
        raise ErreurSimulation(f"Les poids du panier totalisent {total} au lieu de 1")

    apres = {t: p * (1 - part) for t, p in poids.items()}
    for ligne in panier:
        apres[ligne["ticker"]] = apres.get(ligne["ticker"], 0.0) + part * ligne["poids"]
    return {t: p for t, p in apres.items() if p > TOLERANCE_POIDS}


def _poids_actuels(portefeuille: list[dict[str, Any]]) -> dict[str, float]:
    """Poids du portefeuille de départ, vérifiés (un titre par ligne, total de 1)."""
    if not portefeuille:
        raise ErreurSimulation("Portefeuille vide : rien à simuler")
    poids: dict[str, float] = {}
    for ligne in portefeuille:
        ticker, part = ligne["ticker"], ligne["poids"]
        if ticker in poids:
            raise ErreurSimulation(f"Le titre {ticker} apparaît deux fois dans le portefeuille")
        if not 0 < part <= 1:
            raise ErreurSimulation(f"Poids de {ticker} impossible : {part}")
        poids[ticker] = float(part)
    if abs(sum(poids.values()) - 1) > TOLERANCE_POIDS:
        raise ErreurSimulation(f"Les poids du portefeuille totalisent {sum(poids.values())}, pas 1")
    return poids


# --- Simulation ---------------------------------------------------------------


def simuler_portefeuille(portefeuille: list[dict[str, Any]], decision: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Indicateurs du portefeuille avant et après la décision, valeurs brutes.

    Returns:
        ``{"actuel": {...}, "apres": {...}}``, chacun avec ``rendement_annuel``,
        ``volatilite_annuelle``, ``pire_baisse`` et ``rendement_2022`` : le format
        de ``comparaison`` du contrat. Les valeurs ne sont pas arrondies (les
        pièces, elles, le sont à ``DECIMALES_VALEURS``).

    Raises:
        ErreurSimulation: voir ``poids_apres_decision``.
        ErreurDonnees: titre hors de l'univers, ou sans prix au début de la période.
    """
    actuel, apres = _deux_simulations(portefeuille, decision)
    return {"actuel": actuel.indicateurs(), "apres": apres.indicateurs()}


def piece_simulation(
    id_piece: str,
    portefeuille: list[dict[str, Any]],
    decision: dict[str, Any],
    periode: str = "complete",
) -> dict[str, Any]:
    """Pièce du contrat produite par l'outil, étiquette « fictif ».

    Args:
        id_piece: identifiant attribué par l'orchestrateur (ex. : « P1 »).
        portefeuille, decision: voir ``poids_apres_decision``.
        periode: ``complete`` (toute la période d'analyse : pire baisse,
            rendement annualisé et volatilité, avant et après) ou ``2022``
            (rejeu de l'année de crise : rendement 2022 avant et après).

    Returns:
        La pièce au format du contrat : ``valeurs`` brutes (arrondies à
        ``DECIMALES_VALEURS``, comme les pièces de ``indicateurs_actif``),
        ``valeur_affichee`` arrondie par Python.
    """
    actuel, apres = _deux_simulations(portefeuille, decision)
    if periode == "complete":
        return _piece_periode_complete(id_piece, actuel, apres)
    if periode == "2022":
        return _piece_rejeu_2022(id_piece, actuel, apres)
    raise ErreurSimulation(f"Période « {periode} » inconnue : « complete » ou « 2022 » attendue")


class _Simulation:
    """Valeurs quotidiennes d'un portefeuille rééquilibré chaque jour (départ à 1)."""

    def __init__(self, debut: pd.Timestamp, rendements_titres: pd.DataFrame, poids: dict[str, float]):
        ponderation = pd.Series(poids).reindex(rendements_titres.columns, fill_value=0.0)
        valeurs = (1 + rendements_titres @ ponderation).cumprod()
        # La valeur de départ (1) est datée de la première séance : un sommet possible.
        self.valeurs = pd.concat([pd.Series([1.0], index=[debut]), valeurs])

    def indicateurs(self) -> dict[str, float]:
        return {
            "rendement_annuel": float(calculer_rendement_annualise(self.valeurs)),
            "volatilite_annuelle": float(calculer_volatilite_annuelle(self.valeurs)),
            "pire_baisse": float(calculer_pire_baisse(self.valeurs)),
            "rendement_2022": float(calculer_rendement_2022(self.valeurs)),
        }


def _deux_simulations(portefeuille, decision) -> tuple[_Simulation, _Simulation]:
    """Le portefeuille actuel et le portefeuille après la décision, sur les mêmes séances."""
    poids_actuels = _poids_actuels(portefeuille)
    poids_apres = poids_apres_decision(portefeuille, decision)
    tickers = tuple(sorted(set(poids_actuels) | set(poids_apres)))
    debut, rendements = _rendements_quotidiens(tickers)
    return _Simulation(debut, rendements, poids_actuels), _Simulation(debut, rendements, poids_apres)


@lru_cache(maxsize=32)
def _rendements_quotidiens(tickers: tuple[str, ...]) -> tuple[pd.Timestamp, pd.DataFrame]:
    """Première séance et rendements quotidiens en CAD des titres, calculés une seule fois.

    Le cache sert ``taille_max_compatible`` (#21), qui simule le même ensemble de
    titres une trentaine de fois. Le DataFrame renvoyé est partagé : ne pas le modifier.
    """
    prix = charger_donnees(list(tickers))
    return prix.index[0], prix.pct_change().iloc[1:]


def _bornes_2022(valeurs: pd.Series) -> list[str]:
    """Dates ISO de la dernière séance de 2021 et de la dernière séance de 2022.

    Ce sont les bornes du rendement de ``calculer_rendement_2022``, affichées dans la pièce.
    """
    fin_2021 = valeurs.index[valeurs.index.year == 2021]
    fin_2022 = valeurs.index[valeurs.index.year == 2022]
    if fin_2021.empty or fin_2022.empty:
        raise ErreurDonnees("La série ne couvre pas la fin de 2021 et la fin de 2022")
    return [fin_2021[-1].date().isoformat(), fin_2022[-1].date().isoformat()]


# --- Pièces -------------------------------------------------------------------


def _piece_periode_complete(id_piece: str, actuel: _Simulation, apres: _Simulation) -> dict[str, Any]:
    ind_actuel, ind_apres = actuel.indicateurs(), apres.indicateurs()
    debut, fin = apres.valeurs.index[0], apres.valeurs.index[-1]
    annees = round((fin - debut).days / 365.25)
    return {
        "id": id_piece,
        "type": "calculee",
        "etiquette": "fictif",
        "titre": "Simulation du portefeuille avec la décision",
        "outil": NOM_OUTIL,
        "valeurs": _arrondir({
            "pire_baisse": ind_apres["pire_baisse"],
            "rendement_annuel": ind_apres["rendement_annuel"],
            "volatilite_annuelle": ind_apres["volatilite_annuelle"],
            "pire_baisse_actuelle": ind_actuel["pire_baisse"],
            "rendement_annuel_actuel": ind_actuel["rendement_annuel"],
            "volatilite_annuelle_actuelle": ind_actuel["volatilite_annuelle"],
        }),
        "valeur_affichee": (
            f"{formater_pourcentage(ind_apres['pire_baisse'])} max · "
            f"{formater_pourcentage(ind_apres['rendement_annuel'])}/an"
        ),
        "source": source_des_prix(),
        "traitement": (
            "Rendements quotidiens en CAD, calendrier des séances américaines, rééquilibrage "
            f"quotidien, {debut.date().isoformat()} → {fin.date().isoformat()}"
        ),
        "limites": LIMITES_PERIODE_COMPLETE.format(annees=annees),
    }


def _piece_rejeu_2022(id_piece: str, actuel: _Simulation, apres: _Simulation) -> dict[str, Any]:
    rendement_actuel = actuel.indicateurs()["rendement_2022"]
    rendement_apres = apres.indicateurs()["rendement_2022"]
    return {
        "id": id_piece,
        "type": "calculee",
        "etiquette": "fictif",
        "titre": "Rejeu de 2022",
        "outil": NOM_OUTIL,
        "valeurs": {
            "periode": _bornes_2022(apres.valeurs),
            **_arrondir({"rendement_2022_actuel": rendement_actuel, "rendement_2022_apres": rendement_apres}),
        },
        "valeur_affichee": f"{formater_pourcentage(rendement_actuel)} → {formater_pourcentage(rendement_apres)}",
        "source": source_des_prix(),
        "traitement": (
            "Portefeuille avec et sans la position, de la dernière séance de 2021 "
            "à la dernière séance de 2022"
        ),
        "limites": LIMITES_REJEU,
    }


def _arrondir(valeurs: dict[str, float]) -> dict[str, float]:
    """Valeurs brutes d'une pièce : arrondies à DECIMALES_VALEURS, comme dans pipeline.indicateurs."""
    return {nom: round(valeur, DECIMALES_VALEURS) for nom, valeur in valeurs.items()}


@lru_cache(maxsize=1)
def source_des_prix() -> str:
    """Source des prix et du taux de change, avec la date d'extraction des prix."""
    return (
        f"Yahoo Finance via yfinance (adj_close), extrait le {date_extraction('prices_daily.csv')} ; "
        "USD/CAD Banque du Canada"
    )


def formater_pourcentage(valeur: float, decimales: int = 1) -> str:
    """-0.2897 → « −29,0 % » ; 0.1198 → « +12,0 % » (signe écrit, virgule française).

    Le signe moins est le caractère « − » (U+2212), comme dans la maquette. Une
    valeur qui s'arrondit à zéro n'a pas de signe.
    """
    texte = f"{abs(valeur) * 100:.{decimales}f}".replace(".", ",")
    if not texte.strip("0,"):
        return f"{texte} %"
    return f"{'−' if valeur < 0 else '+'}{texte} %"


# --- Description pour l'orchestrateur Bedrock (#12) --------------------------

DESCRIPTION = (
    "Simule le portefeuille du profil avant et après la décision (prix en CAD, rééquilibrage "
    "quotidien) et produit une pièce. periode « complete » : pire baisse, rendement annualisé "
    "et volatilité sur toute la période d'analyse. periode « 2022 » : rejeu de l'année où "
    "actions et obligations ont baissé ensemble. Pièce obligatoire : la simulation complète "
    "de la décision demandée."
)


def decrire_simuler_portefeuille(tickers_univers: list[str], portefeuille: list[dict[str, Any]]) -> dict[str, Any]:
    """Description de l'outil pour Bedrock (*tool use*), propre au portefeuille du profil.

    Les listes de valeurs permises empêchent le modèle de demander un titre hors
    de l'univers ou un financement depuis un titre absent du portefeuille. La
    taille n'a pas de borne dans le schéma : Python la vérifie
    (``poids_apres_decision``) et renvoie une erreur lisible.
    """
    tickers_portefeuille = sorted({ligne["ticker"] for ligne in portefeuille})
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["ticker", "taille", "financement", "periode"],
        "properties": {
            "ticker": {
                "type": "string",
                "enum": sorted(tickers_univers),
                "description": "Titre de la décision",
            },
            "taille": {
                "type": "number",
                "description": "Part du portefeuille visée, en décimale entre 0 et 1 (0.30 = 30 %)",
            },
            "financement": {
                "type": "string",
                "enum": ["proportionnel"] + [f"depuis_{t}" for t in tickers_portefeuille],
                "description": "« proportionnel » : toutes les lignes réduites au prorata ; "
                "« depuis_<ticker> » : seule cette ligne est réduite",
            },
            "periode": {
                "type": "string",
                "enum": ["complete", "2022"],
                "description": "« complete » : toute la période d'analyse ; « 2022 » : rejeu de l'année de crise",
            },
        },
    }
    return decrire_outil(NOM_OUTIL, DESCRIPTION, schema)


def decrire_simuler_reallocation() -> dict[str, Any]:
    """Description de l'outil pour une décision de **réallocation** (#16).

    Le panier est celui de la décision (lu par Python) : le modèle choisit
    seulement la part réallouée et la période.
    """
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["part_reallouee", "periode"],
        "properties": {
            "part_reallouee": {
                "type": "number",
                "description": "Part du portefeuille réallouée vers le panier de la décision, "
                "en décimale entre 0 et 1 (1.0 = tout le portefeuille)",
            },
            "periode": {
                "type": "string",
                "enum": ["complete", "2022"],
                "description": "« complete » : toute la période d'analyse ; « 2022 » : rejeu de l'année de crise",
            },
        },
    }
    return decrire_outil(
        NOM_OUTIL,
        DESCRIPTION + " Ici, la décision est une réallocation vers le panier qu'elle décrit : "
        "la part réallouée est prise au prorata de toutes les lignes.",
        schema,
    )
