# #14 — Interface Astrée : les écrans de la maquette, branchés sur le Tribunal

- **Issue** : #14 · **PR** : #62 · **Statut** : en cours (mode direct à brancher côté AWS)
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`frontend/`** : l'interface « Astrée » (React 18, TypeScript, Vite, CSS Modules), fidèle à la maquette Figma V2 et à [`docs/maquette/spec_interface_astree.md`](../maquette/spec_interface_astree.md). Routes de l'annexe D.1 : entrée, `/:profil/portefeuille` (recherche, confirmation `?archive=1`), `/decision`, `/tribunal` (`?piece=P4` ouvre le tiroir), `/verdict`. Mode d'emploi : [`frontend/README.md`](../../frontend/README.md).
  - `src/api/` : `contrat.ts` (types du contrat, `CLAUDE.md` §5), `types.ts` (annexe D.7), `adaptateur.ts` (`adapterContrat` : contrat → écran Tribunal), `tribunal.ts` (`jugerDecision`, `archiverVerdict`, drapeau `VITE_USE_MOCKS`), `donnees.ts`.
  - `src/domaine/` : logique d'affichage pure, sans nom de profil. `decision.ts` (effets sur le Pacte, messages, demande envoyée au Tribunal), `pacte.ts` (règle clé, signalements de la recherche), `questions.ts` (contre-interrogatoire), `verdict.ts` (options et archivage).
  - `src/data/proces/` : **trois vrais procès** du pipeline (Bedrock Sonnet 5.5, 2026-11-14), enregistrés tels quels, qui passent `python -m contrat.valider`. Celui d'Amira contient une correction du Greffier (argument renvoyé à l'Avocat puis corrigé).
  - `e2e/verifier.mjs` : vérification de bout en bout (playwright-core avec Edge ou Chrome, axe-core).
- **`scripts/build_ui_series.py`** : précalcule toutes les données chiffrées de l'interface dans `frontend/src/data/generated/`, avec **les fonctions du pipeline** (`valeurs_avant_apres`, `poids_apres_decision`, indicateurs, `verifier_pacte`) : profils, courbes hebdomadaires, une table par titre (tailles de 0 à 50 %) et une table de panier (1 771 compositions par pas de 5 points). Environ 1 minute, résultat déterministe.
- **`tests/test_build_ui_series.py`** : 6 tests pytest du script. **`frontend/src/test/`** : 33 tests vitest.

## Comment l'utiliser
```powershell
cd frontend; npm install; npm run dev                         # http://localhost:5173
.venv\Scripts\python -X utf8 scripts\build_ui_series.py      # régénérer les données (depuis la racine)
```

## Comment vérifier
```powershell
cd frontend; npm test            # chiffres de l'annexe E, formats fr-CA, adaptateur, questions, Verdict
npm run verifier                 # avec npm run dev lancé : 3 parcours, clavier seul, axe-core, débordement, console
.venv\Scripts\python -m pytest tests/test_build_ui_series.py
```
Résultat au 2026-11-14 : 33/33 vitest, 6/6 pytest ; `npm run verifier` sans aucun problème, deux fois de suite (23 écrans sans violation axe-core WCAG 2.2 AA, parcours de Robert au clavier seul à 1440 et 1280 px, aucune erreur de console, aucun débordement horizontal, y compris à 390 px).

## Choix faits en cours de route
- **Le backend fait foi** quand la spec diverge (décision de l'équipe, conforme à la note de l'annexe C) :
  - portefeuilles, capitaux et Pactes d'Amira et de Mateo lus dans `personas/*.json`. Exemples : Mateo + 10 % de XOM donne −10,0 % et +13,5 %, pas −10,3 % et +11,8 % ; la règle « revenu fixe ≥ 20 % » de la spec n'existe pas ;
  - XOM : la source ESG documentée de #17 rend une **violation**, pas « à vérifier, source manquante » ;
  - les libellés des règles sont ceux du Pacte (« Pire baisse tolérée », et non « Chute maximale tolérée »).
- **Contenu du Tribunal** : de vrais procès enregistrés plutôt que les textes de l'annexe C.5, pour que chaque argument ait passé le Greffier. Un procès n'est rejoué que pour la décision qu'il a jugée.
- **Pas de « version conforme » choisie à la main pour le panier** : le système ne propose pas de portefeuille (`CLAUDE.md` §4). L'option du Verdict est « Réallouer seulement 28 % », la part maximale calculée par le Tribunal (outil 4, pièce P4).
- **Questions suggérées** : le contre-interrogatoire libre n'est pas encore dans le contrat. Les réponses aux questions suggérées viennent du **Greffier**, en code sans LLM : il lit les pièces ou les tables précalculées, et chaque nouveau calcul devient une pièce numérotée (ex. : P6, « Simulation à 15 % »).
- **Statut du portefeuille** : « respecte les règles mesurables de votre Pacte » (2 règles vérifiées, 2 à juger), car une règle qualitative n'est jamais « respectée » par calcul.
- **Groupes de « Vos positions »** : déduits de la classe, du secteur et des catégories (`groupe_du_titre`), sans nom de profil.
- Compteur à zéro du bilan du Greffier : atténué par la couleur et un contour, pas par l'opacité, pour garder un contraste de 4,5:1.

## Limites et suite
- **Mode direct non testé de bout en bout** : la Function URL est en `AWS_IAM`. Il faut la passer en `NONE` avec CORS limité au domaine de l'interface et `ExposeHeaders: x-proces-id` (`deploiement/README.md`), puis héberger `frontend/dist/`.
- En démonstration, seules les décisions enregistrées ont un procès (30 % en TSLA, 10 % en XOM, panier BTC/ETH/NVDA/QQQ à 25 %). Le panier n'est précalculé que pour ces 4 titres ; un autre panier est signalé et jugé seulement par le Tribunal en direct.
- `POST /verdict` n'archive pas la justification écrite (la Lambda ne garde que `id` et `verdict`) : elle reste dans le journal du navigateur.
- Score Lighthouse non mesuré ici, faute de pouvoir télécharger l'outil dans la session. axe-core, son moteur d'accessibilité, passe sur tous les écrans.
- Table des paniers : environ 1,8 Mo (737 Ko compressés), chargée seulement à l'écran Décision en mode panier.
