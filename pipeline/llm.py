"""Client LLM commun : appelle un modèle Claude via Amazon Bedrock (API Converse).

Règle d'or du projet : Python calcule, le LLM explique. Ce module ne calcule
rien : il transmet les messages au modèle et renvoie ses réponses.

Deux usages :

1. ``appeler_llm`` : un message, une réponse (texte libre ou JSON validé contre
   un schéma). Pour l'Agent Profil, le Procureur et l'Avocat.

2. ``converser_avec_outils`` : un tour de conversation où le modèle peut
   demander des outils (*tool use*). Pour la boucle de l'orchestrateur (#12) ::

       outils = [decrire_outil("indicateurs_actif", "…", schema)]
       conversation = [message_utilisateur(dossier)]
       while True:
           tour = converser_avec_outils(systeme, conversation, outils)
           conversation.append(tour.message_assistant)   # tel quel
           if tour.termine:
               break
           blocs = [resultat_outil(d, executer(d)) for d in tour.demandes]
           conversation.append(message_resultats(blocs))  # tous les résultats ensemble

   La conversation ne fait que grandir : on n'en modifie ni n'en retire jamais
   un message. Les messages du modèle sont renvoyés tels quels, avec leurs
   blocs de réflexion, que Bedrock exige de retrouver intacts au tour suivant.

Appels en parallèle : le client Bedrock est partagé et peut servir plusieurs
threads à la fois. Le Procureur et l'Avocat peuvent donc être appelés en même
temps avec ``concurrent.futures.ThreadPoolExecutor``.

Mesure (#189) : pendant ``with compter_appels() as compteur:``, chaque appel
Converse est compté (jetons lus et écrits, durée mesurée par Bedrock) au nom de
l'agent déclaré par ``with au_nom_de("procureur"):`` dans son fil d'exécution.
``compteur.resume()`` donne le champ ``bedrock`` du contrat. Un seul compteur
actif par processus : une Lambda ne traite qu'un procès à la fois.

Guardrail (#189) : si BEDROCK_GUARDRAIL_ID est défini, ``verifier_garde_fou``
soumet un texte au Guardrail Amazon Bedrock (API ApplyGuardrail) : la demande et
la question de l'utilisateur à l'entrée (attaque de consigne), chaque argument à
la sortie (sujet refusé : conseil personnalisé ou promesse de rendement). Sans
cette variable (tests, local), rien n'est soumis.

Configuration, par variables d'environnement (jamais en dur dans le code) :
- BEDROCK_MODEL_ID : identifiant du profil d'inférence,
  ex. « global.anthropic.claude-sonnet-5-5 ». Sur ce compte, les modèles Claude
  s'appellent par leur profil d'inférence (préfixe « global. » ou « us. »), pas
  par leur identifiant brut.
- AWS_REGION : région Bedrock, ex. « us-east-1 ».
- BEDROCK_GUARDRAIL_ID et BEDROCK_GUARDRAIL_VERSION (facultatifs) : le Guardrail
  créé par ``deploiement/deployer.py`` et sa version publiée.

Les identifiants AWS viennent de la chaîne standard de boto3 : « aws login » en
local, rôle IAM dans Lambda. Aucune clé n'apparaît dans le code.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

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

# Relances automatiques en cas de limitation de débit (ThrottlingException) ou
# d'erreur passagère, fréquentes sur un compte neuf (issue #22, point 4).
# Le mode « adaptive » attend de plus en plus longtemps entre deux essais
# (attente exponentielle avec part aléatoire) et ralentit aussi le rythme des
# appels suivants quand Bedrock signale une limitation. « max_attempts: 6 »
# compte les relances : jusqu'à 7 essais au total.
CONFIG_BOTO = Config(
    retries={"mode": "adaptive", "max_attempts": 6},
    read_timeout=DELAI_LECTURE_S,
)

# Tarif public de Sonnet 5.5 sur Bedrock, en dollars américains par million de
# jetons, relevé le 2026-11-15 (docs/validation/evaluation_orchestrateur.md).
# Hypothèse : sert seulement à estimer le coût d'un procès, jamais facturé ici.
TARIF_ENTREE_USD_PAR_MILLION = 2.0
TARIF_SORTIE_USD_PAR_MILLION = 10.0

_verrou_client = threading.Lock()
_client = None  # client Bedrock partagé, créé au premier appel


class ErreurLLM(Exception):
    """Le modèle n'a pas rendu une réponse exploitable (ou la configuration manque)."""


