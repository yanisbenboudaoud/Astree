"""Outil 9 : mesurer_liquidite — combien de jours de bourse pour revendre une ligne (#117).

Risque de liquidité (atelier de la Banque Nationale) : ne pas trouver d'acheteur le jour
où l'on veut vendre, parce que le titre s'échange peu par rapport à la position. La
colonne ``volume`` de ``prices_daily.csv`` le mesure.

Deux niveaux, comme les autres outils :

1. ``valeur_echangee_moyenne`` et ``jours_pour_vendre`` : fonctions de calcul **pures**.
2. ``piece_liquidite`` : la pièce au format du contrat (section 5) ; l'orchestrateur la
   numérote.

Méthode (hypothèses de l'équipe, reprises dans le traitement de la pièce) :

- **Valeur échangée d'une séance** = volume × prix de clôture (``close`` : le prix
  réellement payé ce jour-là, pas ``adj_close``, qui baisse les prix passés du montant des
  dividendes), dans la devise de cotation, convertie en CAD au taux du jour (dernier taux
  connu reporté). **Crypto** : Yahoo donne le volume directement en dollars US échangés,
  pas en unités ; la valeur échangée est alors le volume lui-même (``CLASSES_VOLUME_EN_DEVISE``).
- **Moyenne** sur les séances du titre lui-même, sans report : un jour férié n'est pas un
  jour sans échange. Un volume nul publié (ZST.TO, 2022-07-06) compte comme zéro ; un
  volume **absent** n'est jamais remplacé par zéro : le titre est signalé dans
  ``titres_sans_volume``, sans valeurs.
- **Position** = poids de la ligne une fois la décision appliquée × capital fictif.
- **Jours pour vendre** = position ÷ (``PART_MAX_VOLUME`` × valeur échangée moyenne) :
  on suppose qu'un vendeur prudent ne pèse pas plus de 10 % des échanges d'une séance,
  pour ne pas faire baisser le prix (hypothèse de l'équipe, pas une règle officielle).

Le code ne connaît aucun persona : il lit le portefeuille, la décision et le capital reçus.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from pipeline.donnees import ErreurDonnees, charger_univers, charger_volumes, date_extraction, taux_usdcad_aux_dates
from pipeline.llm import decrire_outil
from pipeline.simulation import TOLERANCE_POIDS, poids_apres_decision

NOM_OUTIL = "mesurer_liquidite"

# Hypothèse de l'équipe : un vendeur prudent ne pèse pas plus de cette part des échanges d'une séance.
PART_MAX_VOLUME = 0.10

# Classes d'actifs dont Yahoo publie le volume en devise échangée (dollars US), pas en unités.
CLASSES_VOLUME_EN_DEVISE = {"crypto"}

# Au-delà, la pièce deviendrait illisible ; sans titre demandé, les plus grosses lignes sont gardées.
MAX_TITRES = 12

DECIMALES_VALEURS = 6  # valeurs brutes (REFERENCE_DU_PROJET.md, section 5)
DECIMALES_MONTANTS = 2
# Parts et jours souvent minuscules (0,000006) : chiffres significatifs plutôt que décimales,
# pour ne jamais écrire 0 à la place d'une petite valeur.
CHIFFRES_SIGNIFICATIFS = 6

LIMITES = (
    "Moyenne sur toute la période : un jour de crise, les échanges peuvent se tarir au moment "
    "où l'on veut vendre ; la part maximale des échanges est une hypothèse de l'équipe ; les "
    "volumes crypto sont agrégés par Yahoo sur plusieurs plateformes et peuvent être gonflés ; "
    "un FNB s'échange aussi par création et rachat de parts auprès de ses créateurs de marché, "
    "si bien que son volume en bourse ne mesure pas toute sa liquidité ; seul le volume de la "
    "bourse de cotation est compté ; ni frais ni écart entre prix acheteur et vendeur"
)


# --- Fonctions de calcul pures --------------------------------------------------


def valeur_echangee_moyenne(
    volumes: pd.Series,
    prix_cloture: pd.Series,
    taux_cad: pd.Series | float = 1.0,
    volume_en_devise: bool = False,
) -> float | None:
    """Montant moyen échangé par séance, en CAD ; None si le titre n'a aucun volume utilisable.

    Args:
        volumes: volume de chaque séance (NaN si Yahoo ne le donne pas).
        prix_cloture: prix de clôture de chaque séance, dans la devise de cotation.
        taux_cad: taux de conversion vers le CAD de chaque séance (1 pour un titre en CAD).
        volume_en_devise: vrai si le volume est déjà un montant (crypto), pas un nombre d'unités.

    Returns:
        La moyenne des montants des séances où le volume est connu. None, jamais 0, si aucun
        volume n'est connu ou si rien ne s'est échangé : le temps pour vendre serait infini.
    """
    taux = taux_cad if isinstance(taux_cad, pd.Series) else pd.Series(taux_cad, index=volumes.index)
    connues = volumes.notna() & (volume_en_devise or prix_cloture.notna()) & taux.notna()
    if not connues.any():
        return None
    montants = volumes[connues] if volume_en_devise else volumes[connues] * prix_cloture[connues]
    moyenne = float((montants * taux[connues]).mean())
    return moyenne if moyenne > 0 else None


def jours_pour_vendre(valeur_position: float, valeur_echangee: float, part_max: float = PART_MAX_VOLUME) -> float:
    """Jours de bourse pour vendre une position sans dépasser ``part_max`` des échanges d'une séance."""
    if valeur_echangee <= 0 or part_max <= 0:
        raise ValueError("La valeur échangée et la part maximale doivent être positives")
    return valeur_position / (part_max * valeur_echangee)


