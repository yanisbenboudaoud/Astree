# #131 — Écran Tribunal : débat sur un seul écran, verdict toujours visible

- **Issue** : #131 · **PR** : #133 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Une revue d'ergonomie de l'écran Tribunal. L'ordre suit maintenant ce qu'il faut pour juger : le constat, les débats, les limites, puis le dossier à consulter au besoin.

- **`frontend/src/ecrans/Tribunal.tsx`** :
  - **Débat d'un seul regard** (`Debat`, `Case`, `Plaidoyer`) : le carrousel à onglets est remplacé par un tableau, une ligne par question (`regrouperDebat`), le Procureur à gauche, l'Avocat à droite. Tout le texte de chaque argument est visible, avec son étiquette et ses pièces sur la même ligne ; plus de bouton « Voir la preuve ». Les 7 points d'un procès tiennent dans 1440×900. Sous 860 px, chaque ligne s'empile (question, Procureur, Avocat).
  - **Bilan** : le Pacte est affiché règle par règle (statut, § et pièces), avec la date de signature. À côté, « Ce qui rendrait la décision conforme » lit les points de bascule du contrat (`pointsDeBascule`, fiche 061), jusque-là visibles seulement à l'écran Verdict. Les contrôles du système (chiffres, cadre, performance passée…) sont regroupés à part et repliés.
  - **Barre du verdict** : fixe en bas de l'écran (« Le Tribunal a terminé. À vous de juger. », le constat, « Modifier la décision », « Rendre mon verdict »). Sur téléphone, seulement les deux boutons, sur une ligne.
  - **Ordre** : bilan → débats → arguments contrôlés → « Ce que ce procès ne dit pas » (ouvert d'office) → questions aux agents → « Le dossier » (déroulé, pièces, sources, « Mettre le Greffier à l'épreuve »).
- **`frontend/src/domaine/debat.ts`** : nouveau thème `recuperation` (« Combien de temps pour s'en remettre ? »), essayé en premier. Un argument du type « NVDA a mis 1,5 an à retrouver son niveau » n'est plus rangé sous « Combien pourriez-vous perdre ? ».
- **`frontend/src/components/TrompezLeGreffier.tsx`** : option `integre` (pas de carte ni d'en-tête visible dans une section repliable) ; chaque case à cocher montre le nom de la pièce, pas seulement « P5 ».
- **`frontend/src/components/Limites.tsx`** : option `ouvertParDefaut` de `LimitesDonnees`.
- **`frontend/src/styles/tokens.css`** : `--police-solennelle`, police à empattements du système (aucune police à télécharger) pour le titre de l'audience, les questions du débat, le verdict du bilan et la barre du verdict.
- **`frontend/e2e/greffier.mjs`** : ouvre « Mettre le Greffier à l'épreuve » avant l'essai ; attend `#titre-bilan` (même ligne que #130).

## Comment l'utiliser
Rien à faire : l'écran Tribunal l'affiche pour tout procès, enregistré ou en direct.

## Comment vérifier
- Depuis `frontend/` : `npx tsc --noEmit` passe ; `npm test` donne 130 tests sur 132. Les 2 échecs de `domaine.test.ts` (« Tribunal occupé ») existaient avant.
- `src/test/debat.test.ts` : deux cas `recuperation` (« retrouver son niveau », « a retrouvé ce sommet »).
- Mode démonstration (`VITE_USE_MOCKS=true`), Robert, « 30 % en TSLA » : à 1440×900, les 7 points du débat tiennent sur un écran ; à 375 px, aucun défilement horizontal et barre du verdict sur une ligne.

## Choix faits en cours de route
- **Un tableau plutôt qu'un carrousel** : un carrousel cache tous les points sauf un, et on compare mal ce qu'on ne voit pas en même temps. Le tableau est plus long, mais il se lit sans rien retenir.
- **Une ligne même quand un seul camp plaide** : la case vide le dit (« Pas d'argument sur ce point »). Le tableau montre honnêtement où les camps se répondent et où ils ne se croisent pas.
- **Police du système** : une police servie par npm aurait ajouté une dépendance ; la pile `--police-solennelle` utilise ce que le système a (Iowan Old Style, Charter, Cambria, Georgia…).

## Limites et suite
- Le regroupement des arguments reste lu par expressions régulières sur la première phrase (`debat.ts`) : un argument mal formulé peut tomber sous une autre question.
- Le rendu de la police à empattements varie un peu selon le système.
- `verifier:greffier` n'a pas été relancé : il demande la Lambda en direct.
