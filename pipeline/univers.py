"""Univers d'actifs : les seuls titres que le système connaît (assets_universe.csv)."""

from __future__ import annotations

import csv
from pathlib import Path

CHEMIN_UNIVERS = Path(__file__).resolve().parent.parent / "alphaforge_starter" / "assets_universe.csv"


def charger_univers(chemin: Path = CHEMIN_UNIVERS) -> list[dict[str, str]]:
    """Lit l'univers d'actifs : une ligne par titre (ticker, name, asset_class, sector…)."""
    with open(chemin, encoding="utf-8", newline="") as fichier:
        return list(csv.DictReader(fichier))
