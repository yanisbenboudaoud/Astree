"""Sources d'un procès : chaque source réellement utilisée, ses pièces et pourquoi (#111).

Le champ ``sources`` du contrat est construit à partir du dossier lui-même, après coup,
par Python seul : une source n'y figure que si une pièce ou un contrôle s'en sert.

Pour chaque source :
- ``nom``, ``fichier`` (facultatif : des réponses de l'investisseur n'ont pas de fichier),
  ``date_extraction``, ``format`` et ``usage`` (à quoi elle sert, phrase fixe de l'équipe) ;
- ``pieces`` : les pièces qui l'utilisent, chacune avec la **raison** de l'orchestrateur,
  reprise de la trace. Cette raison a été écrite au moment de choisir l'outil, avant le
  calcul : ce n'est pas une explication rédigée après coup. Une pièce versée d'office
  (Pacte, questionnaire, Pacte vécu) porte une raison fixe ;
- ``controles`` : les règles du Pacte contrôlées grâce à elle (plafonds, critère documentaire).

Aucun appel à Bedrock.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pipeline import calibrage, documents, frais, jurisprudence, points_de_bascule, simulation, taille_max
from pipeline.donnees import date_extraction
from pipeline.macro import FICHIER_MACRO
from pipeline.questionnaire import NOM_OUTIL_PIECE as OUTIL_QUESTIONNAIRE

OUTIL_PACTE = "charger_pacte"
FORMAT_PIECE = re.compile(r"P\d+")

# Valeurs qui signalent qu'une pièce de simulation contient les données macro.
VALEURS_MACRO = ("inflation_annuelle", "inflation_2022")
# Valeurs qui signalent qu'une pièce de simulation a consulté le relevé des frais (#114).
VALEURS_FRAIS = ("frais_annuels", "frais_annuels_actuels", "frais_inconnus")


@dataclass(frozen=True)
class _Source:
    nom: str
    format: str
    usage: str


SOURCES = {
    "pacte": _Source("Pacte de l'investisseur", "JSON (règles déclarées)",
                     "Les règles que l'investisseur s'est fixées et que le procès vérifie"),
    "reponses": _Source("Réponses de l'investisseur", "déclarations",
                        "Ce que l'investisseur a lui-même répondu : questionnaire, jours de marché revécus"),
    "prix": _Source("Yahoo Finance via yfinance (prix ajustés)", "CSV",
                    "Les prix des titres : simulations, rejeu de 2022, indicateurs"),
    "change": _Source("Banque du Canada, API Valet : change USD/CAD", "CSV",
                      "Toujours utilisée avec les prix : tous les montants sont convertis en CAD"),
    "univers": _Source("Univers d'actifs des organisateurs du datathon", "CSV",
                       "La devise et la catégorie de chaque titre : conversion en CAD, plafonds du Pacte"),
    "macro": _Source("Banque du Canada, API Valet : IPC, taux directeur, obligation à 10 ans", "CSV",
                     "Le pouvoir d'achat : inflation, rendement réel, taux sans risque, ratio de Sharpe"),
    "frais": _Source("Pages et documents des émetteurs des FNB : ratio des frais, relevé par l'équipe",
                     "JSON (relevé)",
                     "Le coût annuel des frais de gestion des FNB, déjà prélevés dans leurs cours"),
    "documents": _Source("Documents publics sur les critères ESG, choisis et lus par l'équipe", "JSON (texte)",
                         "Les critères non financiers du Pacte, comme les controverses ESG"),
    "jurisprudence": _Source("Archives des verdicts de ce profil", "JSON",
                             "Les procès passés de ce profil et les verdicts rendus"),
}

# Sources de chaque pièce, selon l'outil qui l'a produite.
SOURCES_PAR_OUTIL = {
    OUTIL_PACTE: ("pacte",),
    OUTIL_QUESTIONNAIRE: ("reponses",),
    calibrage.NOM_OUTIL: ("reponses", "prix", "change", "univers"),
    simulation.NOM_OUTIL: ("prix", "change", "univers"),
    "indicateurs_actif": ("prix", "change", "univers"),
    "calculer_correlations": ("prix", "change", "univers"),
    taille_max.NOM_OUTIL: ("prix", "change", "univers"),
    points_de_bascule.NOM_OUTIL: ("prix", "change", "univers"),
    documents.NOM_OUTIL: ("documents",),
    jurisprudence.NOM_OUTIL: ("jurisprudence",),
}

# Sources des règles du Pacte, selon leur type.
SOURCES_PAR_TYPE_DE_REGLE = {
    "plafond": ("univers",),
    "critere_documentaire": ("documents",),
}

# Raison d'une pièce que l'orchestrateur n'a pas choisie : versée d'office par le Tribunal.
RAISONS_D_OFFICE = {
    OUTIL_PACTE: "Toujours au dossier : les règles que le procès vérifie",
    OUTIL_QUESTIONNAIRE: "Versée d'office : les réponses d'où viennent les règles du Pacte",
    calibrage.NOM_OUTIL: "Versée d'office : les réponses aux jours de marché revécus fixent le seuil de pire baisse",
}


def sources_du_proces(contrat: dict[str, Any], anciennes: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Les sources réellement utilisées par le procès, dans un ordre fixe.

    Args:
        contrat: contrat du procès (``pieces``, ``trace``, ``controles``, ``pacte``, et les
            échanges de ``contre_interrogatoire`` s'il y en a).
        anciennes: sources déjà calculées pour ce contrat (contre-interrogatoire) : la date
            de consultation des archives de verdicts est conservée.
    """
    raisons = _raisons_des_pieces(contrat)
    pieces_par_source: dict[str, list[dict[str, str]]] = {cle: [] for cle in SOURCES}
    for piece in contrat["pieces"]:
        cles = list(SOURCES_PAR_OUTIL.get(piece.get("outil"), ()))
        if piece.get("outil") == simulation.NOM_OUTIL and any(v in piece["valeurs"] for v in VALEURS_MACRO):
            cles.append("macro")
        if piece.get("outil") == simulation.NOM_OUTIL and any(v in piece["valeurs"] for v in VALEURS_FRAIS):
            cles.append("frais")
        for cle in cles:
            utilisation = {"id": piece["id"]}
            if piece["id"] in raisons:
                utilisation["raison"] = raisons[piece["id"]]
            pieces_par_source[cle].append(utilisation)

    controles_par_source: dict[str, list[str]] = {cle: [] for cle in SOURCES}
    types = {regle["id"]: regle["type"] for regle in contrat.get("pacte", {}).get("regles", [])}
    for controle in contrat.get("controles", []):
        for cle in SOURCES_PAR_TYPE_DE_REGLE.get(types.get(controle["regle"]), ()):
            if controle["regle"] not in controles_par_source[cle]:
                controles_par_source[cle].append(controle["regle"])

    dates_conservees = {source["nom"]: source["date_extraction"] for source in anciennes or []}
    resultat = []
    for cle, source in SOURCES.items():
        pieces, controles = pieces_par_source[cle], controles_par_source[cle]
        if not pieces and not controles:
            continue
        entree = {"nom": source.nom}
        fichier = _fichier(cle, contrat)
        if fichier:
            entree["fichier"] = fichier
        entree["date_extraction"] = dates_conservees.get(source.nom) or _date(cle, contrat)
        entree["format"] = source.format
        entree["usage"] = source.usage
        if pieces:
            entree["pieces"] = pieces
        if controles:
            entree["controles"] = controles
        resultat.append(entree)
    return resultat


