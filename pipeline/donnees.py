"""Socle de données commun à tous les outils (CLAUDE.md, sections 6 et 6 bis).

Lit les CSV de ``alphaforge_starter/`` et renvoie des prix prêts à calculer.

Méthode retenue (à reprendre dans la documentation technique) :

- **Prix** : colonne ``adj_close``, ajustée pour les dividendes et les
  fractionnements. Les lignes « split » de ``corporate_actions.csv`` ne sont
  jamais réappliquées : elles sont déjà incluses dans ``adj_close``.
- **Calendrier** : séances de la bourse américaine, c'est-à-dire les dates où
  au moins un titre coté sur un marché américain (``MARCHES_AMERICAINS``) a un
  prix. Pour un titre sans prix ce jour-là (jour férié à la TSX, ou crypto
  pendant le week-end), le dernier prix connu est reporté. Les rendements crypto
  du week-end sont donc cumulés dans le lundi.
- **Devise** : ``charger_prix`` garde la devise de cotation du titre (CAD pour
  ``.TO``, USD sinon). ``charger_donnees`` convertit tout en CAD avec le taux
  USD/CAD quotidien de la Banque du Canada (``fx_usdcad_daily.csv``). Ce fichier
  n'a pas de taux les jours fériés canadiens : le dernier taux connu est reporté.

Source des CSV, par la variable d'environnement ``SOURCE_DONNEES`` :
- ``local`` (par défaut) : dossier ``alphaforge_starter/`` du dépôt ;
- ``s3`` : branché plus tard (issue #13).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

DOSSIER_DONNEES = Path(__file__).resolve().parent.parent / "alphaforge_starter"

# Valeurs de la colonne « market » de assets_universe.csv qui définissent le
# calendrier de référence.
MARCHES_AMERICAINS = {"NASDAQ", "NYSE", "NYSE Arca", "Cboe BZX"}

# Hypothèses à reprendre telles quelles dans le champ « hypotheses » du contrat.
HYPOTHESES_DONNEES = [
    "Rendements calculés sur adj_close",
    "Calendrier des séances américaines, dernier prix reporté",
    "Montants convertis en CAD",
]


class ErreurDonnees(Exception):
    """Donnée demandée absente ou inutilisable : l'outil le signale au lieu de deviner."""


def lire_csv(nom_fichier: str) -> pd.DataFrame:
    """Lit un CSV du jeu de données, en local ou dans S3 selon ``SOURCE_DONNEES``."""
    source = os.environ.get("SOURCE_DONNEES", "local")
    if source == "local":
        return pd.read_csv(DOSSIER_DONNEES / nom_fichier)
    if source == "s3":
        raise ErreurDonnees("Lecture depuis S3 pas encore branchée (issue #13)")
    raise ErreurDonnees(f"SOURCE_DONNEES doit valoir « local » ou « s3 », pas « {source} »")


@lru_cache(maxsize=1)
def _univers() -> pd.DataFrame:
    return lire_csv("assets_universe.csv")


@lru_cache(maxsize=1)
def _prix_bruts() -> pd.DataFrame:
    """Prix adj_close, une ligne par date (toutes dates confondues), une colonne par titre."""
    prix = lire_csv("prices_daily.csv")
    if prix.duplicated(["date", "ticker"]).any():
        raise ErreurDonnees("prices_daily.csv contient des lignes en double (date, ticker)")
    prix["date"] = pd.to_datetime(prix["date"])
    return prix.pivot(index="date", columns="ticker", values="adj_close").sort_index()


@lru_cache(maxsize=1)
def _taux_usdcad() -> pd.Series:
    """Taux USD/CAD (1 USD = x CAD), une valeur par jour ouvrable canadien."""
    taux = lire_csv("fx_usdcad_daily.csv")
    taux["date"] = pd.to_datetime(taux["date"])
    if taux["date"].duplicated().any():
        raise ErreurDonnees("fx_usdcad_daily.csv contient des dates en double")
    return taux.set_index("date")["usdcad"].sort_index()


def charger_univers() -> pd.DataFrame:
    """Univers d'actifs (assets_universe.csv) : ticker, classe d'actifs, marché, devise, secteur."""
    return _univers().copy()


