"""Tests de la recherche documentaire (pipeline/documents.py, #17)."""

import json
from pathlib import Path

import jsonschema
import pytest

from pipeline import documents
from pipeline.agent_profil import chemin_profil
from pipeline.donnees import ErreurDonnees
from pipeline.documents import charger_corpus, criteres_disponibles, rechercher_documents
from pipeline.greffier import verifier_pacte
from pipeline.orchestrateur import outils_du_profil
from pipeline.pacte import charger_pacte
from pipeline.simulation import poids_apres_decision

RACINE = Path(__file__).resolve().parent.parent
SCHEMA_CONTRAT = json.loads((RACINE / "contrat" / "schema_sortie.json").read_text(encoding="utf-8"))
ESG = charger_pacte(chemin_profil("mateo"))


# --- Le corpus ---------------------------------------------------------------------


def test_chaque_document_est_source_date_et_borne():
    for document in charger_corpus()["documents"]:
        assert document["source"].startswith(("Sabin", "Vanguard", "FTSE")) and "https://" in document["source"]
        assert document["date_consultation"] == "2026-11-14"
        assert document["limites"] and document["traitement"] and document["extraits"]


def test_criteres_du_corpus():
    assert criteres_disponibles() == ["controverse_esg_importante", "methodologie_fonds_esg"]


def test_corpus_incomplet_refuse(tmp_path):
    chemin = tmp_path / "corpus.json"
    chemin.write_text(json.dumps({"documents": [{"id": "sans_source", "ticker": "XOM"}]}), encoding="utf-8")
    with pytest.raises(ErreurDonnees, match="incomplet"):
        charger_corpus(chemin)


# --- La pièce ----------------------------------------------------------------------


def test_controverse_de_xom():
    piece = rechercher_documents("XOM", "controverse_esg_importante")
    assert piece["type"] == "documentaire"
    assert piece["etiquette"] == "fait"
    assert piece["valeurs"]["ticker"] == "XOM"
    assert piece["valeurs"]["controverse_esg_importante"] is True
    assert piece["valeurs"]["date_decision_cour_supreme"] == "2022-05-24"
    assert "climatecasechart.com" in piece["source"] and "consulté le 2026-11-14" in piece["source"]
    assert "hypothèse de l'équipe" in piece["traitement"]


def test_methodologie_d_esgv_reunit_les_deux_documents():
    piece = rechercher_documents("ESGV", "methodologie_fonds_esg")
    assert piece["valeurs"]["documents"] == ["esgv_prospectus_exclusions", "ftse_choice_regles_exclusions"]
    assert piece["valeurs"]["seuil_revenus_petrole_gaz"] == 0.05
    assert "methodologie_fonds_esg" not in piece["valeurs"]  # aucun verdict : ce sont des règles
    assert "sec.gov" in piece["source"] and "lseg.com" in piece["source"]


@pytest.mark.parametrize("ticker, critere", [("JNJ", "controverse_esg_importante"),
                                             ("XOM", "methodologie_fonds_esg")])
def test_sans_document_source_manquante(ticker, critere):
    with pytest.raises(ErreurDonnees, match="source manquante"):
        rechercher_documents(ticker, critere)


def test_documents_contradictoires_non_tranches(tmp_path):
    corpus = charger_corpus()
    oui = next(d for d in corpus["documents"] if d["ticker"] == "XOM")
    non = {**oui, "id": "autre", "valeur": False}
    chemin = tmp_path / "corpus.json"
    chemin.write_text(json.dumps({"documents": [oui, non]}), encoding="utf-8")
    piece = rechercher_documents("XOM", "controverse_esg_importante", chemin)
    assert piece["valeurs"]["controverse_esg_importante"] is None
    assert "contradictoires" in piece["limites"]


def test_piece_conforme_au_contrat():
    schema = {"$ref": "#/$defs/piece", "$defs": SCHEMA_CONTRAT["$defs"]}
    for ticker, critere in (("XOM", "controverse_esg_importante"), ("ESGV", "methodologie_fonds_esg")):
        jsonschema.validate({"id": "P6", **rechercher_documents(ticker, critere)}, schema,
                            cls=jsonschema.Draft202012Validator)


# --- Avec le Greffier et l'orchestrateur ---------------------------------------------


def test_le_greffier_juge_la_regle_esg_avec_la_piece():
    decision = ESG["decision_demo"]  # 10 % en XOM
    piece = {"id": "P6", **rechercher_documents("XOM", "controverse_esg_importante")}
    controles = verifier_pacte(ESG["pacte"]["regles"], poids_apres_decision(ESG["portefeuille"], decision),
                               None, "P1", [piece])
    esg = next(c for c in controles if c["regle"] == "controverses_esg")
    assert esg["statut"] == "violation"
    assert esg["pieces"] == ["P6", "P1"]


def test_outil_dans_la_liste_blanche():
    outils = {outil.nom: outil for outil in outils_du_profil(ESG)}
    outil = outils[documents.NOM_OUTIL]
    assert outil.description_bedrock["toolSpec"]["inputSchema"]["json"]["required"] == ["ticker", "critere"]
    piece = outil.executer({"ticker": "XOM", "critere": "controverse_esg_importante"}, "P5")
    assert piece["id"] == "P5"
