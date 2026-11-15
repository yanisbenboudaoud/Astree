# #135 — Héberger l'interface : S3 privé + CloudFront (HTTPS), script de déploiement idempotent

- **Issue** : #135 · **PR** : #144 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
L'interface n'est plus seulement sur `localhost:5173` : elle est en ligne à **https://d15khh2djw55mh.cloudfront.net**. Le navigateur charge le site depuis CloudFront, puis le site appelle la Function URL de la Lambda, qui appelle Bedrock et S3.

- **`deploiement/deployer_interface.py`** : script idempotent, dans le style de `deployer.py` (il en réutilise `preparer_bucket`, `REGION` et `FONCTION`). Fonctions publiques :
  - `assurer_oac`, `config_distribution`, `assurer_distribution` : l'OAC et la distribution repérés par leur nom et leur commentaire (`alphaforge-interface`), créés s'ils manquent. Un réglage changé à la main est remis à la valeur du dépôt (`resume_reglages` compare seulement les réglages gérés, car AWS ajoute ses valeurs par défaut) ;
  - `politique_bucket`, `appliquer_politique_bucket` : `s3:GetObject` pour CloudFront, limité à cette distribution (`AWS:SourceArn`) ;
  - `adresse_function_url`, `variables_construction`, `construire_interface` : `npm run build` avec `VITE_API_URL` lue sur le compte et `VITE_USE_MOCKS=false` par défaut ;
  - `en_tetes`, `envoyer_site` : synchronisation de `frontend/dist/` (fichiers modifiés seulement, `index.html` en dernier, fichiers obsolètes supprimés) ;
  - `chemins_a_invalider`, `invalider`, `origine_autorisee` : invalidation si besoin, et un avertissement si le CORS de la Function URL n'autorise pas le site.
- **`tests/test_deployer_interface.py`** : 13 tests avec de faux clients S3 et CloudFront qui gardent leur état (aucun appel AWS ni npm).
- **Ressources AWS créées** : bucket `alphaforge-site-<compte>`, OAC `alphaforge-interface`, distribution `E38EHD2ML8M1CA`.
- **Documentation** : section « Interface hébergée » de `deploiement/README.md` (réglages, raisons, vérifications), schéma et tableau des services de `docs/architecture.md`, `CLAUDE.md` (section 1 bis), `README.md` (« Démarrage », carte du dépôt), `frontend/README.md`.

## Comment l'utiliser
```powershell
aws login
.venv\Scripts\python -X utf8 deploiement\deployer_interface.py              # mode direct (défaut)
.venv\Scripts\python -X utf8 deploiement\deployer_interface.py --mode demo  # procès enregistrés
```
Options : `--sans-construction`, `--forcer`, `--attendre` (détails dans `deploiement/README.md`).

## Comment vérifier
- `.venv\Scripts\python -m pytest tests/test_deployer_interface.py` : 13 tests (réglages de la distribution, politique du bucket, en-têtes, synchronisation, invalidation, aucun doublon au second lancement, mode direct par défaut).
- Sur le site déployé (tableau complet dans `deploiement/README.md`) :
  - `ASTREE_URL=https://d15khh2djw55mh.cloudfront.net npm run verifier` : aucun problème, 23 écrans ;
  - `node e2e/greffier.mjs` avec la même adresse : « Trompez le Greffier » en direct, 4 exemples ;
  - une page profonde (`/robert/tribunal`) et un procès-verbal répondent 200 ;
  - relancé, le script affiche « déjà présent » ou « déjà en place » pour chaque ressource, puis « 0 fichiers envoyés, 146 inchangés » et « rien à invalider ».

## Choix faits en cours de route
- **Site déployé en mode démonstration** (`--mode demo`), pas en mode direct. Sans #137, le site n'a pas d'interrupteur : chaque visiteur lancerait un vrai procès payant, sans repli. Le défaut du script reste le mode direct, comme demandé. Le passage au mode direct est l'issue #141, après #136 et #137.
- **Domaine CloudFront ajouté au CORS à la main** (`deployer.py --url-seulement --origine …`), avec l'accord de l'équipe. Un redéploiement de la Lambda depuis une autre session l'a retiré pendant les vérifications ; il a été remis. #136 le rendra durable.
- **Invalidation seulement si nécessaire** : les fichiers d'`assets/` changent de nom à chaque modification. `/` est invalidé en plus de `/index.html`, par prudence : une requête sur la racine peut être gardée en cache sous `/`.
- **Pas de cache pour les réponses d'erreur** (TTL 0) : une page profonde suit toujours le dernier `index.html`.
- **En-têtes de sécurité gérés** (`SecurityHeadersPolicy`) ajoutés : aucun code, et ils couvrent les bonnes pratiques (HSTS, `nosniff`).
- **Une distribution existait déjà** sur le compte (sans commentaire, devant une instance EC2, créée le 2026-11-13 : l'infrastructure de l'événement). Le repérage par commentaire garantit qu'elle n'est jamais touchée.

## Limites et suite
- **#136** : le CORS du site doit survivre aux redéploiements de la Lambda, et `/tribunal` et `/question` doivent être limités en débit. L'adresse de la Function URL est désormais lisible dans le JavaScript du site.
- **#137** : choix du mode à l'utilisation (`?mode=demo`).
- **#141** : redéployer le site en mode direct une fois #136 et #137 fusionnés.
- Un onglet ouvert avant un redéploiement peut ne plus trouver un morceau chargé à la demande : il suffit de recharger la page.
- Couper l'accès après le jury : `deploiement/README.md`, section « Interface hébergée ».
