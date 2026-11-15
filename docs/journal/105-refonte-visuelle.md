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
- **Positions** (`ecrans/Portefeuille.tsx`, `Positions`) : la barre de répartition prend les couleurs `--categorie-*` (`TEINTES`) au lieu des nuances d'encre. La liste devient un tableau regroupé par classe d'actifs :
  - chaque groupe a un en-tête avec son sous-total en dollars et en part ;
  - chaque titre a un monogramme rond teinté de la couleur du groupe et une barre de poids ;
  - survoler un groupe estompe les autres ;
  - le total du portefeuille est affiché à côté du titre de la section ;
  - `Monogramme` accepte maintenant une `className`.
  - La couleur du groupe passe par la variable CSS `--cat`, posée en ligne sur chaque bloc.
- **Carte « Votre Pacte » et journal** (`ecrans/Portefeuille.tsx`, `Portefeuille.module.css`) : la carte est recomposée.
  - En-tête : « Signé le … » et un état en point coloré au lieu de la pastille.
  - Chiffre clé (`RegleCle`) : la valeur de la règle la plus proche de sa limite en grand (« −15,1 % / −20 % »), une jauge arrondie et ses deux bornes écrites.
  - Les règles sont **toujours visibles**, avec leur statut écrit (Respectée, Enfreinte, À juger), au lieu du bouton « Voir les N règles ».
  - Le Pacte vécu (`PacteVecu`) devient un pied de carte cliquable, au lieu d'un encadré gris imbriqué.
  - Le journal devient une frise verticale : un point coloré par statut et le statut en toutes lettres (« Conforme au Pacte »), au lieu des seules coches.
- **Écran Décision** (`ecrans/Decision.tsx`, `Decision.module.css`) :
  - bloc Taille recomposé : grand chiffre, état écrit avec un point coloré (« Compatible avec votre Pacte jusqu'à 11 % »), **une seule piste** qui porte les zones (vert pâle, hachures rouges), le remplissage et le repère du maximum, poignée blanche ombrée, « max. 11 % » sous la piste ;
  - tailles rapides en contrôle segmenté, avec une pastille « max. » ; la légende des zones et la bande sous la piste sont retirées ;
  - tableau des effets : la colonne de la décision ressort sur fond gris très clair, et le statut devient une icône après la limite (plus de colonne Statut) ;
  - `Message` (`components/Elements`) : fond teinte arrondi sans bordure ;
  - `GraphiqueRecul` **refait** (styles dans `GraphiqueRecul.module.css`, retirés de `Graphiques.module.css`) :
    - une phrase de lecture en tête donne la conclusion (limite franchie pendant N séances et quand, ou jamais franchie) ; « 1 séance » est désormais au singulier ;
    - la légende est intégrée à l'en-tête ;
    - une bande verticale marque la période sous la limite, et les deux pires moments (aujourd'hui et avec la décision) sont annotés ;
    - lecture comparative au survol et au clavier : une bulle avec les deux valeurs à la même date, lues telles quelles dans les séries ;
    - nouvelle prop `creuxActuel` ; tests dans `src/test/graphiqueRecul.test.tsx` (phrase au singulier, limite jamais franchie, lecture au clavier) ;
  - les guillemets « » des messages ESG (`domaine/decision.ts`) sont collés au texte par des espaces insécables, pour ne plus rester seuls en fin de ligne.
- **Correctif : décision sur un titre pour un profil en mode panier.** Amira est en mode panier, et `scripts/build_ui_series.py` ne lui générait que la table du panier. Choisir « Un titre » (#99) laissait donc l'écran Décision sur « Chargement de la simulation… » indéfiniment.
  - Le script génère maintenant les tables d'une position pour **tous** les profils (`decisions/amira/`, 31 titres).
  - `ecrans/Decision.tsx` affiche « Simulation indisponible : aucune simulation précalculée pour ce titre et ce profil » quand une table manque, au lieu d'attendre.
- **Entrée** : initiale en bleu dans un rond, cartes et panneau « Construire mon Pacte » plus aérés.
- **Spec** (`docs/maquette/spec_interface_astree.md`) : annexe A (couleurs, règle d'usage des données, typographie, rayons, ombres, sections, composants) et passages de D.2 et D.3 qui décrivaient l'ancien style.

## Comment l'utiliser
Rien à changer : `npm run dev` depuis `frontend/`. Pour changer une couleur, modifier le jeton dans `tokens.css` ; aucun composant n'écrit de couleur en dur.

## Comment vérifier
- Depuis `frontend/` : `npx tsc --noEmit` passe. `npm test` donne 82 tests sur 84 : les 2 échecs de `domaine.test.ts` (« Tribunal occupé ») existaient déjà sur `main` avant ce changement et ne touchent pas au style.
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
