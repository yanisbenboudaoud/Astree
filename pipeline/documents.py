"""Recherche documentaire : pièces « documentaire » sur des critères extra-financiers (#17).

Cas général 3 (préférences non financières). Le jeu de départ ne contient
aucune donnée ESG : la seule source est le corpus ``donnees_externes/
documents_esg.json``, constitué par l'équipe à partir de documents publics lus
dans leur version originale (source, date, traitement, limites).

``rechercher_documents(ticker, critere)`` rassemble les documents du corpus sur
ce titre et ce critère en une pièce au format du contrat, de type
``documentaire``. Pour un critère de Pacte (règle ``critere_documentaire``),
la pièce porte la valeur du critère (ex. : ``controverse_esg_importante:
true``), que le Greffier lit. **Rien n'est deviné** : sans document, l'outil
lève ``ErreurDonnees`` (« source manquante ») et la règle reste ``a_verifier``.

Le corpus est un fichier local plutôt qu'une base de connaissances Bedrock :
même code en local et dans Lambda, sources entièrement maîtrisées, aucun
service de plus à configurer (voir la fiche 017 du journal).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pipeline.donnees import ErreurDonnees
from pipeline.llm import decrire_outil

CHEMIN_CORPUS = Path(__file__).resolve().parent.parent / "donnees_externes" / "documents_esg.json"
NOM_OUTIL = "rechercher_documents"
CHAMPS_DOCUMENT = ("id", "ticker", "critere", "valeur", "titre", "valeur_affichee", "resume",
                   "extraits", "valeurs", "source", "date_consultation", "traitement", "limites")


@lru_cache(maxsize=4)
def charger_corpus(chemin: Path = CHEMIN_CORPUS) -> dict[str, Any]:
    """Lit le corpus et vérifie que chaque document est complet (source, date, limites…)."""
    corpus = json.loads(Path(chemin).read_text(encoding="utf-8"))
    for document in corpus["documents"]:
        manquants = [champ for champ in CHAMPS_DOCUMENT if champ not in document]
        if manquants:
            raise ErreurDonnees(f"Document « {document.get('id')} » incomplet : {', '.join(manquants)}")
    return corpus


def criteres_disponibles(chemin: Path = CHEMIN_CORPUS) -> list[str]:
    return sorted({document["critere"] for document in charger_corpus(chemin)["documents"]})


def rechercher_documents(ticker: str, critere: str, chemin: Path = CHEMIN_CORPUS) -> dict[str, Any]:
    """Pièce « documentaire » (sans id) sur un titre et un critère.

    Raises:
        ErreurDonnees: aucun document sur ce titre pour ce critère (source manquante).
    """
    documents = [d for d in charger_corpus(chemin)["documents"]
                 if d["ticker"] == ticker and d["critere"] == critere]
    if not documents:
        raise ErreurDonnees(
            f"Aucun document sur {ticker} pour le critère « {critere} » : source manquante, "
            "le critère reste à vérifier"
        )

    valeurs: dict[str, Any] = {"ticker": ticker}
    verdicts = {d["valeur"] for d in documents if isinstance(d["valeur"], bool)}
    if len(verdicts) == 1:
        valeurs[critere] = verdicts.pop()
    elif verdicts:  # documents contradictoires : on ne tranche pas
        valeurs[critere] = None
    for document in documents:
        valeurs.update(document["valeurs"])
    valeurs["resume"] = [d["resume"] for d in documents]
    valeurs["extraits"] = [extrait for d in documents for extrait in d["extraits"]]
    valeurs["documents"] = [d["id"] for d in documents]

    return {
        "type": "documentaire",
        "etiquette": "fait",
        "titre": " ; ".join(d["titre"] for d in documents),
        "outil": NOM_OUTIL,
        "valeurs": valeurs,
        "valeur_affichee": " · ".join(d["valeur_affichee"] for d in documents),
        "source": " ; ".join(f"{d['source']} (consulté le {d['date_consultation']})" for d in documents),
        "traitement": " ".join(d["traitement"] for d in documents),
        "limites": " ".join(d["limites"] for d in documents)
        + (" Documents contradictoires : le critère n'est pas tranché." if valeurs.get(critere, 0) is None else ""),
    }


def decrire_rechercher_documents(tickers_univers: list[str]) -> dict[str, Any]:
    """Description de l'outil pour l'orchestrateur Bedrock."""
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["ticker", "critere"],
        "properties": {
            "ticker": {"type": "string", "enum": sorted(tickers_univers), "description": "Titre concerné"},
            "critere": {
                "type": "string",
                "enum": criteres_disponibles(),
                "description": "« controverse_esg_importante » : controverses environnementales ou "
                "sociales documentées ; « methodologie_fonds_esg » : règles d'exclusion d'un fonds ESG",
            },
        },
    }
    return decrire_outil(
        NOM_OUTIL,
        "Cherche, dans un corpus de documents publics sourcés et datés constitué par l'équipe, "
        "les pièces documentaires sur un titre et un critère extra-financier : controverses ESG "
        "d'une entreprise, ou règles d'exclusion d'un fonds ESG. Utile quand le Pacte contient un "
        "critère non financier (règle « critere_documentaire »). S'il n'existe aucun document, "
        "l'outil le dit : le critère reste à vérifier, rien n'est deviné.",
        schema,
    )
