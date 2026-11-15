"""Tests du contre-interrogatoire (#55).

Le modèle est remplacé par des faux : l'orchestrateur rejoue des tours écrits à
l'avance, et le Procureur et l'Avocat renvoient des arguments écrits à l'avance.
Les tests ne coûtent rien et tournent sans accès AWS.
"""

import copy
import itertools
import json
from pathlib import Path

import pytest

from contrat.valider import valider_contrat
from pipeline import debat
from pipeline.agent_profil import chemin_profil
from pipeline.contre_interrogatoire import (
    LONGUEUR_MAX_QUESTION,
    QuestionInvalide,
    interroger,
    pieces_de_l_echange,
    prochain_numero,
    verifier_question,
)
from pipeline.llm import DemandeOutil, TourOutils
from pipeline.orchestrateur import (
    BUDGET_APPELS_QUESTION,
    RAISON_D_OFFICE,
    CONSIGNES_QUESTION,
    instruire_question,
)
from pipeline.pacte import charger_pacte

RACINE = Path(__file__).resolve().parent.parent
PROFIL = charger_pacte(chemin_profil("robert"))
QUESTION = "Et si je mettais 15 % au lieu de 30 % ?"
RAISON = "Simuler la taille évoquée dans la question"

_identifiants = itertools.count(1)


def contrat_de_depart():
    """Le faux contrat du cas 1 (Robert, 30 % en TSLA), avec l'identifiant de profil du pipeline."""
    contrat = json.loads((RACINE / "docs" / "exemples" / "contrat_robert.json").read_text(encoding="utf-8"))
    contrat["persona"] = "robert"
    return contrat


def simulation_a(taille, raison=RAISON):
    entree = {"ticker": "TSLA", "taille": taille, "financement": "proportionnel", "periode": "complete"}
    return DemandeOutil(id=f"q{next(_identifiants)}", nom="simuler_portefeuille",
                        entree={**entree, "raison": raison})


class FauxModele:
    """Rejoue des tours écrits à l'avance et garde ce que le modèle a reçu."""

    def __init__(self, *tours):
        self.tours = list(tours)
        self.appels = []

    def __call__(self, systeme, conversation, outils):
        self.appels.append({"systeme": systeme, "conversation": list(conversation), "outils": outils})
        demandes = self.tours.pop(0) if self.tours else []
        return TourOutils(message_assistant={"role": "assistant", "content": []}, demandes=demandes, texte="")


def faux_debat(monkeypatch, arguments_par_role, correction=None):
    """Remplace les appels Bedrock du débat ; garde les messages reçus."""
    recus = []

    def faux_llm(systeme, message, schema):
        recus.append(message)
        if "Le Greffier a refusé" in message:
            return correction
        role = "procureur" if "Procureur" in systeme else "avocat"
        return {"arguments": arguments_par_role(role)}

    monkeypatch.setattr(debat, "appeler_llm", faux_llm)
    return recus


# --- La question -----------------------------------------------------------------


def test_question_normalisee():
    assert verifier_question("  Et   à 15 % ?  ") == "Et à 15 % ?"


@pytest.mark.parametrize("question", ["", "   ", None, "x" * (LONGUEUR_MAX_QUESTION + 1)])
def test_question_refusee_avant_tout_appel(question):
    with pytest.raises(QuestionInvalide):
        verifier_question(question)


def test_prochain_numero_suit_la_plus_grande_piece():
    assert prochain_numero([{"id": "P1"}, {"id": "P6"}, {"id": "P2"}]) == 7
    assert prochain_numero([]) == 1


# --- L'orchestrateur ----------------------------------------------------------------


def test_instruire_question_numerote_a_la_suite_sans_piece_d_office():
    modele = FauxModele([simulation_a(0.15)])
    resultat = instruire_question(contrat_de_depart()["decision"], PROFIL, QUESTION,
                                  contrat_de_depart()["pieces"], premier_numero=6, converser=modele)
    assert [piece["id"] for piece in resultat.pieces] == ["P6"]
    assert resultat.piece_simulation is None
    assert all(etape["raison"] != RAISON_D_OFFICE for etape in resultat.trace)
    assert modele.appels[0]["systeme"] == CONSIGNES_QUESTION.format(budget=BUDGET_APPELS_QUESTION)


