"""Tests de l'Agent Profil (pipeline/agent_profil.py).

Les tests unitaires vérifient la partie Python (validation, calculs, trace)
avec des extractions écrites à la main : ils n'appellent pas le LLM. Les tests
réels (marqueur « bedrock ») envoient de vraies demandes au modèle.
"""

import json
from pathlib import Path

import jsonschema
import pytest

from pipeline import agent_profil
from pipeline.agent_profil import (
    ProfilInconnu,
    formater_part,
    interpreter_extraction,
    lancer_agent_profil,
    structurer_decision,
)
from pipeline.pacte import PacteInvalide
from pipeline.univers import charger_univers

RACINE = Path(__file__).resolve().parent.parent
UNIVERS = charger_univers()
SCHEMA_CONTRAT = json.loads((RACINE / "contrat" / "schema_sortie.json").read_text(encoding="utf-8"))
CONTRAT_ROBERT = json.loads(
    (RACINE / "docs" / "exemples" / "contrat_robert.json").read_text(encoding="utf-8")
)


def charger_profil(identifiant):
    return json.loads((RACINE / "personas" / f"{identifiant}.json").read_text(encoding="utf-8"))


def valide_contre_le_contrat(objet, definition):
    """Vérifie un objet contre une définition ($defs) du schéma du contrat."""
    schema = {"$ref": f"#/$defs/{definition}", "$defs": SCHEMA_CONTRAT["$defs"]}
    jsonschema.validate(objet, schema, cls=jsonschema.Draft202012Validator)


def extraction(**champs):
    """Extraction du LLM, complète par défaut : « 30 % en Tesla »."""
    valeurs = {
        "type_decision": "position",
        "actif_mentionne": "Tesla",
        "ticker": "TSLA",
        "taille": 0.30,
        "montant": None,
        "devise_montant": "non_precisee",
        "panier": [],
        "actifs_hors_univers": [],
        "financement_depuis": None,
        "ambiguites": [],
    }
    valeurs.update(champs)
    return valeurs


PANIER_DEMO = [  # panier de la décision de démo du profil audacieux
    {"ticker": "BTC-USD", "poids": 0.3}, {"ticker": "ETH-USD", "poids": 0.2},
    {"ticker": "NVDA", "poids": 0.2}, {"ticker": "QQQ", "poids": 0.2}, {"ticker": "SHOP.TO", "poids": 0.1},
]


def extraction_reallocation(**champs):
    """Extraction du LLM pour « tout réallouer vers le panier de démo »."""
    valeurs = {"type_decision": "reallocation", "actif_mentionne": "panier crypto-tech",
               "ticker": None, "taille": 1.0, "panier": PANIER_DEMO}
    valeurs.update(champs)
    return extraction(**valeurs)


PROFIL_PRUDENT = charger_profil("robert")


# --- Partie Python : validation et calculs -----------------------------------


def test_position_complete():
    decision, controles, hypotheses = interpreter_extraction(extraction(), PROFIL_PRUDENT, UNIVERS)
    assert decision == {
        "type": "position", "ticker": "TSLA", "taille": 0.30,
        "financement": "proportionnel", "libelle": "30 % en TSLA",
    }
    assert controles == []
    assert any("proportionnel" in h for h in hypotheses)
    valide_contre_le_contrat(decision, "decision")


def test_titre_hors_univers_aucune_decision():
    decision, controles, _ = interpreter_extraction(
        extraction(actif_mentionne="Netflix", ticker=None), PROFIL_PRUDENT, UNIVERS
    )
    assert decision is None
    assert controles[0]["statut"] == "a_verifier"
    assert controles[0]["regle"] == "interpretation_demande"
    assert "Netflix" in controles[0]["message"]


def test_taille_absente_aucune_decision():
    decision, controles, _ = interpreter_extraction(extraction(taille=None), PROFIL_PRUDENT, UNIVERS)
    assert decision is None
    assert "Taille absente" in controles[0]["message"]


