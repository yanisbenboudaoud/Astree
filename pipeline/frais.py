"""Frais de gestion des FNB : coût annuel du portefeuille, avant et après la décision (#114).

Source : ``donnees_externes/frais_fnb.json``, relevé par l'équipe sur la page ou le
document officiel de chaque émetteur (source, date, conditions d'utilisation dans le
fichier). Le fichier est livré avec le code, dans le zip de la Lambda.

**Les frais sont déjà dans les cours.** Un FNB prélève ses frais sur son actif, chaque
jour : sa valeur liquidative, donc son cours et ``adj_close``, est déjà nette de frais.
Les rendements des simulations le sont donc aussi. Ce module ne retranche rien : il
calcule seulement ce que les frais coûtent chaque année, pour que l'investisseur le voie.

Méthode :
- **ratio d'un titre** : celui du relevé pour un FNB ; 0 pour un titre détenu en direct
  (classe d'actifs listée dans ``sans_frais_de_gestion``, ex. : action, cryptoactif) ;
  **inconnu** sinon. Un ratio inconnu n'est jamais deviné ;
- **coût annuel du portefeuille** : moyenne des ratios pondérée par les poids. Si un
  seul titre est inconnu, le coût n'est pas calculé et le titre est signalé.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pipeline.donnees import ErreurDonnees, charger_univers
from pipeline.indicateurs import DECIMALES_VALEURS

CHEMIN_FRAIS = Path(__file__).resolve().parent.parent / "donnees_externes" / "frais_fnb.json"
FICHIER_FRAIS = "donnees_externes/frais_fnb.json"
RATIO_MAXIMAL = 0.05  # au-delà, une erreur de saisie (5 % par an) : le relevé est refusé

HYPOTHESE_FRAIS = (
    "Frais de gestion des FNB : déjà prélevés dans les cours (adj_close), affichés sans être déduits une seconde fois"
)
# Sans chiffre : les agents ne reprennent aucun nombre des limites (CLAUDE.md, section 4 ter).
LIMITES_FRAIS = (
    "frais actuels des FNB, qui ont pu changer pendant la période ; commissions de courtage "
    "et écart entre prix d'achat et de vente non comptés"
)


@dataclass(frozen=True)
class CoutFrais:
    """Coût annuel des frais d'un portefeuille : ``ratio`` vaut None si un titre est inconnu."""

    ratio: float | None
    inconnus: tuple[str, ...]


@lru_cache(maxsize=4)
def charger_frais(chemin: Path = CHEMIN_FRAIS) -> dict[str, Any]:
    """Relevé des frais, vérifié : un ratio par FNB, entre 0 et ``RATIO_MAXIMAL``, avec sa source.

    Raises:
        ErreurDonnees: fichier absent ou relevé invalide.
    """
    try:
        releve = json.loads(Path(chemin).read_text(encoding="utf-8"))
    except FileNotFoundError as erreur:
        raise ErreurDonnees(f"Relevé des frais absent : {FICHIER_FRAIS}") from erreur
    vus = set()
    for fnb in releve["fnb"]:
        ticker = fnb["ticker"]
        if ticker in vus:
            raise ErreurDonnees(f"{FICHIER_FRAIS} : {ticker} apparaît deux fois")
        vus.add(ticker)
        if not 0 <= fnb["ratio_frais"] <= RATIO_MAXIMAL:
            raise ErreurDonnees(f"{FICHIER_FRAIS} : ratio de {ticker} impossible ({fnb['ratio_frais']})")
        if not fnb.get("url") or not fnb.get("date_donnee"):
            raise ErreurDonnees(f"{FICHIER_FRAIS} : source ou date manquante pour {ticker}")
    return releve


def ratio_frais(ticker: str) -> float | None:
    """Ratio des frais annuels d'un titre (0.0017 = 0,17 % par an), ou None s'il est inconnu."""
    releve = charger_frais()
    for fnb in releve["fnb"]:
        if fnb["ticker"] == ticker:
            return float(fnb["ratio_frais"])
    univers = charger_univers()
    classe = univers.loc[univers["ticker"] == ticker, "asset_class"]
    if not classe.empty and classe.iloc[0] in releve["sans_frais_de_gestion"]["classes"]:
        return 0.0
    return None


def cout_frais(poids: dict[str, float]) -> CoutFrais:
    """Coût annuel des frais d'un portefeuille : moyenne des ratios pondérée par les poids."""
    ratios = {ticker: ratio_frais(ticker) for ticker in poids}
    inconnus = tuple(sorted(ticker for ticker, ratio in ratios.items() if ratio is None))
    if inconnus:
        return CoutFrais(None, inconnus)
    return CoutFrais(sum(part * ratios[ticker] for ticker, part in poids.items()), ())


def contexte_frais(
    poids_actuels: dict[str, float],
    poids_apres: dict[str, float],
    capital: float | None = None,
) -> tuple[dict[str, Any], str]:
    """Valeurs à ajouter à la pièce de simulation, et la phrase de méthode du traitement.

    Valeurs : ``frais_annuels`` (après la décision) et ``frais_annuels_actuels``, en
    décimales ; avec le capital, les mêmes en dollars, arrondis au dollar
    (``frais_annuels_cad``, ``frais_annuels_cad_actuels``) et leur écart, positif. Un côté
    dont un titre est inconnu n'a pas de valeur ; ``frais_inconnus`` liste ces titres.
    """
    apres, actuel = cout_frais(poids_apres), cout_frais(poids_actuels)
    valeurs: dict[str, Any] = {}
    for suffixe, cout in (("", apres), ("_actuels", actuel)):
        if cout.ratio is not None:
            valeurs[f"frais_annuels{suffixe}"] = round(cout.ratio, DECIMALES_VALEURS)
            if capital:
                valeurs[f"frais_annuels_cad{suffixe}"] = round(capital * valeurs[f"frais_annuels{suffixe}"])
    if capital and apres.ratio is not None and actuel.ratio is not None:
        valeurs["ecart_frais_annuels_cad"] = abs(valeurs["frais_annuels_cad"] - valeurs["frais_annuels_cad_actuels"])
    inconnus = sorted(set(apres.inconnus) | set(actuel.inconnus))
    if inconnus:
        valeurs["frais_inconnus"] = inconnus
    traitement = (
        "frais : ratio des frais de chaque FNB (page ou document de l'émetteur), pondéré par les poids ; "
        "zéro pour un titre détenu en direct ; déjà prélevés dans les cours, donc affichés sans être déduits"
    )
    if inconnus:
        traitement += f" ; frais inconnus pour {', '.join(inconnus)} : coût non calculé"
    return valeurs, traitement


def source_frais() -> str:
    """Libellé de la source, avec la date du relevé."""
    return f"Pages et documents des émetteurs des FNB (ratio des frais), relevés le {charger_frais()['date_releve']}"
