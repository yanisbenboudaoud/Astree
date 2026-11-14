"""Outil 3 : calculer_correlations (CLAUDE.md, section 4 bis ; cas général 2).

Mesure si des titres évoluent ensemble : deux lignes très corrélées (ex. :
BTC et ETH) ne se diversifient pas l'une l'autre. Sert au Procureur pour le
cas « profil tolérant au risque » (#16).

Deux niveaux, comme l'outil 1 :

1. ``calculer_matrice_correlations(prix)`` : fonction de calcul **pure**.
2. ``calculer_correlations(tickers)`` : la pièce au format du contrat
   (section 5), sans « id » : c'est l'orchestrateur qui numérote les pièces.

L'orchestrateur Bedrock appelle l'outil grâce à ``DESCRIPTION_BEDROCK``. Une
demande invalide (titre hors univers, moins de 2 titres…) lève
``ErreurDonnees`` avec un message lisible, que l'orchestrateur renvoie au
modèle comme résultat en erreur.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

import pandas as pd

from pipeline.donnees import ErreurDonnees, charger_donnees, charger_univers, date_extraction
from pipeline.llm import decrire_outil

# Au-delà, la pièce deviendrait illisible (10 titres = 45 paires).
MAX_TITRES = 10

# Les valeurs des pièces sont brutes : au moins 4 décimales (CLAUDE.md, section 5).
DECIMALES_VALEURS = 6

# Paires montrées dans la valeur affichée (les plus corrélées).
PAIRES_AFFICHEES = 3


# --- Fonction de calcul pure ---------------------------------------------------


def calculer_matrice_correlations(prix: pd.DataFrame) -> pd.DataFrame:
    """Corrélations (Pearson) des rendements quotidiens, une ligne et une colonne par titre.

    Args:
        prix: une ligne par date, une colonne par titre (ex. : sortie de ``charger_donnees``).
    """
    return prix.pct_change().dropna().corr()


# --- L'outil ------------------------------------------------------------------


def calculer_correlations(tickers: list[str]) -> dict[str, Any]:
    """Pièce « Corrélations entre … », calculée en CAD sur toute la période.

    Args:
        tickers: 2 à 10 titres de l'univers ; un titre demandé deux fois compte une fois.

    Raises:
        ErreurDonnees: moins de 2 ou plus de 10 titres distincts, titre hors univers.
    """
    tickers = list(dict.fromkeys(tickers))
    if len(tickers) < 2:
        raise ErreurDonnees("Il faut au moins deux titres distincts pour calculer une corrélation")
    if len(tickers) > MAX_TITRES:
        raise ErreurDonnees(f"Au plus {MAX_TITRES} titres à la fois ({len(tickers)} demandés)")

    prix = charger_donnees(tickers)
    matrice = calculer_matrice_correlations(prix)
    paires = {(a, b): round(float(matrice.loc[a, b]), DECIMALES_VALEURS)
              for a, b in combinations(tickers, 2)}

    valeurs: dict[str, Any] = {f"correlation_{a}_{b}": valeur for (a, b), valeur in paires.items()}
    valeurs["titres"] = tickers
    valeurs["nb_rendements_quotidiens"] = len(prix) - 1
    valeurs["periode"] = [prix.index[0].date().isoformat(), prix.index[-1].date().isoformat()]

    return {
        "type": "calculee",
        "etiquette": "fait",
        "titre": f"Corrélations entre {', '.join(tickers)}",
        "outil": "calculer_correlations",
        "valeurs": valeurs,
        "valeur_affichee": _valeur_affichee(paires),
        "source": _source(tickers),
        "traitement": (
            "Prix adj_close convertis en CAD, calendrier des séances américaines (dernier prix "
            f"reporté), {valeurs['periode'][0]} → {valeurs['periode'][1]} ; corrélation de Pearson "
            "des rendements quotidiens, pour chaque paire de titres"
        ),
        "limites": (
            "Une seule période de 5 ans ; les corrélations changent dans le temps et montent souvent "
            "en période de crise ; la conversion en CAD ajoute un facteur de change commun aux titres "
            "en USD ; les rendements crypto du week-end sont cumulés dans le lundi ; le passé ne "
            "prédit pas l'avenir"
        ),
    }


DESCRIPTION_BEDROCK = decrire_outil(
    "calculer_correlations",
    "Corrélations historiques des rendements quotidiens (en CAD, sur toute la période) entre "
    "2 et 10 titres de l'univers, pour chaque paire. Une corrélation proche de 1 signifie que "
    "deux titres montent et baissent ensemble : ils ne se diversifient pas l'un l'autre. Utile "
    "quand la décision concentre le portefeuille, par exemple un panier de cryptoactifs ou de "
    "titres technologiques, ou pour comparer le titre visé aux lignes déjà détenues.",
    {
        "type": "object",
        "properties": {
            "tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2 à 10 tickers exacts de l'univers, ex. [\"BTC-USD\", \"ETH-USD\", \"NVDA\"]",
            },
        },
        "required": ["tickers"],
        "additionalProperties": False,
    },
)


# --- Mise en forme ------------------------------------------------------------


def _nombre(valeur: float) -> str:
    """0.84453 → « 0,84 » ; -0.1234 → « −0,12 »."""
    return f"{valeur:.2f}".replace(".", ",").replace("-", "−")


def _valeur_affichee(paires: dict[tuple[str, str], float]) -> str:
    """Les paires les plus corrélées, ex. « BTC-USD/ETH-USD 0,84 · NVDA/QQQ 0,77 »."""
    plus_correlees = sorted(paires.items(), key=lambda paire: paire[1], reverse=True)
    texte = " · ".join(f"{a}/{b} {_nombre(v)}" for (a, b), v in plus_correlees[:PAIRES_AFFICHEES])
    if len(paires) > PAIRES_AFFICHEES:
        texte += f" · {len(paires)} paires en tout"
    return texte


def _source(tickers: list[str]) -> str:
    univers = charger_univers()
    devises = set(univers.loc[univers["ticker"].isin(tickers), "currency"])
    source = f"Yahoo Finance via yfinance (adj_close), extrait le {date_extraction('prices_daily.csv')}"
    if "USD" in devises:
        source += f" ; USD/CAD Banque du Canada, extrait le {date_extraction('fx_usdcad_daily.csv')}"
    return source
