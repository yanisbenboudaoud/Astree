"""Tests du contrôle du cadre « simulation seulement » (pipeline/cadre_simulation.py, #60)."""

import json
from pathlib import Path

import pytest

from pipeline.cadre_simulation import (
    controle_cadre_simulation,
    detecter_infractions,
    verifier_cadre_simulation,
)
from pipeline.chiffres import controle_verifier_chiffres, trier_arguments

RACINE = Path(__file__).resolve().parent.parent
PERIODE = ["2021-11-12", "2026-11-12"]
DOSSIER = {
    "decision": {"type": "position", "ticker": "TSLA", "taille": 0.30, "financement": "proportionnel"},
    "periode": PERIODE,
    "pieces": [{"id": "P1", "type": "calculee",
                "valeurs": {"pire_baisse": -0.2897, "pire_baisse_actuelle": -0.0776, "rendement_annuel": 0.1198}}],
}


def argument(texte, *pieces):
    return {"etiquette": "fait", "texte": texte, "pieces": list(pieces or ["P1"])}


def familles(texte):
    return [(i.famille, i.expression) for i in detecter_infractions(texte)]


# --- Exemples de l'issue #60 ------------------------------------------------------

def test_vous_devriez_acheter_rejete():
    verification = verifier_cadre_simulation(argument("Vous devriez acheter TSLA."))
    assert not verification.valide
    assert verification.motif == (
        "Conseil personnalisé : « Vous devriez » (le Tribunal ne recommande aucune transaction : "
        "exposer ce que montrent les pièces et laisser l'utilisateur décider)"
    )


def test_citation_du_pacte_acceptee():
    assert verifier_cadre_simulation(argument("Vous avez écrit : « Préserver mon capital ».")).valide


def test_promesse_va_continuer_a_monter_rejetee():
    verification = verifier_cadre_simulation(argument("TSLA va continuer à monter."))
    assert verification.motif == (
        "Promesse ou prévision sur l'avenir : « va continuer à monter » (le passé ne prédit pas "
        "l'avenir : décrire ce que montrent les pièces, ou un scénario au conditionnel avec "
        "l'étiquette « hypothese »)"
    )


def test_negation_acceptee():
    assert verifier_cadre_simulation(argument("Le passé ne prédit pas l'avenir.")).valide


# --- 1. Conseil ---------------------------------------------------------------------

@pytest.mark.parametrize("texte, expression", [
    ("Je vous recommande de vendre XOM.", "Je vous recommande"),
    ("Nous conseillons de limiter la position.", "Nous conseillons"),
    ("Il est recommandé de réduire la taille.", "est recommandé de"),
    ("Il n'est pas conseillé d'acheter TSLA.", "est pas conseillé d'"),
    ("Il faut vendre TSLA avant la retraite.", "Il faut vendre"),
    ("Il ne faut pas vendre vos obligations.", "Il ne faut pas vendre"),
    ("Il vaudrait mieux alléger la position.", "Il vaudrait mieux alléger"),
    ("Il serait prudent de réduire la taille.", "serait prudent de réduire"),
    ("Robert devrait donc renoncer à cette décision.", "devrait donc renoncer"),
    ("Vous auriez intérêt à diversifier.", "Vous auriez intérêt"),
    ("Vous ne devriez pas maintenir cette décision.", "Vous ne devriez"),
    ("Achetez TSLA maintenant.", "Achetez"),
    ("Ne vendez pas vos obligations.", "vendez"),
    ("Mon conseil : rester prudent.", "Mon conseil"),
])
def test_conseils_detectes(texte, expression):
    assert familles(texte) == [("conseil", expression)]