def test_montant_converti_en_part_par_python():
    decision, controles, hypotheses = interpreter_extraction(
        extraction(taille=None, montant=50000, devise_montant="CAD"), PROFIL_PRUDENT, UNIVERS
    )
    assert decision["taille"] == pytest.approx(50000 / 650000)
    assert decision["libelle"] == "7,7 % en TSLA"
    assert controles == []
    assert any("50 000 $" in h and "650 000 $ CAD" in h for h in hypotheses)


def test_montant_sans_devise_interprete_en_cad_et_signale():
    decision, _, hypotheses = interpreter_extraction(
        extraction(taille=None, montant=50000), PROFIL_PRUDENT, UNIVERS
    )
    assert decision is not None
    assert any("dollars canadiens" in h for h in hypotheses)


def test_montant_en_usd_non_converti():
    decision, controles, _ = interpreter_extraction(
        extraction(taille=None, montant=50000, devise_montant="USD"), PROFIL_PRUDENT, UNIVERS
    )
    assert decision is None
    assert "USD" in controles[0]["message"]


def test_part_et_montant_ensemble_non_tranches():
    decision, controles, _ = interpreter_extraction(
        extraction(taille=0.3, montant=50000), PROFIL_PRUDENT, UNIVERS
    )
    assert decision is None
    assert "à la fois" in controles[0]["message"]


@pytest.mark.parametrize("taille", [0, 30, 1.5])
def test_taille_hors_limites_refusee(taille):
    decision, controles, _ = interpreter_extraction(extraction(taille=taille), PROFIL_PRUDENT, UNIVERS)
    assert decision is None
    assert "comprise entre 0 et 100 %" in controles[0]["message"]


def test_decision_non_reconnue_signalee():
    decision, controles, _ = interpreter_extraction(
        extraction(type_decision="autre", ticker=None), PROFIL_PRUDENT, UNIVERS
    )
    assert decision is None
    assert "Décision non reconnue" in controles[0]["message"]


# --- Réallocations (#16) ---------------------------------------------------------


def test_reallocation_avec_panier_explicite():
    decision, controles, hypotheses = interpreter_extraction(
        extraction_reallocation(), charger_profil("amira"), UNIVERS
    )
    assert decision == {
        "type": "reallocation",
        "panier": PANIER_DEMO,
        "part_reallouee": 1.0,
        "libelle": "100 % réalloué vers BTC-USD 30 %, ETH-USD 20 %, NVDA 20 %, QQQ 20 % et SHOP.TO 10 %",
    }
    assert controles == []
    assert any("prorata" in h for h in hypotheses)
    valide_contre_le_contrat(decision, "decision")


def test_reallocation_identique_a_la_decision_de_demo():
    profil = charger_profil("amira")
    decision, _, _ = interpreter_extraction(extraction_reallocation(), profil, UNIVERS)
    attendu = profil["decision_demo"]
    assert decision["panier"] == attendu["panier"]
    assert decision["part_reallouee"] == attendu["part_reallouee"]


def test_panier_vague_aucune_decision():
    decision, controles, _ = interpreter_extraction(
        extraction_reallocation(panier=[]), PROFIL_PRUDENT, UNIVERS
    )
    assert decision is None
    assert "Composition du panier « panier crypto-tech » non précisée" in controles[0]["message"]


def test_titre_du_panier_hors_univers():
    decision, controles, _ = interpreter_extraction(
        extraction_reallocation(actifs_hors_univers=["Solana"]), PROFIL_PRUDENT, UNIVERS
    )
    assert decision is None
    assert "Solana" in controles[0]["message"]


def test_titre_en_double_dans_le_panier():
    panier = [{"ticker": "NVDA", "poids": 0.5}, {"ticker": "NVDA", "poids": 0.5}]
    decision, controles, _ = interpreter_extraction(
        extraction_reallocation(panier=panier), PROFIL_PRUDENT, UNIVERS
    )
    assert decision is None
    assert "deux fois" in controles[0]["message"]