def _raisons_des_pieces(contrat: dict[str, Any]) -> dict[str, str]:
    """Raison donnée pour chaque pièce : celle de l'orchestrateur (procès et questions), ou d'office."""
    raisons = {piece["id"]: RAISONS_D_OFFICE[piece["outil"]]
               for piece in contrat["pieces"] if piece.get("outil") in RAISONS_D_OFFICE}
    traces = [contrat.get("trace", [])] + [echange.get("trace", []) for echange in contrat.get("contre_interrogatoire", [])]
    for trace in traces:
        for etape in trace:
            sortie, raison = etape.get("sortie"), etape.get("raison")
            if etape.get("etape") == "orchestrateur" and isinstance(sortie, str) and FORMAT_PIECE.fullmatch(sortie) and raison:
                raisons.setdefault(sortie, raison)
    return raisons


def _fichier(cle: str, contrat: dict[str, Any]) -> str | None:
    persona = contrat.get("persona", "")
    cree = any(piece.get("outil") == OUTIL_QUESTIONNAIRE for piece in contrat["pieces"])
    return {
        "pacte": f"profils/{persona}.json (S3)" if cree else f"personas/{persona}.json",
        "prix": "prices_daily.csv",
        "change": "fx_usdcad_daily.csv",
        "univers": "assets_universe.csv",
        "macro": FICHIER_MACRO,
        "frais": frais.FICHIER_FRAIS,
        "documents": "donnees_externes/documents_esg.json",
        "jurisprudence": f"verdicts/{persona}/ (S3)",
    }.get(cle)


def _date(cle: str, contrat: dict[str, Any]) -> str:
    if cle == "pacte":
        return contrat["pacte"]["date_signature"]
    if cle == "reponses":
        return max(piece["valeurs"]["date_reponses"] for piece in contrat["pieces"]
                   if piece.get("outil") in (OUTIL_QUESTIONNAIRE, calibrage.NOM_OUTIL))
    if cle == "documents":
        return documents.charger_corpus()["date_constitution"]
    if cle == "frais":
        return frais.charger_frais()["date_releve"]
    if cle == "jurisprudence":  # les archives sont lues le jour du procès
        return datetime.now(timezone.utc).date().isoformat()
    return date_extraction({"prix": "prices_daily.csv", "change": "fx_usdcad_daily.csv",
                            "univers": "assets_universe.csv", "macro": FICHIER_MACRO}[cle])