def test_instruire_question_montre_la_question_et_les_pieces_au_modele():
    modele = FauxModele([])
    instruire_question(contrat_de_depart()["decision"], PROFIL, QUESTION, contrat_de_depart()["pieces"],
                       premier_numero=6, converser=modele)
    message = modele.appels[0]["conversation"][0]["content"][0]["text"]
    assert QUESTION in message
    assert "Pièces déjà au dossier" in message
    assert '"id": "P1"' in message


def test_instruire_question_respecte_son_budget():
    tailles = [0.05, 0.1, 0.15, 0.2, 0.25, 0.35]
    modele = FauxModele([simulation_a(t) for t in tailles])
    resultat = instruire_question(contrat_de_depart()["decision"], PROFIL, QUESTION,
                                  contrat_de_depart()["pieces"], premier_numero=6, converser=modele)
    assert len(resultat.pieces) == BUDGET_APPELS_QUESTION
    refus = [e for e in resultat.trace if e["sortie"].startswith("Erreur")]
    assert len(refus) == len(tailles) - BUDGET_APPELS_QUESTION


# --- Le débat ------------------------------------------------------------------------


def test_message_du_debat_sans_question_inchange():
    dossier = {"decision": {}, "pacte": {}, "pieces": [], "periode": ["2021-11-12", "2026-11-12"]}
    assert "Contre-interrogatoire" not in debat.construire_message(dossier)
    assert QUESTION in debat.construire_message({**dossier, "question": QUESTION})


# --- interroger, de bout en bout ------------------------------------------------------


def test_interroger_ajoute_les_pieces_et_l_echange(monkeypatch):
    depart = contrat_de_depart()
    nouvelle = f"P{prochain_numero(depart['pieces'])}"
    recus = faux_debat(monkeypatch, lambda role: [
        {"etiquette": "fait", "pieces": [nouvelle],
         "texte": f"La simulation à cette taille est la pièce {nouvelle} ; comparez-la à votre règle."},
    ])
    complete = interroger(depart, QUESTION, converser=FauxModele([simulation_a(0.15)]))

    assert valider_contrat(complete) == []
    assert complete["pieces"][-1]["id"] == nouvelle
    [echange] = complete["contre_interrogatoire"]
    assert echange["question"] == QUESTION
    assert echange["pieces_ajoutees"] == [nouvelle]
    assert len(echange["requisitoire"]) == len(echange["plaidoirie"]) == 1
    assert echange["controle_chiffres"]["regle"] == "verifier_chiffres"
    assert [e["etape"] for e in echange["trace"]] == ["orchestrateur", "procureur", "avocat", "greffier", "greffier"]
    assert [e["outil"] for e in echange["trace"][-2:]] == ["verifier_chiffres", "verifier_cadre_simulation"]
    assert all(QUESTION in message for message in recus)
    assert pieces_de_l_echange(complete, echange) == [complete["pieces"][-1]]
    assert "contre_interrogatoire" not in depart  # le contrat reçu n'est pas modifié
    # #111 : la pièce ajoutée rejoint ses sources, avec la raison de l'orchestrateur.
    prix = next(s for s in complete["sources"] if s["fichier"] == "prices_daily.csv")
    assert any(u["id"] == nouvelle and u.get("raison") for u in prix["pieces"])


def test_un_chiffre_invente_est_rejete_par_le_greffier(monkeypatch):
    depart = contrat_de_depart()
    nouvelle = f"P{prochain_numero(depart['pieces'])}"
    faux = {"etiquette": "fait", "pieces": [nouvelle], "texte": "La pire baisse serait de −99,0 %."}
    faux_debat(monkeypatch, lambda role: [faux], correction=faux)
    complete = interroger(depart, QUESTION, converser=FauxModele([simulation_a(0.15)]))

    [echange] = complete["contre_interrogatoire"]
    assert echange["requisitoire"] == [] and echange["plaidoirie"] == []
    assert len(echange["arguments_rejetes"]) == 2
    assert "−99,0 %" in echange["arguments_rejetes"][0]["raison"]
    assert valider_contrat(complete) == []