def test_poids_arrondis_ajustes_a_100():
    panier = [{"ticker": t, "poids": 0.3333} for t in ("BTC-USD", "ETH-USD", "NVDA")]
    decision, controles, hypotheses = interpreter_extraction(
        extraction_reallocation(panier=panier), PROFIL_PRUDENT, UNIVERS
    )
    assert controles == []
    assert sum(ligne["poids"] for ligne in decision["panier"]) == pytest.approx(1.0, abs=1e-9)
    assert any("99,99 %" in h for h in hypotheses)
    valide_contre_le_contrat(decision, "decision")


def test_poids_qui_ne_totalisent_pas_100_aucune_decision():
    panier = [{"ticker": "BTC-USD", "poids": 0.5}, {"ticker": "ETH-USD", "poids": 0.3}]
    decision, controles, _ = interpreter_extraction(
        extraction_reallocation(panier=panier), PROFIL_PRUDENT, UNIVERS
    )
    assert decision is None
    assert "totalisent 80 %" in controles[0]["message"]


def test_part_reallouee_absente_aucune_decision():
    decision, controles, _ = interpreter_extraction(
        extraction_reallocation(taille=None), PROFIL_PRUDENT, UNIVERS
    )
    assert decision is None
    assert "Part réallouée absente" in controles[0]["message"]


def test_part_reallouee_depuis_un_montant():
    decision, _, hypotheses = interpreter_extraction(
        extraction_reallocation(taille=None, montant=65000, devise_montant="CAD"), PROFIL_PRUDENT, UNIVERS
    )
    assert decision["part_reallouee"] == pytest.approx(0.1)
    assert decision["libelle"].startswith("10 % réalloué vers")


def test_financement_ignore_pour_une_reallocation():
    decision, controles, _ = interpreter_extraction(
        extraction_reallocation(financement_depuis="ZST.TO"), PROFIL_PRUDENT, UNIVERS
    )
    assert decision is not None
    assert "prorata" in controles[0]["message"]


def test_ambiguite_signalee_sans_bloquer():
    decision, controles, _ = interpreter_extraction(
        extraction(ambiguites=["« environ 30 % » : taille approximative"]), PROFIL_PRUDENT, UNIVERS
    )
    assert decision is not None
    assert controles[0]["statut"] == "a_verifier"
    assert "environ 30 %" in controles[0]["message"]


def test_financement_depuis_un_titre_du_portefeuille():
    decision, controles, hypotheses = interpreter_extraction(
        extraction(financement_depuis="ZST.TO"), PROFIL_PRUDENT, UNIVERS
    )
    assert decision["financement"] == "depuis_ZST.TO"
    assert decision["libelle"] == "30 % en TSLA, financé par ZST.TO"
    assert controles == []
    assert not any("proportionnel" in h for h in hypotheses)
    valide_contre_le_contrat(decision, "decision")


def test_financement_depuis_un_titre_absent_du_portefeuille():
    decision, controles, _ = interpreter_extraction(
        extraction(financement_depuis="AAPL"), PROFIL_PRUDENT, UNIVERS
    )
    assert decision["financement"] == "proportionnel"
    assert "AAPL" in controles[0]["message"]


@pytest.mark.parametrize("part, texte", [
    (0.30, "30 %"), (0.1, "10 %"), (1.0, "100 %"), (50000 / 650000, "7,7 %"), (0.3333, "33,3 %"),
])
def test_formater_part(part, texte):
    assert formater_part(part) == texte


def test_schema_d_extraction_limite_les_tickers():
    schema = agent_profil.schema_extraction(UNIVERS, PROFIL_PRUDENT)
    jsonschema.Draft202012Validator.check_schema(schema)
    tickers = schema["properties"]["ticker"]["anyOf"][0]["enum"]
    assert "TSLA" in tickers and len(tickers) == len(UNIVERS)
    financement = schema["properties"]["financement_depuis"]["anyOf"][0]["enum"]
    assert set(financement) == {ligne["ticker"] for ligne in PROFIL_PRUDENT["portefeuille"]}


