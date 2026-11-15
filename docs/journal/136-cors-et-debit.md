# #136 — Function URL ouverte au site hébergé : CORS qui survit aux redéploiements, débit limité sur les routes Bedrock

- **Issue** : #136 · **PR** : à renseigner · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Deux problèmes apparus avec le site hébergé (#135) sont réglés. Le CORS ne perd plus le site à chaque redéploiement de la Lambda, et les routes qui déclenchent Bedrock sont limitées par adresse IP, maintenant que l'adresse de la Function URL est lisible dans le JavaScript du site.

- **`deploiement/deployer.py`** :
  - `trouver_distribution_interface(cf)` repère la distribution du site par son commentaire `COMMENTAIRE_INTERFACE` (`alphaforge-interface`). La fonction était dans `deployer_interface.py`, qui l'importe désormais d'ici ;
  - `origines_cors(cf, supplementaires)` renvoie `http://localhost:5173`, puis le domaine du site **lu sur le compte**, puis les `--origine`, sans doublon. `main` l'appelle à chaque lancement, y compris avec `--url-seulement`.
- **`deploiement/lambda_tribunal.py`** : `DEBIT_MAX_TRIBUNAL = 3` et `DEBIT_MAX_QUESTION = 10` par minute et par adresse IP, avec le mécanisme existant (`trop_d_appels`, fenêtre glissante d'une minute). Le contrôle est la première instruction de `_tribunal` et de `_question` : au-delà du seuil, la réponse 429 part avant toute lecture S3, toute vérification et tout appel Bedrock. Les demandes refusées (400, 404) comptent aussi, comme pour `/verifier`.
- **`deploiement/deployer_interface.py`** : utilise la recherche de `deployer.py`. Son avertissement de fin propose `deployer.py --url-seulement`, sans `--origine`.
- **`frontend/src/api/config.ts`** : `lireErreur` affiche le message de la Lambda quand elle en donne un, y compris pour un 429 (le seuil y est écrit). Un 429 d'AWS, sans champ `erreur` (deux procès en cours), donne `MESSAGE_TRIBUNAL_OCCUPE`, qui cite aussi le nombre limité de procès, de questions et de vérifications par minute.
- **`frontend/e2e/direct.mjs`** :
  - l'adresse vient de `ASTREE_URL` ;
  - trois sélecteurs avaient vieilli avec #131, #143 et #149 : le nom de la phase en cours, « Mettre le Greffier à l'épreuve » à ouvrir avant les exemples, le verdict du Greffier ;
  - les 429 d'AWS sur `/progression` sont comptés (« Tribunal occupé ») au lieu de faire échouer le parcours.
- **Tests** :
  - `tests/test_deployer.py` : 3 tests (CORS avec et sans distribution, origines ajoutées sans doublon) ;
  - `tests/test_lambda_tribunal.py` : 3 tests de débit et une fixture `autouse` qui remet les compteurs à zéro ;
  - `frontend/src/test/config.test.ts` : 3 tests de `lireErreur`.

## Comment l'utiliser
Rien à retenir : `deployer.py`, lancé par n'importe qui et sans option, garde le site dans le CORS. `--origine` ne sert plus qu'à une origine temporaire (autre port en local), valable jusqu'au déploiement suivant.

## Comment vérifier
- `.venv\Scripts\python -m pytest tests/test_deployer.py tests/test_lambda_tribunal.py`, et `npm test` dans `frontend/`.
- Sur AWS, tableau « CORS et débit » de `deploiement/README.md` :
  - CORS gardé après deux `deployer.py` complets sans `--origine` ; prévol accepté depuis le site, refusé ailleurs ;
  - 4ᵉ procès et 11ᵉ question de la minute : 429 en 0,1 s ;
  - `ASTREE_URL=https://d15khh2djw55mh.cloudfront.net npm run verifier:direct` : vrais procès de Robert (avec une question) et d'Amira depuis le site, verdicts archivés.

## Choix faits en cours de route
- **Seuils de 3 procès et 10 questions par minute** : ce sont les exemples de l'issue, retenus comme hypothèses de l'équipe. La concurrence réservée de 2 permet de toute façon environ 4 procès par minute.
- **Origines déclarées, pas fusionnées** : `deployer.py` ne reprend pas les origines déjà présentes sur la Function URL. Le CORS est toujours celui que le dépôt décrit, et une origine ajoutée à la main disparaît au déploiement suivant.
- **Site remis en démonstration après le test** : il a été construit en mode direct seulement de 21 h 13 à 21 h 16 UTC, comme convenu. Le passage durable au mode direct est #141.
- **Lambda redéployée depuis `main` + #136** à 21 h 07 UTC, après la fusion de #151 (profil `global.`). Le premier déploiement de 20 h 58, fait juste avant cette fusion, avait remis le profil `us.`.

## Limites et suite
- **Compteurs en mémoire** de chaque instance : avec deux instances, une adresse peut lancer jusqu'à 6 procès par minute. Ils repartent aussi de zéro au démarrage de la Lambda.
- **Adresse IP partagée** : derrière un même réseau (salle du jury, Wi-Fi), tout le monde partage les mêmes 3 procès par minute.
- **Tant que cette PR n'est pas fusionnée**, un déploiement de la Lambda depuis une autre branche retire la limite de débit et le CORS automatique.
- **Suite : #141** (site en mode direct) et #137 (`?mode=demo`).