@pytest.mark.parametrize("texte", [
    "Si vous vendez XOM, la part des énergies fossiles disparaît.",       # indicatif, pas impératif
    "Le portefeuille que vous en achetez reste diversifié.",
    "Jusqu'à 9 %, la pire baisse reste dans les limites de son Pacte : il peut s'exposer au titre.",
    "Il faut rappeler que la volatilité n'est qu'un indicateur parmi d'autres.",
    "Gardez à l'esprit qu'une seule période passée est observée.",
    "C'est à vous de trancher.",
    "Le Tribunal ne recommande rien : c'est vous qui rendez le verdict.",
    "Ceci n'est pas un conseil financier personnalisé.",
    "La pire chute dépasse le seuil recommandé de −12 % par l'équipe.",
])
def test_pas_un_conseil(texte):
    assert familles(texte) == []


def test_un_conseil_nie_reste_un_conseil():
    assert familles("Vous ne devriez pas vendre.") == [("conseil", "Vous ne devriez")]


# --- 2. Promesse ----------------------------------------------------------------------

@pytest.mark.parametrize("texte, expression", [
    ("Ce placement rapportera +12,0 % par an.", "rapportera"),
    ("Les cryptoactifs vont s'effondrer.", "vont s'effondrer"),
    ("TSLA devrait rebondir après sa chute.", "devrait rebondir"),
    ("TSLA reviendra à son sommet.", "reviendra"),
    ("La performance passée se répétera.", "répétera"),
    ("Le portefeuille perdra 29,0 % si 2022 se répète.", "perdra"),
    ("TSLA va doubler en un an.", "va doubler"),
    ("Le rendement est garanti.", "garanti"),
    ("Un gain assuré pour votre retraite.", "gain assuré"),
    ("Un placement sans risque.", "sans risque"),
    ("Le passé prédit l'avenir.", "prédit"),
    ("Ce n'est pas garanti, mais TSLA va monter.", "va monter"),  # la négation est dans l'autre proposition
])
def test_promesses_detectees(texte, expression):
    assert familles(texte) == [("promesse", expression)]


@pytest.mark.parametrize("texte", [
    "Rien ne garantit que TSLA va continuer à monter.",
    "Rien, dans les pièces, ne permet de dire que TSLA va monter.",
    "Il s'agit d'une seule année de crise, qui ne prédit pas la suivante.",
    "Cette croissance, qui ne se répétera pas forcément, reste incertaine.",
    "Les rendements passés ne garantissent pas les rendements futurs.",
    "Aucune décision n'est sans risque.",
    "C'est un constat sur une seule période passée et non une promesse pour l'avenir.",
])
def test_promesse_niee_acceptee(texte):
    assert familles(texte) == []


@pytest.mark.parametrize("texte", [
    "Si une année comme 2022 se répétait, le portefeuille ferait −23,7 % au lieu de −2,6 %.",  # conditionnel
    "Le portefeuille rapporterait +12,0 % par an.",
    "TSLA a rapporté +45 % en 2023.",                                                        # passé
    "TSLA pourrait rebondir, sans que rien ne l'assure.",                                    # possibilité
    "Les corrélations montent souvent en période de crise.",                                 # présent
    "La décision va doubler la part crypto.",                 # effet de la décision, pas une prévision
    "Le verdict vous reviendra.",
])
def test_pas_une_promesse(texte):
    assert familles(texte) == []


def test_conseil_et_promesse_dans_le_meme_motif():
    verification = verifier_cadre_simulation(argument("Achetez TSLA : le titre va monter."))
    assert [i.famille for i in verification.infractions] == ["conseil", "promesse"]
    assert verification.motif.startswith("Conseil personnalisé : « Achetez » (")
    assert " ; Promesse ou prévision sur l'avenir : « va monter » (" in verification.motif


# --- Boucle du Greffier : une relance, puis rejet ----------------------------------------

def test_argument_qui_conseille_corrige_apres_une_relance():
    motifs = []

    def corriger(arg, motif):
        motifs.append(motif)
        return argument("Avec 30 % en TSLA, la pire chute passe de −7,8 % à −29,0 %.")

    tri = trier_arguments([argument("Vous devriez vendre TSLA.")], "requisitoire", DOSSIER, corriger)
    assert len(motifs) == 1 and motifs[0].startswith("Conseil personnalisé : « Vous devriez »")
    assert len(tri.valides) == 1 and tri.rejetes == []