def test_structurer_decision_ecrit_la_trace(monkeypatch):
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: extraction())
    resultat = structurer_decision("Je veux mettre 30 % de mon portefeuille en Tesla",
                                   PROFIL_PRUDENT, UNIVERS)
    assert resultat.decision["ticker"] == "TSLA"
    assert [etape["outil"] for etape in resultat.trace] == ["bedrock", "valider_decision"]
    for etape in resultat.trace:
        valide_contre_le_contrat(etape, "etape_trace")


# --- Point d'entrée : chargement du Pacte, puis décision ----------------------


def llm_interdit(*args):
    raise AssertionError("Le LLM ne doit pas être appelé si le profil est refusé")


def test_lancer_agent_profil_charge_le_pacte_puis_structure(monkeypatch):
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: extraction())
    resultat = lancer_agent_profil("Je veux mettre 30 % de mon portefeuille en Tesla", "robert", "P3")

    assert resultat.decision["ticker"] == "TSLA"
    assert resultat.profil["portefeuille"] == PROFIL_PRUDENT["portefeuille"]
    # Le pacte et la pièce sont ceux attendus par l'interface dans le faux contrat.
    assert resultat.pacte == CONTRAT_ROBERT["pacte"]
    piece_p3 = next(p for p in CONTRAT_ROBERT["pieces"] if p["id"] == "P3")
    assert resultat.piece_pacte == piece_p3

    assert resultat.trace[0] == {
        "etape": "agent_profil", "outil": "charger_pacte", "entree": "robert", "sortie": "P3",
    }
    assert [etape["outil"] for etape in resultat.trace] == [
        "charger_pacte", "bedrock", "valider_decision",
    ]
    for etape in resultat.trace:
        valide_contre_le_contrat(etape, "etape_trace")


@pytest.mark.parametrize("identifiant", ["robert", "amira", "mateo"])
def test_chaque_profil_de_test_se_charge(monkeypatch, identifiant):
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: extraction())
    resultat = lancer_agent_profil("30 % en Tesla", identifiant, "P1")
    assert resultat.profil["id"] == identifiant
    valide_contre_le_contrat(resultat.pacte, "pacte")
    valide_contre_le_contrat(resultat.piece_pacte, "piece")


def test_profil_invente_se_charge_sans_changer_le_code(monkeypatch, tmp_path):
    profil = charger_profil("robert") | {"id": "inventee", "nom": "Inventée"}
    (tmp_path / "inventee.json").write_text(json.dumps(profil), encoding="utf-8")
    monkeypatch.setattr(agent_profil, "DOSSIER_PERSONAS", tmp_path)
    monkeypatch.setattr(agent_profil, "appeler_llm", lambda *args: extraction())

    resultat = lancer_agent_profil("30 % en Tesla", "inventee", "P1")
    assert resultat.pacte["id"] == "inventee"
    assert resultat.decision is not None


@pytest.mark.parametrize("identifiant", [
    "inconnu", "Robert", "../personas/robert", "robert.json", "", "schema_pacte", None,
])
def test_profil_inconnu_refuse_avant_le_llm(monkeypatch, identifiant):
    monkeypatch.setattr(agent_profil, "appeler_llm", llm_interdit)
    with pytest.raises(ProfilInconnu):
        lancer_agent_profil("30 % en Tesla", identifiant, "P1")


def test_pacte_invalide_refuse_avant_le_llm(monkeypatch, tmp_path):
    profil = charger_profil("robert") | {"id": "casse"}
    del profil["pacte"]["regles"][0]["seuil"]
    (tmp_path / "casse.json").write_text(json.dumps(profil), encoding="utf-8")
    monkeypatch.setattr(agent_profil, "DOSSIER_PERSONAS", tmp_path)
    monkeypatch.setattr(agent_profil, "appeler_llm", llm_interdit)

    with pytest.raises(PacteInvalide):
        lancer_agent_profil("30 % en Tesla", "casse", "P1")


# --- Vrais appels Bedrock (payants) : pytest -m bedrock -----------------------

