"""Tests de l'orchestrateur et du Tribunal (#12).

Le modèle est remplacé par un faux qui rejoue des tours écrits à l'avance : les
tests ne coûtent rien et tournent sans accès AWS. Les tests réels (marqueur
« bedrock ») font de vrais appels payants ; ils ne tournent qu'avec
« pytest -m bedrock ».
"""

import copy
import itertools
import json

import pytest
from jsonschema import Draft202012Validator

from contrat.valider import charger_schema
from pipeline import agent_profil
from pipeline.agent_profil import chemin_profil
from pipeline.donnees import ErreurDonnees
from pipeline.llm import DemandeOutil, TourOutils, decrire_outil
from pipeline.orchestrateur import (
    BUDGET_APPELS,
    RAISON_D_OFFICE,
    RAISON_REFUSEE,
    Outil,
    construire_dossier,
    entree_simulation_obligatoire,
    instruire_dossier,
    raison_valide,
)
from pipeline.pacte import charger_pacte
from pipeline.tribunal import AVERTISSEMENT, juger_decision

PROFIL = charger_pacte(chemin_profil("robert"))
DECISION = {"type": "position", "ticker": "TSLA", "taille": 0.3, "financement": "proportionnel",
            "libelle": "30 % en TSLA"}
RAISON = "Horizon court : mesurer le temps de récupération du titre"
SIMULATION_DECISION = entree_simulation_obligatoire(DECISION)

_identifiants = itertools.count(1)


def demande(nom, raison=RAISON, **entree):
    return DemandeOutil(id=f"u{next(_identifiants)}", nom=nom, entree={**entree, "raison": raison})


class FauxModele:
    """Rejoue des tours écrits à l'avance et garde ce que le modèle a reçu."""

    def __init__(self, *tours):
        self.tours = list(tours)
        self.appels = []

    def __call__(self, systeme, conversation, outils):
        self.appels.append({"systeme": systeme, "conversation": list(conversation), "outils": outils})
        demandes = self.tours.pop(0) if self.tours else []
        return TourOutils(message_assistant={"role": "assistant", "content": []},
                          demandes=demandes, texte="")


def resultats_envoyes(modele, tour):
    """Blocs toolResult renvoyés au modèle après le tour donné (0 = premier)."""
    return [bloc["toolResult"] for bloc in modele.appels[tour + 1]["conversation"][-1]["content"]]


def faux_outil(nom, champs, erreur=None):
    schema = {"type": "object", "properties": {c: {"type": "string"} for c in champs},
              "required": list(champs), "additionalProperties": False}

    def executer(entree, id_piece):
        if erreur:
            raise ErreurDonnees(erreur)
        return {"id": id_piece, "outil": nom, "entree": entree}

    return Outil(nom, decrire_outil(nom, f"Outil {nom}", schema), executer)


INDICATEURS = faux_outil("indicateurs_actif", ["ticker"])
SIMULER = faux_outil("simuler_portefeuille", ["ticker", "taille", "financement", "periode"])
FAUX_OUTILS = [INDICATEURS, SIMULER]


def instruire(modele, outils=FAUX_OUTILS):
    return instruire_dossier(DECISION, PROFIL, premier_numero=2, outils=outils, converser=modele)


# --- Boucle et pièces ---------------------------------------------------------


def test_execute_les_outils_choisis_et_numerote_les_pieces():
    modele = FauxModele([demande("indicateurs_actif", ticker="TSLA"),
                         demande("simuler_portefeuille", **{**SIMULATION_DECISION, "periode": "2022"})])
    resultat = instruire(modele)
    assert [p["id"] for p in resultat.pieces] == ["P2", "P3", "P4"]  # P4 : simulation d'office
    assert resultat.trace[0] == {"etape": "orchestrateur", "outil": "indicateurs_actif",
                                 "raison": RAISON, "entree": {"ticker": "TSLA"}, "sortie": "P2"}
    envoye = resultats_envoyes(modele, 0)[0]
    assert envoye["status"] == "success"
    assert envoye["content"][0]["json"]["id"] == "P2"
    assert "raison" not in envoye["content"][0]["json"]["entree"]  # la raison ne va pas à l'outil


def test_le_modele_recoit_chaque_outil_avec_le_parametre_raison():
    modele = FauxModele()
    instruire(modele)
    schema_envoye = modele.appels[0]["outils"][0]["toolSpec"]["inputSchema"]["json"]
    assert schema_envoye["required"] == ["ticker", "raison"]
    assert INDICATEURS.description_bedrock["toolSpec"]["inputSchema"]["json"]["required"] == ["ticker"]