# --- L'outil ----------------------------------------------------------------------


def piece_liquidite(
    id_piece: str,
    portefeuille: list[dict[str, Any]],
    decision: dict[str, Any] | None,
    capital: float | None,
    titres: list[str] | None = None,
) -> dict[str, Any]:
    """Pièce « Liquidité » : jours pour revendre chaque ligne du portefeuille après la décision.

    Args:
        id_piece: identifiant de la pièce (``P4``…), donné par l'orchestrateur.
        portefeuille: lignes ``{"ticker", "poids"}`` du profil.
        decision: décision du contrat (position ou réallocation) ; None : portefeuille actuel.
        capital: capital fictif du profil, en CAD.
        titres: lignes à examiner ; None ou vide : toutes les lignes après la décision
            (les ``MAX_TITRES`` plus grosses).

    Raises:
        ErreurDonnees: capital inconnu, titre absent du portefeuille après la décision, trop de
            titres, ou aucun titre avec un volume utilisable.
    """
    if not capital or capital <= 0:
        raise ErreurDonnees("Capital fictif inconnu : la taille des positions en dollars ne peut pas être calculée")
    poids = _poids_detenus(portefeuille, decision)
    titres = _titres_examines(titres, poids)

    univers = charger_univers().set_index("ticker")
    lignes = charger_volumes(titres)
    valeurs: dict[str, Any] = {"capital": capital, "part_max_volume": PART_MAX_VOLUME, "titres": titres}
    sans_volume, jours, debuts, fins = [], {}, [], []
    for ticker in titres:
        seances = lignes[lignes["ticker"] == ticker].set_index("date")
        devise, classe = univers.loc[ticker, "currency"], univers.loc[ticker, "asset_class"]
        taux = 1.0 if devise == "CAD" else taux_usdcad_aux_dates(seances.index)
        moyenne = valeur_echangee_moyenne(seances["volume"], seances["close"], taux,
                                          volume_en_devise=classe in CLASSES_VOLUME_EN_DEVISE)
        if moyenne is None:
            sans_volume.append(ticker)
            continue
        position = poids[ticker] * capital
        jours[ticker] = jours_pour_vendre(position, moyenne)
        valeurs.update({
            f"poids_{ticker}": round(poids[ticker], DECIMALES_VALEURS),
            f"valeur_position_cad_{ticker}": round(position, DECIMALES_MONTANTS),
            f"valeur_echangee_moyenne_cad_{ticker}": round(moyenne, DECIMALES_MONTANTS),
            # Le même montant en millions, pour qu'un agent écrive « 1,6 million $ » sans calculer.
            f"valeur_echangee_moyenne_millions_cad_{ticker}": round(moyenne / 1e6, DECIMALES_VALEURS),
            f"part_volume_quotidien_{ticker}": _significatif(position / moyenne),
            f"jours_pour_vendre_{ticker}": _significatif(jours[ticker]),
        })
        debuts.append(seances.index[0])
        fins.append(seances.index[-1])
    if not jours:
        raise ErreurDonnees(f"Aucun volume utilisable pour : {', '.join(titres)}")

    plus_long = max(jours, key=jours.get)
    valeurs["jours_pour_vendre_max"] = _significatif(jours[plus_long])
    valeurs["titre_le_moins_liquide"] = plus_long
    if sans_volume:
        valeurs["titres_sans_volume"] = sans_volume
    valeurs["periode"] = [min(debuts).date().isoformat(), max(fins).date().isoformat()]

    return {
        "id": id_piece,
        "type": "calculee",
        "etiquette": "fictif",
        "titre": _titre(titres),
        "outil": NOM_OUTIL,
        "valeurs": valeurs,
        "valeur_affichee": _valeur_affichee(plus_long, jours[plus_long], sans_volume),
        "source": _source(titres, univers),
        "traitement": (
            "Valeur échangée par séance = volume × prix de clôture (close) dans la devise de cotation, "
            "convertie en CAD au taux du jour (dernier taux reporté) ; crypto : volume déjà exprimé en "
            f"dollars US échangés ; moyenne sur les séances de chaque titre, {valeurs['periode'][0]} → "
            f"{valeurs['periode'][1]}, sans report ni jour férié compté comme nul ; position = poids après "
            "la décision × capital fictif ; jours pour vendre = position ÷ (part maximale × valeur "
            "échangée moyenne)"
        ),
        "limites": LIMITES,
    }


