# Déploiement AWS : paramètres vérifiés (#22)

Référence pour le déploiement (#13). Chaque valeur a été vérifiée sur le compte de l'événement le 2026-11-14 ; le pourquoi est dans l'issue #22.

## Lambda

| Paramètre | Valeur | Pourquoi |
|---|---|---|
| Runtime | `python3.14`, architecture `x86_64` | Même version que les postes de l'équipe ; la couche pandas existe pour 3.14 |
| Couche | `arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python314:12` | Couche gérée par AWS : pandas 3.1.0, numpy 2.5.4, pyarrow 24.0.0, les mêmes versions que `requirements-dev.txt` |
| Délai | 300 s | Procès complet mesuré : de 18 à 27 s en local, environ 33 s au pire observé, plus le démarrage à froid et une éventuelle relance du Greffier |
| Mémoire | 1024 Mo au moins | pandas et les CSV ; plus de mémoire donne aussi plus de processeur |
| Concurrence réservée | 2 | Limite les appels Bedrock payants. Le compte laisse 110 exécutions non réservées : en réserver 2 est possible |
| Variables d'environnement | `BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-5-5`, `SOURCE_DONNEES=local` tant que la lecture S3 n'existe pas (#13) | Ne pas définir `AWS_REGION` : Lambda la fournit elle-même (us-east-1) |

**Données en mémoire** : `pipeline/donnees.py` garde les CSV en mémoire après la première lecture (`lru_cache`). Le module d'entrée de la Lambda doit importer le pipeline **au niveau du module**, hors du handler, pour qu'une Lambda déjà démarrée ne relise pas les CSV.

## Contenu du zip

Les dépendances de `requirements.txt` (boto3, jsonschema), **en version Linux**, plus le code et les données :

```powershell
pip install -r requirements.txt --platform manylinux2014_x86_64 --implementation cp --python-version 3.14 --only-binary=:all: --target build
# puis copier dans build/ : pipeline/, contrat/, personas/, config/, alphaforge_starter/*.csv
```

- **Ne pas** y mettre pandas, numpy ni pyarrow : ils viennent de la couche.
- **Y mettre boto3** : il n'est pas dans la couche, et celui du runtime peut être trop ancien pour la sortie JSON structurée de Bedrock (`outputConfig`).
- **Taille décompressée** : 218 Mo sur les 250 permis (couche 190 Mo, dépendances 24 Mo, CSV 4 Mo, code 0,2 Mo). La marge est de 32 Mo : n'ajoutez pas de grosse bibliothèque.

## Point d'accès : Lambda Function URL

- **Pourquoi pas API Gateway** : il coupe la requête après environ 29 s, et un procès complet dure de 18 à 33 s avant même l'outil 4 (#21). La démo échouerait par moments avec une erreur 504.
- Type d'authentification `NONE` (l'interface appelle directement), avec **CORS limité au domaine de l'interface** : `AllowOrigins` = ce domaine seul, `AllowMethods` = `POST`, `AllowHeaders` = `content-type`.
- Vérifier avec un `curl` après la création, puis **supprimer l'adresse après le jury** (`aws lambda delete-function-url-config`).

## IAM

Le rôle de la Lambda utilise [`politique_iam_lambda.json`](politique_iam_lambda.json), en remplaçant `NOM_DU_BUCKET` :
- `bedrock:InvokeModel` sur le **profil d'inférence** `us.anthropic.claude-sonnet-5-5` **et** sur le modèle dans les **trois régions** vers lesquelles le profil répartit les appels : us-east-1, us-east-2 et us-west-2. Sans ces trois régions, certains appels échoueraient au hasard.
- Les journaux CloudWatch, et la lecture et l'écriture dans le bucket du projet.
- Si `BEDROCK_MODEL_ID` change, mettre la politique à jour (`aws bedrock get-inference-profile` donne les régions du profil).

## Bedrock

- Région `us-east-1`, profil `us.anthropic.claude-sonnet-5-5`. Quota : 6 millions de jetons par minute, bien au-delà d'un procès.
- Les relances adaptatives et le délai de lecture de 300 s sont déjà dans `pipeline/llm.py` (#7).
- **Vérifié** : 5 procès complets d'affilée, soit 25 appels Converse, sans aucune relance de boto3 ni erreur de limitation.
