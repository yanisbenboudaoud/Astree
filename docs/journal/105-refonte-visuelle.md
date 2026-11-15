# #105 — Refonte visuelle épurée : fond blanc, Inter, graphiques en couleur

- **Issue** : #105 · **PR** : #106 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Une refonte du style seulement, sans changer le parcours ni les données. Le style « papier crème + serif » cède la place à un style fintech épuré : fond blanc, une seule famille sans empattement, surfaces gris très clair, formes arrondies.

- **Jetons** (`frontend/src/styles/tokens.css`) : nouvelle palette sur fond `#ffffff` (encre `#111111`, texte tertiaire `#626262` à 6,1:1, `--trait-moyen` `#8a8a8a` à 3,4:1). Nouveaux jetons :
  - `--fond-sourdine` pour les grands panneaux ;
  - `--donnee-principale` (indigo), `--donnee-secondaire` (gris) et `--categorie-1` à `--categorie-6` pour les données ;
  - `--rayon` 16, `--rayon-moyen` 12, `--rayon-petit` 8 et `--rayon-pilule` ;
  - `--ombre-flottante` et `--police-code`.
  - Les ratios de contraste sont notés en commentaire à côté de chaque couleur.
- **Typographie** (`index.html`, `styles/base.css`) : Inter remplace Newsreader et Atkinson Hyperlegible. JetBrains Mono est gardé pour la trace (`.t-trace`). Les titres sont en graisse 600 avec une approche serrée, et les chiffres en chasse fixe (`tabular-nums` sur `body`). Les sections ont un filet fin `--trait-fin` au lieu du filet encre de 1,5 px.
- **Arrondis** : les rayons écrits en dur (2, 3, 4 px) de tous les `*.module.css` passent par les jetons. Boutons, champ de recherche, étiquettes de statut et de provenance sont en pilule.
- **Composants** :
  - `Bouton` : 48 px, et le secondaire a une bordure `--trait-moyen` ;
  - `Gabarit` : bandeau de simulation clair, en-tête de 72 px, étape faite en vert, menus avec ombre ;
  - `Elements` : jauge indigo arrondie, message bordé au lieu de la barre gauche de 4 px ;
  - `Etiquettes` : provenance et statut en pilule, code des pièces en gras.
- **Recherche** (`components/Recherche.module.css`, `Recherche.tsx`) : le bandeau noir devient un panneau clair (`--fond-sourdine`). Le sélecteur titre / panier devient segmenté et le champ passe en pilule avec un halo bleu au focus. « Instruire le panier » passe de la variante `inverse` à `primaire`.
- **Graphiques** :
  - `GraphiqueValeur.tsx` : ajout d'un `<linearGradient id="degrade-valeur">` pour l'aire ;
  - `Graphiques.module.css` : courbe de valeur et courbe « avec la décision » en indigo, « Actuel » en gris, limite du Pacte et pire baisse en rouge, repères en pointillés légers, bulle de lecture avec ombre.
- **Portefeuille** (`ecrans/Portefeuille.tsx`) : la barre de répartition prend les couleurs `--categorie-*` (`TEINTES`) au lieu des nuances d'encre, avec des segments arrondis et des puces rondes dans la légende.
- **Entrée** : initiale en bleu dans un rond, cartes et panneau « Construire mon Pacte » plus aérés.
- **Spec** (`docs/maquette/spec_interface_astree.md`) : annexe A (couleurs, règle d'usage des données, typographie, rayons, ombres, sections, composants) et passages de D.2 et D.3 qui décrivaient l'ancien style.

## Comment l'utiliser
Rien à changer : `npm run dev` depuis `frontend/`. Pour changer une couleur, modifier le jeton dans `tokens.css` ; aucun composant n'écrit de couleur en dur.

## Comment vérifier
- Depuis `frontend/` : `npx tsc --noEmit` passe. `npm test` donne 79 tests sur 81 : les 2 échecs de `domaine.test.ts` (« Tribunal occupé ») existaient déjà sur `main` avant ce changement et ne touchent pas au style.
- `npm run verifier` : 23 écrans vérifiés par axe-core (contrastes compris), aucun débordement à 1440 et 1280 px. Lancé sur le serveur de démonstration (port 5175), il ne signale que des erreurs CORS vers la Lambda : seul `http://localhost:5173` est autorisé (#14).
- Captures de Robert à 1440 px. Avant : celles de la fiche 103. Après :

| Écran | Avant | Après |
|---|---|---|
| Portefeuille | [avant](captures/103/apres-portefeuille.png) | [après](captures/105/apres-portefeuille.png) |
| Décision | [avant](captures/103/apres-decision.png) | [après](captures/105/apres-decision.png) |
| Verdict | [avant](captures/103/apres-verdict.png) | [après](captures/105/apres-verdict.png) |
| Entrée, Tribunal | — | [entrée](captures/105/apres-entree.png), [tribunal](captures/105/apres-tribunal.png) |

## Choix faits en cours de route
- **Une seule famille (Inter)** : plus sobre et plus lisible pour les chiffres qu'un mélange serif + mono. Les noms de variables (`--police-titre`, `--police-mono`) et de classes (`.t-h1`…) sont gardés pour ne toucher à aucun composant.
- **Une couleur = un sens, toujours** : l'indigo des données n'est utilisé pour aucun statut. Le vert n'est pas pris pour la courbe, parce qu'il signifie « conforme ». Les couleurs de catégorie ne servent qu'à la barre de répartition, et la légende donne toujours le libellé et le pourcentage : la couleur ne porte jamais seule l'information.
- **Contraste d'abord** : tout texte reste à 4,5:1 ou plus, tout bord de contrôle à 3:1 ou plus (règle de #103). Les teintes de catégorie, plus claires, sont décoratives.
- Le bouton secondaire et le champ gardent une bordure `--trait-moyen`. Un bouton gris plein sans bordure aurait été plus minimaliste, mais il aurait cassé la règle WCAG 1.4.11 de #103.

## Limites et suite
- Les captures « avant » de la fiche 103 montrent l'ancien style.
- Les gains et pertes restent en encre avec ▲/▼, comme le veut la spec. Les colorer en vert ou en rouge mélangerait leur sens avec celui des statuts du Greffier.
- Inter et JetBrains Mono viennent de Google Fonts : hors ligne, l'interface retombe sur la police système.
