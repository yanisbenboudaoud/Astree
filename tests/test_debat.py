"""Tests du Procureur et de l'Avocat (pipeline/debat.py).

Les tests unitaires remplacent le LLM par une fonction écrite à la main. Les
tests réels (marqueur « bedrock ») font plaider les deux agents, sur les pièces
des faux contrats de docs/exemples/ et sur les vraies pièces d'un procès, puis
passent chaque argument au Greffier (verifier_chiffres, #10). Ajouter « -s »
pour lire les arguments.
"""

import json
import threading
from pathlib import Path

import jsonschema
import pytest

from pipeline import debat
from pipeline.chiffres import controle_verifier_chiffres, trier_arguments, verifier_argument
from pipeline.donnees import seances_americaines
from pipeline.tribunal import juger_decision

RACINE = Path(__file__).resolve().parent.parent
SCHEMA_CONTRAT = json.loads((RACINE / "contrat" / "schema_sortie.json").read_text(encoding="utf-8"))
PERIODE = ["2021-11-12", "2026-11-12"]


def valide_contre_le_contrat(objet, definition):
    schema = {"$ref": f"#/$defs/{definition}", "$defs": SCHEMA_CONTRAT["$defs"]}
    jsonschema.validate(objet, schema, cls=jsonschema.Draft202012Validator)


def dossier_depuis_exemple(nom):
    """Dossier du débat construit à partir d'un faux contrat de docs/exemples/."""
    contrat = json.loads((RACINE / "docs" / "exemples" / f"{nom}.json").read_text(encoding="utf-8"))
    return {
        "decision": contrat["decision"],
        "pacte": contrat["pacte"],
        "pieces": contrat["pieces"],
        "periode": PERIODE,
    }


DOSSIER = dossier_depuis_exemple("contrat_robert")
IDS_PIECES = [piece["id"] for piece in DOSSIER["pieces"]]


# --- Partie Python ---------------------------------------------------------------


def test_schema_limite_les_pieces_citees_a_celles_du_dossier():
    schema = debat.schema_arguments(IDS_PIECES)
    jsonschema.Draft202012Validator.check_schema(schema)
    pieces = schema["properties"]["arguments"]["items"]["properties"]["pieces"]
    assert pieces["items"]["enum"] == IDS_PIECES
    assert pieces["minItems"] == 1


def test_message_contient_le_dossier_sans_les_champs_inutiles():
    message = debat.construire_message(DOSSIER)
    assert "TSLA" in message
    assert "Préserver mon capital" in message
    assert "du 2021-11-12 au 2026-11-12" in message
    assert "-0.2897" in message  # valeurs brutes des pièces
    assert "Yahoo Finance" not in message  # la source n'est pas transmise


def test_les_deux_roles_partagent_les_regles_sur_les_chiffres():
    for role in ("procureur", "avocat"):
        assert debat.REGLES_COMMUNES in debat.CONSIGNES[role]
    assert "CONTRE" in debat.CONSIGNES["procureur"]
    assert "HONNÊTEMENT" in debat.CONSIGNES["avocat"]


def test_consignes_rappellent_le_cadre_simulation():
    """#60 : aucun conseil, aucune promesse, dans les deux rôles et dans le mode correction."""
    assert "A. Aucun conseil" in debat.REGLES_COMMUNES
    assert "B. Aucune promesse ni prévision" in debat.REGLES_COMMUNES


def test_plaider_nettoie_les_arguments_et_ecrit_la_trace(monkeypatch):
    def faux_llm(systeme, message, schema):
        return {"arguments": [
            {"etiquette": "fait", "texte": "  La pire chute passe de −7,8 % à −29,0 %.  ",
             "pieces": ["P1", "P3", "P1"]},
        ]}
    monkeypatch.setattr(debat, "appeler_llm", faux_llm)

    arguments, etape = debat.plaider("procureur", DOSSIER)

    assert arguments == [{"etiquette": "fait", "texte": "La pire chute passe de −7,8 % à −29,0 %.",
                          "pieces": ["P1", "P3"]}]
    assert etape == {"etape": "procureur", "outil": "bedrock", "entree": IDS_PIECES,
                     "sortie": arguments}
    valide_contre_le_contrat(arguments[0], "argument")
    valide_contre_le_contrat(etape, "etape_trace")


def test_debattre_appelle_les_deux_roles_en_parallele(monkeypatch):
    # Chaque appel attend l'autre : si les deux n'étaient pas lancés en même
    # temps, la barrière expirerait et le test échouerait.
    barriere = threading.Barrier(2, timeout=5)

    def faux_llm(systeme, message, schema):
        barriere.wait()
        cote = "contre" if "Procureur" in systeme else "pour"
        return {"arguments": [{"etiquette": "fait", "texte": f"Argument {cote}.", "pieces": ["P1"]}]}
    monkeypatch.setattr(debat, "appeler_llm", faux_llm)

    resultat = debat.debattre(DOSSIER)

    assert resultat.requisitoire[0]["texte"] == "Argument contre."
    assert resultat.plaidoirie[0]["texte"] == "Argument pour."
    assert [etape["etape"] for etape in resultat.trace] == ["procureur", "avocat"]


