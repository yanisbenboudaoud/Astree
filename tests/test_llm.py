"""Tests du client LLM commun (pipeline/llm.py).

Les tests unitaires remplacent Bedrock par un faux (botocore Stubber) : ils ne
coûtent rien et tournent sans accès AWS. Le test réel (marqueur « bedrock »)
fait un vrai appel payant ; il ne tourne qu'avec « pytest -m bedrock ».
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor

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

# Outil factice, sur le modèle de l'outil 1 (indicateurs_actif).
OUTIL_FACTICE = llm.decrire_outil(
    "indicateurs_actif",
    "Calcule les indicateurs d'un titre (rendement, volatilité, pire baisse) à partir des CSV.",
    {
        "type": "object",
        "properties": {"ticker": {"type": "string", "description": "Symbole du titre, ex. TSLA"}},
        "required": ["ticker"],
        "additionalProperties": False,
    },
)


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


def test_client_configure_avec_relances_et_delai(monkeypatch):
    monkeypatch.setattr(llm, "_client", None)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    client = llm._client_bedrock()
    # boto3 note « max_attempts: 6 » (relances) en « total_max_attempts: 7 » (1 essai + 6 relances).
    assert client.meta.config.retries == {"mode": "adaptive", "total_max_attempts": 7}
    assert client.meta.config.read_timeout == llm.DELAI_LECTURE_S
    assert llm._client_bedrock() is client  # créé une seule fois


# --- Conversation avec outils (orchestrateur) --------------------------------


def test_outils_renvoie_les_demandes_et_le_message_tel_quel(faux_bedrock):
    message_modele = [
        {"reasoningContent": {"reasoningText": {"text": "il faut les chiffres", "signature": "x"}}},
        {"text": "Je consulte les indicateurs."},
        {"toolUse": {"toolUseId": "id-1", "name": "indicateurs_actif", "input": {"ticker": "TSLA"}}},
    ]
    conversation = [llm.message_utilisateur("Quelle est la volatilité de TSLA ?")]
    faux_bedrock.add_response(
        "converse",
        reponse_converse(message_modele, motif_arret="tool_use"),
        expected_params={
            "modelId": ANY,
            "system": ANY,
            "messages": conversation,
            "inferenceConfig": ANY,
            "toolConfig": {"tools": [OUTIL_FACTICE]},
        },
    )
    tour = llm.converser_avec_outils("Tu es l'orchestrateur.", conversation, [OUTIL_FACTICE])

    assert tour.demandes == [llm.DemandeOutil("id-1", "indicateurs_actif", {"ticker": "TSLA"})]
    assert not tour.termine
    assert tour.texte == "Je consulte les indicateurs."
    # Renvoyé tel quel, avec le bloc de réflexion, pour le tour suivant.
    assert tour.message_assistant == {"role": "assistant", "content": message_modele}


def test_outils_tour_final_sans_demande(faux_bedrock):
    faux_bedrock.add_response(
        "converse", reponse_converse([{"text": "Dossier complet."}], motif_arret="end_turn")
    )
    tour = llm.converser_avec_outils("s", [llm.message_utilisateur("m")], [OUTIL_FACTICE])
    assert tour.termine
    assert tour.demandes == []
    assert tour.texte == "Dossier complet."


def test_outils_rejette_une_reponse_coupee(faux_bedrock):
    faux_bedrock.add_response(
        "converse", reponse_converse([{"text": "…"}], motif_arret="max_tokens")
    )
    with pytest.raises(llm.ErreurLLM, match="max_tokens"):
        llm.converser_avec_outils("s", [llm.message_utilisateur("m")], [OUTIL_FACTICE])


def test_resultats_d_un_tour_regroupes_dans_un_seul_message():
    d1 = llm.DemandeOutil("id-1", "indicateurs_actif", {"ticker": "TSLA"})
    d2 = llm.DemandeOutil("id-2", "indicateurs_actif", {"ticker": "INCONNU"})
    message = llm.message_resultats([
        llm.resultat_outil(d1, {"volatilite_annuelle": 0.5734}),
        llm.resultat_outil(d2, {"erreur": "Titre absent de l'univers"}, erreur=True),
    ])
    assert message == {
        "role": "user",
        "content": [
            {"toolResult": {"toolUseId": "id-1", "content": [{"json": {"volatilite_annuelle": 0.5734}}],
                            "status": "success"}},
            {"toolResult": {"toolUseId": "id-2", "content": [{"json": {"erreur": "Titre absent de l'univers"}}],
                            "status": "error"}},
        ],
    }


def test_message_resultats_refuse_une_liste_vide():
    with pytest.raises(ValueError):
        llm.message_resultats([])


def test_decrire_outil_active_le_mode_strict():
    spec = OUTIL_FACTICE["toolSpec"]
    assert spec["name"] == "indicateurs_actif"
    assert spec["strict"] is True
    assert spec["inputSchema"]["json"]["required"] == ["ticker"]


# --- Vrais appels Bedrock (payants) : pytest -m bedrock -----------------------


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


@pytest.mark.bedrock
def test_appel_reel_avec_outil_factice():
    """Le modèle demande l'outil, reçoit le résultat, puis répond avec ce chiffre."""
    systeme = (
        "Tu es l'orchestrateur d'un dossier d'investissement. Tu ne calcules rien : "
        "pour tout chiffre, appelle l'outil indicateurs_actif. N'invente aucun chiffre. "
        "Exprime les volatilités en pourcentage."
    )
    conversation = [llm.message_utilisateur("Quelle est la volatilité annuelle de TSLA ?")]

    tour = llm.converser_avec_outils(systeme, conversation, [OUTIL_FACTICE])
    assert not tour.termine, "le modèle aurait dû demander l'outil"
    assert tour.demandes[0].nom == "indicateurs_actif"
    assert tour.demandes[0].entree == {"ticker": "TSLA"}

    conversation.append(tour.message_assistant)
    conversation.append(llm.message_resultats([
        llm.resultat_outil(d, {"ticker": "TSLA", "volatilite_annuelle": 0.5734})
        for d in tour.demandes
    ]))
    tour_final = llm.converser_avec_outils(systeme, conversation, [OUTIL_FACTICE])
    assert tour_final.termine
    assert "57" in tour_final.texte  # le chiffre de l'outil (57,3 %) est repris


@pytest.mark.bedrock
def test_deux_appels_reels_en_parallele():
    """Procureur et Avocat seront appelés en même temps : vérifier que ça marche."""
    def appel(cote):
        debut = time.perf_counter()
        texte = llm.appeler_llm(f"Tu es l'{cote}. Réponds en une phrase courte.",
                                "Présente-toi.")
        return texte, time.perf_counter() - debut

    debut = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as executeur:
        resultats = list(executeur.map(appel, ["accusation", "défense"]))
    duree_totale = time.perf_counter() - debut

    assert all(texte for texte, _ in resultats)
    durees = [duree for _, duree in resultats]
    print(f"\nDurées : {durees[0]:.2f} s et {durees[1]:.2f} s ; total en parallèle : {duree_totale:.2f} s")
