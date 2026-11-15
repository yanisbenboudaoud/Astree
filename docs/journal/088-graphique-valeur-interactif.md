# #88 — Graphique de valeur du portefeuille interactif

- **Issue** : #88 · **PR** : #89 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- `frontend/src/components/graphiques/GraphiqueValeur.tsx` : la courbe de valeur de l'écran Portefeuille (spec D.2) devient lisible point par point.
  - Survol et toucher : un repère vertical, un point sur la courbe et une bulle « date · valeur » suivent le pointeur. La bulle passe à gauche du repère près du bord droit.
  - Clavier : le graphique est focalisable (`tabIndex={0}`) ; ← → avancent d'un point (une semaine), Page ↑ ↓ de 13 points (environ un trimestre), Début et Fin vont aux extrémités, Échap ferme la lecture. Une zone `aria-live` annonce « 12 nov. 2021 : 416 966 $ ».
  - `indiceLePlusProche(abscisses, cible)` (exportée) : recherche dichotomique du point le plus proche du pointeur.
- `frontend/src/components/graphiques/Graphiques.module.css` : styles du repère et de la bulle, tracé animé de la courbe (`pathLength={1}` et `stroke-dashoffset`), apparition du point le plus bas.
- `frontend/src/test/graphiqueValeur.test.tsx` : 4 tests.

## Comment l'utiliser
Rien à changer : `Portefeuille.tsx` utilise déjà `<GraphiqueValeur serie={…} pointBas={…} />`.

## Comment vérifier
```bash
cd frontend && npx vitest run src/test/graphiqueValeur.test.tsx
```
Les tests prouvent que les valeurs lues au clavier sont exactement celles de `serieValeur`. Dans le navigateur : `/robert/portefeuille`, survoler la courbe ou la parcourir au clavier.

## Choix faits en cours de route
- **Aucun chiffre calculé dans le navigateur** : la bulle affiche la date et la valeur du point de la série (`scripts/build_ui_series.py`), sans interpolation ni variation dérivée (« +12 % depuis le début »), pour rester dans la règle « Python calcule ».
- **Pas de choix de période** : la spec D.2 l'exclut volontairement ; le graphique reste sur les 5 ans.
- L'animation est coupée par la règle globale `prefers-reduced-motion` de `base.css`.

## Limites et suite
- La série est hebdomadaire (263 points) : la lecture se fait à la semaine, pas au jour.
- Après un clic, le graphique garde le focus, donc son contour reste visible jusqu'au clic suivant ailleurs.
