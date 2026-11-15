# #90 — Le Tribunal en direct : afficher la vraie progression du procès pendant l'attente

- **Issue** : #90 · **PR** : #95 · **Statut** : terminée côté code ; Lambda à redéployer
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Avant, pendant 20 à 40 s, l'écran « Le Tribunal instruit le dossier » montrait 4 phases grises qui ne bougeaient pas : la Lambda ne renvoyait rien avant la fin. Maintenant, chaque étape réelle est publiée au moment où elle a lieu, et l'interface la relit. Rien n'avance selon le temps écoulé.

- **`pipeline/progression.py`** (nouveau) : le format des signaux (`phase`, `etape`, `activite`) et `Progression`, qui les cumule dans le document publié (`statut`, `phase`, `activite`, `etapes`, `erreur`). Il est sûr entre fils d'exécution (le Procureur et l'Avocat signalent depuis deux fils) et publie ses versions dans l'ordre.
- **`pipeline/tribunal.py`** :
  - `juger_decision(..., signaler=None)` signale le début de chaque phase (avec ce que fait le Tribunal), les étapes de l'Agent Profil, **chaque appel d'outil de l'orchestrateur au moment où il est fait**, chaque plaidoirie dès son retour (puis « L'Avocat plaide encore »), chaque renvoi du Greffier (annoncé avant l'appel Bedrock) et ses contrôles. Sans `signaler`, rien ne change : le contrat est identique, un test le vérifie.
  - `verifier_avant_proces` : contrôles sans Bedrock (profil de `personas/` ou profil créé par `/profil` (#87), Pacte, Pacte vécu).
- **`pipeline/orchestrateur.py`** : `instruire_dossier(..., signaler_etape=None)`, appelé dans `_tracer`, le point unique où chaque appel est tracé. **`pipeline/debat.py`** : `debattre(..., signaler_etape=None)`, appelé depuis le fil de chaque rôle.
- **`deploiement/lambda_tribunal.py`** :
  - `POST /tribunal` avec `"progression": true` vérifie la demande, écrit la progression initiale, **s'invoque elle-même en asynchrone** (`InvocationType="Event"`, événement interne `juger_en_arriere_plan`) et répond 202 `{id}`. Sans ce champ, l'ancien comportement reste (contrat en 200).
  - `juger_en_arriere_plan` fait le procès, archive le contrat, **puis** passe la progression à `termine`. Toute erreur y est écrite avec son motif ; la fonction se termine normalement, donc Lambda ne relance jamais un procès raté.
  - `EcrivainProgression` écrit dans S3 depuis un fil à part (le procès n'attend jamais S3) ; dans une rafale, seule la dernière version est écrite.
  - `POST /progression` `{id}` renvoie la progression, ou le contrat quand il est archivé. 404 si le procès est inconnu, 90 relectures par minute et par adresse IP au plus (`trop_d_appels`, commun avec `/verifier` et `/profil`).
- **`deploiement/deployer.py`** et **`politique_iam_lambda.json`** : `lambda:InvokeFunction` sur la fonction elle-même seulement ; `regler_invocation_asynchrone` (`MaximumRetryAttempts` 0, `MaximumEventAgeInSeconds` 60).
- **Interface** :
  - `src/components/ChargementTribunal.tsx` (nouveau) : les 4 phases, la phase en cours pulsée (immobile si l'utilisateur réduit les animations), les phases finies cochées, et sous chaque phase ses étapes réelles (outils avec leur pièce et leur raison, plaidoiries, renvois). Il affiche aussi ce que fait le Tribunal en ce moment, et la phase en cours est annoncée aux lecteurs d'écran.
  - `src/domaine/progression.ts` : phase de chaque étape (`phaseDeLEtape`), état des phases, relecture d'un procès enregistré (`phaseEnRelecture`), renvois du Greffier.
  - `src/api/tribunal.ts` : `suivreProces` relit `/progression` toutes les 1,5 s jusqu'au contrat. Elle s'arrête sur une erreur (motif affiché), après 120 s, ou sur `AbortSignal`. Un 429 et une coupure réseau donnent un avis, puis la relecture continue. `jugerDecision(id, decision, options)` prend maintenant un objet d'options. `reprendreProces` reprend la relecture d'un procès déjà accepté.
  - `src/ecrans/Tribunal.tsx` : quitter l'écran arrête la relecture. En revenant, ou après un rechargement (`procesId` gardé dans l'état), elle reprend sur le même procès, sans en relancer un. En démonstration, la trace enregistrée est relue une étape toutes les 0,5 s, annoncée à l'écran.
  - `e2e/direct.mjs` vérifie maintenant le 202, les relectures et la phase qui avance.

## Comment l'utiliser
Interface en mode direct (`frontend/README.md`) : rien à faire, `jugerDecision` lance le procès et suit sa progression. Côté Python : `juger_decision(profil, demande, signaler=Progression(id, publier).signaler)`.

## Comment vérifier
- `pytest` : 755 tests passent. Les tests nouveaux couvrent `tests/test_progression.py` (cumul, ordre, deux fils), les signaux dans l'ordre des phases fixes avec un signal par appel d'outil, le contrat identique avec ou sans `signaler`, et la Lambda : 202 et invocation asynchrone, progression lisible **pendant** le procès, contrat à la fin, erreur avec motif, 404, 400, débit limité, requête publique qui ne peut pas déclencher l'action interne, rafale. S'y ajoutent les réglages IAM et asynchrones du déploiement.
- `npm test` (68) et `npm run build` : la relecture d'un faux `/progression` (la phase change à chaque relecture, les outils arrivent un par un), l'écran, et les traces enregistrées rejouées phase par phase.
- **Navigateur, vrai procès en local** : le vrai handler derrière un serveur HTTP local (S3 en mémoire, invocation asynchrone dans un fil), vrais appels Bedrock, Robert à 30 % en TSLA. Chaque étape réelle s'est affichée **0,6 à 1,2 s** après sa publication, et le procès a duré 28 s. Aucune violation axe-core, aucune erreur de console (détail dans `deploiement/README.md`).
- Démonstration : relecture en 8 s, phases dans l'ordre, une étape à la fois.

## Choix faits en cours de route
- **`/tribunal` sans `progression: true` garde l'ancien comportement**, et l'interface accepte un 200 avec le contrat. Le déploiement ne casse donc ni les scripts (`tester_function_url.py`) ni une interface pas encore à jour, et l'interface marche avec une Lambda pas encore redéployée (sans progression).
- **Concurrence réservée gardée à 2** (`CLAUDE.md`, coûts). Elle compte le procès en arrière-plan **et** les relectures : avec deux procès en cours, les relectures reçoivent 429 jusqu'à ce qu'un procès finisse. L'interface l'affiche (« Tribunal occupé ») et continue de relire. Augmenter la concurrence aurait relevé le plafond des appels Bedrock simultanés.
- **Les étapes de l'Agent Profil sont signalées à la fin de sa phase** (un seul appel Bedrock). La phase, elle, s'affiche dès son début.
- **Une étape qui dure quelques millisecondes peut ne jamais s'afficher « en cours »** (le Greffier sans renvoi) : la relecture toutes les 1,5 s la trouve déjà finie. La montrer « en cours » serait du faux ; l'écran final la montre cochée, avec ses étapes.
- **Les 5 outils peuvent apparaître ensemble** : l'orchestrateur les demande souvent dans un même tour, et Python les exécute en 0,1 s.
- **Diffusion en flux écartée** : les Function URL ne la prennent en charge nativement qu'avec Node.js (issue).

## Limites et suite
- **Lambda à redéployer** (`deploiement/deployer.py`) pour la progression en direct ; puis `npm run verifier:direct` sur la vraie Lambda.
- Le contre-interrogatoire (`/question`) reste synchrone : il pourrait suivre le même principe.
- La limite de débit de `/progression` est en mémoire de chaque instance, comme celle de `/verifier` et de `/profil` (`trop_d_appels`).
