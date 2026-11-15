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


def appel_refuse(sortie):
    return {"etape": "orchestrateur", "outil": "rechercher_documents",
            "raison": "Le Pacte contient un critère non financier.",
            "entree": {"ticker": "TSLA", "critere": "controverse_esg_importante"}, "sortie": sortie}


def test_appel_d_outil_refuse_accepte(contrat):
    """Un outil en erreur ne crée pas de pièce : le procès continue (#65)."""
    contrat["trace"].append(appel_refuse("Erreur : Aucun document sur TSLA : source manquante"))
    assert valider_contrat(contrat) == []


@pytest.mark.parametrize("sortie", ["P99", "Erreur : ", "rien"])
def test_sortie_ni_piece_ni_erreur_rejetee(contrat, sortie):
    contrat["trace"].append(appel_refuse(sortie))
    assert valider_contrat(contrat) == [f"trace/{len(contrat['trace']) - 1} : la sortie « {sortie} » "
                                        "n'est ni une pièce ni une erreur d'outil"]


def test_simulation_obligatoire_en_erreur_rejetee(contrat):
    for etape in contrat["trace"]:
        if etape["outil"] == "simuler_portefeuille":
            etape["sortie"] = "Erreur : taille impossible"
    assert "trace : la pièce obligatoire simuler_portefeuille est absente" in valider_contrat(contrat)


def test_meme_prefixe_d_erreur_que_l_orchestrateur():
    from contrat.valider import PREFIXE_ERREUR_OUTIL
    from pipeline.orchestrateur import PREFIXE_ERREUR
    assert PREFIXE_ERREUR_OUTIL == PREFIXE_ERREUR


def test_panier_dont_les_poids_ne_totalisent_pas_un_rejete():
    contrat = charger_exemple("contrat_amira.json")
    contrat["decision"]["panier"][0]["poids"] = 0.5
    assert len(valider_contrat(contrat)) == 1


def test_taille_max_nulle_acceptee(contrat):
    contrat["taille_max_compatible"] = None
    assert valider_contrat(contrat) == []


# --- Points de bascule (#61) --------------------------------------------------------


def test_contrat_sans_points_de_bascule_accepte(contrat):
    """Champ facultatif : les contrats antérieurs à #61 (procès enregistrés) restent valides."""
    del contrat["points_de_bascule"]
    assert valider_contrat(contrat) == []


def test_regle_en_violation_sans_point_de_bascule_rejetee(contrat):
    contrat["points_de_bascule"] = []
    assert valider_contrat(contrat) == [
        "points_de_bascule : la règle « pire_baisse_max » est en violation sans point de bascule"]


def test_point_de_bascule_sur_une_regle_conforme_rejete(contrat):
    contrat["points_de_bascule"].append({**contrat["points_de_bascule"][0], "regle": "plafond_crypto", "type": "plafond"})
    assert valider_contrat(contrat) == ["points_de_bascule/1 : la règle « plafond_crypto » n'est pas en violation"]


def test_point_de_bascule_sur_une_regle_non_calculable_rejete(contrat):
    contrat["points_de_bascule"].append({**contrat["points_de_bascule"][0], "regle": "preserver_capital"})
    assert valider_contrat(contrat) == [
        "points_de_bascule/1 : « preserver_capital » n'est pas une règle calculable du Pacte"]


def test_point_de_bascule_d_un_autre_type_que_sa_regle_rejete(contrat):
    contrat["points_de_bascule"][0]["type"] = "plafond"
    assert valider_contrat(contrat) == ["points_de_bascule/0 : type « plafond » au lieu de « pire_baisse_max »"]


def test_point_de_bascule_en_double_rejete(contrat):
    contrat["points_de_bascule"].append(copy.deepcopy(contrat["points_de_bascule"][0]))
    assert valider_contrat(contrat) == ["points_de_bascule/1 : règle « pire_baisse_max » en double"]


def test_point_de_bascule_cite_une_piece_inexistante_rejete(contrat):
    contrat["points_de_bascule"][0]["pieces"] = ["P9"]
    assert valider_contrat(contrat) == ["points_de_bascule/0 : pièce P9 inexistante"]


def test_point_de_bascule_sans_piece_rejete(contrat):
    contrat["points_de_bascule"][0]["pieces"] = []
    assert valider_contrat(contrat)


def test_trois_points_de_bascule_du_cas_2():
    contrat = charger_exemple("contrat_amira.json")
    assert [p["regle"] for p in contrat["points_de_bascule"]] == [
        "pire_baisse_max", "plafond_crypto", "pas_exclusivement_tech"]