def test_debattre_signale_chaque_role_des_qu_il_repond(monkeypatch):
    """#90 : l'Avocat répond avant le Procureur, il est signalé le premier ; la trace garde l'ordre fixe."""
    procureur_peut_repondre = threading.Event()
    signales = []

    def faux_llm(systeme, message, schema):
        if "Procureur" in systeme:
            assert procureur_peut_repondre.wait(timeout=5)
            return {"arguments": [{"etiquette": "fait", "texte": "Contre.", "pieces": ["P1"]}]}
        return {"arguments": [{"etiquette": "fait", "texte": "Pour.", "pieces": ["P1"]}]}

    def signaler(etape):
        signales.append(etape["etape"])
        procureur_peut_repondre.set()

    monkeypatch.setattr(debat, "appeler_llm", faux_llm)
    resultat = debat.debattre(DOSSIER, signaler_etape=signaler)

    assert signales == ["avocat", "procureur"]
    assert [etape["etape"] for etape in resultat.trace] == ["procureur", "avocat"]


def test_corriger_argument_transmet_le_motif_du_greffier(monkeypatch):
    recu = {}

    def faux_llm(systeme, message, schema):
        recu["message"] = message
        return {"etiquette": "fait", "texte": "Le rendement annualisé serait de +12,0 %.",
                "pieces": ["P1"]}
    monkeypatch.setattr(debat, "appeler_llm", faux_llm)
    refuse = {"etiquette": "fait", "texte": "Le rendement serait de +12,5 %.", "pieces": ["P1"]}

    corrige, etape = debat.corriger_argument("avocat", DOSSIER, refuse, "« +12,5 % » introuvable dans P1")

    assert "« +12,5 % » introuvable dans P1" in recu["message"]
    assert "Le rendement serait de +12,5 %." in recu["message"]
    assert "sans recommander de transaction ni présenter l'avenir comme certain" in recu["message"]
    assert corrige["texte"] == "Le rendement annualisé serait de +12,0 %."
    assert etape["etape"] == "avocat" and etape["outil"] == "bedrock_correction"
    valide_contre_le_contrat(etape, "etape_trace")


# --- Vrais appels Bedrock (payants) : pytest -m bedrock -s ------------------------


def passer_au_greffier(dossier, resultat):
    """Affiche les arguments, puis les fait trier par le Greffier (une relance au plus).

    Returns:
        (arguments refusés au premier jet, tris du réquisitoire et de la plaidoirie)
    """
    refuses = []
    tris = []
    for role, cote, arguments in (("procureur", "requisitoire", resultat.requisitoire),
                                  ("avocat", "plaidoirie", resultat.plaidoirie)):
        print(f"--- {cote.upper()}")
        for argument in arguments:
            verification = verifier_argument(argument, dossier)
            print(f"[{'OK ' if verification.valide else 'NON'}] [{argument['etiquette']}] "
                  f"{argument['texte']}  ({', '.join(argument['pieces'])})")
            if not verification.valide:
                refuses.append(verification.motif)

        def corriger(argument, motif, role=role):
            return debat.corriger_argument(role, dossier, argument, motif)[0]

        tris.append(trier_arguments(arguments, cote, dossier, corriger))
    print(controle_verifier_chiffres(*tris)["message"], f"; refusés au premier jet : {refuses}")
    return refuses, tris


@pytest.mark.bedrock
@pytest.mark.parametrize("exemple", ["contrat_robert", "contrat_amira"])
def test_debat_reel_sur_un_faux_contrat(exemple):
    dossier = dossier_depuis_exemple(exemple)
    ids = {piece["id"] for piece in dossier["pieces"]}

    resultat = debat.debattre(dossier)

    print(f"\n===== {exemple} : {dossier['decision']['libelle']}")
    for arguments in (resultat.requisitoire, resultat.plaidoirie):
        assert 1 <= len(arguments) <= 5
        for argument in arguments:
            valide_contre_le_contrat(argument, "argument")
            assert set(argument["pieces"]) <= ids
    _, tris = passer_au_greffier(dossier, resultat)
    assert all(not tri.rejetes for tri in tris), [tri.rejetes for tri in tris]


