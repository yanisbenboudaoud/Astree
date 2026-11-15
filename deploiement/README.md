# Déploiement AWS

Paramètres vérifiés dans #22, déploiement et scripts dans #13, interface hébergée dans #135 (section « Interface hébergée »). Chaque valeur a été vérifiée sur le compte de l'événement le 2026-11-14. Schéma d'ensemble : [`docs/architecture.md`](../docs/architecture.md).

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
  4. concurrence réservée de 2, et invocation asynchrone sans relance (#90) ;
  5. Function URL.

  `--sans-donnees` évite de renvoyer les CSV.
- [`lambda_tribunal.py`](lambda_tribunal.py) : le point d'entrée (handler `lambda_tribunal.handler`, à la racine du zip). Il expose huit routes (`/proces-verbal` : fiche 057) :
  - `POST /tribunal` `{"profil", "demande"}` (`profil` : un profil de `personas/` ou un profil créé par `/profil`), plus `"calibrage": {"reponses": {…}}` facultatif (Pacte vécu, #68 ; des réponses invalides donnent un 400 sans appel Bedrock), renvoie le contrat, archivé dans `traces/<date>/<id>.json`, avec l'identifiant dans l'en-tête `x-proces-id` ;
    - **avec `"progression": true`** (l'interface, #90) : la demande est vérifiée sans Bedrock (profil, Pacte, Pacte vécu : 400, 404 ou 422 tout de suite), la progression initiale est écrite dans `progression/<id>.json`, puis la Lambda **s'invoque elle-même en asynchrone** (`InvocationType="Event"`, événement interne `{"action": "juger_en_arriere_plan", …}`) et répond aussitôt **202** `{"id", "statut": "en_cours"}`. Le procès en arrière-plan publie chaque étape réelle dans `progression/<id>.json` (fil d'écriture à part : le procès n'attend jamais S3), archive le contrat dans `traces/`, puis passe la progression à `termine`. Une erreur y est écrite avec son motif ;
  - `POST /progression` `{"id"}` (#90) : relit `progression/<id>.json` et renvoie `{"id", "statut": "en_cours", "phase", "activite", "etapes"}` (étapes au format de `trace`), ou `{"id", "statut": "termine", "contrat"}`, ou `{"statut": "erreur", "erreur"}`. 404 pour un procès inconnu. **Aucun appel Bedrock** ; 90 relectures par minute et par adresse IP au plus (l'interface relit toutes les 1,5 s) ;
  - `POST /verdict` `{"id", "verdict"}` archive le procès avec le choix de l'utilisateur dans `verdicts/<profil>/<id>.json` (relu par l'outil de jurisprudence, #56) ;
  - `POST /question` `{"id", "question"}` : contre-interrogatoire (#55). Relit `traces/<date>/<id>.json`, répond à la question, réarchive le contrat complété au même endroit et renvoie `{"id", "echange", "pieces"}` (l'échange et les pièces ajoutées). Appels Bedrock payants, comme `/tribunal`.
  - `POST /verifier` `{"id", "texte", "pieces"}` : « Trompez le Greffier » (#69). Relit `traces/<date>/<id>.json` et vérifie chaque nombre du texte contre les pièces citées (`detailler_argument`, outil 6). Renvoie `{"valide", "motif", "nombres", "compte"}`, chaque nombre trouvé (avec sa pièce) ou introuvable (avec son motif). **Aucun appel Bedrock** : gratuit, environ 50 ms une fois la Lambda démarrée. Garde-fous du point d'accès public : texte de 600 caractères au plus, 10 pièces au plus, 30 vérifications par minute et par adresse IP (en mémoire de chaque instance, réponse 429 au-delà).
  - `POST /questionnaire` `{}` : les 15 questions du questionnaire investisseur (#84). **Aucun appel Bedrock.**
  - `POST /profil` `{"reponses", "capital", "portefeuille", "nom", "modifications"}` (#87) : Python construit le profil à partir des réponses (`profil_depuis_reponses`), applique les seuils choisis par l'utilisateur (`modifications` : `{"pire_baisse_max": -0.15}`), le valide et le range dans `profils/<id>.json`. L'identifiant (`investisseur_<12 hex>`) est généré par la Lambda, jamais tiré du nom saisi, et l'écriture est conditionnelle (`IfNoneMatch`) : un profil créé n'écrase jamais rien. Réponse 201 `{"id", "profil", "bareme", "contradictions", "archive", "vues"}` (`vues` : ce que les écrans Portefeuille et « Revivez 4 jours » affichent, `pipeline/vues_interface.py`, #86) ; avec `"apercu": true`, rien n'est rangé et la réponse est 200 `{"profil", "bareme", "contradictions"}` (aperçu avant signature) ; 400 avec `details` si une réponse est refusée. **Aucun appel Bedrock.** Garde-fous : corps de 20 000 caractères, 31 lignes de portefeuille, nom de 40 caractères, 10 modifications, 10 profils par minute et par adresse IP (réponse 429 au-delà).
  - `POST /table` `{"profil", "ticker"}` (#86) : la table de l'écran Décision pour ce titre (position de 0 à 50 %, statut de chaque règle du Pacte), identique à celles que `scripts/build_ui_series.py` précalcule pour les profils de démonstration. Environ 0,1 s une fois la Lambda démarrée. **Aucun appel Bedrock.**

## Lambda

| Paramètre | Valeur | Pourquoi |
|---|---|---|
| Runtime | `python3.14`, architecture `x86_64` | Même version que les postes de l'équipe ; la couche pandas existe pour 3.14 |
| Couche | `arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python314:12` | Couche gérée par AWS : pandas 3.1.0, numpy 2.5.4, pyarrow 24.0.0, les mêmes versions que `requirements-dev.txt` |
| Délai | 300 s | Procès complet mesuré : de 18 à 27 s en local, environ 33 s au pire observé, plus le démarrage à froid et une éventuelle relance du Greffier |
| Mémoire | 1024 Mo au moins | pandas et les CSV ; plus de mémoire donne aussi plus de processeur |
| Concurrence réservée | 2 | Limite les appels Bedrock payants. Le compte laisse 110 exécutions non réservées : en réserver 2 est possible. Elle compte aussi le procès en arrière-plan et chaque relecture de `/progression` (#90) : avec deux procès en cours, un 3ᵉ `POST /tribunal` reçoit 429, et les relectures aussi tant qu'aucun ne finit (l'interface l'affiche et continue) |
| Invocation asynchrone | `MaximumRetryAttempts` 0, `MaximumEventAgeInSeconds` 60 | Procès lancé par `/tribunal` (#90). Aucune relance : un procès raté ne se rejoue pas tout seul (nouveaux appels Bedrock). Un procès qui ne peut pas démarrer en 60 s est abandonné, au lieu de tourner quand l'interface a cessé d'attendre |
| Variables d'environnement | `BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-5-5`, `SOURCE_DONNEES=s3`, `BUCKET_PROJET=alphaforge-<compte>` | Les CSV sont lus dans `donnees/` du bucket (#13). Ne pas définir `AWS_REGION` : Lambda la fournit elle-même (us-east-1) |

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
- **Depuis #14 : type d'authentification `NONE`**, car un navigateur ne sait pas signer une requête AWS. L'interface (`frontend/`, `npm run dev`) l'appelle directement. Réglages, appliqués par `deployer.py` (`assurer_function_url`) :
  - **CORS limité à l'interface** : `AllowOrigins` = `http://localhost:5173`, plus, depuis #135, le domaine du site hébergé ajouté avec `--origine` (voir « Interface hébergée »), `AllowMethods` = `POST`, `AllowHeaders` = `content-type`, `ExposeHeaders` = `x-proces-id` (sinon le navigateur cache l'identifiant du procès, nécessaire pour `POST /verdict`), `MaxAge` = 300 s ;
  - **permissions publiques exigées par Lambda** pour une URL en `NONE` : `lambda:InvokeFunctionUrl` (`FunctionUrlAuthType: NONE`) et `lambda:InvokeFunction` avec `InvokedViaFunctionUrl: true`, donc uniquement par l'URL ;
  - le CORS ne protège que des navigateurs : n'importe quel client peut appeler l'adresse. Les coûts restent bornés par la concurrence réservée de 2 et l'alerte de budget, et l'adresse n'est pas dans le dépôt.
- **Changer ou ajouter une origine** (interface hébergée, autre port), sans toucher au code de la Lambda :
  ```powershell
  .venv\Scripts\python -X utf8 deploiement\deployer.py --url-seulement --origine https://mon-domaine
  ```
- **Tester sans navigateur** : [`tester_function_url.py`](tester_function_url.py) lit l'adresse sur le compte, envoie la requête (encore signée, ce qui reste accepté) et affiche le statut, la durée et un résumé du contrat :
  ```powershell
  .venv\Scripts\python -X utf8 deploiement\tester_function_url.py robert "Je veux mettre 30 % de mon portefeuille en Tesla"
  ```
- **Couper l'accès après le jury** : `aws lambda delete-function-url-config --function-name alphaforge-tribunal`, ou revenir en `AWS_IAM` (`aws lambda update-function-url-config --function-name alphaforge-tribunal --auth-type AWS_IAM`).

## Interface hébergée : S3 privé + CloudFront (#135)

**Adresse : https://d15khh2djw55mh.cloudfront.net**. Le site est actuellement en **mode démonstration** (procès enregistrés, « Trompez le Greffier » en direct). Le passage au mode direct attend #136 et #137 : c'est l'issue #141.

```powershell
aws login                                                                    # une fois par session
.venv\Scripts\python -X utf8 deploiement\deployer_interface.py              # construit puis envoie, mode direct (défaut)
.venv\Scripts\python -X utf8 deploiement\deployer_interface.py --mode demo  # procès enregistrés
```

Options : `--sans-construction` envoie `frontend/dist/` tel quel ; `--forcer` renvoie tous les fichiers (après un changement des en-têtes) ; `--attendre` attend que la distribution soit déployée.

[`deployer_interface.py`](deployer_interface.py) est **idempotent** comme `deployer.py` : un second lancement ne crée rien, n'envoie que les fichiers modifiés et n'invalide rien si `index.html` et les procès-verbaux n'ont pas changé.

| Réglage | Valeur | Pourquoi |
|---|---|---|
| Bucket | `alphaforge-site-<compte>`, accès public bloqué | Pas le bucket des données : il contient les traces, les verdicts et les profils |
| Lecture du bucket | Contrôle d'accès à l'origine (OAC) `alphaforge-interface`, et politique du bucket : `s3:GetObject` pour `cloudfront.amazonaws.com`, condition `AWS:SourceArn` = la distribution | Personne ne lit le bucket directement, même pas une autre distribution |
| Repérage | Commentaire `alphaforge-interface` | Le script retrouve sa distribution et n'en crée jamais une deuxième. L'autre distribution du compte (devant une instance EC2, créée le 2026-11-13 : l'infrastructure de l'événement) n'est jamais touchée. Un réglage changé à la main est remis à la valeur du dépôt au lancement suivant |
| Pages profondes | Erreurs 403 et 404 → `/index.html` avec le statut 200, sans cache d'erreur (TTL 0) | L'interface utilise `BrowserRouter` : `/robert/tribunal` n'existe pas dans le bucket. Sans `s3:ListBucket`, S3 répond 403, et non 404, pour un objet absent |
| Protocole | `index.html` à la racine, HTTP → HTTPS, HTTP/2 et HTTP/3, compression | Certificat `*.cloudfront.net` fourni : aucun domaine ni certificat à gérer |
| Cache | Politique gérée `CachingOptimized`. `assets/*` : `public, max-age=31536000, immutable` ; tout le reste (`index.html`, `proces-verbaux/*.html`, `marque.svg`) : `no-cache` | Vite hache le nom des fichiers d'`assets/` : un fichier modifié change de nom. Le reste doit suivre chaque déploiement |
| En-têtes de sécurité | Politique gérée `SecurityHeadersPolicy` (HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`) | Bonnes pratiques, sans code |
| Zone de diffusion | `PriceClass_100` (Amérique du Nord et Europe) | Le jury est à Montréal ; la classe la moins chère |
| Construction | `npm run build` avec `VITE_API_URL` lue sur le compte (`get_function_url_config`) et `VITE_USE_MOCKS=false` par défaut | L'adresse de la Lambda n'est jamais écrite dans le dépôt. Les variables du processus passent avant `frontend/.env.local` : la configuration locale de chacun n'entre pas dans le site |
| Envoi | Seuls les fichiers modifiés (ETag = MD5 local), `index.html` en dernier, fichiers absents de `dist/` supprimés. `Content-Type` fixé par extension | `index.html` ne désigne jamais un fichier pas encore envoyé. Sous Windows, `mimetypes` peut donner `text/plain` pour `.js` |
| Invalidation | `/`, `/index.html` et `/proces-verbaux/*`, seulement si un fichier hors `assets/` a changé | Les 1 000 premiers chemins invalidés par mois sont gratuits |

**Pourquoi S3 privé + CloudFront** :

| Option | Pour | Contre |
|---|---|---|
| **S3 privé + CloudFront (OAC)**, retenue | HTTPS d'office ; bucket non public ; un seul service de plus (S3 est déjà utilisé) ; même style de script que `deployer.py` | Une invalidation du cache à chaque mise à jour |
| Site web S3 seul | Le plus simple | HTTP seulement, bucket public |
| Amplify Hosting | Déploiement automatique à chaque fusion | Un service de plus ; la connexion au dépôt GitHub demande l'accord du propriétaire du dépôt |

**Appels à la Lambda** : le site appelle la Function URL directement, comme en local. Les faire passer par CloudFront (`/api/*`) couperait les réponses longues : le délai de CloudFront vers son origine est de 30 s par défaut et de 60 s au plus sans demande de quota. Le domaine du site doit donc être dans le CORS de la Function URL. Il y a été ajouté le 2026-11-15 avec `deployer.py --url-seulement --origine https://d15khh2djw55mh.cloudfront.net`. **Attention : le prochain `deployer.py` lancé sans `--origine` le retire**, jusqu'à #136 (lecture du domaine sur le compte). `deployer_interface.py` le signale à la fin s'il manque.

**Coûts** : CloudFront offre chaque mois 1 To de transfert et 10 millions de requêtes gratuits ; le site pèse 16 Mo (146 fichiers) dans S3.

**Vérifié le 2026-11-15** (site construit avec `--mode demo`) :

| Vérification | Résultat |
|---|---|
| Accueil, page profonde (`/robert/tribunal`), procès-verbal (`/proces-verbaux/<id>.html`) | HTTP 200, `text/html; charset=utf-8`, `no-cache`. La page profonde passe par la réponse d'erreur (`X-Cache: Error from cloudfront`) et reçoit bien l'interface |
| Fichier haché (`assets/index-<hash>.js`) | `text/javascript; charset=utf-8`, `public, max-age=31536000, immutable`, compressé en Brotli |
| `http://` | 301 vers `https://` ; en-têtes HSTS et `X-Content-Type-Options` présents |
| Lecture directe du bucket (`https://alphaforge-site-<compte>.s3.us-east-1.amazonaws.com/index.html`) | 403 |
| `ASTREE_URL=https://d15khh2djw55mh.cloudfront.net npm run verifier` | Aucun problème : parcours des 3 profils, 23 écrans sous axe-core, débordement, console ; le procès-verbal s'ouvre |
| `ASTREE_URL=… node e2e/greffier.mjs` (« Trompez le Greffier » en direct depuis le site) | 4 exemples vérifiés par la Lambda, de 72 à 100 ms chacun |
| Prévol CORS depuis le site / depuis une autre origine | 200 avec `Access-Control-Allow-Origin` / aucun en-tête `Access-Control-*` |
| Second lancement du script | Aucune ressource créée (toujours 1 OAC et 1 distribution `alphaforge-interface`), 0 fichier envoyé sur 146, aucune invalidation |

Pendant ces vérifications, un redéploiement de la Lambda depuis une autre session (`deployer.py` sans `--origine`, 20 h 46 UTC) a retiré le domaine du CORS : le Greffier en direct échouait depuis le site. Il a été remis avec `--url-seulement --origine`. C'est le problème que règle #136. Une modification du CORS met aussi quelques secondes à s'appliquer partout.

**Limites** :
- Un onglet ouvert avant un redéploiement peut ne plus trouver un morceau de l'interface chargé à la demande (la table des paniers de l'écran Décision) : il a été supprimé du bucket. Recharger la page suffit.
- **Couper après le jury** : désactiver la distribution (console CloudFront → *Disable*), puis la supprimer une fois désactivée ; vider et supprimer le bucket `alphaforge-site-<compte>`.

## Progression en direct : vérifié en local (2026-11-15, #90)

Le vrai `lambda_tribunal.handler` derrière un serveur HTTP local (S3 en mémoire, invocation asynchrone remplacée par un fil d'exécution), vrais appels Bedrock, interface en mode direct, écran observé toutes les 150 ms. Procès de Robert, « 30 % en TSLA » :

| Vérification | Résultat |
|---|---|
| `POST /tribunal` avec `progression: true` | 202 en 0,1 s ; procès en arrière-plan ; 20 relectures de `/progression`, toutes en 200 |
| Passage de l'Agent Profil à l'Orchestrateur | publié à +2,5 s, affiché à +3,1 s |
| Outils de l'orchestrateur | les 5 outils demandés ensemble par le modèle, exécutés en 0,1 s, affichés 0,8 s après |
| Retour du premier agent du débat, puis fin | affichés 1,2 s après leur publication ; procès complet en 28 s |
| Délai entre une étape réelle et son affichage | de 0,6 à 1,2 s (relecture toutes les 1,5 s) |
| Erreur pendant le procès (Bedrock mal configuré) | motif écrit dans la progression et affiché ; la fonction se termine sans relance |
| axe-core (WCAG 2.2 AA) sur l'écran de chargement, console | aucune violation, aucune erreur |

À refaire sur la Lambda déployée, une fois `deployer.py` relancé : `npm run verifier:direct` vérifie le 202, les relectures et la phase qui avance.

## Vérifié depuis le navigateur (2026-11-15, #14)

Function URL en `NONE`, interface en mode direct sur `http://localhost:5173`, script `frontend/e2e/direct.mjs` :

| Vérification | Résultat |
|---|---|
| Prévol CORS depuis `http://localhost:5173` | HTTP 200 avec `Access-Control-Allow-Origin`, `-Methods: POST`, `-Headers: content-type` |
| Prévol CORS depuis une autre origine | Aucun en-tête `Access-Control-*` : le navigateur bloque l'appel |
| Procès de Robert (« 30 % en TSLA ») dans l'interface | HTTP 200 en 28 s ; identifiant du procès lisible par la page (`x-proces-id` exposé) ; verdict signé, `POST /verdict` HTTP 200 |
| Procès d'Amira (panier crypto-tech, le plus long) dans l'interface | HTTP 200 en 44 s, sans coupure ; verdict signé, `POST /verdict` HTTP 200 |

## Vérifié sur la Lambda déployée (2026-11-14)

Lambda `alphaforge-tribunal`, appelée par sa Function URL avec `tester_function_url.py` :

| Vérification | Résultat |
|---|---|
| Procès le plus long (cas 2 : réallocation vers le panier crypto-tech, 5 outils) | HTTP 200 en **37,4 s**, dont 4,2 s de démarrage à froid. API Gateway aurait coupé à 29 s |
| Procès du cas 1 (« 30 % en TSLA »), Lambda déjà démarrée | HTTP 200 en 31,0 s, puis 26,3 s |
| CSV lus une seule fois | « Données chargées en 0.5 s » n'apparaît qu'au démarrage dans CloudWatch ; les appels suivants n'ont pas de temps d'initialisation |
| Mémoire | 234 Mo utilisés au maximum sur 1024 Mo |
| Archivage | Chaque procès est écrit dans `traces/<date>/<id>.json` du bucket ; l'identifiant revient dans l'en-tête `x-proces-id` |
| Profils créés | `profils/<id>.json` du bucket (#87) ; relus par `/tribunal`, `/question` et la jurisprudence. Les droits S3 existants (`GetObject`, `PutObject` sur le bucket) suffisent |
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
- `bedrock:InvokeModel` sur le **profil d'inférence global** `global.anthropic.claude-sonnet-5-5`, sur le modèle dans us-east-1 **et** sur le modèle sans région (`arn:aws:bedrock:::foundation-model/anthropic.claude-sonnet-5-5`) : le profil global peut répartir les appels sur toutes les régions commerciales. Sans ce dernier ARN, certains appels échoueraient au hasard.
- Les journaux CloudWatch, et la lecture et l'écriture dans le bucket du projet.
- `s3:ListBucket` sur ce bucket seulement : sans ce droit, S3 répond « accès refusé » au lieu de « introuvable » pour un objet absent, et `/verdict` renverrait une erreur 500 au lieu de 404 pour un procès inconnu.
- `lambda:InvokeFunction` sur la fonction `alphaforge-tribunal` **elle-même seulement** (#90) : `/tribunal` lance le procès en arrière-plan. La progression (`progression/*`) est couverte par le droit sur le bucket.
- Si `BEDROCK_MODEL_ID` change, mettre la politique à jour (`aws bedrock get-inference-profile` donne les régions du profil).

## Bedrock

- Région `us-east-1`, profil global `global.anthropic.claude-sonnet-5-5` (15 novembre 2026 : la page « Utilisation responsable » recommande le profil `global.` quand il existe ; vérifié par un procès complet sur la Lambda, contrat valide). Avant : `us.anthropic.claude-sonnet-5-5`. Quota : 6 millions de jetons par minute, bien au-delà d'un procès.
- Les relances adaptatives et le délai de lecture de 300 s sont déjà dans `pipeline/llm.py` (#7).
- **Vérifié** : 5 procès complets d'affilée, soit 25 appels Converse, sans aucune relance de boto3 ni erreur de limitation.
