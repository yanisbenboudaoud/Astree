# #121 — Limites des données sur chaque écran

- **Issue** : #121 · **PR** : #PR · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Chaque écran dit ce que ses chiffres ne disent pas, là où on les lit, comme le demande l'énoncé (p. 13, 16 et 17) :
- distinguer faits, hypothèses et scénarios fictifs ;
- présenter les incertitudes de façon compréhensible ;
- expliquer chaque indicateur et ses limites sur une période explicitée ;
- rappeler que la volatilité n'est qu'un indicateur de risque parmi d'autres.

- **`frontend/src/domaine/limites.ts`** : le catalogue unique.
  - `INDICATEURS` : pour chaque indicateur, ce qu'il mesure et sa limite, en une phrase chacun (rendement, volatilité, pire baisse, rendement 2022, parts des catégories, valeur, taille compatible, corrélation, récupération, seuil du Pacte).
  - `LIMITES` : les limites de la méthode (période unique, biais du survivant, prix réels et portefeuille simulé, conversion en CAD, risque en un chiffre, avenir, seuils hypothétiques, arguments écrits par une IA, données ESG, Pacte vécu, barème du questionnaire, rien après la fin des données). Les sources citées ont été vérifiées dans `alphaforge_starter/sources_metadata.csv`.
  - `LIMITES_PAR_ECRAN` : les limites de chaque écran, de la plus importante à la moins importante.
- **`frontend/src/components/Limites.tsx`** :
  - `InfoLimite` : un ⓘ à côté d'un indicateur. Sa bulle est rendue au-dessus de la page (portail, position fixe), pour qu'aucun tableau ne la coupe. Elle se ferme au clic dehors, avec Échap ou au défilement.
  - `LimitesDonnees` : « Ce que ces chiffres ne disent pas », en `ligne` repliée ou en `panneau` pour une colonne latérale. Le panneau est ouvert d'office à partir de 1280 px de large.
- **Écrans** :
  - Portefeuille : ⓘ sur la valeur et les indicateurs, étiquettes « Fait » (prix) et « Fictif » (portefeuille), panneau dans la colonne latérale.
  - Décision : ⓘ sur chaque ligne du tableau, sur la limite du Pacte et sur la taille compatible ; colonne « avec la décision » marquée « simulation » (`Effet.indicateur` ajouté dans `domaine/decision.ts`).
  - Tribunal : « Ce que ce procès ne dit pas » sous le débat, à la place du seul encadré sur le biais du survivant.
  - Verdict, Pacte vécu et aperçu de Construire mon Pacte : panneau dans la colonne latérale.

**Mise en page en paysage** (portables de 14 à 16 pouces) :
- `--conteneur-large` passe de 1344 à 1600 px.
- Décision en trois colonnes à partir de 1280 px : réglage, effet sur le Pacte, limites. Le bouton « Soumettre au Tribunal » reste visible en bas de l'écran.
- `GraphiqueRecul` accepte `hauteurTrace` (150 px sur Décision).
- Construire mon Pacte en deux colonnes. Pour les questions, la progression est à gauche avec « À quoi sert votre réponse » (`USAGES`, tiré du champ `alimente` de `config/questionnaire.json`) et la question à droite. L'aperçu a son résumé, ses limites et sa signature à gauche, et les règles à droite.

## Comment l'utiliser
Pour changer une phrase de limite, modifier `domaine/limites.ts` : tous les écrans suivent. Pour ajouter une limite à un écran, l'ajouter à `LIMITES_PAR_ECRAN`.

## Comment vérifier
- Depuis `frontend/` : `npx tsc --noEmit` passe ; `npm test` donne 118 tests sur 120. Les 2 échecs de `domaine.test.ts` (« Tribunal occupé ») existaient avant.
- `src/test/limites.test.tsx` vérifie :
  - que chaque limite citée existe ;
  - que la période est explicitée et que la volatilité est dite « parmi d'autres » ;
  - qu'aucune phrase ne promet ni ne conseille ;
  - l'ouverture et la fermeture de la bulle et du bloc.
- Navigateur, mode démonstration : à 1556×900, l'écran Décision montre le réglage, le bouton de soumission, le tableau et les six limites sans défiler. À 375 px de large, aucun écran ne déborde.

## Choix faits en cours de route
- **La limite au bon endroit, pas en bloc** : un ⓘ par indicateur et une liste par écran, plutôt qu'un avertissement général que personne ne lit.
- **Trois étiquettes seulement** (fait, hypothèse, fictif, CLAUDE.md section 4) : la simulation est « Fictif », précisée par le mot « simulation ».
- **Panneau ouvert d'office sur grand écran, replié sur téléphone** : l'espace libre du paysage sert à lire les limites sans clic.

## Limites et suite
- Sur Décision, à 900 px de haut, le bas des messages d'alerte et l'axe des années du graphique demandent encore un léger défilement.
- `USAGES` résume le champ `alimente` à la main : une nouvelle question du questionnaire doit y avoir sa phrase.
