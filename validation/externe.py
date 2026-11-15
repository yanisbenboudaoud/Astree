"""Validation externe : nos rendements annuels comparés à ceux publiés par les émetteurs (#168).

Toutes les pièces du Tribunal partent de ``adj_close`` (Yahoo Finance via yfinance,
``alphaforge_starter/prices_daily.csv``). Ce module confronte ces données à une source
indépendante : les rendements totaux par année civile que publient les émetteurs des FNB,
relevés dans ``donnees_externes/rendements_emetteurs.json``.

- **Notre rendement** : ``adj_close`` dans la devise de cotation (pas en CAD : l'émetteur
  publie dans la devise du fonds), de la dernière séance de l'année précédente à la
  dernière séance de l'année, sur le calendrier propre du titre (aucun report).
- **Rendement de l'émetteur** : le cours de marché s'il est publié (``adj_close`` est un
  cours), sinon la valeur liquidative, sinon le rendement du fonds publié sans base.
- **Seuil** : écrit dans le fichier des relevés **avant** le calcul. Un écart au-delà est
  expliqué (champ ``explications`` du même fichier), jamais retouché.

Usage : ``python -m validation.externe`` écrit ``docs/validation/validation_externe.md``.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline.donnees import ErreurDonnees, charger_adj_close_cotation, date_extraction
from validation.evaluation import cellule, taux

RACINE = Path(__file__).resolve().parent.parent
CHEMIN_RELEVES = RACINE / "donnees_externes" / "rendements_emetteurs.json"
CHEMIN_RAPPORT = RACINE / "docs" / "validation" / "validation_externe.md"

# Ordre de préférence des bases publiées : la première présente sert de comparaison.
BASES = {
    "cours": "cours de marché",
    "valeur_liquidative": "valeur liquidative",
    "fonds_base_non_precisee": "fonds, base non précisée",
}
ANNEE_CLE = 2022  # l'année de crise rejouée par chaque procès


@dataclass(frozen=True)
class Comparaison:
    """Un FNB, une année : notre rendement, celui de l'émetteur, et l'écart."""

    ticker: str
    annee: int
    debut: str            # dernière séance de l'année précédente (ISO)
    fin: str              # dernière séance de l'année (ISO)
    notre: float          # rendement en décimale (0.1182 = 11,82 %)
    emetteur: float       # rendement publié, même unité
    base: str             # clé de BASES
    autres_bases: dict[str, float]
    seuil_points: float

    @property
    def ecart_points(self) -> float:
        """Notre rendement moins celui de l'émetteur, en points de pourcentage."""
        return (self.notre - self.emetteur) * 100

    @property
    def dans_le_seuil(self) -> bool:
        # Arrondi à 1e-9 : un écart de 0,25 point tout juste est dans le seuil.
        return round(abs(self.ecart_points), 9) <= self.seuil_points


# --- Calcul -------------------------------------------------------------------------

def charger_releves(chemin: Path = CHEMIN_RELEVES) -> dict[str, Any]:
    return json.loads(chemin.read_text(encoding="utf-8"))


def rendement_annee_civile(serie: pd.Series, annee: int) -> tuple[float, str, str]:
    """Rendement d'une année civile : dernière séance de l'année précédente → dernière de l'année.

    Returns:
        (rendement en décimale, date de début ISO, date de fin ISO).

    Raises:
        ErreurDonnees: aucune séance l'année précédente ou l'année demandée.
    """
    avant = serie[serie.index.year == annee - 1]
    pendant = serie[serie.index.year == annee]
    if avant.empty or pendant.empty:
        raise ErreurDonnees(f"{serie.name} : pas de séance en {annee - 1} ou en {annee}")
    return (float(pendant.iloc[-1] / avant.iloc[-1] - 1),
            avant.index[-1].date().isoformat(), pendant.index[-1].date().isoformat())


def base_de_comparaison(releve: dict[str, Any]) -> tuple[str, float, dict[str, float]]:
    """La base publiée qui sert de comparaison (ordre de ``BASES``) et les autres bases publiées."""
    publiees = {base: releve[base] for base in BASES if base in releve}
    if not publiees:
        raise ValueError(f"Aucun rendement publié pour {releve.get('annee')}")
    base = next(iter(publiees))
    return base, publiees.pop(base), publiees


