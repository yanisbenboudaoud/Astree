"""Données macroéconomiques du Canada : inflation et taux de la Banque du Canada (#111).

Source : ``macro_rates.csv`` du jeu de départ (Banque du Canada, API Valet), lu comme
les autres CSV (``pipeline.donnees.lire_csv`` : en local ou dans S3). Seules les séries
canadiennes servent : le portefeuille est mesuré en CAD.

- ``STATIC_TOTALCPICHANGE`` : IPC du Canada, variation sur 12 mois, une valeur par mois
  de référence (datée du premier jour du mois) ;
- ``V39079`` : taux directeur de la Banque du Canada (taux cible du financement à un jour) ;
- ``BD.CDN.10YR.DQ.YLD`` : rendement de l'obligation de référence du Canada à 10 ans.

Les valeurs du fichier sont en pour cent (6,3 pour 6,3 %) ; ce module les renvoie en
décimales (0,063), comme toutes les valeurs des pièces : le Greffier convertit lui-même
« 6,3 % » en 0,063 pour les comparer.

Méthode :
- **Inflation d'une période** : produit des variations sur 12 mois, une par année
  entière, en partant du dernier mois de référence disponible à la fin de la période.
  Ce produit vaut exactement IPC(fin) / IPC(début). L'IPC d'un mois est publié quelques
  semaines plus tard : pour une période qui finit avant la publication, on s'arrête
  au dernier mois publié (ex. : septembre 2026 pour une période qui finit en novembre).
- **Rendement réel** : relation de Fisher, (1 + rendement) / (1 + inflation) − 1.
- **Taux sans risque** : moyenne du taux directeur sur la période (hypothèse de l'équipe :
  l'équivalent d'un placement liquide en CAD).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

from pipeline.donnees import ErreurDonnees, date_extraction, lire_csv

FICHIER_MACRO = "macro_rates.csv"

SERIE_INFLATION = "STATIC_TOTALCPICHANGE"
SERIE_TAUX_DIRECTEUR = "V39079"
SERIE_OBLIGATION_10_ANS = "BD.CDN.10YR.DQ.YLD"
SERIES_UTILISEES = (SERIE_INFLATION, SERIE_TAUX_DIRECTEUR, SERIE_OBLIGATION_10_ANS)

HYPOTHESE_TAUX_SANS_RISQUE = "Taux sans risque : taux directeur moyen de la Banque du Canada sur la période"


@dataclass(frozen=True)
class Inflation:
    """Inflation mesurée sur une période, avec les mois de référence de l'IPC utilisés."""

    cumulee: float  # IPC(mois_fin) / IPC(mois_debut) − 1
    annuelle: float  # taux composé annuel
    annees: int
    mois_debut: str  # « 2021-09 »
    mois_fin: str  # « 2026-09 »


@lru_cache(maxsize=1)
def _series() -> dict[str, pd.Series]:
    """Séries canadiennes utilisées, en décimales, indexées par date et triées."""
    brut = lire_csv(FICHIER_MACRO)
    manquantes = [serie for serie in SERIES_UTILISEES if serie not in set(brut["series_id"])]
    if manquantes:
        raise ErreurDonnees(f"{FICHIER_MACRO} ne contient pas la série : {', '.join(manquantes)}")
    series = {}
    for serie in SERIES_UTILISEES:
        lignes = brut[brut["series_id"] == serie]
        if (lignes["unit"] != "percent").any():
            raise ErreurDonnees(f"{FICHIER_MACRO} : la série {serie} n'est pas en pour cent")
        valeurs = pd.Series(lignes["value"].to_numpy() / 100, index=pd.to_datetime(lignes["date"]))
        if valeurs.index.duplicated().any():
            raise ErreurDonnees(f"{FICHIER_MACRO} : dates en double dans la série {serie}")
        series[serie] = valeurs.sort_index()
    return series


def inflation(debut: pd.Timestamp, fin: pd.Timestamp) -> Inflation:
    """Inflation du Canada sur la période, en années entières de mois de référence.

    Args:
        debut, fin: bornes de la période (ex. : première et dernière séance simulées).

    Raises:
        ErreurDonnees: période de moins d'un an, ou mois de référence manquant.
    """
    debut, fin = pd.Timestamp(debut), pd.Timestamp(fin)
    annees = round(((fin.year - debut.year) * 12 + fin.month - debut.month) / 12)
    if annees < 1:
        raise ErreurDonnees("Inflation : la période doit couvrir au moins un an")
    ipc = _series()[SERIE_INFLATION]
    disponibles = ipc[ipc.index <= fin.to_period("M").to_timestamp()]
    if disponibles.empty:
        raise ErreurDonnees(f"Inflation : aucun IPC publié avant le {fin.date()}")
    mois_fin = disponibles.index[-1]
    cumul = 1.0
    for annee in range(annees):
        mois = mois_fin - pd.DateOffset(years=annee)
        if mois not in ipc.index:
            raise ErreurDonnees(f"Inflation : IPC de {mois:%Y-%m} absent de {FICHIER_MACRO}")
        cumul *= 1 + ipc[mois]
    mois_debut = mois_fin - pd.DateOffset(years=annees)
    return Inflation(cumul - 1, cumul ** (1 / annees) - 1, annees, f"{mois_debut:%Y-%m}", f"{mois_fin:%Y-%m}")


def taux_au(serie: str, date: pd.Timestamp) -> float:
    """Dernière valeur publiée de la série à cette date (ex. : taux directeur au 2021-12-31)."""
    valeurs = _series()[serie]
    connues = valeurs[valeurs.index <= pd.Timestamp(date)]
    if connues.empty:
        raise ErreurDonnees(f"{serie} : aucune valeur connue au {pd.Timestamp(date).date()}")
    return float(connues.iloc[-1])


def taux_moyen(serie: str, debut: pd.Timestamp, fin: pd.Timestamp) -> float:
    """Moyenne des valeurs quotidiennes de la série entre deux dates, bornes comprises."""
    valeurs = _series()[serie]
    periode = valeurs[(valeurs.index >= pd.Timestamp(debut)) & (valeurs.index <= pd.Timestamp(fin))]
    if periode.empty:
        raise ErreurDonnees(f"{serie} : aucune valeur entre le {pd.Timestamp(debut).date()} et le {pd.Timestamp(fin).date()}")
    return float(periode.mean())


def rendement_reel(rendement: float, taux_inflation: float) -> float:
    """Relation de Fisher : (1 + rendement) / (1 + inflation) − 1."""
    return (1 + rendement) / (1 + taux_inflation) - 1


def source_macro() -> str:
    """Libellé de la source, avec sa date d'extraction."""
    return (f"Banque du Canada, API Valet (IPC, taux directeur, obligation à 10 ans), "
            f"extrait le {date_extraction(FICHIER_MACRO)}")