def seances_americaines() -> pd.DatetimeIndex:
    """Dates des séances de la bourse américaine, triées."""
    univers = _univers()
    tickers_us = univers.loc[univers["market"].isin(MARCHES_AMERICAINS), "ticker"]
    prix = _prix_bruts()[list(tickers_us)]
    return prix.dropna(how="all").index


def charger_prix(tickers: list[str]) -> pd.DataFrame:
    """Prix adj_close des titres demandés, alignés sur les séances américaines.

    Args:
        tickers: titres de l'univers, ex. ``["RY.TO", "SPY", "BTC-USD"]``. Un titre
            demandé deux fois n'apparaît qu'une fois.

    Returns:
        Une ligne par séance américaine (index ``date``, trié, sans doublon), une
        colonne par titre dans l'ordre demandé. Prix dans la devise de cotation,
        dernier prix connu reporté quand le titre n'a pas de prix ce jour-là.

    Raises:
        ErreurDonnees: titre absent de l'univers, ou titre sans prix connu à une
            séance (ex. : pas encore coté au début de la période).
    """
    tickers = list(dict.fromkeys(tickers))
    if not tickers:
        raise ErreurDonnees("Aucun titre demandé")
    inconnus = [t for t in tickers if t not in set(_univers()["ticker"])]
    if inconnus:
        raise ErreurDonnees(f"Titre(s) absent(s) de l'univers d'actifs : {', '.join(inconnus)}")

    # Le report se fait sur toutes les dates (week-ends crypto compris) avant de
    # ne garder que les séances américaines : le prix du lundi est alors le
    # dernier prix connu, et le rendement du week-end tombe dans le lundi.
    prix = _prix_bruts()[tickers].ffill().loc[seances_americaines()]
    sans_prix = prix.columns[prix.isna().any()].tolist()
    if sans_prix:
        raise ErreurDonnees(f"Aucun prix connu au début de la période pour : {', '.join(sans_prix)}")
    prix.columns.name = None
    return prix


def convertir_en_cad(prix: pd.DataFrame, devises: dict[str, str]) -> pd.DataFrame:
    """Convertit en CAD des prix exprimés dans leur devise de cotation.

    Args:
        prix: une ligne par date, une colonne par titre (sortie de ``charger_prix``).
        devises: devise de cotation de chaque colonne, ``"CAD"`` ou ``"USD"``.

    Returns:
        Les mêmes prix en CAD. Une colonne en CAD est inchangée ; une colonne en
        USD est multipliée par le taux USD/CAD du jour, ou par le dernier taux
        connu quand la Banque du Canada n'en publie pas (jour férié canadien).

    Raises:
        ErreurDonnees: devise manquante ou non prise en charge, ou date sans
            taux connu (avant le premier taux du fichier).
    """
    non_gerees = {t: devises.get(t) for t in prix.columns if devises.get(t) not in ("CAD", "USD")}
    if non_gerees:
        detail = ", ".join(f"{t} ({d})" for t, d in non_gerees.items())
        raise ErreurDonnees(f"Devise manquante ou non prise en charge : {detail}")

    taux = _taux_usdcad()
    taux = taux.reindex(taux.index.union(prix.index)).ffill().reindex(prix.index)
    if taux.isna().any():
        premiere = taux.index[taux.isna()][0].date()
        raise ErreurDonnees(f"Aucun taux USD/CAD connu au {premiere}")

    en_cad = prix.copy()
    for ticker in prix.columns:
        if devises[ticker] == "USD":
            en_cad[ticker] = prix[ticker] * taux
    return en_cad


def charger_donnees(tickers: list[str]) -> pd.DataFrame:
    """Prix adj_close en CAD, alignés sur les séances américaines : l'entrée de tous les outils.

    Même format et mêmes erreurs que ``charger_prix``, mais tous les prix sont
    convertis en CAD (``convertir_en_cad``).
    """
    prix = charger_prix(tickers)
    univers = _univers()
    devises = dict(zip(univers["ticker"], univers["currency"]))
    return convertir_en_cad(prix, devises)