DEMANDES_DEMO = [
    # (profil de test, demande, décision attendue ou None si elle ne peut pas être construite)
    ("robert", "Je veux mettre 30 % de mon portefeuille en Tesla", "decision_demo"),
    ("mateo", "Je veux ajouter 10 % d'Exxon Mobil à mon portefeuille", "decision_demo"),
    ("amira", "Je veux réallouer tout mon portefeuille vers un panier : 30 % Bitcoin, 20 % Ether, "
              "20 % Nvidia, 20 % QQQ et 10 % Shopify", "decision_demo"),
    # Le panier n'est pas décrit : il n'est jamais complété au hasard.
    ("amira", "Je veux tout réallouer vers un panier crypto-tech", None),
]


@pytest.mark.bedrock
@pytest.mark.parametrize("identifiant, demande, attendu", DEMANDES_DEMO)
def test_demande_de_demo_de_chaque_profil(identifiant, demande, attendu):
    resultat = lancer_agent_profil(demande, identifiant, "P1")
    profil = resultat.profil
    if attendu is None:
        assert resultat.decision is None
        assert resultat.controles and all(c["statut"] == "a_verifier" for c in resultat.controles)
        return
    decision_demo = profil["decision_demo"]
    assert resultat.decision["type"] == decision_demo["type"]
    if decision_demo["type"] == "position":
        assert resultat.decision["ticker"] == decision_demo["ticker"]
        assert resultat.decision["financement"] == decision_demo["financement"]
        assert resultat.decision["taille"] == pytest.approx(decision_demo["taille"])
    else:
        assert resultat.decision["panier"] == decision_demo["panier"]
        assert resultat.decision["part_reallouee"] == pytest.approx(decision_demo["part_reallouee"])


FORMULATIONS = [
    # (demande, ticker attendu, taille attendue, financement attendu)
    ("Ajoute 30% de TSLA", "TSLA", 0.30, "proportionnel"),
    ("Je voudrais placer un tiers de mon portefeuille dans Apple", "AAPL", 1 / 3, "proportionnel"),
    ("Je veux investir 50 000 $ CAD dans Microsoft", "MSFT", 50000 / 650000, "proportionnel"),
    ("Mets 20 % en Tesla en vendant mes obligations ultra court terme", "TSLA", 0.20, "depuis_ZST.TO"),
]


@pytest.mark.bedrock
@pytest.mark.parametrize("demande, ticker, taille, financement", FORMULATIONS)
def test_formulations_variees(demande, ticker, taille, financement):
    resultat = structurer_decision(demande, PROFIL_PRUDENT, UNIVERS)
    assert resultat.decision is not None, resultat.controles
    assert resultat.decision["ticker"] == ticker
    assert resultat.decision["taille"] == pytest.approx(taille, abs=1e-3)
    assert resultat.decision["financement"] == financement


@pytest.mark.bedrock
def test_reallocation_partielle_reelle():
    resultat = structurer_decision(
        "Je veux réallouer la moitié de mon portefeuille vers 60 % Apple et 40 % Microsoft",
        PROFIL_PRUDENT, UNIVERS,
    )
    assert resultat.decision is not None, resultat.controles
    assert resultat.decision["part_reallouee"] == pytest.approx(0.5)
    assert resultat.decision["panier"] == [{"ticker": "AAPL", "poids": 0.6}, {"ticker": "MSFT", "poids": 0.4}]


@pytest.mark.bedrock
@pytest.mark.parametrize("demande, mot_attendu", [
    ("Je veux mettre 10 % en Netflix", "Netflix"),
    ("Je veux acheter des actions Nvidia", "Taille absente"),
    ("Je veux réallouer 20 % de mon portefeuille vers 50 % Bitcoin et 50 % Solana", "Solana"),
])
def test_demande_incomplete_signalee_sans_deviner(demande, mot_attendu):
    resultat = structurer_decision(demande, PROFIL_PRUDENT, UNIVERS)
    assert resultat.decision is None
    assert any(mot_attendu in c["message"] for c in resultat.controles), resultat.controles
