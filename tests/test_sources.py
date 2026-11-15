"""Sources d'un procès, reliées aux pièces et aux raisons de l'orchestrateur (#111)."""

import copy
import json
from pathlib import Path

import pytest

from contrat.valider import valider_contrat
from pipeline import sources
from pipeline.orchestrateur import outils_du_profil
from pipeline.sources import SOURCES, SOURCES_PAR_OUTIL, sources_du_proces

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_PROCES = RACINE / "frontend" / "src" / "data" / "proces"
INDEX = json.loads((DOSSIER_PROCES / "index.json").read_text(encoding="utf-8"))["proces"]


def proces_de_demo(profil, calibrage=False):
    """Premier procès de démonstration enregistré pour ce profil (avec ou sans Pacte vécu)."""
    entree = next(e for e in INDEX if e["profil"] == profil and bool(e.get("calibrage")) == calibrage)
    return json.loads((DOSSIER_PROCES / f"{entree['procesId']}.json").read_text(encoding="utf-8"))


def par_nom(liste):
    return {source["nom"]: source for source in liste}


def test_robert_toutes_les_sources_utilisees():
    contrat = proces_de_demo("robert")
    liste = par_nom(sources_du_proces(contrat))
    assert set(liste) == {SOURCES[cle].nom for cle in ("pacte", "prix", "change", "univers", "jurisprudence")}
    assert liste[SOURCES["pacte"].nom]["fichier"] == "personas/robert.json"
    assert liste[SOURCES["pacte"].nom]["date_extraction"] == contrat["pacte"]["date_signature"]
    assert liste[SOURCES["univers"].nom]["controles"] == ["plafond_crypto"]


def test_chaque_piece_garde_la_raison_de_l_orchestrateur():
    contrat = proces_de_demo("robert")
    raisons = {e["sortie"]: e["raison"] for e in contrat["trace"] if e["etape"] == "orchestrateur"}
    [archives] = [s for s in sources_du_proces(contrat) if s["nom"] == SOURCES["jurisprudence"].nom]
    [utilisation] = archives["pieces"]
    assert utilisation["raison"] == raisons[utilisation["id"]]
    assert archives["fichier"] == "verdicts/robert/ (S3)"


def test_le_pacte_a_une_raison_d_office():
    [pacte] = [s for s in sources_du_proces(proces_de_demo("robert")) if s["nom"] == SOURCES["pacte"].nom]
    assert pacte["pieces"] == [{"id": "P1", "raison": sources.RAISONS_D_OFFICE["charger_pacte"]}]


def test_mateo_les_documents_esg_et_leur_regle():
    liste = par_nom(sources_du_proces(proces_de_demo("mateo")))
    documents = liste[SOURCES["documents"].nom]
    assert documents["format"] == "JSON (texte)"
    assert documents["controles"] == ["controverses_esg"]
    assert documents["date_extraction"] == "2026-11-14"  # date de constitution du corpus


def test_pacte_vecu_les_reponses_de_l_investisseur():
    contrat = proces_de_demo("robert", calibrage=True)
    reponses = par_nom(sources_du_proces(contrat))[SOURCES["reponses"].nom]
    assert "fichier" not in reponses  # des réponses n'ont pas de fichier
    piece = next(p for p in contrat["pieces"] if p["outil"] == "calibrer_pacte")
    assert reponses["date_extraction"] == piece["valeurs"]["date_reponses"]
    assert reponses["pieces"][0]["id"] == piece["id"]


def test_les_donnees_macro_apparaissent_avec_la_simulation():
    contrat = copy.deepcopy(proces_de_demo("robert"))
    assert SOURCES["macro"].nom not in par_nom(sources_du_proces(contrat))  # procès enregistré avant #111
    simulation = next(p for p in contrat["pieces"] if p["outil"] == "simuler_portefeuille")
    simulation["valeurs"]["inflation_annuelle"] = 0.0354
    macro = par_nom(sources_du_proces(contrat))[SOURCES["macro"].nom]
    assert macro["fichier"] == "macro_rates.csv"
    assert [u["id"] for u in macro["pieces"]] == [simulation["id"]]


def test_ordre_fixe_et_contrat_valide():
    for profil in ("robert", "amira", "mateo"):
        contrat = copy.deepcopy(proces_de_demo(profil))
        contrat["sources"] = sources_du_proces(contrat)
        noms = [s["nom"] for s in contrat["sources"]]
        assert noms == [s.nom for s in SOURCES.values() if s.nom in noms]
        assert valider_contrat(contrat) == []


def test_le_validateur_refuse_une_piece_inexistante():
    contrat = copy.deepcopy(proces_de_demo("robert"))
    contrat["sources"] = sources_du_proces(contrat)
    contrat["sources"][0]["pieces"].append({"id": "P99"})
    assert any("pièce P99 inexistante" in erreur for erreur in valider_contrat(contrat))


def test_une_date_deja_calculee_est_conservee():
    contrat = proces_de_demo("robert")
    anciennes = sources_du_proces(contrat)
    anciennes[-1]["date_extraction"] = "2026-11-01"  # archives lues le jour du procès
    assert sources_du_proces(contrat, anciennes=anciennes)[-1]["date_extraction"] == "2026-11-01"


@pytest.mark.parametrize("profil", ["robert", "amira", "mateo"])
def test_chaque_outil_de_l_orchestrateur_a_ses_sources(profil):
    contrat = proces_de_demo(profil)
    profil_complet = json.loads((RACINE / "personas" / f"{profil}.json").read_text(encoding="utf-8"))
    for outil in outils_du_profil(profil_complet, contrat["decision"]):
        assert outil.nom in SOURCES_PAR_OUTIL, outil.nom
