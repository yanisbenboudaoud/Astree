# #153 — Pièces à conviction : expliquer ce que montre chaque pièce et ce que sont P1, P2, P3

- **Issue** : #153 · **PR** : à venir · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Le tiroir d'une pièce dit maintenant, en mots simples, ce qu'est une pièce, ce qu'elle montre et comment lire son chiffre. Ses textes techniques sont coupés en listes courtes.

- **`frontend/src/domaine/pieces.ts`** (nouveau) :
  - `DEFINITION_PIECE` : ce que sont P1, P2, P3 (preuves numérotées, seules citables par le Procureur et l'Avocat, vérifiées par le Greffier).
  - `guidePiece(piece)` : « Ce que montre cette pièce » et, au besoin, « Lire le chiffre », selon l'outil qui l'a produite (`simuler_portefeuille`, `indicateurs_actif`, `points_de_bascule`, `calibrer_pacte`…). Le rejeu de 2022 a son propre texte. Outil inconnu : texte selon le type (`calculee`, `documentaire`, `declaree`). Aucun chiffre : les valeurs restent celles de la pièce.
  - `decouperEnPoints(texte)` : coupe source, traitement et limites aux « ; », comme les pièces les séparent.
  - `numeroPiece(code)` : « P2 » → 2.
- **`frontend/src/components/TiroirPiece.tsx`** : « Pièce P2 · 2e preuve du dossier », encart repliable « C'est quoi, une pièce (P1, P2, P3…) ? », encart « Ce que montre cette pièce », listes « D'où viennent les données » et « À garder en tête », et « Comment c'est calculé » replié, en étapes numérotées.
- **`frontend/src/components/Etiquettes.tsx`** : contexte `TitresPieces` ; chaque pastille P1, P2… affiche le titre de sa pièce au survol et dans son nom accessible (« Ouvrir la pièce P2 : Simulation du portefeuille… »).
- **`frontend/src/ecrans/Tribunal.tsx`** : fournit `TitresPieces` ; la liste « Pièces à conviction » du dossier commence par `DEFINITION_PIECE`.
- **`frontend/src/api/types.ts`**, **`adaptateur.ts`** : `Piece` porte `outil` et `type`, repris du contrat.

## Comment l'utiliser
Ouvrir une pastille P1, P2… sur l'écran Tribunal.

## Comment vérifier
```bash
cd frontend
npx vitest run src/test/pieces.test.ts
ASTREE_URL=http://localhost:5173 node e2e/verifier.mjs
```
Le premier test vérifie le découpage, les explications par outil et le repli par type. Le parcours e2e passe (23 écrans, axe-core sans erreur) ; son contrôle du retour du focus accepte le nouveau nom accessible des pastilles.

## Choix faits en cours de route
- Les textes de la pièce (`source`, `traitement`, `limites`) ne sont pas réécrits : ils viennent de Python et restent fidèles aux données. L'interface les découpe seulement et ajoute une explication par outil, écrite une fois.
- Le traitement, le plus technique, est replié par défaut ; la source et les limites restent visibles.

## Limites et suite
- Un nouvel outil sans entrée dans `guidePiece` reçoit l'explication générique de son type : ajouter une entrée dans `pieces.ts`.
- Les termes techniques des sources (« adj_close ») restent tels que Python les écrit.