class RefusGardeFou(Exception):
    """Le Guardrail Bedrock a refusé le texte de l'utilisateur (attaque de consigne)."""


@dataclass(frozen=True)
class DemandeOutil:
    """Un outil que le modèle demande d'exécuter."""

    id: str  # toolUseId, à reprendre dans le résultat
    nom: str
    entree: dict[str, Any]


@dataclass(frozen=True)
class TourOutils:
    """Réponse du modèle pour un tour de conversation avec outils."""

    message_assistant: dict[str, Any]  # à ajouter tel quel à la conversation
    demandes: list[DemandeOutil]  # outils demandés ; vide quand le modèle a fini
    texte: str  # texte écrit par le modèle pendant ce tour (peut être vide)

    @property
    def termine(self) -> bool:
        return not self.demandes


# --- Mesure des appels (#189) -------------------------------------------------


@dataclass
class Compteur:
    """Appels Bedrock d'un procès : par agent, jetons lus et écrits, durée mesurée par Bedrock."""

    appels: list[dict[str, Any]] = field(default_factory=list)
    garde_fou: list[bool] = field(default_factory=list)  # une entrée par vérification : intervenu ?
    _verrou: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def noter(self, agent: str, reponse: dict[str, Any]) -> None:
        usage = reponse.get("usage", {})
        with self._verrou:
            self.appels.append({
                "agent": agent,
                "jetons_entree": int(usage.get("inputTokens", 0)),
                "jetons_sortie": int(usage.get("outputTokens", 0)),
                "duree_ms": int(reponse.get("metrics", {}).get("latencyMs", 0)),
            })

    def noter_garde_fou(self, intervenu: bool) -> None:
        with self._verrou:
            self.garde_fou.append(intervenu)

    def resume(self) -> dict[str, Any]:
        """Champ ``bedrock`` du contrat : totaux, coût estimé et détail par agent, dans l'ordre d'apparition."""
        with self._verrou:
            appels, garde_fou = list(self.appels), list(self.garde_fou)
        par_agent: dict[str, dict[str, Any]] = {}
        for appel in appels:
            ligne = par_agent.setdefault(appel["agent"], {"agent": appel["agent"], "appels": 0,
                                                          "jetons_entree": 0, "jetons_sortie": 0})
            ligne["appels"] += 1
            ligne["jetons_entree"] += appel["jetons_entree"]
            ligne["jetons_sortie"] += appel["jetons_sortie"]
        entree = sum(a["jetons_entree"] for a in appels)
        sortie = sum(a["jetons_sortie"] for a in appels)
        resume = {
            "modele": os.environ.get("BEDROCK_MODEL_ID", "").strip() or "inconnu",
            "appels": len(appels),
            "jetons_entree": entree,
            "jetons_sortie": sortie,
            "duree_bedrock_s": round(sum(a["duree_ms"] for a in appels) / 1000, 1),
            "cout_estime_usd": round((entree * TARIF_ENTREE_USD_PAR_MILLION
                                      + sortie * TARIF_SORTIE_USD_PAR_MILLION) / 1_000_000, 4),
            "par_agent": list(par_agent.values()),
        }
        if garde_fou:
            resume["garde_fou"] = {"verifications": len(garde_fou), "interventions": sum(garde_fou)}
        return resume


_compteur: Compteur | None = None
_agent = threading.local()


@contextmanager
def compter_appels() -> Iterator[Compteur]:
    """Compte les appels Bedrock faits pendant le bloc, dans tous les fils d'exécution."""
    global _compteur
    precedent, _compteur = _compteur, Compteur()
    try:
        yield _compteur
    finally:
        _compteur = precedent


@contextmanager
def au_nom_de(agent: str) -> Iterator[None]:
    """Attribue à ``agent`` les appels faits pendant le bloc, dans ce fil d'exécution."""
    precedent = getattr(_agent, "nom", None)
    _agent.nom = agent
    try:
        yield
    finally:
        _agent.nom = precedent


def _noter(reponse: dict[str, Any]) -> None:
    if _compteur is not None:
        _compteur.noter(getattr(_agent, "nom", None) or "autre", reponse)


