"""Tests du procès-verbal (pipeline/proces_verbal.py, #57)."""

import copy
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from contrat.valider import valider_contrat
from pipeline import proces_verbal
from pipeline.proces_verbal import DOSSIER_PV_DEMO, LIBELLES, proces_verbal_html, proces_demo

RACINE = Path(__file__).resolve().parent.parent
EXEMPLES = sorted((RACINE / "docs" / "exemples").glob("contrat_*.json")) + sorted(
    p for p in (RACINE / "frontend" / "src" / "data" / "proces").glob("*.json") if p.name != "index.json"
)


def lire(chemin):
    return json.loads(chemin.read_text(encoding="utf-8"))


class Textes(HTMLParser):
    """Texte visible d'une page (hors <style>)."""

    def __init__(self):
        super().__init__()
        self.morceaux, self._style = [], False

    def handle_starttag(self, tag, attrs):
        self._style = tag == "style"

    def handle_endtag(self, tag):
        self._style = False

    def handle_data(self, data):
        if not self._style:
            self.morceaux.append(data)


def texte_visible(page):
    lecteur = Textes()
    lecteur.feed(page)
    return re.sub(r"\s+", " ", " ".join(lecteur.morceaux))


@pytest.fixture(params=EXEMPLES, ids=lambda p: p.name)
def contrat(request):
    return lire(request.param)


def test_les_contrats_testes_sont_valides(contrat):
    assert valider_contrat(contrat) == []


def test_tout_le_dossier_est_dans_le_proces_verbal(contrat):
    texte = texte_visible(proces_verbal_html(contrat))
    attendus = [contrat["demande"], contrat["pacte"]["date_signature"], contrat["avertissement"]]
    attendus += [regle["libelle"] for regle in contrat["pacte"]["regles"]]
    attendus += [c["message"] for c in contrat["controles"]]
    attendus += [a["texte"] for cote in ("requisitoire", "plaidoirie") for a in contrat[cote]]
    attendus += [a["raison"] for a in contrat["arguments_rejetes"]]
    for piece in contrat["pieces"]:
        attendus += [piece["titre"], piece["valeur_affichee"], piece["source"], piece["traitement"], piece["limites"]]
    attendus += [etape["outil"] for etape in contrat["trace"]]
    attendus += contrat["hypotheses"] + contrat["limites"]
    manquants = [a for a in attendus if re.sub(r"\s+", " ", a) not in texte]
    assert manquants == []


def test_verdict_rendu_ou_non(contrat):
    contrat = copy.deepcopy(contrat)
    contrat["verdict"] = None
    assert "Verdict non encore rendu" in texte_visible(proces_verbal_html(contrat))
    contrat["verdict"] = "maintenu"
    assert "Décision maintenue par l'utilisateur" in texte_visible(proces_verbal_html(contrat))


def test_meme_contrat_meme_page(contrat):
    assert proces_verbal_html(contrat) == proces_verbal_html(copy.deepcopy(contrat))


def test_identifiant_d_audience_affiche(contrat):
    assert "2026-11-14-0123456789ab" in proces_verbal_html(contrat, "2026-11-14-0123456789ab")


def test_texte_du_contrat_echappe():
    contrat = lire(EXEMPLES[0])
    contrat["demande"] = "<script>alert(1)</script>"
    page = proces_verbal_html(contrat)
    assert "<script>" not in page and "&lt;script&gt;" in page


def test_bandeau_de_simulation_et_origine():
    texte = texte_visible(proces_verbal_html(lire(EXEMPLES[0])))
    assert LIBELLES["bandeau"] in texte and "sans texte ajouté par un modèle de langage" in texte


def test_aucun_llm_dans_le_module():
    source = Path(proces_verbal.__file__).read_text(encoding="utf-8")
    assert "pipeline.llm" not in source and "bedrock" not in source.lower()


def test_contre_interrogatoire_affiche():
    contrat = lire(EXEMPLES[0])
    contrat["contre_interrogatoire"] = [{
        "question": "Et à 15 % ?", "pieces_ajoutees": [], "requisitoire": [],
        "plaidoirie": [{"etiquette": "fait", "texte": "À 15 %, la pire baisse serait moindre.", "pieces": ["P1"]}],
        "arguments_rejetes": [],
        "controle_chiffres": {"statut": "conforme", "regle": "verifier_chiffres", "message": "1/1 chiffre"},
        "trace": [{"etape": "orchestrateur", "outil": "simuler_portefeuille", "raison": "Tester une taille",
                   "entree": {}, "sortie": "P9"}],
    }]
    texte = texte_visible(proces_verbal_html(contrat))
    assert "« Et à 15 % ? »" in texte and "À 15 %, la pire baisse serait moindre." in texte


def test_proces_verbaux_de_l_interface_a_jour():
    """frontend/public/proces-verbaux/ correspond aux procès enregistrés (« python -m pipeline.proces_verbal --demo »)."""
    attendus = {f"{identifiant}.html": proces_verbal_html(contrat, identifiant) for identifiant, contrat in proces_demo()}
    presents = {chemin.name: chemin.read_text(encoding="utf-8") for chemin in DOSSIER_PV_DEMO.glob("*.html")}
    assert presents == attendus