def comparer(releves: dict[str, Any]) -> list[Comparaison]:
    """Une comparaison par FNB et par année publiée, dans l'ordre du fichier des relevés."""
    seuil = releves["seuil_acceptation"]["ecart_max_points"]
    comparaisons = []
    for fnb in releves["fnb"]:
        serie = charger_adj_close_cotation(fnb["ticker"])
        for releve in fnb["rendements"]:
            notre, debut, fin = rendement_annee_civile(serie, releve["annee"])
            base, valeur, autres = base_de_comparaison(releve)
            comparaisons.append(Comparaison(fnb["ticker"], releve["annee"], debut, fin, notre, valeur,
                                            base, autres, seuil))
    return comparaisons


# --- Rapport ------------------------------------------------------------------------

def pourcentage(x: float, decimales: int = 2) -> str:
    """0.1182 → « +11,82 % » ; −0.0636 → « −6,36 % » (signe écrit, virgule française)."""
    texte = f"{abs(x) * 100:.{decimales}f}".replace(".", ",")
    return f"{'−' if x < 0 else '+'}{texte} %"


def points(x: float, decimales: int = 2) -> str:
    """0.034 → « +0,03 » ; écart signé en points de pourcentage."""
    texte = f"{abs(x):.{decimales}f}".replace(".", ",")
    return f"{'−' if x < 0 and texte.strip('0,') else '+'}{texte}"


def _publie(c: Comparaison) -> str:
    texte = f"{pourcentage(c.emetteur)} ({BASES[c.base]})"
    for base, valeur in c.autres_bases.items():
        texte += f" ; {pourcentage(valeur)} ({BASES[base]})"
    return texte


def _ligne(c: Comparaison) -> str:
    verdict = "oui" if c.dans_le_seuil else "**non**"
    return (f"| {c.ticker} | {c.annee} | {c.debut} → {c.fin} | {pourcentage(c.notre)} | {_publie(c)} "
            f"| {points(c.ecart_points)} | {verdict} |")


ENTETE = [
    "| FNB | Année | Séances (adj_close) | Notre rendement | Publié par l'émetteur | Écart (points) | Dans le seuil |",
    "|---|---|---|---|---|---|---|",
]


def _lignes_bases(comparaisons: list[Comparaison]) -> list[str]:
    """Quand l'émetteur publie le cours et la valeur liquidative : à laquelle adj_close ressemble-t-il ?

    Justifie, chiffres à l'appui, le choix du cours comme base de comparaison.
    """
    deux_bases = [c for c in comparaisons if c.base == "cours" and "valeur_liquidative" in c.autres_bases]
    if not deux_bases:
        return []
    au_cours = [abs(c.ecart_points) for c in deux_bases]
    a_la_vl = [abs(c.notre - c.autres_bases["valeur_liquidative"]) * 100 for c in deux_bases]
    fnb = ", ".join(dict.fromkeys(c.ticker for c in deux_bases))
    return [
        f"- **Cours ou valeur liquidative** : sur les {len(deux_bases)} rendements où l'émetteur publie les "
        f"deux ({fnb}), notre rendement s'écarte en moyenne de {points(sum(au_cours) / len(au_cours), 3).lstrip('+')} "
        f"point du cours de marché (au plus {points(max(au_cours)).lstrip('+')}) et de "
        f"{points(sum(a_la_vl) / len(a_la_vl), 3).lstrip('+')} point de la valeur liquidative (au plus "
        f"{points(max(a_la_vl)).lstrip('+')}) : `adj_close` suit le cours, d'où le cours comme base quand il "
        "est publié.",
    ]