def test_argument_qui_promet_encore_rejete_apres_la_relance():
    appels = []

    def corriger(arg, motif):
        appels.append(motif)
        return argument("Le rendement de +12,0 % se répétera.")

    tri = trier_arguments([argument("TSLA va continuer à monter.")], "plaidoirie", DOSSIER, corriger)
    assert len(appels) == 1  # renvoyé une seule fois
    assert tri.valides == []
    assert tri.rejetes[0]["cote"] == "plaidoirie"
    assert tri.rejetes[0]["texte"] == "Le rendement de +12,0 % se répétera."
    assert tri.rejetes[0]["raison"].startswith("Promesse ou prévision sur l'avenir : « répétera »")
    assert (tri.rejetes_cadre, tri.rejetes_chiffres) == (1, 0)


def test_chiffre_faux_et_conseil_en_une_seule_relance():
    motifs = []
    tri = trier_arguments([argument("Vendez : la pire chute passe à −31 %.")], "requisitoire", DOSSIER,
                          lambda arg, motif: motifs.append(motif) or arg)
    assert len(motifs) == 1
    assert motifs[0].startswith("« −31 % » introuvable dans P1 ; Conseil personnalisé : « Vendez »")
    assert (tri.rejetes_chiffres, tri.rejetes_cadre) == (1, 1)


# --- Contrôle cadre_simulation du contrat ------------------------------------------------

def test_controle_conforme_avec_le_nombre_d_arguments():
    requisitoire = trier_arguments([argument("La pire chute passe de −7,8 % à −29,0 %.")], "requisitoire", DOSSIER)
    plaidoirie = trier_arguments([argument("Le rendement annualisé passe à +12,0 %.")], "plaidoirie", DOSSIER)
    assert controle_cadre_simulation(requisitoire, plaidoirie) == {
        "statut": "conforme",
        "regle": "cadre_simulation",
        "message": "Aucun conseil personnalisé ni promesse sur l'avenir : 2 arguments vérifiés",
    }


def test_controle_compte_ses_propres_rejets():
    """Un rejet pour un conseil est compté par cadre_simulation, pas par verifier_chiffres."""
    requisitoire = trier_arguments([argument("La pire chute passe de −7,8 % à −29,0 %.")], "requisitoire", DOSSIER)
    plaidoirie = trier_arguments([argument("Achetez TSLA.")], "plaidoirie", DOSSIER, lambda arg, motif: arg)
    assert controle_cadre_simulation(requisitoire, plaidoirie)["message"] == (
        "Aucun conseil personnalisé ni promesse sur l'avenir : 1 argument vérifié ; "
        "1 argument rejeté après une relance"
    )
    assert controle_verifier_chiffres(requisitoire, plaidoirie)["message"] == (
        "Chiffres cités vérifiés contre leurs pièces : 2/2 chiffres, 1 argument"
    )


def test_controle_sans_argument_a_verifier():
    tri = trier_arguments([argument("Achetez TSLA.")], "plaidoirie", DOSSIER)
    assert controle_cadre_simulation(tri)["statut"] == "a_verifier"


# --- Vrais arguments ----------------------------------------------------------------------

@pytest.mark.parametrize("chemin", [
    *sorted((RACINE / "docs" / "exemples").glob("contrat_*.json")),
    *sorted((RACINE / "frontend" / "src" / "data" / "proces").glob("[!i]*.json")),  # procès réels enregistrés
], ids=lambda chemin: f"{chemin.parent.name}/{chemin.name}")
def test_tous_les_arguments_des_contrats_enregistres_passent(chemin):
    contrat = json.loads(chemin.read_text(encoding="utf-8"))
    arguments = contrat["requisitoire"] + contrat["plaidoirie"]
    assert arguments
    assert [a["texte"] for a in arguments if not verifier_cadre_simulation(a).valide] == []
