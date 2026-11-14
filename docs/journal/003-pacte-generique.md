# #3 — Pacte générique : schéma, validation et chargement

- **Issue** : #3 · **PR** : #20, #23 · **Statut** : en cours (fichiers en place, chargeur à écrire)
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`personas/robert.json`, `personas/amira.json`, `personas/mateo.json`** : les trois profils de test (étiquette `fictif`). Chacun contient le profil, le portefeuille de départ, la `decision_demo` et le **Pacte** : une liste de règles typées (`pire_baisse_max`, `plafond`, `critere_documentaire`, `qualitative`), chacune avec un `id`, ses paramètres, un `libelle` et une `justification`. Format décrit dans `CLAUDE.md`, section 3.
- **`config/categories.json`** (#23) : les catégories `tech` et `crypto` utilisées par les règles `plafond`, définies **une seule fois** pour tous les profils, à partir des champs `asset_class` et `sector` de `assets_universe.csv`, plus des ajouts justifiés (`GOOGL`, `AMZN`, `QQQ` dans `tech`).

## Comment l'utiliser
Ajouter un profil = ajouter un fichier `personas/<id>.json` au même format. Aucun code ne doit tester un nom de profil.

## Comment vérifier
Pas encore de test automatique. Pendant #23, un script jetable a appliqué les Pactes aux trois profils : portefeuilles de départ conformes, « 30 % en TSLA » en violation pour le profil prudent, 3 violations pour le panier du profil audacieux.

## Choix faits en cours de route
- Les champs sur mesure (`interdit_exclusivement_tech`, catégories propres à un profil, exclusion `speculatif` jamais définie) ont disparu au profit des règles typées (#23).
- « Pas exclusivement tech » devient **tech + crypto ≤ 75 %** : hypothèse de l'équipe, à valider.
- `QQQ` est compté en entier dans `tech`, par simplicité.

## Limites et suite
Reste à faire dans cette issue :
- `personas/schema_pacte.json` (schéma du format) et la fonction `charger_pacte(chemin)` qui valide et renvoie la pièce « Pacte » ;
- une fonction qui donne les catégories d'un titre ; un titre absent de l'univers est signalé, jamais classé au hasard ;
- un test avec un 4e profil inventé, chargé sans changer le code.
