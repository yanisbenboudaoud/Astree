# #141 — Site hébergé en mode direct : mettre en ligne le vrai Tribunal

- **Issue** : #141 · **PR** : à venir · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-16

## Ce qui a été construit
Aucun code : cette issue met en ligne ce que #135, #136 et #137 ont construit. Depuis le 2026-11-16 à 01 h 36 UTC, https://d15khh2djw55mh.cloudfront.net tient de vrais procès par défaut : le site appelle la Lambda, qui appelle Bedrock et S3. Les procès enregistrés restent disponibles par `?mode=demo` ou par l'interrupteur du bandeau.

Étapes faites, dans l'ordre de l'issue :
1. **Dépendances** : #136 (PR #155) et #137 (PR #193) sont fusionnées dans `main`.
2. **Lambda** redéployée depuis `main` par un `deployer.py` complet, **sans `--origine`** (01 h 35 UTC, `LastModified` 01:35:22). Le CORS contient encore le domaine CloudFront, lu sur le compte.
3. **Site** construit et envoyé depuis `main` par `deployer_interface.py`, **sans `--mode`** : `VITE_USE_MOCKS=false`, adresse de la Lambda lue sur le compte. 34 fichiers envoyés, 2 supprimés, invalidation terminée.
4. **`LastModified`** vérifié juste avant les procès de démonstration : toujours 01:35:22, aucune autre branche n'a remplacé la Lambda.

Documentation mise à jour :
- `deploiement/README.md`, section « Interface hébergée » : mode actuel, consigne de mise à jour (sans `--mode`), tableau « Vérifié le 2026-11-16 » ;
- `README.md` (« Essayer sans rien installer ») ;
- `CLAUDE.md` (architecture AWS).

## Comment l'utiliser
- Vrai procès : https://d15khh2djw55mh.cloudfront.net, de 20 à 50 s par procès, deux procès au plus en même temps.
- Procès enregistrés, instantanés : https://d15khh2djw55mh.cloudfront.net/?mode=demo. Le choix est mémorisé dans le navigateur ; l'interrupteur en haut à droite ramène au direct.
- Mettre le site à jour après une fusion : `.venv\Scripts\python -X utf8 deploiement\deployer_interface.py`, **sans `--mode`**.

## Comment vérifier
Les trois critères de l'issue, vérifiés le 2026-11-16 (détail dans `deploiement/README.md`) :
- `ASTREE_URL=https://d15khh2djw55mh.cloudfront.net npm run verifier:direct` passe.
  - Robert, « 30 % en TSLA » : vrai procès en 53 s, question libre en 19 s (22/22 chiffres), verdict archivé.
  - Amira : procès en 62 s, verdict archivé.
  - Contrats relus dans S3 : décisions jugées exactes, contrôles `verifier_chiffres` et `cadre_simulation` conformes.
- `?mode=demo` rejoue les procès enregistrés sans aucun appel à la Lambda : `npm run verifier:mode` compte 0 requête vers `*.lambda-url.*` jusqu'au verdict signé.
- Après le `deployer.py` complet sans `--origine`, le prévol CORS depuis le domaine CloudFront répond 200 avec `Access-Control-Allow-Origin`. Depuis une autre origine, il n'y a aucun en-tête CORS.

Aussi : un nouveau visiteur arrive en direct, sans aucun appel à la Lambda sur l'accueil. `npm run verifier` (23 écrans) et `npm run verifier:greffier` (de 82 à 103 ms) passent contre le site.

## Choix faits en cours de route
- **Défaut direct prouvé à part** : depuis #137, `verifier:direct` fixe lui-même le mode direct dans le navigateur. Il prouve qu'un procès en direct marche depuis le site, mais pas que le site est en direct **par défaut**. Ce point a été vérifié à part, avec un navigateur sans mode mémorisé (interrupteur « En direct (Bedrock sur AWS) »).
- **Les vérifications gratuites d'abord** (`verifier:mode`, `verifier`, `verifier:greffier`), puis les procès payants de `verifier:direct`. Coût : deux procès, une question, quelques cents de Bedrock. Deux verdicts ont été ajoutés à la jurisprudence de Robert et d'Amira.

## Limites et suite
- **Redéploiements par d'autres sessions** : un `deployer_interface.py --mode demo` remettrait les procès enregistrés par défaut pour tous ; la consigne est maintenant « sans `--mode` ». Un `deployer.py` depuis une autre branche remplacerait le code de la Lambda : comparer `LastModified` avant une démonstration.
- **Coûts** : chaque visiteur peut lancer de vrais procès. Les bornes restent la concurrence réservée de 2, 3 procès et 10 questions par minute et par adresse IP (#136), et l'alerte de budget.
- **Hors périmètre** : couper l'accès après le jury (Function URL, distribution, bucket du site), à faire à part (`deploiement/README.md`, « Couper après le jury »).
