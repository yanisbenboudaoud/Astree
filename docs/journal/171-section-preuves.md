# #171 — Section « Preuves » : chaque promesse reliée à sa mesure

- **Issue** : #171 · **PR** : à venir · **Statut** : en cours (la ligne de #172 attend le bulletin du Greffier)
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
- `README.md`, section **« Preuves »** (et une ligne vers elle dans « Par où commencer ») : un tableau promesse → résultat mesuré (k/N, intervalle de Wilson à 95 % quand le rapport le donne) → rapport, pour #165, #166, #167, #168 et #169. La ligne de #172 est marquée « à venir ».
- `docs/validation/README.md` : index des rapports de `docs/validation/`, ce que mesure chacun, la commande qui le régénère et ses limites.
- `docs/DOCUMENTATION_TECHNIQUE.md` : les chiffres de l'orchestrateur (sections 3 et 8) étaient ceux d'une lecture antérieure (183 procès) ; ils sont alignés sur le rapport actuel (201 procès). La section 8 renvoie à « Preuves » et à l'index.
- `docs/CHOIX_CONCEPTION.md` : choix 6 et « Limites connues » renvoient aux mesures, sans recopier les chiffres.
- `docs/CARTE_DU_DEPOT.md` : ligne `docs/validation/README.md`.

## Comment l'utiliser
Lire la section « Preuves » du `README.md`, puis suivre le lien du rapport de chaque ligne. Pour refaire une mesure : la commande est dans `docs/validation/README.md`.

## Comment vérifier
Chaque chiffre de la section se retrouve tel quel dans le rapport de sa ligne (bloc « Résultat » ou « En bref ») :
- #165 : `docs/validation/evaluation_chiffres.md` ; #166 : `evaluation_cadre.md` ; #168 : `validation_externe.md` ;
- #167 : `evaluation_orchestrateur.md`, « En bref », tableau « Par profil » (robert, amira, mateo) et « Plan de procès » ;
- #169 : le run GitHub Actions cité (commit `e8f0a34`) : `1033 passed, 24 deselected`, `Tests 144 passed (144)`, 10 contrats ✓.

## Choix faits en cours de route
- **Recopier les chiffres plutôt que de seulement renvoyer** : le but de l'issue est que le jury les trouve en une minute. En contrepartie, chaque cellule nomme son rapport, et l'index dit comment le régénérer.
- **Pas d'intervalle calculé ici** : quand le rapport ne donne pas d'intervalle (outils par profil, comptes de tests), la section donne k/N seul. Aucun chiffre de la section n'est absent de son rapport.
- **Les taux bas restent en évidence** (cadre : 47/78, et 9/20 sur les cas écrits sans accès au code ; mauvaise grandeur : 0/6), avec la raison en une phrase.
- **Tests** : les comptes changent à chaque push ; la section les date et cite le run, le badge donne l'état courant.
- PR découpée en deux (`Avance #171`) : tout ce qui ne dépend pas de #172 maintenant.

## Limites et suite
- **Reste à faire** : remplir la ligne #172 quand le bulletin du Greffier (`frontend/src/data/bulletin.json`) sera fusionné, puis fermer l'issue.
- Les chiffres recopiés vieillissent : après une nouvelle mesure (surtout `evaluation_orchestrateur`, qui relit les procès archivés), mettre à jour la section « Preuves » et la section 3 de la documentation technique.
