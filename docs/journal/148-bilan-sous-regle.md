# #148 — Bilan du Greffier : chaque explication sous sa règle

- **Issue** : #148 · **PR** : #149 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Dans le bilan du Greffier (écran Tribunal), l'explication de la première règle enfreinte (« Votre portefeuille perdrait 58,2 % de sa valeur… ») était affichée sous le titre général et masquée sous sa propre règle. On ne voyait pas à quelle règle elle se rapportait. Désormais, chaque explication reste sous sa règle.

- **`frontend/src/domaine/bilan.ts`** : `Bilan` perd le champ `explication` ; `bilanGreffier` ne donne plus que le compte (`verdict` : « 2 règles de votre Pacte sont enfreintes »). L'explication de chaque règle reste dans `controles[].detail`.
- **`frontend/src/ecrans/Tribunal.tsx`** :
  - la phrase sous le titre du bilan est retirée ; le `detail` de chaque règle s'affiche toujours, §1 compris ;
  - dans « Ce qui rendrait la décision conforme », chaque ligne porte le numéro de sa règle (« §1 · Règle « Pire baisse tolérée : −20 % » »), comme la liste de gauche.
- **`frontend/src/test/bilan.test.ts`** : les tests lisent l'explication dans le contrôle de la règle (Robert : pire baisse en pourcentage et en dollars ; Mateo : source sur XOM).

## Comment vérifier
- Depuis `frontend/` : `npx tsc --noEmit` passe ; `npm test` donne 135 tests sur 137. Les 2 échecs de `domaine.test.ts` (« Tribunal occupé ») existaient avant.
- Mode démonstration, Robert, 30 % en TSLA : sous « 1 règle de votre Pacte est enfreinte », plus de phrase ; « Votre portefeuille perdrait 29,0 %… » est sous « Au pire moment, la baisse dépasse votre limite · §1 », et la bascule de droite dit « §1 · Règle… ».

## Choix faits en cours de route
- **Pas de résumé sous le titre**, même avec une seule règle enfreinte : la phrase se lit déjà sous sa règle, juste en dessous ; la répéter en ferait un doublon.

## Limites et suite
- La barre du bas de l'écran Tribunal (« Le Tribunal a terminé ») reprend le compte et le premier point de bascule, sans numéro de règle.