def test_les_questions_s_enchainent(monkeypatch):
    faux_debat(monkeypatch, lambda role: [{"etiquette": "fait", "pieces": ["P1"],
                                           "texte": "Votre Pacte reste la référence."}])
    premiere = interroger(contrat_de_depart(), QUESTION, converser=FauxModele([simulation_a(0.15)]))
    seconde = interroger(premiere, "Et à 20 % ?", converser=FauxModele([simulation_a(0.2)]))

    assert len(seconde["contre_interrogatoire"]) == 2
    premier_ajout = seconde["contre_interrogatoire"][0]["pieces_ajoutees"][0]
    second_ajout = seconde["contre_interrogatoire"][1]["pieces_ajoutees"][0]
    assert int(second_ajout[1:]) == int(premier_ajout[1:]) + 1
    assert valider_contrat(seconde) == []


def test_demande_de_conseil_sans_outil(monkeypatch):
    faux_debat(monkeypatch, lambda role: [{"etiquette": "fait", "pieces": ["P1"],
                                           "texte": "Le Tribunal ne conseille pas : c'est à vous de trancher."}])
    complete = interroger(contrat_de_depart(), "Que dois-je acheter ?", converser=FauxModele([]))
    [echange] = complete["contre_interrogatoire"]
    assert echange["pieces_ajoutees"] == []
    assert valider_contrat(complete) == []


def test_reponse_a_une_demande_de_conseil_acceptee_mais_un_conseil_rejete(monkeypatch):
    """#60 : « ne dit pas s'il faut vendre » passe ; « vous devriez vendre » est rejeté après une relance."""
    reponse = {"etiquette": "fait", "pieces": ["P1"],
               "texte": "Le Tribunal ne vous dit pas s'il faut vendre TSLA : c'est à vous de trancher."}
    conseil = {"etiquette": "fait", "pieces": ["P1"], "texte": "Vous devriez vendre TSLA."}
    faux_debat(monkeypatch, lambda role: [reponse] if role == "procureur" else [conseil], correction=conseil)
    complete = interroger(contrat_de_depart(), "Dois-je vendre TSLA ?", converser=FauxModele([]))

    [echange] = complete["contre_interrogatoire"]
    assert echange["requisitoire"] == [reponse] and echange["plaidoirie"] == []
    [rejete] = echange["arguments_rejetes"]
    assert rejete["cote"] == "plaidoirie" and rejete["raison"].startswith("Conseil personnalisé : « Vous devriez »")
    assert echange["trace"][-1]["sortie"] == (
        "Aucun conseil personnalisé ni promesse sur l'avenir : 1 argument vérifié ; "
        "1 argument rejeté après une relance")
    assert valider_contrat(complete) == []


def test_proces_sans_decision_refuse():
    contrat = contrat_de_depart()
    contrat["decision"] = None
    with pytest.raises(QuestionInvalide, match="décision"):
        interroger(contrat, QUESTION, converser=FauxModele([]))


# --- Validateur ----------------------------------------------------------------------


def test_validateur_refuse_un_echange_qui_cite_une_piece_inconnue(monkeypatch):
    faux_debat(monkeypatch, lambda role: [{"etiquette": "fait", "pieces": ["P1"], "texte": "Votre Pacte."}])
    complete = interroger(contrat_de_depart(), QUESTION, converser=FauxModele([]))
    casse = copy.deepcopy(complete)
    casse["contre_interrogatoire"][0]["requisitoire"][0]["pieces"] = ["P99"]
    assert any("P99" in erreur for erreur in valider_contrat(casse))


def test_contrat_sans_contre_interrogatoire_toujours_valide():
    assert valider_contrat(contrat_de_depart()) == []


# --- Test réel (payant) : pytest -m bedrock ----------------------------------------------


@pytest.mark.bedrock
def test_question_reelle_tous_les_chiffres_passent_le_greffier():
    complete = interroger(contrat_de_depart(), QUESTION)
    [echange] = complete["contre_interrogatoire"]
    assert valider_contrat(complete) == []
    assert echange["requisitoire"] or echange["plaidoirie"]
    assert echange["controle_chiffres"]["statut"] == "conforme"
