"""Univers d'actifs, sous forme de liste de dictionnaires (pour les prompts et les listes de valeurs).

Simple vue de ``pipeline.donnees.charger_univers`` : la lecture passe donc par
``lire_csv`` et respecte ``SOURCE_DONNEES`` (fichier local, ou bucket S3 dans
Lambda, #13). Lire le CSV directement sur le disque ferait échouer la Lambda,
dont le zip ne contient pas les données.
"""

from __future__ import annotations

from pipeline import donnees


def charger_univers() -> list[dict[str, str]]:
    """Une ligne par titre (ticker, name, asset_class, market, currency, sector…), en texte."""
    return donnees.charger_univers().astype(str).to_dict("records")
