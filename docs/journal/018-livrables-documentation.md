# #18 — Livrables : README, documentation technique, vidéo et one pager

- **Issue** : #18 · **PR** : #30, #PR_DOC · **Statut** : en cours (README, journal, documentation technique et one pager en place ; reste la vidéo)
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
- **`README.md`** (racine) : présentation du projet, « Par où commencer », démarrage, configuration, **carte du dépôt** (chaque fichier important, son rôle et sa fiche du journal), sources des données.
- **`docs/journal/`** : le journal de construction.
  - `README.md` : à quoi sert le journal, ses règles et le modèle de fiche.
  - Fiches rétroactives pour le travail déjà fusionné : `000` (fondations), `002` (contrat JSON), `003` (Pacte générique), `004` (`charger_donnees`), `007` (client LLM).
- **`CLAUDE.md`, section 11** : nouvelle règle « Journal » : chaque PR qui termine ou avance une issue ajoute ou met à jour sa fiche, et la carte du dépôt si besoin. Comme `CLAUDE.md` est partagé par Git, la session Claude de chaque membre suit cette règle.
- **`.github/pull_request_template.md`** : deux cases à cocher, la fiche du journal et la carte du dépôt.

PR #PR_DOC (2026-11-15) :
- **`docs/DOCUMENTATION_TECHNIQUE.md`** : rôle de chaque agent, orchestrateur et garde-fous (liste blanche, budget de 8 appels, pièce obligatoire, phases fixes), outils, méthode de calcul et hypothèses, Pacte générique, explicabilité, règles de `verifier_chiffres`, validations, limites et schéma AWS. Elle renvoie à `CLAUDE.md`, `docs/CHOIX_CONCEPTION.md`, `docs/architecture.md` et aux fiches au lieu de les recopier ; chaque chiffre cité renvoie à son fichier.
  - Exemple d'explicabilité tiré d'un vrai procès (`frontend/src/data/proces/2026-11-15-032ec3367b19.json`, 25 % en TSLA) : argument du Procureur → pièce `P4` (`indicateurs_actif`) → étape de la trace avec la raison de l'orchestrateur → `prices_daily.csv` et `fx_usdcad_daily.csv`, puis la commande qui recalcule la pièce.
  - Exemple d'argument renvoyé puis corrigé, tiré de l'étape `bedrock_correction` du même procès (« 30 % » introuvable dans `P6`).
- **`docs/ONE_PAGER.md`** : problème, Tribunal, originalité, données, explicabilité, bénéfices, en une page.
- **`README.md`** : « Par où commencer » et carte du dépôt pointent vers les deux fichiers ; nouvelles sections « Juger une décision en local », « Déployer sur AWS », « Reproduire les résultats » et « Ajouter un profil ».

## Comment l'utiliser
- Pour s'y retrouver : la carte du `README.md`, puis la fiche liée.
- Pour une nouvelle issue : copier le modèle de `docs/journal/README.md` dans `docs/journal/NNN-titre-court.md` et le remplir dans la même PR que le code.

## Comment vérifier
Ouvrir le `README.md` sur GitHub : chaque lien de la colonne « Fiche » mène à une fiche existante.

Documentation technique : chaque lien relatif mène à un fichier existant (sauf `docs/validation/evaluation_orchestrateur.md`, cité par sa PR #175 tant qu'elle n'est pas fusionnée). L'exemple de la section 6 se rejoue : `python -c "from pipeline.indicateurs import indicateurs_actif as i; print(i('TSLA')['valeurs'])"` redonne les valeurs de `P4` (`pire_baisse` −0.708806, `annees_recuperation` 2.921287).

## Choix faits en cours de route
- **Un fichier par issue**, plutôt qu'un seul `JOURNAL.md` : plusieurs PR avancent en parallèle, et un fichier commun entrerait en conflit à chaque fusion.
- **Deux vues séparées** : la carte du `README.md` donne l'état actuel et se met à jour sur place ; les fiches gardent l'histoire et ne sont pas réécrites quand le code change plus tard.
- **Pas d'index des fiches** : la liste du dossier, triée par numéro, en tient lieu, et un index commun serait une autre source de conflits.
- **Pas de hook** : une règle dans `CLAUDE.md` et une case dans le modèle de PR suffisent pour un projet de 2 jours.

## Limites et suite
Reste à faire dans cette issue : la **vidéo**.

- Les chiffres de l'évaluation de l'orchestrateur (#167) viennent de la PR #175, encore ouverte le 2026-11-15 : relire la section 3 de la documentation technique si son rapport est régénéré avant la fusion.
- `docs/architecture.md` indique encore le profil d'inférence `us.` et une durée de procès de 25 à 40 s ; la documentation technique s'en tient au profil global (#150) et à la mesure de la fiche 022 (37,4 s pour le procès le plus long).
- La documentation décrit l'état du 2026-11-15 : une fonction renommée plus tard doit y être corrigée.