# --- Guardrail Amazon Bedrock (#189) -------------------------------------------


def garde_fou_actif() -> bool:
    """Vrai si un Guardrail est configuré (BEDROCK_GUARDRAIL_ID)."""
    return bool(os.environ.get("BEDROCK_GUARDRAIL_ID", "").strip())


def verifier_garde_fou(texte: str, source: str) -> str | None:
    """Soumet un texte au Guardrail Bedrock ; renvoie le motif s'il intervient, sinon None.

    Args:
        texte: la demande ou la question de l'utilisateur (``source="INPUT"``), ou le texte
            d'un argument (``source="OUTPUT"``).
        source: « INPUT » ou « OUTPUT » : le Guardrail n'applique que ses filtres de ce côté.

    Sans Guardrail configuré, rien n'est soumis et la fonction renvoie None.
    """
    identifiant = os.environ.get("BEDROCK_GUARDRAIL_ID", "").strip()
    if not identifiant:
        return None
    reponse = _client_bedrock().apply_guardrail(
        guardrailIdentifier=identifiant,
        guardrailVersion=os.environ.get("BEDROCK_GUARDRAIL_VERSION", "").strip() or "DRAFT",
        source=source,
        content=[{"text": {"text": texte}}],
    )
    intervenu = reponse.get("action") == "GUARDRAIL_INTERVENED"
    if _compteur is not None:
        _compteur.noter_garde_fou(intervenu)
    return motif_garde_fou(reponse) if intervenu else None


def motif_garde_fou(reponse: dict[str, Any]) -> str:
    """Motif lisible d'une intervention du Guardrail : sujets refusés et filtres déclenchés."""
    raisons = []
    for evaluation in reponse.get("assessments", []):
        for sujet in evaluation.get("topicPolicy", {}).get("topics", []):
            raisons.append(f"sujet refusé « {sujet.get('name', '?')} »")
        for filtre in evaluation.get("contentPolicy", {}).get("filters", []):
            if filtre.get("type") == "PROMPT_ATTACK":
                raisons.append("tentative de détourner les consignes des agents")
            else:
                raisons.append(f"filtre « {filtre.get('type', '?')} »")
    detail = ", ".join(dict.fromkeys(raisons)) or "intervention sans détail"
    return f"Guardrail Bedrock : {detail}"


# --- Usage 1 : un message, une réponse --------------------------------------


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
    requete = _requete_de_base(systeme, [message_utilisateur(message)])
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
    _noter(reponse)
    _verifier_motif_arret(reponse, {"end_turn"})
    texte = _extraire_texte(reponse)
    if not texte:
        raise ErreurLLM("Le modèle n'a renvoyé aucun texte.")
    if schema_sortie is None:
        return texte
    return _decoder_et_valider_json(texte, schema_sortie)


# --- Usage 2 : conversation avec outils (orchestrateur) ---------------------


def converser_avec_outils(
    systeme: str,
    conversation: list[dict[str, Any]],
    outils: list[dict[str, Any]],
) -> TourOutils:
    """Fait jouer un tour au modèle, qui peut répondre ou demander des outils.

    Args:
        systeme: consignes de l'agent.
        conversation: messages échangés jusqu'ici (format Converse). Le premier
            vient de ``message_utilisateur`` ; ensuite alternent les
            ``message_assistant`` des tours précédents et les
            ``message_resultats``. Cette liste n'est pas modifiée.
        outils: descriptions créées avec ``decrire_outil``.

    Returns:
        Un ``TourOutils``. Si ``termine`` est faux, exécuter chaque demande en
        Python, puis rappeler cette fonction avec la conversation complétée.

    Raises:
        ErreurLLM: configuration manquante ou réponse incomplète.
    """
    requete = _requete_de_base(systeme, conversation)
    # Choix d'outil laissé au modèle (« auto », la valeur par défaut) : les
    # modèles Claude récents refusent qu'on leur impose un outil précis.
    requete["toolConfig"] = {"tools": outils}

    reponse = _client_bedrock().converse(**requete)
    _noter(reponse)
    _verifier_motif_arret(reponse, {"end_turn", "tool_use"})
    message = reponse["output"]["message"]
    demandes = [
        DemandeOutil(id=bloc["toolUse"]["toolUseId"], nom=bloc["toolUse"]["name"],
                     entree=bloc["toolUse"]["input"])
        for bloc in message["content"]
        if "toolUse" in bloc
    ]
    return TourOutils(message_assistant=message, demandes=demandes,
                      texte=_extraire_texte(reponse))


