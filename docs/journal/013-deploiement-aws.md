# #13 — Déployer : Lambda, S3, Function URL, IAM

- **Issue** : #13 · **PR** : #54 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **Récupéré du déploiement existant.** Une première Lambda avait été déployée pendant la #22, mais son code n'était dans aucun commit. Il a été téléchargé depuis AWS et versionné tel quel :
  - **`deploiement/lambda_tribunal.py`** : le point d'entrée (handler `lambda_tribunal.handler`). Deux routes en `POST` :
    - `/tribunal` `{"profil", "demande"}` : fait le procès et renvoie le contrat **sans en changer le format** ; l'archive dans `traces/<date>/<id>.json` ; renvoie l'identifiant dans l'en-tête `x-proces-id` ;
    - `/verdict` `{"id", "verdict"}` : archive le procès avec le choix de l'utilisateur dans `verdicts/<id>.json`.

    Erreurs lisibles : 400 (corps invalide), 404 (profil ou procès inconnu), 422 (Pacte invalide). Les données sont chargées au niveau du module, hors du handler.
  - **`pipeline/donnees.py`** : `lire_csv` lit les CSV dans S3 quand `SOURCE_DONNEES=s3` (objets `donnees/<fichier>` du bucket `BUCKET_PROJET`).
- **Nouveau** :
  - **`deploiement/construire_zip.py`** : construit `build/lambda_tribunal.zip`. Il contient les dépendances en version Linux pour Python 3.14, le code, les profils, la configuration, le corpus ESG et le point d'entrée. **Pas les CSV** : la Lambda les lit dans S3.
  - **`deploiement/deployer.py`** : déploie ou met à jour toute l'infrastructure de façon **idempotente** : bucket et CSV, rôle IAM et politique, code et configuration de la Lambda, concurrence, Function URL.
  - **`deploiement/tester_function_url.py`** : option `--verdict`, qui envoie aussi le verdict du procès à `/verdict`.
  - **`deploiement/politique_iam_lambda.json`** : `s3:ListBucket` sur le bucket. Sans ce droit, un procès inconnu donnait une erreur 500 au lieu de 404.
  - **`docs/architecture.md`** : le schéma d'architecture (Mermaid) pour la documentation et la vidéo, et le rôle de chaque service.
  - **`pipeline/univers.py`** : devient une vue de `donnees.charger_univers`. Il lisait le CSV sur le disque, ce qui a fait échouer la Lambda dès que les CSV ont quitté le zip (erreur trouvée dans CloudWatch, puis corrigée). Un test empêche ce retour en arrière.
  - **Tests** : `tests/test_lambda_tribunal.py` (17 tests : routes, archivage, verdict, lecture S3). `tests/test_donnees.py` : le test « S3 pas encore branché » devient « S3 exige le nom du bucket ».

## Comment l'utiliser
```powershell
.venv\Scripts\python -X utf8 deploiement\deployer.py
.venv\Scripts\python -X utf8 deploiement\tester_function_url.py mateo "Je veux ajouter 10 % d'Exxon Mobil à mon portefeuille" --verdict modifie
```
Détails, paramètres et vérifications : `deploiement/README.md`.

## Comment vérifier
- `pytest` : tests unitaires, sans AWS.
- **Sur la Lambda déployée** (code de `main` avec les cas 2 et 3, CSV dans S3) :
  - `/tribunal` pour le cas 3 répond HTTP 200 en **32,5 s**, et le contrat passe `contrat.valider` ;
  - `/verdict` répond HTTP 200, et `verdicts/<id>.json` contient le procès complet avec le verdict ;
  - un identifiant inconnu donne HTTP 404.

  La #22 avait déjà vérifié le procès le plus long (37,4 s) et la lecture unique des CSV.

## Choix faits en cours de route
- **Versionner le code déployé plutôt que le réécrire** : il fonctionnait et avait été vérifié par la #22. Le dépôt correspond maintenant exactement à ce qui tourne.
- **Function URL en `AWS_IAM`** tant que l'interface n'existe pas, comme décidé dans la #22 : `curl` seul ne suffit pas, la requête doit être signée (`tester_function_url.py`). Le passage en `NONE` avec CORS revient à la #14.
- **Contrat inchangé** : l'identifiant du procès passe par un en-tête HTTP, pas par un nouveau champ.
- **Un `verdict` remplace le précédent** pour le même procès : c'est le dernier choix de l'utilisateur qui compte.

## Limites et suite
- **#14** : passer la Function URL en `NONE`, avec `AllowOrigins` limité au domaine de l'interface et `ExposeHeaders` = `x-proces-id`.
- **Après chaque fusion**, relancer `deploiement/deployer.py` pour que la Lambda suive `main`.
- **Après le jury** : `aws lambda delete-function-url-config --function-name alphaforge-tribunal`.