@pytest.mark.bedrock
@pytest.mark.parametrize("identifiant, demande", [
    ("robert", "Je veux mettre 30 % de mon portefeuille en Tesla"),        # cas de démo (cas 1)
    ("mateo", "Je veux ajouter 10 % d'Exxon Mobil à mon portefeuille"),
])
def test_proces_reel_tous_les_chiffres_passent_le_greffier(identifiant, demande):
    """Critère de fin de #11 : vraies pièces (Agent Profil + orchestrateur), débat, Greffier."""
    contrat = juger_decision(identifiant, demande)
    seances = seances_americaines()
    dossier = {
        "decision": contrat["decision"],
        "pacte": contrat["pacte"],
        "pieces": contrat["pieces"],
        "periode": [seances[0].date().isoformat(), seances[-1].date().isoformat()],
    }

    resultat = debat.debattre(dossier)

    print(f"\n===== {identifiant} : {contrat['decision']['libelle']} ; pièces "
          f"{[piece['id'] + ' ' + piece['titre'] for piece in contrat['pieces']]}")
    _, tris = passer_au_greffier(dossier, resultat)
    assert all(not tri.rejetes for tri in tris), [tri.rejetes for tri in tris]
    assert controle_verifier_chiffres(*tris)["statut"] == "conforme"


@pytest.mark.bedrock
def test_correction_reelle_d_un_nombre_derive():
    """Argument rejeté du faux contrat du cas 2 : un ratio inventé (« 4 fois plus »)."""
    dossier = dossier_depuis_exemple("contrat_amira")
    rejete = json.loads((RACINE / "docs" / "exemples" / "contrat_amira.json")
                        .read_text(encoding="utf-8"))["arguments_rejetes"][0]
    argument = {champ: rejete[champ] for champ in ("etiquette", "texte", "pieces")}

    corrige, _ = debat.corriger_argument("avocat", dossier, argument, rejete["raison"])

    print(f"\nAvant : {argument['texte']}\nAprès : {corrige['texte']}  ({', '.join(corrige['pieces'])})")
    assert "4 fois" not in corrige["texte"]
    valide_contre_le_contrat(corrige, "argument")


# --- Réplique (#189) ---------------------------------------------------------------

POUR = [{"etiquette": "fait", "texte": "Le rendement serait de +12,0 % par an.", "pieces": ["P1"]},
        {"etiquette": "fait", "texte": "Votre horizon est long.", "pieces": ["P1"]}]
CONTRE = [{"etiquette": "fait", "texte": "La pire chute passe de −7,8 % à −29,0 %.", "pieces": ["P1"]}]


def test_repliquer_vise_un_argument_adverse_par_son_numero(monkeypatch):
    recu = {}

    def faux_llm(systeme, message, schema):
        recu.update(systeme=systeme, message=message, schema=schema)
        return {"repond_a": 2, "etiquette": "fait", "texte": " Votre Pacte fixe une pire baisse. ",
                "pieces": ["P3", "P3"]}
    monkeypatch.setattr(debat, "appeler_llm", faux_llm)

    replique = debat.repliquer("procureur", DOSSIER, POUR)

    assert recu["systeme"] == debat.CONSIGNES["procureur"]
    assert "Arguments de l'Avocat" in recu["message"] and debat.CONSIGNE_REPLIQUE in recu["message"]
    assert recu["schema"]["properties"]["repond_a"] == {"type": "integer", "enum": [1, 2]}
    assert recu["schema"]["required"][0] == "repond_a"
    assert replique.cible is POUR[1]  # le même objet : le Tribunal le retrouve dans la liste finale
    assert replique.argument == {"etiquette": "fait", "texte": "Votre Pacte fixe une pire baisse.", "pieces": ["P3"]}
    assert replique.etape == {"etape": "procureur", "outil": "bedrock_replique",
                              "entree": {"repond_a": 2, "argument": "Votre horizon est long."},
                              "sortie": replique.argument}
    valide_contre_le_contrat(replique.etape, "etape_trace")


def test_repliquer_les_deux_en_parallele_et_sans_adversaire_pas_de_replique(monkeypatch):
    def faux_llm(systeme, message, schema):
        return {"repond_a": 1, "etiquette": "fait", "texte": "Réponse.", "pieces": ["P1"]}
    monkeypatch.setattr(debat, "appeler_llm", faux_llm)
    signales = []

    repliques = debat.repliquer_les_deux(DOSSIER, CONTRE, POUR, signaler_etape=signales.append)
    assert [r.role for r in repliques] == ["procureur", "avocat"]
    assert [r.cible for r in repliques] == [POUR[0], CONTRE[0]]
    assert sorted(e["etape"] for e in signales) == ["avocat", "procureur"]

    seul = debat.repliquer_les_deux(DOSSIER, CONTRE, [])  # l'Avocat n'a rien dit : le Procureur ne réplique pas
    assert [r.role for r in seul] == ["avocat"]
