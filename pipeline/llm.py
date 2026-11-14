"""Client LLM commun : appelle un modèle Claude via Amazon Bedrock (API Converse).

Règle d'or du projet : Python calcule, le LLM explique. Ce module ne calcule
rien : il envoie un message au modèle et renvoie sa réponse, en texte libre ou
en JSON validé contre un schéma.

Configuration, par variables d'environnement (jamais en dur dans le code) :
- BEDROCK_MODEL_ID : identifiant du profil d'inférence,
  ex. « us.anthropic.claude-sonnet-5-5 ». Sur ce compte, les modèles Claude
  s'appellent par leur profil d'inférence (préfixe « us. »), pas par leur
  identifiant brut.
- AWS_REGION : région Bedrock, ex. « us-east-1 ».

Les identifiants AWS viennent de la chaîne standard de boto3 : « aws login » en
local, rôle IAM dans Lambda. Aucune clé n'apparaît dans le code.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

import boto3
import jsonschema
from botocore.config import Config

# Plafond de jetons générés par réponse. Un plafond trop bas coupe la réponse
# en plein milieu (stopReason « max_tokens ») ; seuls les jetons réellement
# générés sont facturés.
MAX_JETONS_SORTIE = 16000

# boto3 abandonne une réponse après 60 s par défaut : trop court pour une longue
# plaidoirie. On s'aligne sur le délai visé pour la Lambda (issue #22).
DELAI_LECTURE_S = 300

# Relances automatiques en cas de limitation de débit (ThrottlingException),
# fréquente sur un compte neuf (issue #22, point 4).
CONFIG_BOTO = Config(
    retries={"mode": "adaptive", "max_attempts": 6},
    read_timeout=DELAI_LECTURE_S,
)


class ErreurLLM(Exception):
    """Le modèle n'a pas rendu une réponse exploitable (ou la configuration manque)."""


def appeler_llm(
    systeme: str,
    message: str,
    schema_sortie: dict[str, Any] | None = None,
) -> Any:
    """Envoie un message au modèle et renvoie sa réponse.

    Args:
        systeme: consignes de l'agent (rôle, règles, format attendu).
        message: contenu de la demande.
        schema_sortie: schéma JSON (JSON Schema) de la réponse attendue. S'il est
            fourni, Bedrock contraint le modèle à ce schéma, puis Python revérifie
            la réponse. Chaque objet du schéma doit déclarer
            « "additionalProperties": false ».

    Returns:
        Le texte de la réponse si aucun schéma n'est donné, sinon le JSON décodé
        (en général un dict), déjà validé contre le schéma.

    Raises:
        ErreurLLM: configuration manquante, réponse incomplète, JSON invalide ou
            non conforme au schéma.
    """
    requete: dict[str, Any] = {
        "modelId": _identifiant_modele(),
        "system": [{"text": systeme}],
        "messages": [{"role": "user", "content": [{"text": message}]}],
        # Pas de « temperature » : les modèles Claude récents refusent les
        # valeurs autres que celle par défaut.
        "inferenceConfig": {"maxTokens": MAX_JETONS_SORTIE},
    }
    if schema_sortie is not None:
        # Vérifie le schéma avant de payer un appel Bedrock.
        jsonschema.Draft202012Validator.check_schema(schema_sortie)
        requete["outputConfig"] = {
            "textFormat": {
                "type": "json_schema",
                "structure": {
                    "jsonSchema": {"name": "sortie", "schema": json.dumps(schema_sortie)}
                },
            }
        }

    reponse = _client_bedrock().converse(**requete)
    texte = _extraire_texte(reponse)
    if schema_sortie is None:
        return texte
    return _decoder_et_valider_json(texte, schema_sortie)


def _identifiant_modele() -> str:
    """Lit l'identifiant du modèle dans l'environnement, sans valeur par défaut."""
    identifiant = os.environ.get("BEDROCK_MODEL_ID", "").strip()
    if not identifiant:
        raise ErreurLLM(
            "Variable d'environnement BEDROCK_MODEL_ID absente "
            "(ex. : us.anthropic.claude-sonnet-5-5). Voir .env.example."
        )
    return identifiant


@lru_cache(maxsize=1)
def _client_bedrock():
    """Crée le client Bedrock une seule fois par processus (réutilisé entre appels Lambda)."""
    return boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION") or None,
        config=CONFIG_BOTO,
    )


def _extraire_texte(reponse: dict[str, Any]) -> str:
    """Assemble les blocs de texte de la réponse.

    Les blocs de réflexion du modèle (« reasoningContent ») sont ignorés : seul
    le texte final est renvoyé.
    """
    motif_arret = reponse.get("stopReason")
    if motif_arret != "end_turn":
        raise ErreurLLM(f"Réponse incomplète du modèle (stopReason : {motif_arret}).")

    blocs = reponse["output"]["message"]["content"]
    texte = "".join(bloc["text"] for bloc in blocs if "text" in bloc).strip()
    if not texte:
        raise ErreurLLM("Le modèle n'a renvoyé aucun texte.")
    return texte


def _decoder_et_valider_json(texte: str, schema: dict[str, Any]) -> Any:
    """Décode le texte en JSON et vérifie qu'il respecte le schéma."""
    try:
        donnees = json.loads(texte)
    except json.JSONDecodeError as erreur:
        raise ErreurLLM(f"Réponse non JSON : {erreur.msg}.") from erreur

    try:
        jsonschema.validate(donnees, schema, cls=jsonschema.Draft202012Validator)
    except jsonschema.ValidationError as erreur:
        raise ErreurLLM(f"Réponse non conforme au schéma : {erreur.message}.") from erreur
    return donnees
