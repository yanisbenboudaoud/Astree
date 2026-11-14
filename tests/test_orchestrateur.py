"""Tests de l'orchestrateur.

Les tests unitaires remplacent le modèle par un faux qui rejoue des tours écrits
à l'avance : ils ne coûtent rien et tournent sans accès AWS. Le test réel
(marqueur « bedrock ») fait de vrais appels payants ; il ne tourne qu'avec
« pytest -m bedrock ».
"""

import itertools
import json
from pathlib import Path

import pytest

from pipeline import orchestrateur
from pipeline.donnees import ErreurDonnees
from pipeline.llm import DemandeOutil, TourOutils, decrire_outil
from pipeline.orchestrateur import (
    BUDGET_APPELS,
    RAISON_D_OFFICE,
    RAISON_INDISPONIBLE,
    Outil,
    construire_dossier,
    instruire_dossier,
    raison_valide,
)

PROFIL = json.loads((Path(__file__).resolve().parent.parent / "personas" / "robert.json").read_text("utf-8"))
DECISION = {"type": "position", "ticker": "TSLA", "taille": 0.3, "financement": "proportionnel",
            "libelle": "30 % en TSLA"}
RAISON = "Horizon court : mesurer le temps de récupération du titre"


def schema(*champs):
    return {"type": "object", "properties": {c: {"type": "string"} for c in champs},
            "required": list(champs), "additionalProperties": False}


def faux_outil(nom, *champs, erreur=None):
    def executer(**entree):
        if erreur:
            raise ErreurDonnees(erreur)
        return {"type": "calculee", "titre": f"{nom} {entree}", "valeurs": {"x": 1.0}}
    return Outil(nom, decrire_outil(nom, f"Outil {nom}", schema(*champs)), executer)


INDICATEURS = faux_outil("indicateurs_actif", "ticker")
SIMULER = faux_outil("simuler_portefeuille", "type", "ticker", "taille", "financement")


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


# --- Boucle et pièces ---------------------------------------------------------


def test_execute_les_outils_choisis_et_numerote_les_pieces():
    modele = FauxModele([demande("indicateurs_actif", ticker="TSLA"),
                         demande("simuler_portefeuille", type="position", ticker="TSLA",
                                 taille="0.3", financement="proportionnel")])
    resultat = instruire_dossier(DECISION, PROFIL, [INDICATEURS, SIMULER], modele)
    assert [p["id"] for p in resultat.pieces] == ["P1", "P2"]
    assert [e["sortie"] for e in resultat.trace] == ["P1", "P2"]
    assert resultat.trace[0] == {"etape": "orchestrateur", "outil": "indicateurs_actif",
                                 "raison": RAISON, "entree": {"ticker": "TSLA"}, "sortie": "P1"}
    # Les pièces numérotées sont renvoyées au modèle ; la raison n'est pas passée à l'outil.
    envoyes = resultats_envoyes(modele, 0)
    assert envoyes[0]["status"] == "success"
    assert envoyes[0]["content"][0]["json"]["id"] == "P1"
    assert "raison" not in envoyes[0]["content"][0]["json"]["titre"]


def test_premier_numero_configurable():
    modele = FauxModele([demande("indicateurs_actif", ticker="TSLA")])
    resultat = instruire_dossier(DECISION, PROFIL, [INDICATEURS, SIMULER], modele, premier_numero=4)
    assert resultat.pieces[0]["id"] == "P4"


def test_le_modele_recoit_les_outils_avec_le_parametre_raison():
    modele = FauxModele()
    instruire_dossier(DECISION, PROFIL, [INDICATEURS, SIMULER], modele)
    schema_envoye = modele.appels[0]["outils"][0]["toolSpec"]["inputSchema"]["json"]
    assert schema_envoye["required"] == ["ticker", "raison"]
    assert "raison" in schema_envoye["properties"]
    # La description d'origine n'est pas modifiée.
    assert INDICATEURS.description_bedrock["toolSpec"]["inputSchema"]["json"]["required"] == ["ticker"]


def test_dossier_sans_justifications_ni_nom():
    dossier = construire_dossier(DECISION, PROFIL)
    assert "justification" not in dossier
    assert PROFIL["nom"] not in dossier
    assert "pire_baisse_max" in dossier and "ZST.TO" in dossier


# --- Garde-fous ---------------------------------------------------------------


def test_budget_maximum_d_appels():
    tours = [[demande("indicateurs_actif", ticker=f"T{i}")] for i in range(BUDGET_APPELS + 3)]
    modele = FauxModele(*tours)
    resultat = instruire_dossier(DECISION, PROFIL, [INDICATEURS, SIMULER], modele)
    assert resultat.appels == BUDGET_APPELS
    assert len(modele.appels) == BUDGET_APPELS  # plus aucun tour une fois le budget atteint


