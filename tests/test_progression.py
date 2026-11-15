"""Tests de pipeline/progression.py : le document de progression d'un procès en direct (#90)."""

import threading

import pytest

from pipeline.progression import PHASES, Progression

HORLOGE = "2026-11-15T10:00:00+00:00"


def nouvelle(publiees=None):
    return Progression("2026-11-15-0123456789ab", publiees.append if publiees is not None else lambda d: None,
                       horloge=lambda: HORLOGE)


def test_etat_initial_publie_avant_le_premier_signal():
    publiees = []
    progression = nouvelle(publiees)
    progression.publier_etat_initial()
    assert publiees == [{"id": "2026-11-15-0123456789ab", "statut": "en_cours", "phase": None, "activite": None,
                         "etapes": [], "debut": HORLOGE, "mise_a_jour": HORLOGE}]


def test_phases_etapes_et_activites_cumulees_dans_l_ordre():
    publiees = []
    progression = nouvelle(publiees)
    progression.signaler({"type": "phase", "phase": "orchestrateur", "activite": "L'orchestrateur choisit"})
    etape = {"etape": "orchestrateur", "outil": "simuler_portefeuille", "raison": "Pièce obligatoire", "sortie": "P2"}
    progression.signaler({"type": "etape", "etape": etape})
    progression.signaler({"type": "activite", "activite": "Python calcule"})

    assert [d["phase"] for d in publiees] == ["orchestrateur"] * 3
    assert [len(d["etapes"]) for d in publiees] == [0, 1, 1]  # une version publiée par signal
    assert publiees[-1]["etapes"] == [etape] and publiees[-1]["activite"] == "Python calcule"


def test_une_version_publiee_ne_change_plus():
    publiees = []
    progression = nouvelle(publiees)
    etape = {"etape": "greffier", "outil": "verifier_pacte", "sortie": "1 violation"}
    progression.signaler({"type": "etape", "etape": etape})
    etape["sortie"] = "modifiée après coup"
    progression.signaler({"type": "phase", "phase": "greffier"})
    assert publiees[0]["etapes"][0]["sortie"] == "1 violation"
    assert publiees[0]["phase"] is None  # copie, pas une référence au document vivant


def test_terminer_et_echouer():
    progression = nouvelle()
    progression.signaler({"type": "phase", "phase": "debat", "activite": "Plaidoiries"})
    progression.terminer()
    document = progression.document
    assert (document["statut"], document["phase"], document["activite"]) == ("termine", None, None)
    assert "erreur" not in document

    echec = nouvelle()
    echec.echouer("Bedrock indisponible")
    assert echec.document["statut"] == "erreur" and echec.document["erreur"] == "Bedrock indisponible"


@pytest.mark.parametrize("evenement", [{"type": "inconnu"}, {"type": "phase", "phase": "verdict"}])
def test_evenement_inconnu_refuse(evenement):
    with pytest.raises(ValueError):
        nouvelle().signaler(evenement)


def test_signaux_de_deux_fils_tous_gardes():
    """Le Procureur et l'Avocat signalent depuis deux fils : aucune étape n'est perdue."""
    publiees = []
    progression = nouvelle(publiees)

    def signaler(role):
        for n in range(200):
            progression.signaler({"type": "etape", "etape": {"etape": role, "outil": "bedrock", "sortie": n}})

    fils = [threading.Thread(target=signaler, args=(role,)) for role in ("procureur", "avocat")]
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    assert len(progression.document["etapes"]) == 400
    assert [len(d["etapes"]) for d in publiees] == list(range(1, 401))  # versions publiées dans l'ordre


def test_phases_dans_l_ordre_fixe_du_tribunal():
    assert PHASES == ("agent_profil", "orchestrateur", "debat", "greffier")