def test_dossier_sans_justifications_ni_nom():
    dossier = construire_dossier(DECISION, PROFIL)
    assert "justification" not in dossier
    assert PROFIL["nom"] not in dossier
    assert "pire_baisse_max" in dossier and "ZST.TO" in dossier


# --- Garde-fous ---------------------------------------------------------------


def test_budget_maximum_d_appels():
    modele = FauxModele(*[[demande("indicateurs_actif", ticker=f"T{i}")] for i in range(BUDGET_APPELS + 3)])
    resultat = instruire(modele)
    assert resultat.appels == BUDGET_APPELS
    assert len(modele.appels) == BUDGET_APPELS  # plus aucun tour une fois le budget atteint


def test_budget_depasse_dans_un_meme_tour():
    modele = FauxModele([demande("indicateurs_actif", ticker=f"T{i}") for i in range(BUDGET_APPELS + 2)])
    resultat = instruire(modele)
    refusees = [e for e in resultat.trace if e["sortie"] == "Erreur : Budget d'appels atteint"]
    assert len(refusees) == 2
    assert len(resultat.pieces) == BUDGET_APPELS + 1  # 8 demandées + la simulation d'office


def test_outil_hors_liste_blanche_refuse():
    modele = FauxModele([demande("verifier_chiffres", texte="…")])
    resultat = instruire(modele)
    assert resultats_envoyes(modele, 0)[0]["status"] == "error"
    assert resultat.trace[0]["sortie"] == "Erreur : Outil « verifier_chiffres » non autorisé"
    assert resultat.trace[0]["raison"] == RAISON_REFUSEE


@pytest.mark.parametrize("raison", ["La pire baisse dépasse 12 %", "", "   ", "x" * 200, None])
def test_raison_avec_chiffre_vide_ou_trop_longue_refusee(raison):
    assert not raison_valide(raison)
    modele = FauxModele([demande("indicateurs_actif", raison=raison, ticker="TSLA")])
    resultat = instruire(modele)
    assert resultats_envoyes(modele, 0)[0]["status"] == "error"
    assert resultat.trace[0]["raison"] == RAISON_REFUSEE


def test_erreur_d_outil_renvoyee_au_modele_sans_planter():
    titre_inconnu = faux_outil("indicateurs_actif", ["ticker"],
                               erreur="Titre(s) absent(s) de l'univers d'actifs : ZZZ")
    modele = FauxModele([demande("indicateurs_actif", ticker="ZZZ")])
    resultat = instruire(modele, [titre_inconnu, SIMULER])
    envoye = resultats_envoyes(modele, 0)[0]
    assert envoye["status"] == "error"
    assert "ZZZ" in envoye["content"][0]["json"]["erreur"]
    assert resultat.trace[0]["sortie"].startswith("Erreur : Titre(s) absent(s)")
    assert [e["outil"] for e in resultat.trace] == ["indicateurs_actif", "simuler_portefeuille"]


def test_simulation_ajoutee_d_office():
    resultat = instruire(FauxModele([demande("indicateurs_actif", ticker="TSLA")]))
    derniere = resultat.trace[-1]
    assert derniere == {"etape": "orchestrateur", "outil": "simuler_portefeuille",
                        "raison": RAISON_D_OFFICE, "entree": SIMULATION_DECISION, "sortie": "P3"}


def test_simulation_pas_dupliquee_si_deja_demandee():
    resultat = instruire(FauxModele([demande("simuler_portefeuille", **SIMULATION_DECISION)]))
    assert len(resultat.pieces) == 1
    assert RAISON_D_OFFICE not in [e["raison"] for e in resultat.trace]


def test_simulation_d_une_autre_taille_ne_compte_pas():
    resultat = instruire(FauxModele([demande("simuler_portefeuille", **{**SIMULATION_DECISION, "taille": 0.1})]))
    assert [e["raison"] for e in resultat.trace] == [RAISON, RAISON_D_OFFICE]


def test_raisons_de_la_trace_sans_chiffre():
    modele = FauxModele([demande("indicateurs_actif", raison="Il y a 3 risques", ticker="TSLA")],
                        [demande("indicateurs_actif", ticker="TSLA")])
    assert all(raison_valide(e["raison"]) for e in instruire(modele).trace)


# --- Avec les vrais outils (sans Bedrock) ------------------------------------


def valider_piece(piece):
    schema = charger_schema()
    validateur = Draft202012Validator({"$defs": schema["$defs"], "$ref": "#/$defs/piece"})
    assert list(validateur.iter_errors(piece)) == []


