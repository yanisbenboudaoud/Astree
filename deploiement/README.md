# Déploiement AWS

Paramètres vérifiés dans #22, déploiement et scripts dans #13. Chaque valeur a été vérifiée sur le compte de l'événement le 2026-11-14. Schéma d'ensemble : [`docs/architecture.md`](../docs/architecture.md).

## Déployer ou mettre à jour (après chaque fusion)

```powershell
aws login                                                   # une fois par session
.venv\Scripts\python -X utf8 deploiement\deployer.py        # construit le zip puis déploie
.venv\Scripts\python -X utf8 deploiement\tester_function_url.py robert "Je veux mettre 30 % de mon portefeuille en Tesla" --verdict maintenu
```

- [`construire_zip.py`](construire_zip.py) : construit `build/lambda_tribunal.zip` (voir « Contenu du zip »).
- [`deployer.py`](deployer.py) : **idempotent**, chaque étape est sautée si elle est déjà faite :
  1. bucket `alphaforge-<compte>` (accès public bloqué) et CSV dans `donnees/` ;
  2. rôle `alphaforge-lambda` avec la politique minimale ;
  3. code et configuration de la Lambda `alphaforge-tribunal` ;
  4. concurrence réservée de 2 ;
  5. Function URL.

  `--sans-donnees` évite de renvoyer les CSV.
