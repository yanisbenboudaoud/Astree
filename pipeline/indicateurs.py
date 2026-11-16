"""Outil 1 : indicateurs_actif (REFERENCE_DU_PROJET.md, sections 4 bis et 6 bis).

Deux niveaux :

1. Des fonctions de calcul **pures**, sur une série de valeurs indexée par date
   (prix d'un titre ou valeur d'un portefeuille). Elles seront réutilisées par
   ``simuler_portefeuille`` (#9).
2. ``indicateurs_actif(ticker)`` : calcule ces indicateurs pour un titre, en CAD,
   et les rend sous forme de pièce au format du contrat (section 5), sans « id » :
   c'est l'orchestrateur qui numérote les pièces.

L'orchestrateur Bedrock appelle l'outil grâce à ``DESCRIPTION_BEDROCK``. Un titre
hors univers lève ``ErreurDonnees`` avec un message lisible : l'orchestrateur
(#12) l'attrape et renvoie ce message au modèle comme résultat en erreur.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from pipeline.donnees import ErreurDonnees, charger_donnees, charger_univers, date_extraction
from pipeline.llm import decrire_outil

JOURS_DE_SEANCE_PAR_AN = 252
JOURS_PAR_AN = 365.25

# Les valeurs des pièces sont brutes : au moins 4 décimales (REFERENCE_DU_PROJET.md, section 5).
DECIMALES_VALEURS = 6


# --- Fonctions de calcul pures ----------------------------------------------


def calculer_rendement_annualise(valeurs: pd.Series) -> float:
    """Taux composé annuel entre la première et la dernière date de la série."""
    annees = (valeurs.index[-1] - valeurs.index[0]).days / JOURS_PAR_AN
    return (valeurs.iloc[-1] / valeurs.iloc[0]) ** (1 / annees) - 1


def calculer_volatilite_annuelle(valeurs: pd.Series) -> float:
    """Écart type des rendements quotidiens × √252."""
    return valeurs.pct_change().dropna().std() * JOURS_DE_SEANCE_PAR_AN**0.5


def calculer_pire_baisse(valeurs: pd.Series) -> float:
    """Plus forte chute depuis un sommet (nombre négatif, ou 0 sans aucune baisse)."""
    return (valeurs / valeurs.cummax() - 1).min()


def calculer_rendement_2022(valeurs: pd.Series) -> float:
    """Rendement de la dernière valeur de 2021 à la dernière valeur de 2022."""
    fin_2021 = valeurs[valeurs.index.year == 2021]
    fin_2022 = valeurs[valeurs.index.year == 2022]
    if fin_2021.empty or fin_2022.empty:
        raise ErreurDonnees("La série ne couvre pas la fin de 2021 et la fin de 2022")
    return fin_2022.iloc[-1] / fin_2021.iloc[-1] - 1


def calculer_temps_recuperation(valeurs: pd.Series) -> dict[str, Any]:
    """Durée entre le sommet qui précède la pire baisse et le retour à ce sommet.

    Returns:
        ``date_sommet``, ``date_creux``, ``date_retour_sommet`` (dates ISO) et
        ``annees_recuperation``. Les deux derniers valent ``None`` si la série
        n'est pas revenue à son sommet avant la fin ; tous valent ``None`` si la
        série n'a jamais baissé.
    """
    baisses = valeurs / valeurs.cummax() - 1
    if baisses.min() == 0:
        return {"date_sommet": None, "date_creux": None, "date_retour_sommet": None,
                "annees_recuperation": None}
    date_creux = baisses.idxmin()
    date_sommet = valeurs[:date_creux].idxmax()
    apres_creux = valeurs[date_creux:]
    retours = apres_creux.index[apres_creux >= valeurs[date_sommet]]
    date_retour = retours[0] if len(retours) else None
    return {
        "date_sommet": date_sommet.date().isoformat(),
        "date_creux": date_creux.date().isoformat(),
        "date_retour_sommet": date_retour.date().isoformat() if date_retour is not None else None,
        "annees_recuperation": (date_retour - date_sommet).days / JOURS_PAR_AN
        if date_retour is not None else None,
    }


# --- L'outil ------------------------------------------------------------------


def indicateurs_actif(ticker: str) -> dict[str, Any]:
    """Pièce « Indicateurs de <ticker> », calculée en CAD sur toute la période.

    Raises:
        ErreurDonnees: titre absent de l'univers, ou données insuffisantes.
    """
    prix = charger_donnees([ticker])[ticker]
    recuperation = calculer_temps_recuperation(prix)
    valeurs = {
        "rendement_annuel": calculer_rendement_annualise(prix),
        "volatilite_annuelle": calculer_volatilite_annuelle(prix),
        "pire_baisse": calculer_pire_baisse(prix),
        "rendement_2022": calculer_rendement_2022(prix),
        **recuperation,
        "periode": [prix.index[0].date().isoformat(), prix.index[-1].date().isoformat()],
    }
    valeurs = {cle: _brute(valeur) for cle, valeur in valeurs.items()}
    return {
        "type": "calculee",
        "etiquette": "fait",
        "titre": f"Indicateurs de {ticker}",
        "outil": "indicateurs_actif",
        "valeurs": valeurs,
        "valeur_affichee": _valeur_affichee(valeurs),
        "source": _source(ticker),
        "traitement": (
            "Prix adj_close convertis en CAD, calendrier des séances américaines (dernier prix "
            f"reporté), {valeurs['periode'][0]} → {valeurs['periode'][1]} ; rendement annualisé "
            "composé, volatilité = écart type quotidien × √252, pire baisse depuis un sommet, "
            "temps de récupération du sommet précédant la pire baisse au retour à ce sommet"
        ),
        "limites": (
            "Une seule période de 5 ans ; une seule chute observée pour le temps de récupération ; "
            "biais du survivant ; le passé ne prédit pas l'avenir"
        ),
    }


DESCRIPTION_BEDROCK = decrire_outil(
    "indicateurs_actif",
    "Indicateurs historiques d'un seul titre de l'univers, en CAD sur toute la période : "
    "rendement annualisé, volatilité annuelle, pire baisse, rendement de 2022 et temps de "
    "récupération après la pire baisse. Utile pour juger le risque propre du titre visé par "
    "la décision, par exemple face à un horizon court.",
    {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Ticker exact de l'univers, ex. « TSLA » ou « RY.TO »"},
        },
        "required": ["ticker"],
        "additionalProperties": False,
    },
)


# --- Mise en forme ------------------------------------------------------------


def _brute(valeur: Any) -> Any:
    """Arrondit les nombres à DECIMALES_VALEURS sans toucher aux dates ni aux None."""
    if isinstance(valeur, float):
        return round(valeur, DECIMALES_VALEURS)
    return valeur


def _pourcentage(part: float) -> str:
    """-0.70876 → « −70,9 % » (une décimale, signe toujours écrit, virgule française)."""
    texte = f"{part * 100:+.1f}".replace(".", ",").replace("-", "−")
    return f"{texte} %"


def _valeur_affichee(valeurs: dict[str, Any]) -> str:
    texte = f"{_pourcentage(valeurs['pire_baisse'])} max · {_pourcentage(valeurs['rendement_annuel'])}/an"
    if valeurs["date_sommet"] is None:
        return texte
    if valeurs["annees_recuperation"] is None:
        return f"{texte} · pas revenu à son sommet"
    annees = f"{valeurs['annees_recuperation']:.1f}".replace(".", ",")
    return f"{texte} · {annees} ans pour revenir au sommet"


def _source(ticker: str) -> str:
    univers = charger_univers()
    devise = univers.loc[univers["ticker"] == ticker, "currency"].iloc[0]
    source = f"Yahoo Finance via yfinance (adj_close), extrait le {date_extraction('prices_daily.csv')}"
    if devise == "USD":
        source += f" ; USD/CAD Banque du Canada, extrait le {date_extraction('fx_usdcad_daily.csv')}"
    return source