def test_budget_depasse_dans_un_meme_tour():
    modele = FauxModele([demande("indicateurs_actif", ticker=f"T{i}") for i in range(BUDGET_APPELS + 2)])
    resultat = instruire_dossier(DECISION, PROFIL, [INDICATEURS, SIMULER], modele)
    refusees = [e for e in resultat.trace if e["sortie"] == "Erreur : Budget d'appels atteint"]
    assert len(refusees) == 2
    assert len(resultat.pieces) == BUDGET_APPELS + 1  # 8 demandées + la simulation d'office


def test_outil_hors_liste_blanche_refuse():
    modele = FauxModele([demande("verifier_chiffres", texte="…")])
    resultat = instruire_dossier(DECISION, PROFIL, [INDICATEURS, SIMULER], modele)
    assert resultats_envoyes(modele, 0)[0]["status"] == "error"
    assert resultat.trace[0]["sortie"] == "Erreur : Outil « verifier_chiffres » non autorisé"
    assert all(p["titre"].startswith("simuler_portefeuille") for p in resultat.pieces)


@pytest.mark.parametrize("raison", ["La pire baisse dépasse 12 %", "", "   ", "x" * 200, None])
def test_raison_avec_chiffre_vide_ou_trop_longue_refusee(raison):
    assert not raison_valide(raison)
    modele = FauxModele([demande("indicateurs_actif", raison=raison, ticker="TSLA")])
    resultat = instruire_dossier(DECISION, PROFIL, [INDICATEURS, SIMULER], modele)
    assert resultats_envoyes(modele, 0)[0]["status"] == "error"
    assert resultat.trace[0]["raison"] == orchestrateur.RAISON_REFUSEE


def test_erreur_d_outil_renvoyee_au_modele_sans_planter():
    titre_inconnu = faux_outil("indicateurs_actif", "ticker",
                               erreur="Titre(s) absent(s) de l'univers d'actifs : ZZZ")
    modele = FauxModele([demande("indicateurs_actif", ticker="ZZZ")])
    resultat = instruire_dossier(DECISION, PROFIL, [titre_inconnu, SIMULER], modele)
    envoye = resultats_envoyes(modele, 0)[0]
    assert envoye["status"] == "error"
    assert "ZZZ" in envoye["content"][0]["json"]["erreur"]
    assert resultat.trace[0]["sortie"].startswith("Erreur : Titre(s) absent(s)")


def test_simulation_ajoutee_d_office():
    modele = FauxModele([demande("indicateurs_actif", ticker="TSLA")])
    resultat = instruire_dossier(DECISION, PROFIL, [INDICATEURS, SIMULER], modele)
    derniere = resultat.trace[-1]
    assert derniere["outil"] == "simuler_portefeuille"
    assert derniere["raison"] == RAISON_D_OFFICE
    assert derniere["entree"] == {"type": "position", "ticker": "TSLA", "taille": 0.3,
                                  "financement": "proportionnel"}
    assert derniere["sortie"] == "P2"


def test_simulation_pas_dupliquee_si_deja_demandee():
    modele = FauxModele([demande("simuler_portefeuille", type="position", ticker="TSLA",
                                 taille="0.3", financement="proportionnel")])
    resultat = instruire_dossier(DECISION, PROFIL, [INDICATEURS, SIMULER], modele)
    assert len(resultat.pieces) == 1
    assert RAISON_D_OFFICE not in [e["raison"] for e in resultat.trace]


def test_simulation_indisponible_notee_dans_la_trace():
    resultat = instruire_dossier(DECISION, PROFIL, [INDICATEURS], FauxModele())
    assert resultat.pieces == []
    assert resultat.trace[-1]["raison"] == RAISON_INDISPONIBLE
    assert resultat.trace[-1]["sortie"] == "Aucune pièce"


def test_raisons_de_la_trace_sans_chiffre():
    modele = FauxModele([demande("indicateurs_actif", raison="Il y a 3 risques", ticker="TSLA")],
                        [demande("indicateurs_actif", ticker="TSLA")])
    resultat = instruire_dossier(DECISION, PROFIL, [INDICATEURS, SIMULER], modele)
    assert all(raison_valide(e["raison"]) for e in resultat.trace)


# --- Vrai appel à Bedrock (payant) -------------------------------------------


@pytest.mark.bedrock
def test_bedrock_instruit_le_dossier_tsla():
    resultat = instruire_dossier(DECISION, PROFIL)
    appels_du_modele = [e for e in resultat.trace if e["raison"] != RAISON_INDISPONIBLE]
    assert appels_du_modele, "le modèle aurait dû demander au moins un outil"
    assert any(p["outil"] == "indicateurs_actif" for p in resultat.pieces)
    assert all(raison_valide(e["raison"]) for e in resultat.trace)
    print(json.dumps(resultat.trace, ensure_ascii=False, indent=2))