- [`lambda_tribunal.py`](lambda_tribunal.py) : le point d'entrée (handler `lambda_tribunal.handler`, à la racine du zip). Il expose deux routes :
  - `POST /tribunal` `{"profil", "demande"}`, plus `"calibrage": {"reponses": {…}}` facultatif (Pacte vécu, #68 ; des réponses invalides donnent un 400 sans appel Bedrock), renvoie le contrat, archivé dans `traces/<date>/<id>.json`, avec l'identifiant dans l'en-tête `x-proces-id` ;
  - `POST /verdict` `{"id", "verdict"}` archive le procès avec le choix de l'utilisateur dans `verdicts/<profil>/<id>.json` (relu par l'outil de jurisprudence, #56).

## Lambda

| Paramètre | Valeur | Pourquoi |
|---|---|---|
| Runtime | `python3.14`, architecture `x86_64` | Même version que les postes de l'équipe ; la couche pandas existe pour 3.14 |
| Couche | `arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python314:12` | Couche gérée par AWS : pandas 3.1.0, numpy 2.5.4, pyarrow 24.0.0, les mêmes versions que `requirements-dev.txt` |
| Délai | 300 s | Procès complet mesuré : de 18 à 27 s en local, environ 33 s au pire observé, plus le démarrage à froid et une éventuelle relance du Greffier |
| Mémoire | 1024 Mo au moins | pandas et les CSV ; plus de mémoire donne aussi plus de processeur |
| Concurrence réservée | 2 | Limite les appels Bedrock payants. Le compte laisse 110 exécutions non réservées : en réserver 2 est possible |
| Variables d'environnement | `BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-5-5`, `SOURCE_DONNEES=s3`, `BUCKET_PROJET=alphaforge-<compte>` | Les CSV sont lus dans `donnees/` du bucket (#13). Ne pas définir `AWS_REGION` : Lambda la fournit elle-même (us-east-1) |

**Données en mémoire** : `pipeline/donnees.py` garde les CSV en mémoire après la première lecture (`lru_cache`). Le module d'entrée de la Lambda doit importer le pipeline **au niveau du module**, hors du handler, pour qu'une Lambda déjà démarrée ne relise pas les CSV.

## Contenu du zip

`construire_zip.py` y met :
- les dépendances de `requirements.txt` (boto3, jsonschema), **en version Linux** pour Python 3.14 ;
- `pipeline/`, `contrat/`, `personas/`, `config/` et `donnees_externes/` (corpus ESG, #17) ;
- `lambda_tribunal.py` à la racine.

Remarques :
- **Pas de CSV** : la Lambda les lit dans S3. Aucun module ne doit donc lire `alphaforge_starter/` sur le disque. Tout passe par `pipeline/donnees.lire_csv`, un test le vérifie pour l'univers.
- **Ne pas** y mettre pandas, numpy ni pyarrow : ils viennent de la couche.
- **Y mettre boto3** : il n'est pas dans la couche, et celui du runtime peut être trop ancien pour la sortie JSON structurée de Bedrock (`outputConfig`).
- **Taille** : 17,7 Mo compressés, 30 Mo décompressés, plus 190 Mo pour la couche, soit 220 Mo sur les 250 permis. N'ajoutez pas de grosse bibliothèque.

## Point d'accès : Lambda Function URL

- **Pourquoi pas API Gateway** : il coupe la requête après environ 29 s, et un procès complet dure de 18 à 33 s avant même l'outil 4 (#21). La démo échouerait par moments avec une erreur 504.
- **Aujourd'hui : type d'authentification `AWS_IAM`.** Seuls les membres connectés au compte (`aws login`) peuvent l'appeler, ce qui évite d'exposer des appels Bedrock payants tant que l'interface n'existe pas. Pour tester, `curl` ne suffit pas : la requête doit être signée. Utiliser [`tester_function_url.py`](tester_function_url.py) :
  ```powershell
  .venv\Scripts\python -X utf8 deploiement\tester_function_url.py robert "Je veux mettre 30 % de mon portefeuille en Tesla"
  ```
  Il lit l'adresse sur le compte (elle n'est pas dans le dépôt), signe la requête et affiche le statut, la durée et un résumé du contrat.
- **Quand l'interface sera en ligne (#14)** : passer en type `NONE` (un navigateur ne sait pas signer une requête AWS), avec **CORS limité au domaine de l'interface** : `AllowOrigins` = ce domaine seul, `AllowMethods` = `POST`, `AllowHeaders` = `content-type`, `ExposeHeaders` = `x-proces-id` (sinon le navigateur cache l'identifiant du procès, nécessaire pour `POST /verdict`).
- **Supprimer l'adresse après le jury** : `aws lambda delete-function-url-config --function-name alphaforge-tribunal`.

## Vérifié sur la Lambda déployée (2026-11-14)

Lambda `alphaforge-tribunal`, appelée par sa Function URL avec `tester_function_url.py` :

| Vérification | Résultat |
|---|---|
| Procès le plus long (cas 2 : réallocation vers le panier crypto-tech, 5 outils) | HTTP 200 en **37,4 s**, dont 4,2 s de démarrage à froid. API Gateway aurait coupé à 29 s |
| Procès du cas 1 (« 30 % en TSLA »), Lambda déjà démarrée | HTTP 200 en 31,0 s, puis 26,3 s |
| CSV lus une seule fois | « Données chargées en 0.5 s » n'apparaît qu'au démarrage dans CloudWatch ; les appels suivants n'ont pas de temps d'initialisation |
| Mémoire | 234 Mo utilisés au maximum sur 1024 Mo |
| Archivage | Chaque procès est écrit dans `traces/<date>/<id>.json` du bucket ; l'identifiant revient dans l'en-tête `x-proces-id` |
| Contrat | La réponse passe `python -m contrat.valider` |
| Concurrence réservée | 2 |

Aucun des procès n'a eu d'argument rejeté puis régénéré : une relance du Greffier ajouterait 2 appels Bedrock, soit quelques secondes, très loin des 300 s.

Après le redéploiement de #13 (code de `main` avec les cas 2 et 3, CSV lus dans S3) :

| Vérification | Résultat |
|---|---|
| Procès du cas 3 (profil ESG, 10 % en XOM) par `/tribunal` | HTTP 200 en **32,5 s** ; l'orchestrateur appelle `rechercher_documents` ; le contrat passe `contrat.valider` |
| `/verdict` sur ce procès | HTTP 200 en 0,2 s ; `verdicts/<id>.json` contient le procès complet (5 pièces) avec `"verdict": "modifie"` |
| `/verdict` avec un identifiant inconnu | HTTP 404 (« Aucun procès archivé… ») |

## Coûts

- **Alerte de budget** `alphaforge-budget-mensuel` : 100 $ par mois pour tout le compte, avec un courriel à 80 % du coût réel et à 100 % du coût prévu. Elle compte aussi l'infrastructure de l'événement (environ 2,55 $ le 14 novembre). Pour ajouter un destinataire : console AWS → Billing → Budgets.
- Les coûts Bedrock apparaissent dans la facturation avec environ 24 h de retard.

## IAM

Le rôle de la Lambda utilise [`politique_iam_lambda.json`](politique_iam_lambda.json), en remplaçant `NOM_DU_BUCKET` :
- `bedrock:InvokeModel` sur le **profil d'inférence** `us.anthropic.claude-sonnet-5-5` **et** sur le modèle dans les **trois régions** vers lesquelles le profil répartit les appels : us-east-1, us-east-2 et us-west-2. Sans ces trois régions, certains appels échoueraient au hasard.
- Les journaux CloudWatch, et la lecture et l'écriture dans le bucket du projet.
- `s3:ListBucket` sur ce bucket seulement : sans ce droit, S3 répond « accès refusé » au lieu de « introuvable » pour un objet absent, et `/verdict` renverrait une erreur 500 au lieu de 404 pour un procès inconnu.
- Si `BEDROCK_MODEL_ID` change, mettre la politique à jour (`aws bedrock get-inference-profile` donne les régions du profil).

## Bedrock

- Région `us-east-1`, profil `us.anthropic.claude-sonnet-5-5`. Quota : 6 millions de jetons par minute, bien au-delà d'un procès.
- Les relances adaptatives et le délai de lecture de 300 s sont déjà dans `pipeline/llm.py` (#7).
- **Vérifié** : 5 procès complets d'affilée, soit 25 appels Converse, sans aucune relance de boto3 ni erreur de limitation.
