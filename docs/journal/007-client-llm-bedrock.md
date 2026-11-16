# #7 — Accès à Amazon Bedrock et client LLM commun

- **Issue** : #7 · **PR** : #25 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`pipeline/llm.py`** : le client LLM commun à tous les agents (Agent Profil #8, orchestrateur #12, Procureur et Avocat #11), basé sur l'API **Converse** de Bedrock.
  - `appeler_llm(systeme, message, schema_sortie=None)` : un message, une réponse. Sans schéma, renvoie le texte. Avec un schéma, Bedrock contraint la sortie JSON, puis Python la revalide avec `jsonschema`.
  - `converser_avec_outils(systeme, conversation, outils)` : un tour de conversation avec *tool use*, pour la boucle de l'orchestrateur. Renvoie un `TourOutils` (les `DemandeOutil` du modèle et son message tel quel).
  - Fonctions d'aide : `decrire_outil`, `message_utilisateur`, `resultat_outil`, `message_resultats`.
  - `ErreurLLM` : configuration manquante, réponse coupée, JSON invalide ou non conforme.
  - Relances automatiques (mode `adaptive` de boto3, 7 essais au total), délai de lecture de 300 s, client partagé entre threads pour les appels en parallèle.
- **`.env.example`** : `AWS_REGION` et `BEDROCK_MODEL_ID`. `.env` reste ignoré par Git.
- **`requirements.txt`** (pipeline, déployé dans Lambda) et **`requirements-dev.txt`** (poste local), versions épinglées.
- **`pyproject.toml`** : les tests marqués `bedrock` (payants) ne tournent que sur demande.
- **`tests/test_llm.py`** : tests unitaires sans réseau (Bedrock remplacé par `botocore.stub.Stubber`) et 3 vrais appels marqués `bedrock`.

## Comment l'utiliser
```python
from pipeline.llm import appeler_llm

schema = {"type": "object", "properties": {"ticker": {"type": "string"}},
          "required": ["ticker"], "additionalProperties": False}
decision = appeler_llm("Tu extrais le titre demandé.", "30 % en Tesla", schema)
```
La docstring du module montre la boucle complète de l'orchestrateur avec `converser_avec_outils`.

## Comment vérifier
```bash
pytest                # tests unitaires, sans réseau ni AWS
pytest -m bedrock     # 3 vrais appels Bedrock (payants, quelques jetons)
```
Configuration du poste : voir « Installation (guide court) » dans le `README.md` de la racine.

## Choix faits en cours de route
- **Modèles** : `us.anthropic.claude-sonnet-5-5` pour les agents, `us.anthropic.claude-haiku-5-5` (moins cher) pour les tests ; on change avec `BEDROCK_MODEL_ID`, sans toucher au code.
- **Région `us-east-1`** : sur ce compte, les modèles Claude s'appellent **uniquement par profil d'inférence** (préfixe `us.` ou `global.`).
- **Aucune clé dans le code** : les identifiants viennent de `aws login`, qui exige `botocore[crt]`.
- **Organisation** : code dans le paquet `pipeline/`, tests dans `tests/`.

## Limites et suite
- **Unités** : sans consigne, Haiku a rendu `"taille": 30` pour « 30 % ». Les prompts doivent préciser que les tailles sont des décimales (#8).
- **Schémas** : chaque objet doit déclarer `"additionalProperties": false`, et chaque schéma d'outil lister ses champs dans `required`.
- **On ne peut pas forcer un outil** : les modèles Claude récents refusent un `toolChoice` forcé. La pièce obligatoire est ajoutée d'office par Python (#12).
- **La conversation ne fait que grandir** : ne jamais modifier ni retirer un message, car Bedrock exige de retrouver intacts les blocs de réflexion du modèle.
- Le budget de 8 appels d'outils est compté par la boucle de l'orchestrateur (#12), pas par ce client.
- **Python** : développement en 3.14 ; la version commune doit être alignée sur celle de Lambda (#22).