def decrire_outil(nom: str, description: str, schema_entree: dict[str, Any]) -> dict[str, Any]:
    """Décrit un outil Python au modèle (nom, rôle, schéma JSON des paramètres).

    Le mode strict oblige le modèle à fournir des paramètres conformes au
    schéma. Le schéma doit donc lister ses champs dans « required » et
    déclarer « "additionalProperties": false ».
    """
    jsonschema.Draft202012Validator.check_schema(schema_entree)
    return {
        "toolSpec": {
            "name": nom,
            "description": description,
            "inputSchema": {"json": schema_entree},
            "strict": True,
        }
    }


def message_utilisateur(texte: str) -> dict[str, Any]:
    """Message de l'utilisateur (ou de Python) au format Converse."""
    return {"role": "user", "content": [{"text": texte}]}


def resultat_outil(demande: DemandeOutil, contenu: dict[str, Any],
                   erreur: bool = False) -> dict[str, Any]:
    """Résultat d'un outil, à renvoyer au modèle.

    Args:
        demande: la demande à laquelle ce résultat répond.
        contenu: sortie de l'outil (dict JSON), ou description de l'erreur.
        erreur: vrai si l'outil a échoué ; le modèle en est informé au lieu
            de recevoir un faux résultat.
    """
    return {
        "toolResult": {
            "toolUseId": demande.id,
            "content": [{"json": contenu}],
            "status": "error" if erreur else "success",
        }
    }


def message_resultats(blocs: list[dict[str, Any]]) -> dict[str, Any]:
    """Regroupe dans un seul message les résultats de toutes les demandes d'un tour.

    Les résultats d'un même tour doivent partir ensemble : un message par
    résultat pousserait le modèle à ne plus demander plusieurs outils à la fois.
    """
    if not blocs:
        raise ValueError("Aucun résultat d'outil à envoyer.")
    return {"role": "user", "content": blocs}


# --- Fonctions internes -----------------------------------------------------


def _requete_de_base(systeme: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "modelId": _identifiant_modele(),
        "system": [{"text": systeme}],
        "messages": messages,
        # Pas de « temperature » : les modèles Claude récents refusent les
        # valeurs autres que celle par défaut.
        "inferenceConfig": {"maxTokens": MAX_JETONS_SORTIE},
    }


def _identifiant_modele() -> str:
    """Lit l'identifiant du modèle dans l'environnement, sans valeur par défaut."""
    identifiant = os.environ.get("BEDROCK_MODEL_ID", "").strip()
    if not identifiant:
        raise ErreurLLM(
            "Variable d'environnement BEDROCK_MODEL_ID absente "
            "(ex. : global.anthropic.claude-sonnet-5-5). Voir .env.example."
        )
    return identifiant


def _client_bedrock():
    """Renvoie le client Bedrock, créé une seule fois par processus.

    Le même client sert d'un appel Lambda à l'autre. Le verrou empêche deux
    threads de le créer en même temps : la création d'un client boto3 n'est pas
    sûre entre threads (son utilisation, si).
    """
    global _client
    with _verrou_client:
        if _client is None:
            _client = boto3.session.Session().client(
                "bedrock-runtime",
                region_name=os.environ.get("AWS_REGION") or None,
                config=CONFIG_BOTO,
            )
        return _client


def _verifier_motif_arret(reponse: dict[str, Any], motifs_acceptes: set[str]) -> None:
    motif_arret = reponse.get("stopReason")
    if motif_arret not in motifs_acceptes:
        raise ErreurLLM(f"Réponse incomplète du modèle (stopReason : {motif_arret}).")


def _extraire_texte(reponse: dict[str, Any]) -> str:
    """Assemble les blocs de texte de la réponse.

    Les blocs de réflexion (« reasoningContent ») et les demandes d'outils
    sont ignorés : seul le texte écrit par le modèle est renvoyé.
    """
    blocs = reponse["output"]["message"]["content"]
    return "".join(bloc["text"] for bloc in blocs if "text" in bloc).strip()


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
