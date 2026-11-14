import copy
import json
from pathlib import Path

import pytest

from contrat.valider import valider_contrat

EXEMPLES = Path(__file__).resolve().parent.parent / "docs" / "exemples"


def charger_exemple(nom):
    with open(EXEMPLES / nom, encoding="utf-8") as fichier:
        return json.load(fichier)


@pytest.fixture
def contrat():
    return copy.deepcopy(charger_exemple("contrat_robert.json"))


@pytest.mark.parametrize("nom", ["contrat_robert.json", "contrat_amira.json"])
def test_exemples_valides(nom):
    assert valider_contrat(charger_exemple(nom)) == []


def test_statut_inconnu_rejete(contrat):
    contrat["controles"][0]["statut"] = "ok"
    assert valider_contrat(contrat)


def test_verdict_inconnu_rejete(contrat):
    contrat["verdict"] = "accepte"
    assert valider_contrat(contrat)


def test_champ_inconnu_rejete(contrat):
    contrat["recommandation"] = "acheter"
    assert valider_contrat(contrat)


def test_decision_sans_type_rejetee(contrat):
    del contrat["decision"]["type"]
    assert valider_contrat(contrat)


def test_financement_inconnu_rejete(contrat):
    contrat["decision"]["financement"] = "comptant"
    assert valider_contrat(contrat)


def test_financement_depuis_un_titre_accepte(contrat):
    contrat["decision"]["financement"] = "depuis_ZST.TO"
    assert valider_contrat(contrat) == []


def test_plafond_sans_max_rejete(contrat):
    del contrat["pacte"]["regles"][1]["max"]
    assert valider_contrat(contrat)


def test_regle_avec_justification_rejetee(contrat):
    contrat["pacte"]["regles"][0]["justification"] = "Hypothèse de l'équipe"
    assert valider_contrat(contrat)


def test_argument_sans_piece_rejete(contrat):
    contrat["requisitoire"][0]["pieces"] = []
    assert valider_contrat(contrat)


def test_orchestrateur_sans_raison_rejete(contrat):
    etape = next(e for e in contrat["trace"] if e["etape"] == "orchestrateur")
    del etape["raison"]
    assert valider_contrat(contrat)


def test_raison_avec_chiffre_rejetee(contrat):
    etape = next(e for e in contrat["trace"] if e["etape"] == "orchestrateur")
    etape["raison"] = "La pire baisse dépasse 12 %"
    assert valider_contrat(contrat)


def test_piece_citee_inexistante_rejetee(contrat):
    contrat["plaidoirie"][0]["pieces"] = ["P9"]
    assert valider_contrat(contrat) == ["plaidoirie/0 : pièce P9 inexistante"]


def test_controle_sur_regle_inconnue_rejete(contrat):
    contrat["controles"][0]["regle"] = "regle_fantome"
    erreurs = valider_contrat(contrat)
    assert "controles/0 : règle « regle_fantome » inconnue du Pacte" in erreurs


def test_regle_du_pacte_sans_controle_rejetee(contrat):
    contrat["controles"] = [c for c in contrat["controles"] if c["regle"] != "plafond_crypto"]
    assert valider_contrat(contrat) == ["controles : la règle « plafond_crypto » du Pacte n'a aucun contrôle"]


def test_simulation_obligatoire_absente_rejetee(contrat):
    contrat["trace"] = [e for e in contrat["trace"] if e["outil"] != "simuler_portefeuille"]
    assert "trace : la pièce obligatoire simuler_portefeuille est absente" in valider_contrat(contrat)


def test_panier_dont_les_poids_ne_totalisent_pas_un_rejete():
    contrat = charger_exemple("contrat_amira.json")
    contrat["decision"]["panier"][0]["poids"] = 0.5
    assert len(valider_contrat(contrat)) == 1


def test_taille_max_nulle_acceptee(contrat):
    contrat["taille_max_compatible"] = None
    assert valider_contrat(contrat) == []
