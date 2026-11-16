# Preuves de l'intégration AWS

> Exportées le **2026-11-16T01:50:30+00:00** par `python -m deploiement.preuves_aws` (#191), en lecture seule, avant la suppression du compte de l'événement. Chaque fichier JSON est la réponse de l'API, sans modification (variables d'environnement au nom de secret masquées).

## Résumé

- **Lambda `alphaforge-tribunal`** : runtime `python3.14`, 1024 Mo, délai 300 s, modèle `global.anthropic.claude-sonnet-5-5`, dernière modification 2026-11-16T01:35:22.000+0000.
- **Function URL** : authentification `NONE`, invocation `BUFFERED`, CORS ['http://localhost:5173', 'https://d15khh2djw55mh.cloudfront.net'].
- **Concurrence réservée** : 2.
- **Invocation asynchrone** : 0 relance, 60 s d'attente au plus.
- **Lambda, depuis le 14 nov.** : Invocations 1573, Errors 0, Throttles 419.
- **Bedrock `global.anthropic.claude-sonnet-5-5`, depuis le 14 nov.** : Invocations 313, InputTokenCount 2 427 586, OutputTokenCount 325 423, InvocationClientErrors 0.
- **Bedrock `us.anthropic.claude-haiku-5-5`, depuis le 14 nov.** : Invocations 2, InputTokenCount 281, OutputTokenCount 25, InvocationClientErrors 0.
- **Bedrock `us.anthropic.claude-opus-5-5`, depuis le 14 nov.** : Invocations 1, InputTokenCount 24, OutputTokenCount 405, InvocationClientErrors 0.
- **Bedrock `us.anthropic.claude-sonnet-5-5`, depuis le 14 nov.** : Invocations 1 412, InputTokenCount 7 855 039, OutputTokenCount 1 207 390, InvocationClientErrors 0.
- **S3 `alphaforge-908027376963`** : `traces/` 218 objets; `verdicts/` 15 objets; `profils/` 5 objets; `progression/` 121 objets; `donnees/` 6 objets.
- **S3 `alphaforge-site-908027376963`** (site) : 162 objets.
- **CloudFront** : `d15khh2djw55mh.cloudfront.net`, état `Deployed`, activée : True.

## Fichiers

- [`identite.json`](identite.json)
- [`lambda_configuration.json`](lambda_configuration.json)
- [`lambda_function_url.json`](lambda_function_url.json)
- [`lambda_concurrence.json`](lambda_concurrence.json)
- [`lambda_invocation_asynchrone.json`](lambda_invocation_asynchrone.json)
- [`cloudwatch_lambda.json`](cloudwatch_lambda.json)
- [`cloudwatch_bedrock_modeles.json`](cloudwatch_bedrock_modeles.json)
- [`cloudwatch_bedrock.json`](cloudwatch_bedrock.json)
- [`s3_projet.json`](s3_projet.json)
- [`s3_site.json`](s3_site.json)
- [`iam_role.json`](iam_role.json)
- [`iam_politiques.json`](iam_politiques.json)
- [`iam_politiques_gerees.json`](iam_politiques_gerees.json)
- [`cloudfront.json`](cloudfront.json)
- [`budget.json`](budget.json)

## Refusés par le rôle de l'atelier ou introuvables : à capturer dans la console

- Refusés : aucun.
- `cloudwatch_journaux` : aucune ligne du groupe `/aws/lambda/alphaforge-tribunal` ne citait l'identifiant du dernier procès (`2026-11-16-bfd65308abc2`). Depuis cet export, le script se rabat sur les dernières lignes du flux le plus récent ; à capturer dans la console CloudWatch si besoin.
