# Fondations : règles, conception, maquette et conventions

- **Issue** : aucune (travail posé avant les issues de code) · **PR** : #1, #19, #20, #23, #26 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`CLAUDE.md`** : les règles du projet, lues automatiquement par Claude Code.
  - #1 : renommé depuis `instruction.md` ; ajout de l'exigence AWS (diapo 7) et de la grille d'évaluation (diapo 10).
  - #20 : architecture du **Tribunal** (Agent Profil → pièces → Procureur et Avocat → Greffier → verdict de l'utilisateur), les 6 outils (section 4 bis), le contrat JSON (section 5), la méthode de calcul (section 6 bis).
  - Commit `abe9458` : conception orientée vers **trois cas généraux** plutôt que trois personas (section 3).
  - #23 : **orchestrateur Bedrock** et ses garde-fous (section 4), **Pacte générique** à règles typées (section 3), règles de `verifier_chiffres` (section 4 ter), `taille_max_compatible` en V1.
  - #26 : conventions de PR, `Closes #N` / `Avance #N` (section 11).
- **`docs/CHOIX_CONCEPTION.md`** (#19, réécrit par #20 et #23) : le *pourquoi* de chaque choix d'architecture, avec les alternatives écartées. Base de la documentation technique (#18).
- **`docs/maquette/`** (#20) : lien Figma (référence visuelle) et `prototype.html` (comportement des 4 écrans).
- **`.github/pull_request_template.md`** (#26) : chaque PR commence par `Closes #`.
- **`.claude/settings.json`** (commit `71190cd`) : aucune signature de Claude dans les commits et les PR.

## Comment l'utiliser
Lire `CLAUDE.md` en premier, puis `docs/CHOIX_CONCEPTION.md`. Ouvrir `docs/maquette/prototype.html` dans un navigateur pour voir le parcours visé.

## Comment vérifier
Rien à exécuter. Les chiffres de la maquette et du faux contrat ont été recalculés depuis les CSV avec la méthode de la section 6 bis (#23).

## Choix faits en cours de route
- **Un procès plutôt qu'une recommandation** (#20) : le système ne propose pas de portefeuille, ce qui le garde du côté de l'aide à la décision. L'ancien agent Analyse est retiré.
- **Un LLM choisit les outils, Python fixe les phases** (#23) : l'orchestrateur décide quelles preuves rassembler ; l'ordre des étapes, le budget de 8 appels et la pièce obligatoire restent imposés par Python.
- **Bedrock Converse plutôt que Bedrock Agents** (#23) : trace mieux maîtrisée, et le même code tourne en local.

## Limites et suite
Points encore ouverts à la fin de cette phase :
- « Pas exclusivement tech » traduit en **tech + crypto ≤ 75 %** : hypothèse à valider en équipe.
- Point d'accès de l'interface : API Gateway ou Lambda Function URL (#22).
- Format de réponse du contre-interrogatoire, à ajouter au contrat (#12, #14).
