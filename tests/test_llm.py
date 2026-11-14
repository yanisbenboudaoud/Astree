"""Tests du client LLM commun (pipeline/llm.py).

Les tests unitaires remplacent Bedrock par un faux (botocore Stubber) : ils ne
coûtent rien et tournent sans accès AWS. Le test réel (marqueur « bedrock »)
fait un vrai appel payant ; il ne tourne qu'avec « pytest -m bedrock ».
"""

import json

import boto3
import jsonschema
import pytest
from botocore.stub import ANY, Stubber

from pipeline import llm

SCHEMA_DECISION = {
    "type": "object",
    "properties": {"ticker": {"type": "string"}, "taille": {"type": "number"}},
    "required": ["ticker", "taille"],
    "additionalProperties": False,
}


def reponse_converse(blocs, motif_arret="end_turn"):
    """Construit une réponse Converse minimale, au format de Bedrock."""
    return {
        "output": {"message": {"role": "assistant", "content": blocs}},
        "stopReason": motif_arret,
        "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
        "metrics": {"latencyMs": 100},
    }


@pytest.fixture
def faux_bedrock(monkeypatch):
    """Remplace le client Bedrock par un faux qui rejoue des réponses prévues."""
    monkeypatch.setenv("BEDROCK_MODEL_ID", "modele-de-test")
    client = boto3.client(
        "bedrock-runtime",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    monkeypatch.setattr(llm, "_client_bedrock", lambda: client)
    with Stubber(client) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()


def test_renvoie_le_texte_sans_les_blocs_de_reflexion(faux_bedrock):
    faux_bedrock.add_response(
        "converse",
        reponse_converse([
            {"reasoningContent": {"reasoningText": {"text": "je réfléchis", "signature": "x"}}},
            {"text": "Bonjour"},
        ]),
    )
    assert llm.appeler_llm("Tu es poli.", "Salut") == "Bonjour"


def test_envoie_le_modele_le_systeme_et_le_message(faux_bedrock):
    faux_bedrock.add_response(
        "converse",
        reponse_converse([{"text": "OK"}]),
        expected_params={
            "modelId": "modele-de-test",
            "system": [{"text": "Consignes"}],
            "messages": [{"role": "user", "content": [{"text": "Question"}]}],
            "inferenceConfig": ANY,
        },
    )
    llm.appeler_llm("Consignes", "Question")


def test_avec_schema_renvoie_le_json_valide(faux_bedrock):
    faux_bedrock.add_response(
        "converse",
        reponse_converse([{"text": '{"ticker": "TSLA", "taille": 0.30}'}]),
        expected_params={
            "modelId": ANY,
            "system": ANY,
            "messages": ANY,
            "inferenceConfig": ANY,
            "outputConfig": {
                "textFormat": {
                    "type": "json_schema",
                    "structure": {
                        "jsonSchema": {"name": "sortie", "schema": json.dumps(SCHEMA_DECISION)}
                    },
                }
            },
        },
    )
    resultat = llm.appeler_llm("Extrais la décision.", "30 % en Tesla", SCHEMA_DECISION)
    assert resultat == {"ticker": "TSLA", "taille": 0.30}


def test_rejette_une_reponse_qui_n_est_pas_du_json(faux_bedrock):
    faux_bedrock.add_response("converse", reponse_converse([{"text": "pas du JSON"}]))
    with pytest.raises(llm.ErreurLLM, match="non JSON"):
        llm.appeler_llm("s", "m", SCHEMA_DECISION)


def test_rejette_un_json_non_conforme_au_schema(faux_bedrock):
    faux_bedrock.add_response("converse", reponse_converse([{"text": '{"ticker": "TSLA"}'}]))
    with pytest.raises(llm.ErreurLLM, match="non conforme"):
        llm.appeler_llm("s", "m", SCHEMA_DECISION)


def test_rejette_une_reponse_coupee(faux_bedrock):
    faux_bedrock.add_response(
        "converse", reponse_converse([{"text": "Début de répo"}], motif_arret="max_tokens")
    )
    with pytest.raises(llm.ErreurLLM, match="max_tokens"):
        llm.appeler_llm("s", "m")


def test_rejette_un_schema_invalide_avant_tout_appel(faux_bedrock):
    # Aucune réponse prévue : un appel à Bedrock ferait échouer le faux client.
    with pytest.raises(jsonschema.SchemaError):
        llm.appeler_llm("s", "m", {"type": "objet_inconnu"})


def test_exige_l_identifiant_du_modele(monkeypatch):
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    with pytest.raises(llm.ErreurLLM, match="BEDROCK_MODEL_ID"):
        llm.appeler_llm("s", "m")


@pytest.mark.bedrock
def test_appel_reel_a_bedrock():
    """Vrai appel Bedrock (payant, quelques jetons). Lancer avec : pytest -m bedrock"""
    reponse = llm.appeler_llm(
        "Tu extrais une décision d'investissement. La taille est une décimale (0.30 = 30 %).",
        "Je veux mettre 30 % de mon portefeuille en Tesla",
        SCHEMA_DECISION,
    )
    assert reponse["ticker"] == "TSLA"
    assert reponse["taille"] == pytest.approx(0.30)
