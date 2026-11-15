# #129 — Parcours e2e bloqués à l'écran Tribunal depuis #118

- **Issue** : #129 · **PR** : #130 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
- **`frontend/e2e/verifier.mjs`**, **`direct.mjs`** et **`greffier.mjs`** : l'écran Tribunal est attendu par l'identifiant du titre du bilan, `#titre-bilan`, au lieu du texte « Bilan du Greffier ». Depuis #118, ce texte n'est plus affiché : le titre du bilan est le verdict lui-même (« 1 règle de votre Pacte est enfreinte »), qui change d'un procès à l'autre. `direct.mjs` utilisait déjà la section `aria-labelledby="titre-bilan"` pour lire le constat.

## Comment l'utiliser
```bash
cd frontend
npm run dev                                   # ou : npx vite --port 5180
npm run verifier                              # ou : ASTREE_URL=http://localhost:5180 node e2e/verifier.mjs
```

## Comment vérifier
`npm run verifier` va au bout des 3 profils : 23 écrans vérifiés par axe-core, « Aucun problème : parcours, axe-core, débordement et console » (avant : arrêt à l'écran Tribunal de Robert, 4 écrans seulement).

## Choix faits en cours de route
- **Un identifiant plutôt qu'un texte** : le titre du bilan dépend du verdict, et un texte d'interface peut encore changer. `#titre-bilan` est aussi la cible de `aria-labelledby` : le retirer casserait l'accessibilité, donc il a peu de chances de disparaître sans qu'on le voie.

## Limites et suite
- `verifier:direct` et `verifier:greffier` n'ont pas été relancés : ils demandent la Lambda en direct, dont le CORS n'accepte que `http://localhost:5173` (port occupé par une autre session pendant ce travail), et `verifier:direct` fait de vrais procès Bedrock. Leur correction est la même ligne que dans `verifier.mjs`.