def decrire_mesurer_liquidite(titres_detenus: list[str]) -> dict[str, Any]:
    """Description pour Bedrock, propre au portefeuille après la décision (titres permis)."""
    return decrire_outil(
        NOM_OUTIL,
        "Risque de liquidité : combien de jours de bourse il faudrait pour revendre chaque ligne du "
        "portefeuille une fois la décision appliquée, sans peser plus qu'une part prudente des montants "
        "échangés chaque jour (volumes Yahoo Finance, convertis en CAD, moyenne sur la période). Utile "
        "pour un titre peu échangé, une grosse position par rapport à ce qui s'échange, ou un horizon "
        "court où il faudrait pouvoir vendre vite.",
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["titres"],
            "properties": {
                "titres": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(titres_detenus)},
                    "description": "Lignes à examiner ; liste vide : toutes les lignes après la décision",
                },
            },
        },
    )


def titres_apres_decision(portefeuille: list[dict[str, Any]], decision: dict[str, Any] | None) -> list[str]:
    """Titres détenus une fois la décision appliquée (ceux que l'outil accepte)."""
    return sorted(_poids_detenus(portefeuille, decision))


# --- Détails ------------------------------------------------------------------------


def _poids_detenus(portefeuille: list[dict[str, Any]], decision: dict[str, Any] | None) -> dict[str, float]:
    if decision is None:
        poids = {ligne["ticker"]: ligne["poids"] for ligne in portefeuille}
    else:
        poids = poids_apres_decision(portefeuille, decision)
    return {ticker: p for ticker, p in poids.items() if p > TOLERANCE_POIDS}


def _titres_examines(titres: list[str] | None, poids: dict[str, float]) -> list[str]:
    if not titres:
        return sorted(poids, key=lambda t: -poids[t])[:MAX_TITRES]
    titres = list(dict.fromkeys(titres))
    absents = [t for t in titres if t not in poids]
    if absents:
        raise ErreurDonnees(f"Absent(s) du portefeuille après la décision : {', '.join(absents)} "
                            f"(lignes détenues : {', '.join(sorted(poids))})")
    if len(titres) > MAX_TITRES:
        raise ErreurDonnees(f"Au plus {MAX_TITRES} titres à la fois ({len(titres)} demandés)")
    return titres


def _significatif(valeur: float) -> float:
    """0.0000062317 → 6.2317e-06 : une petite valeur garde ses chiffres au lieu de devenir 0."""
    return float(f"{valeur:.{CHIFFRES_SIGNIFICATIFS}g}")


def _titre(titres: list[str]) -> str:
    if len(titres) == 1:
        return f"Liquidité de la ligne {titres[0]} : jours pour la revendre"
    return f"Liquidité de {len(titres)} lignes du portefeuille : jours pour les revendre"


def _jours(jours: float) -> str:
    """0.83 → « 0,8 jour » ; 3.25 → « 3,2 jours » ; 0.0004 → « moins de 0,1 jour »."""
    if jours < 0.05:
        return "moins de 0,1 jour"
    return f"{jours:.1f}".replace(".", ",") + (" jours" if round(jours, 1) >= 2 else " jour")


def _valeur_affichee(plus_long: str, jours: float, sans_volume: list[str]) -> str:
    part = f"{PART_MAX_VOLUME * 100:.0f} %"
    texte = f"Le plus long : {plus_long}, {_jours(jours)} de bourse · au plus {part} des échanges par jour"
    if sans_volume:
        texte += f" · volume absent : {', '.join(sans_volume)}"
    return texte


def _source(titres: list[str], univers: pd.DataFrame) -> str:
    source = f"Yahoo Finance via yfinance (volume et close), extrait le {date_extraction('prices_daily.csv')}"
    if (univers.loc[titres, "currency"] == "USD").any():
        source += f" ; USD/CAD Banque du Canada, extrait le {date_extraction('fx_usdcad_daily.csv')}"
    return source
