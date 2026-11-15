# #118 — Bilan du Greffier en langage clair

- **Issue** : #118 · **PR** : #PR · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Le bilan en tête de l'écran Tribunal dit ce qui se passe et à quoi sert le Greffier, au lieu de reprendre ses messages bruts (« 1 Violation · 4 À vérifier · 3 Conforme — Pire baisse −13,5 % au-delà du seuil −12,0 % »).

- **`frontend/src/domaine/bilan.ts`** :
  - `bilanGreffier(controles, contrat)` rend le ton (`violation`, `a_juger` ou `conforme`), une phrase de verdict (« 1 règle de votre Pacte est enfreinte »), l'explication de la première règle enfreinte, les contrôles expliqués et leurs comptes par groupe.
  - `expliquerControle(controle, contrat)` donne à chaque contrôle un groupe (`enfreint`, `a_juger`, `verifie`), un titre et une phrase. Pour une règle du Pacte, la phrase dépend de son type : pire baisse, avec le pourcentage tiré de `comparaison.apres` et le montant en dollars de la pièce de simulation (`perte_au_pire_moment_cad`, `capital`, fiche 107) ; plafond ; critère documentaire ; règle qualitative. Les contrôles du système (`verifier_chiffres`, `cadre_simulation`, `performance_passee`, `biais_survivant`…) ont un titre fixe (« Aucun chiffre inventé », « Un passé un peu trop beau »).
  - `GROUPES` : titre et phrase d'aide de chaque groupe.
- **`frontend/src/ecrans/Tribunal.tsx`** : le bloc du bilan montre un surtitre (« Le Greffier a vérifié votre décision · calcul Python, sans IA »), le verdict coloré selon le ton, l'explication, les comptes en mots et « Voir le détail ». Le détail range les contrôles par groupe ; le rappel « Règle que vous avez signée… » reste en tête. L'écart entre les blocs de la page passe de 32 à 24 px, pour que la salle d'audience (fiche 107) tienne toujours dans 1440×900.
- **Le Greffier et le contrat ne changent pas** : rien n'est recalculé, les chiffres viennent du contrat.
- Cette PR apporte aussi dans `main` le débat point par point et la salle d'audience décrits dans la fiche 107 : leurs deux commits ont été poussés après la fusion de #108.

## Comment l'utiliser
Rien à faire : l'écran Tribunal l'affiche pour tout procès, enregistré ou en direct.

## Comment vérifier
- Depuis `frontend/` : `npx tsc --noEmit` passe ; `npm test` donne 112 tests sur 114. Les 2 échecs de `domaine.test.ts` (« Tribunal occupé ») existaient avant.
- `src/test/bilan.test.ts`, sur les procès enregistrés :
  - Robert : verdict, pourcentage et dollars tirés du contrat ;
  - Amira : pluriel ;
  - Mateo : aucun nom technique ;
  - chaque contrôle est rangé, et le § du Pacte n'est pas répété dans la phrase.

## Choix faits en cours de route
- **Traduire dans l'interface plutôt que dans le Greffier** : les messages du Greffier restent courts et stables pour le contrat, la trace et le procès-verbal ; l'interface les dit pour un visiteur.
- **Une phrase par type de règle**, pas par profil : comme le Greffier, `bilan.ts` lit le type de la règle, jamais un nom de profil.

## Limites et suite
- Un nouveau contrôle du système sans titre dans `SYSTEME` s'affiche avec le message brut du Greffier.
- Le montant en dollars n'apparaît que pour les procès dont la pièce de simulation porte le capital (fiche 107) ; les plus anciens n'ont que le pourcentage.
