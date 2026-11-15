# #150 — Bedrock : passer au profil d'inférence global

- **Issue** : #150 · **PR** : #151 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Les agents appellent maintenant Bedrock par le profil d'inférence **global** `global.anthropic.claude-sonnet-5-5` au lieu de `us.anthropic.claude-sonnet-5-5`. La page « Utilisation responsable » de l'événement le recommande quand il existe : les requêtes sont réparties sur plus de régions, donc plus de capacité et moins d'erreurs de limitation.

- **`deploiement/politique_iam_lambda.json`** : `bedrock:InvokeModel` sur le profil global, sur le modèle dans us-east-1 et sur le modèle **sans région** (`arn:aws:bedrock:::foundation-model/anthropic.claude-sonnet-5-5`). Les ARN des trois régions américaines du profil `us.` sont retirés.
- **`deploiement/deployer.py`** : `MODELE` vaut le profil global, pour qu'un prochain déploiement ne revienne pas en arrière.
- **`.env.example`**, **`README.md`**, **`CLAUDE.md`** (section 1 bis), **`deploiement/README.md`** et le commentaire de **`pipeline/llm.py`** : nouvel identifiant.
- Déjà appliqué sur le compte : politique du rôle `alphaforge-lambda` et variable `BEDROCK_MODEL_ID` de la Lambda `alphaforge-tribunal`.

## Comment l'utiliser
En local, mettre `BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-5-5` dans `.env` (copié de `.env.example`). Sur AWS, rien à faire : `python deploiement/deployer.py` applique le nouveau modèle et la nouvelle politique.

## Comment vérifier
```bash
aws bedrock get-inference-profile --inference-profile-identifier global.anthropic.claude-sonnet-5-5 --region us-east-1 --query 'models[].modelArn'
python -X utf8 deploiement/tester_function_url.py robert "Je veux mettre 30 % de mon portefeuille en Tesla" --sortie contrat.json
python -X utf8 -m contrat.valider contrat.json
```
Vérifié le 2026-11-15 : HTTP 200 en 51,7 s (procès `2026-11-15-a25802fb5604`), 8 pièces, 4 arguments contre et 4 pour, 0 rejeté ; contrat valide.

## Choix faits en cours de route
- Le profil global liste deux ARN de modèle : us-east-1 et un ARN sans région. Sans ce dernier, les appels routés hors des régions autorisées échoueraient au hasard.
- Les droits sur le profil `us.` sont retirés (permissions minimales). Pour revenir en arrière : remettre l'ancienne politique et l'ancienne valeur de `BEDROCK_MODEL_ID`.

## Limites et suite
- Le premier procès après le changement a pris 51,7 s, contre 18 à 33 s mesurés avant (#22). Probablement un démarrage à froid ; à remesurer avant le jury.
- Les procès enregistrés de l'interface (`frontend/src/data/proces/`) ont été tenus avec le profil `us.` ; leur description le dit et reste exacte.
