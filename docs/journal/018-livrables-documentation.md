# #18 — Livrables : README, documentation technique, vidéo et one pager

- **Issue** : #18 · **PR** : à compléter · **Statut** : en cours (README et journal en place)
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`README.md`** (racine) : présentation du projet, « Par où commencer », démarrage, configuration, **carte du dépôt** (chaque fichier important, son rôle et sa fiche du journal), sources des données.
- **`docs/journal/`** : le journal de construction.
  - `README.md` : à quoi sert le journal, ses règles et le modèle de fiche.
  - Fiches rétroactives pour le travail déjà fusionné : `000` (fondations), `002` (contrat JSON), `003` (Pacte générique), `004` (`charger_donnees`), `007` (client LLM).
- **`CLAUDE.md`, section 11** : nouvelle règle « Journal » : chaque PR qui termine ou avance une issue ajoute ou met à jour sa fiche, et la carte du dépôt si besoin. Comme `CLAUDE.md` est partagé par Git, la session Claude de chaque membre suit cette règle.
- **`.github/pull_request_template.md`** : deux cases à cocher, la fiche du journal et la carte du dépôt.

## Comment l'utiliser
- Pour s'y retrouver : la carte du `README.md`, puis la fiche liée.
- Pour une nouvelle issue : copier le modèle de `docs/journal/README.md` dans `docs/journal/NNN-titre-court.md` et le remplir dans la même PR que le code.

## Comment vérifier
Ouvrir le `README.md` sur GitHub : chaque lien de la colonne « Fiche » mène à une fiche existante.

## Choix faits en cours de route
- **Un fichier par issue**, plutôt qu'un seul `JOURNAL.md` : plusieurs PR avancent en parallèle, et un fichier commun entrerait en conflit à chaque fusion.
- **Deux vues séparées** : la carte du `README.md` donne l'état actuel et se met à jour sur place ; les fiches gardent l'histoire et ne sont pas réécrites quand le code change plus tard.
- **Pas d'index des fiches** : la liste du dossier, triée par numéro, en tient lieu, et un index commun serait une autre source de conflits.
- **Pas de hook** : une règle dans `CLAUDE.md` et une case dans le modèle de PR suffisent pour un projet de 2 jours.

## Limites et suite
Reste à faire dans cette issue :
- README : reproduction des résultats et « comment ajouter un profil », quand le chargeur de Pacte (#3) existera ;
- documentation technique (les fiches du journal et `docs/CHOIX_CONCEPTION.md` en sont la base) ;
- vidéo et one pager.