def test_vrais_outils_produisent_des_pieces_du_contrat():
    modele = FauxModele([
        demande("indicateurs_actif", ticker="TSLA"),
        demande("simuler_portefeuille", **{**SIMULATION_DECISION, "periode": "2022"}),
    ])
    resultat = instruire_dossier(DECISION, PROFIL, premier_numero=2, converser=modele)
    assert [p["outil"] for p in resultat.pieces] == ["indicateurs_actif", "simuler_portefeuille",
                                                     "simuler_portefeuille"]
    for piece in resultat.pieces:
        valider_piece(piece)
    # Simulation d'office : mêmes chiffres que la pièce P1 de la maquette.
    assert round(resultat.pieces[-1]["valeurs"]["pire_baisse"], 4) == -0.2897


def test_taille_impossible_renvoyee_au_modele():
    modele = FauxModele([demande("simuler_portefeuille", **{**SIMULATION_DECISION, "taille": 1.5})])
    resultat = instruire_dossier(DECISION, PROFIL, premier_numero=2, converser=modele)
    assert resultats_envoyes(modele, 0)[0]["status"] == "error"
    assert "1.5" in resultat.trace[0]["sortie"]


# --- Le Tribunal : Profil puis Orchestrateur ---------------------------------


EXTRACTION_TSLA = {"type_decision": "position", "actif_mentionne": "Tesla", "ticker": "TSLA", "taille": 0.30,
                   "montant": None, "devise_montant": "non_precisee", "financement_depuis": None,
                   "ambiguites": []}


def test_juger_decision_enchaine_profil_et_orchestrateur(monkeypatch):
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: copy.deepcopy(EXTRACTION_TSLA))
    contrat = juger_decision("robert", "Je veux mettre 30 % en Tesla",
                             converser=FauxModele([demande("indicateurs_actif", ticker="TSLA")]))
    assert contrat["persona"] == "robert"
    assert contrat["decision"]["ticker"] == "TSLA"
    assert [p["id"] for p in contrat["pieces"]] == ["P1", "P2", "P3"]
    assert contrat["pieces"][0]["outil"] == "charger_pacte"
    assert [e["etape"] for e in contrat["trace"]] == ["agent_profil"] * 3 + ["orchestrateur"] * 2
    assert contrat["comparaison"]["actuel"]["pire_baisse"] == pytest.approx(-0.0776, abs=5e-5)
    assert contrat["comparaison"]["apres"]["pire_baisse"] == pytest.approx(-0.2897, abs=5e-5)
    assert contrat["hypotheses"][0] == "Période : 2021-11-12 au 2026-11-12"
    assert "Montants convertis en CAD" in contrat["hypotheses"]
    assert contrat["verdict"] is None and contrat["avertissement"] == AVERTISSEMENT
    for piece in contrat["pieces"]:
        valider_piece(piece)


def test_juger_decision_sans_decision_ne_calcule_rien(monkeypatch):
    monkeypatch.setattr(agent_profil, "appeler_llm",
                        lambda *args: {**EXTRACTION_TSLA, "taille": None})

    def modele_interdit(*args):
        raise AssertionError("l'orchestrateur ne doit pas être appelé sans décision")

    contrat = juger_decision("robert", "Je veux de la Tesla", converser=modele_interdit)
    assert contrat["decision"] is None
    assert [p["id"] for p in contrat["pieces"]] == ["P1"]
    assert contrat["controles"] and all(c["statut"] == "a_verifier" for c in contrat["controles"])


# --- Vrais appels à Bedrock (payants) ----------------------------------------


@pytest.mark.bedrock
def test_bedrock_instruit_le_dossier_tsla():
    resultat = instruire_dossier(DECISION, PROFIL, premier_numero=2)
    assert resultat.appels >= 1, "le modèle aurait dû demander au moins un outil"
    assert all(raison_valide(e["raison"]) for e in resultat.trace)
    assert resultat.pieces[-1]["outil"] == "simuler_portefeuille"
    print(json.dumps(resultat.trace, ensure_ascii=False, indent=2))


@pytest.mark.bedrock
def test_bedrock_meme_decision_deux_profils():
    # La même décision, instruite pour deux Pactes différents.
    for identifiant in ["robert", "amira"]:
        profil = charger_pacte(chemin_profil(identifiant))
        resultat = instruire_dossier(DECISION, profil, premier_numero=2)
        print(identifiant, json.dumps(resultat.trace, ensure_ascii=False, indent=2))
        assert any(p["outil"] == "simuler_portefeuille" for p in resultat.pieces)
