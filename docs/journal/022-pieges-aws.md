# #22 — Pièges AWS à régler avant le déploiement

- **Issue** : #22 · **PR** : #46, #52 · **Statut** : terminée (le CORS passe à #14, avec le domaine de l'interface)
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
2e PR, une fois la Lambda déployée par #13 :
- **Vérifications sur la Lambda déployée** (`alphaforge-tribunal`), consignées dans `deploiement/README.md`, section « Vérifié sur la Lambda déployée ».
- **`deploiement/tester_function_url.py`** : lance un procès sur la Lambda par sa Function URL. Il lit l'adresse sur le compte, signe la requête (la Function URL est en `AWS_IAM`) et affiche le statut, la durée et un résumé du contrat.
- **Alerte de budget** `alphaforge-budget-mensuel`, créée sur le compte : 100 $ par mois, courriel à 80 % du réel et à 100 % du prévu.
- **`deploiement/README.md`**, **`CLAUDE.md`** (section 1 bis) : la Function URL reste en `AWS_IAM` tant que l'interface n'est pas en ligne ; ce qu'il faudra régler pour l'interface (`NONE`, CORS, `ExposeHeaders`) ; la section « Coûts ».

1re PR (#46) :
- **`deploiement/README.md`** : les paramètres vérifiés du déploiement, pour la #13. On y trouve le runtime, la couche pandas, le délai, la mémoire, la concurrence, les variables d'environnement, le contenu et la taille du zip, la Function URL et le CORS.
- **`deploiement/politique_iam_lambda.json`** : la politique IAM minimale de la Lambda. Elle couvre Bedrock (profil d'inférence et modèle dans ses trois régions), CloudWatch et le bucket.
- **`requirements-dev.txt`** : pandas 3.1.0, numpy 2.5.4 et pyarrow 24.0.0, **les versions de la couche Lambda** (pandas était en 2.3.3).
- **`requirements.txt`** : un commentaire explique ce qui va dans le zip, dont boto3.
- **`tests/test_donnees.py`** : `dayofweek` remplacé par `day_of_week`, obsolète en pandas 3.
- **`CLAUDE.md`** (section 1 bis) et **`docs/CHOIX_CONCEPTION.md`** (choix 13) : la décision et les valeurs retenues.

## Comment l'utiliser
Mettre à jour son environnement local (pandas passe en 3.1.0) :
```powershell
.venv\Scripts\pip install -r requirements-dev.txt
```
Pour déployer (#13) : suivre `deploiement/README.md`.

Pour lancer un procès sur la Lambda déployée (quelques appels Bedrock payants) :
```powershell
.venv\Scripts\python -X utf8 deploiement\tester_function_url.py robert "Je veux mettre 30 % de mon portefeuille en Tesla" --sortie contrat.json
```

## Comment vérifier
- `pytest` passe avec pandas 3.1.0 : 302 tests, y compris ceux qui comparent les chiffres à la maquette.
- Vérifications sur le compte, en lecture seule :
  - `aws lambda get-account-settings` : 110 exécutions non réservées ;
  - `aws bedrock get-inference-profile --inference-profile-identifier us.anthropic.claude-sonnet-5-5` : les trois régions.
- **Sur la Lambda déployée** (2e PR), par sa Function URL :
  - procès le plus long (cas 2, réallocation, 5 outils) : HTTP 200 en **37,4 s** avec le démarrage à froid. API Gateway aurait coupé à 29 s : le choix de la Function URL est confirmé ;
  - cas 1 : HTTP 200 en 31,0 s puis 26,3 s, Lambda déjà démarrée ;
  - CloudWatch : « Données chargées » n'apparaît qu'au démarrage, donc le second appel ne relit pas les CSV ; 234 Mo utilisés sur 1024 ;
  - chaque procès est archivé dans S3, et le contrat renvoyé passe `python -m contrat.valider`.

## Choix faits en cours de route
- **Lambda Function URL plutôt qu'API Gateway.** 5 procès complets d'affilée (Agent Profil, orchestrateur, Greffier du Pacte, débat, `verifier_chiffres`) ont duré de 18,1 à 26,6 s en local, 21,8 s en moyenne. Le pire cas observé plus tôt était d'environ 33 s. Il faudra encore ajouter le démarrage à froid, une éventuelle relance du Greffier et l'outil 4 (#21) : la limite de 29 s d'API Gateway serait dépassée par moments.
- **Python 3.14 pour tout le monde.** AWS publie la couche `AWSSDKPandas-Python314:12` (version 3.18.0, du 2026-10-27). Personne n'a besoin de changer de version de Python.
- **Versions alignées sur la couche, pas l'inverse.** La couche impose pandas 3.1.0 (une version majeure de plus que celle du poste), numpy 2.5.4 et pyarrow 24.0.0. Les 302 tests passent avec ces versions.
- **boto3 embarqué dans le zip** : il n'est pas dans la couche, et celui du runtime peut être trop ancien pour `outputConfig`, dont dépendent tous les agents.
- **Taille** : 218 Mo décompressés sur 250 permis, soit 32 Mo de marge.
- **Pas de limitation de débit** : les 5 procès ont fait 25 appels Converse sans aucune relance de boto3. Le quota de Sonnet 5.5 est de 6 millions de jetons par minute.

## Limites et suite
- **CORS, pour #14** : quand l'interface sera en ligne, passer la Function URL en `NONE` avec le CORS limité à son domaine, et exposer l'en-tête `x-proces-id`. Le test « sans erreur 504 depuis l'interface » se refera alors depuis le navigateur ; le chemin réseau est le même que celui vérifié ici.
- **Aucune régénération observée** : aucun des procès n'a eu d'argument rejeté puis réécrit. Une relance ajouterait 2 appels Bedrock, très loin du délai de 300 s.
- L'alerte de budget compte tout le compte, y compris l'infrastructure de l'événement.
- La Function URL doit être supprimée après le jury.
