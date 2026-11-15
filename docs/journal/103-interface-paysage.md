# #103 — Recherche au premier plan, mise en page en paysage, chiffres compacts, contrastes et retours visuels

- **Issue** : #103 · **PR** : à venir · **Statut** : en cours (code fait et vérifié ; spec et PR à faire)
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
- **Jetons** (`frontend/src/styles/tokens.css`) :
  - `--marge-page` 48 px dès 1024 px (au lieu de 128 px à 1440 px et plus) et `--conteneur-large` 1344 px (au lieu de 1184) ;
  - `--trait-moyen` passe à `#8a8171` (3,3:1 sur le papier, au lieu de 1,8:1), pour les bords qui montrent un état (WCAG 1.4.11) ;
  - `--trait-fin` un peu plus marqué (`#cbc3b2`) ; nouveaux `--encre-200` (ancienne teinte, décorative), `--ombre-survol` et `--transition`.
- **Portefeuille** (`ecrans/Portefeuille.tsx`, `components/Recherche.tsx`) : la recherche devient un **bandeau en haut, sur toute la largeur** (« Quelle décision voulez-vous tester ? »), avec un champ de 56 px, des **titres suggérés en un clic** (`suggestionsDe` : titres de la décision de démonstration du profil, puis TSLA, NVDA, XOM, BTC-USD) et, à droite, les **3 étapes** du parcours (`EtapesParcours`). Le Pacte et le journal restent dans la colonne de droite. Les indicateurs (rendement, chute maximale, volatilité) sont compacts : chiffre et contexte sur la même ligne.
- **Entrée** (`ecrans/Entree.tsx`) : le titre dit ce que fait Astrée (« Testez une décision d'investissement avant de la prendre. ») ; les cartes se soulèvent au survol.
- **Décision** (`ecrans/Decision.tsx`) : deux colonnes (grille à zones : réglage, messages, actions à gauche ; « Effet sur votre Pacte » à droite, fixe au défilement). Les deux grandes cartes deviennent un **tableau compact** (`LigneEffet`) avec 4 indicateurs : chute maximale, rendement annualisé, volatilité, rendement en 2022 (`effetsSurLePacte` dans `domaine/decision.ts`, champ `detail` ajouté, `limite` facultative). La piste du curseur se remplit en rouge au-delà de la limite, la zone hors limite est hachurée, le chiffre « avec la décision » clignote quand il change. L'écran tient sur une hauteur d'écran (1010 px au lieu de 1580 à 1440 px).
- **Verdict** (`ecrans/Verdict.tsx`) : deux colonnes, les choix à gauche, « Ce qui changerait la réponse » et un bloc « Procès-verbal » à droite.
- **Chargement du Tribunal** (`components/ChargementTribunal.tsx`, `ecrans/Tribunal.tsx`) : deux colonnes ; à droite, `DossierInstruit` (décision, règles du Pacte, pièces versées au fil des étapes réelles). Pastilles des phases à venir en `--encre-500`, phases faites pleines.
- **Retours visuels** : survol et appui des boutons (flèche qui avance, léger enfoncement), raccourcis, suggestions, pièces, menu du profil, options du Verdict, poignée du curseur. Pas de transition sur les couleurs (un état intermédiaire échouait au contraste d'axe-core).
- **Contrastes** : courbe « Actuel » des graphiques en `--trait-moyen` (3,3:1 au lieu de 2,4:1).
- **« Essayez de tromper le Greffier »** : message compréhensible en démonstration au lieu de `VITE_API_URL` (`e2e/greffier.mjs` suit le nouveau texte).

## Comment vérifier
- `npx tsc --noEmit` passe ; `npm test` : 81 tests passent.
- `npm run verifier` : 23 écrans, aucun problème (parcours, axe-core, débordement à 1440 et 1280 px, console).
- À 390 px de large : aucun débordement horizontal sur le Portefeuille et la Décision.

## Choix faits en cours de route
- Les écrans courts (Pacte vécu, Construire mon Pacte, messages d'erreur du Tribunal) gardent la colonne étroite de 776 px : ce sont des formulaires ou des messages, la lecture y est meilleure.
- Le Portefeuille garde « Bonjour Robert. » comme titre de page (le vérificateur l'attend) ; la question de la recherche est le titre du bandeau.

## Limites et suite
- **À faire** : mettre à jour `docs/maquette/spec_interface_astree.md` (annexe A : jetons ; D.2 Portefeuille ; D.4 Décision ; D.5 chargement ; Verdict), ajouter des captures avant / après, ouvrir la PR (`Closes #103`) et renseigner son numéro ici.