def rapport(releves: dict[str, Any], comparaisons: list[Comparaison]) -> str:
    seuil = releves["seuil_acceptation"]
    explications = releves.get("explications", {})
    hors_seuil = [c for c in comparaisons if not c.dans_le_seuil]
    annee_cle = [c for c in comparaisons if c.annee == ANNEE_CLE]
    ecarts = [abs(c.ecart_points) for c in comparaisons]
    seuil_texte = f"{seuil['ecart_max_points']:.2f}".replace(".", ",")

    lignes = [
        "# Validation externe : nos rendements comparés à ceux publiés par les émetteurs",
        "",
        "> Généré par `python -m validation.externe` à partir de `donnees_externes/rendements_emetteurs.json` "
        f"(relevé du {releves['date_releve']}) et de `alphaforge_starter/prices_daily.csv` (extrait le "
        f"{date_extraction('prices_daily.csv')}). Ne pas modifier à la main : relancer la commande.",
        "",
        "Toutes les pièces du Tribunal partent de `adj_close` (Yahoo Finance via yfinance). Ce rapport "
        "confronte ces données à une source indépendante : les rendements totaux par année civile publiés "
        "par les émetteurs des FNB de l'univers.",
        "",
        "## Seuil d'acceptation, fixé avant le calcul",
        "",
        f"- **Écart maximal : {seuil_texte} point de pourcentage** par FNB et par année "
        f"(fixé le {seuil['fixe_le']}, commité avec les relevés avant le code de calcul : voir l'historique "
        "Git de `donnees_externes/rendements_emetteurs.json`).",
        f"- Règle : {seuil['regle']}",
        f"- Justification : {seuil['justification']}",
        "",
        "## Résultat",
        "",
        f"- **Rendements annuels dans le seuil** : {taux(len(comparaisons) - len(hors_seuil), len(comparaisons))}, "
        f"sur {len({c.ticker for c in comparaisons})} FNB.",
        f"- **{ANNEE_CLE}**, l'année de crise rejouée par chaque procès : "
        f"{taux(sum(c.dans_le_seuil for c in annee_cle), len(annee_cle))}.",
        f"- Écart absolu moyen : {points(sum(ecarts) / len(ecarts), 3).lstrip('+')} point ; écart maximal : "
        f"{points(max(ecarts)).lstrip('+')} point.",
        f"- Écarts au-delà du seuil : {len(hors_seuil)}, chacun expliqué plus bas." if hors_seuil
        else "- Écarts au-delà du seuil : aucun.",
        *_lignes_bases(comparaisons),
        "",
        f"## {ANNEE_CLE}, l'année au centre des procès",
        "",
        *ENTETE,
        *(_ligne(c) for c in annee_cle),
        "",
        "## Tous les FNB, toutes les années",
        "",
        *ENTETE,
        *(_ligne(c) for c in comparaisons),
        "",
        "Écart = notre rendement moins celui de l'émetteur, sur la base de comparaison (la première citée).",
        "",
        "## Écarts au-delà du seuil",
        "",
    ]
    if hors_seuil:
        for c in hors_seuil:
            explication = explications.get(f"{c.ticker}/{c.annee}", "**Explication manquante.**")
            lignes.append(f"- **{c.ticker} {c.annee}** ({points(c.ecart_points)} point) : {explication}")
    else:
        lignes.append("Aucun.")
    lignes += [
        "",
        "## Sources",
        "",
        "| FNB | Émetteur | Base publiée | Document | Adresse |",
        "|---|---|---|---|---|",
    ]
    for fnb in releves["fnb"]:
        documents = list(dict.fromkeys((r["document"], r["url"]) for r in fnb["rendements"]))
        for document, url in documents:
            lignes.append(f"| {fnb['ticker']} | {fnb['emetteur']} | {cellule(fnb['base_publiee'])} "
                          f"| {cellule(document)} | <{url}> |")
    lignes += ["", "Non relevés :", ""]
    lignes += [f"- **{n['ticker']}**, {n['emetteur']} : {n['motif']}" for n in releves.get("non_releves", [])]
    lignes += [
        "",
        "## Méthode",
        "",
        "- Notre rendement : `adj_close` de `prices_daily.csv`, dans la devise de cotation du FNB, de la "
        "dernière séance de l'année précédente à la dernière séance de l'année, sur les seules séances "
        "du titre (`pipeline.donnees.charger_adj_close_cotation` : ni conversion en CAD, ni report, "
        "ni alignement sur les séances américaines). Le pipeline, lui, convertit en CAD : cette "
        "validation porte sur la donnée de départ, avant conversion.",
        "- Rendement de l'émetteur : relevé tel que publié (arrondi à 1 ou 2 décimales), avec la "
        "citation de la ligne du document dans `donnees_externes/rendements_emetteurs.json`.",
        "- Intervalle de confiance du taux : Wilson à 95 % (`validation.evaluation.intervalle_wilson`).",
        "- Un écart n'est jamais retouché : il est expliqué. Le seuil ne change pas après le calcul.",
        "",
    ]
    return "\n".join(lignes)


def main(arguments: list[str]) -> int:
    if arguments:
        print("Usage : python -m validation.externe")
        return 2
    releves = charger_releves()
    comparaisons = comparer(releves)
    CHEMIN_RAPPORT.parent.mkdir(parents=True, exist_ok=True)
    CHEMIN_RAPPORT.write_text(rapport(releves, comparaisons), encoding="utf-8")
    hors_seuil = [c for c in comparaisons if not c.dans_le_seuil]
    print(f"{len(comparaisons) - len(hors_seuil)}/{len(comparaisons)} rendements annuels dans le seuil "
          f"→ {CHEMIN_RAPPORT.relative_to(RACINE)}")
    for c in hors_seuil:
        print(f"HORS SEUIL  {c.ticker} {c.annee} : notre {pourcentage(c.notre)}, émetteur "
              f"{pourcentage(c.emetteur)} ({BASES[c.base]}), écart {points(c.ecart_points)} point")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
