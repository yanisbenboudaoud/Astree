"""Tests du Procureur et de l'Avocat (pipeline/debat.py).

Les tests unitaires remplacent le LLM par une fonction écrite à la main. Les
tests réels (marqueur « bedrock ») font plaider les deux agents sur les pièces
des faux contrats de docs/exemples/ : on peut commencer avant les vrais outils
de calcul (#6, #9).

La vérification des chiffres cités (verifier_chiffres, #10) n'existe pas
encore : les tests réels affichent les arguments (pytest -m bedrock -s) pour
une relecture humaine, en attendant de les passer au Greffier.
"""

import json
import threading
from pathlib import Path

import jsonschema
import pytest

from pipeline import debat

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
    assert corrige["texte"] == "Le rendement annualisé serait de +12,0 %."
    assert etape["etape"] == "avocat" and etape["outil"] == "bedrock_correction"
    valide_contre_le_contrat(etape, "etape_trace")


# --- Vrais appels Bedrock (payants) : pytest -m bedrock -s ------------------------


@pytest.mark.bedrock
@pytest.mark.parametrize("exemple", ["contrat_robert", "contrat_amira"])
def test_debat_reel_sur_un_faux_contrat(exemple):
    dossier = dossier_depuis_exemple(exemple)
    ids = {piece["id"] for piece in dossier["pieces"]}

    resultat = debat.debattre(dossier)

    print(f"\n===== {exemple} : {dossier['decision']['libelle']}")
    for cote, arguments in (("RÉQUISITOIRE", resultat.requisitoire), ("PLAIDOIRIE", resultat.plaidoirie)):
        print(f"--- {cote}")
        for argument in arguments:
            print(f"[{argument['etiquette']}] {argument['texte']}  ({', '.join(argument['pieces'])})")
        assert 1 <= len(arguments) <= 5
        for argument in arguments:
            valide_contre_le_contrat(argument, "argument")
            assert set(argument["pieces"]) <= ids


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
