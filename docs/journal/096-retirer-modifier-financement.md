# #96 — Décision : retirer le bouton « Modifier » du financement et sa note

- **Issue** : #96 · **PR** : à venir · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Sur l'écran Décision, sous le curseur de taille, le bouton « Modifier » du financement n'ouvrait aucun réglage. Il affichait seulement une note qui renvoyait au Tribunal en direct et montrait un détail technique (`depuis_<titre>`). Le bouton et la note sont retirés.

- **`frontend/src/ecrans/Decision.tsx`** (`BlocTaille`) : plus de bouton « Modifier », plus de note, plus d'état `noteFinancement`. La phrase factuelle « Financement simulé : réduction proportionnelle de vos positions. » reste affichée, seule, à la fin de la section « Taille de la position ».
- **`frontend/src/ecrans/Decision.module.css`** : le style `.financement` (ligne flexible phrase + bouton) est supprimé ; la phrase n'a plus besoin d'enveloppe.
- **`docs/maquette/spec_interface_astree.md`** (annexe D.4) : la ligne de financement n'a plus de lien « Modifier ».

## Comment l'utiliser
Rien à faire : `npm run dev`, puis un profil avec une décision de type position (Robert ou Mateo) → écran Décision.

## Comment vérifier
- `npx tsc --noEmit` passe.
- `npm test` : 68 tests passent (aucun ne dépendait du bouton).
- `npm run verifier` : parcours des 3 profils, 23 écrans vérifiés par axe-core, aucun problème (parcours, axe-core, débordement, console). La capture `robert-2-decision.png` montre la phrase sur le financement, sans bouton.

## Choix faits en cours de route
- **Rien ne remplace le bouton.** La démonstration ne précalcule que le financement proportionnel ; un autre financement reste possible en le décrivant au Tribunal en direct, mais l'écran Décision n'a pas à l'annoncer.

## Limites et suite
- L'écran Décision ne permet toujours pas de choisir un financement `depuis_<ticker>`. Il faudrait précalculer ces tables dans `scripts/build_ui_series.py` avant d'offrir un vrai réglage.
