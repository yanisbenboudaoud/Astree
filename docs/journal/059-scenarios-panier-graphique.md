# #59 — Scénarios : panier crypto-tech et graphique de sensibilité

- **Issue** : #59 · **PR** : #PR_A_RENSEIGNER · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
Ce travail complète les scénarios de la fiche [015](015-scenarios-validation.md).

- **`validation/scenarios.py`** :
  - le scénario « panier crypto-tech du profil audacieux », jusque-là « ⏸ en attente de #16 », est maintenant un vrai test. #16 permet de simuler les réallocations, et le panier donne bien **3 violations** (`pire_baisse_max` à −61,9 %, `plafond_crypto`, `pas_exclusivement_tech`) pour une taille maximale de 28 % ;
  - `sensibilite_seuil()` calcule, avec `rechercher_taille_max` (#21), la taille maximale compatible pour chaque seuil de pire baisse de −8 % à −30 % (par pas de 1 point), pour le profil prudent et 30 % de TSLA. Le résultat est mis en cache ;
  - `graphique_svg(points)` dessine ces points en **SVG statique**, sans bibliothèque de graphiques ni nouvelle dépendance. Le fichier contient un titre et une description pour les lecteurs d'écran, et un mode sombre ;
  - `section_graphique(points)` ajoute au rapport le graphique et ses valeurs en tableau, pour une lecture sans couleur.
- **`docs/validation/sensibilite_seuil.svg`** : le graphique, réécrit par `python -m validation` en même temps que le rapport.
- **`tests/test_scenarios.py`** : plus aucun scénario en attente ; le graphique doit être à jour ; la taille maximale croît quand le seuil s'assouplit, et vaut 9 % au seuil de −12 % (la valeur de P5 dans le faux contrat).

## Comment l'utiliser
```bash
python -m validation        # « 34 réussis, 0 en échec, 0 en attente » ; réécrit le rapport et le graphique
```
Le graphique s'affiche dans `docs/validation/resultats_scenarios.md`. Il peut être repris tel quel dans la doc technique et le pitch (#18).

## Comment vérifier
`pytest tests/test_scenarios.py` (11 tests). Si un seuil, un profil ou une catégorie change, les tests du rapport et du graphique échouent : relancer `python -m validation` et committer les deux fichiers.

Résultat : de 1 % (seuil de −8 %) à 30 % (seuil de −29 %), avec 9 % au seuil de −12 % du profil prudent. La courbe est croissante : plus le Pacte tolère de baisse, plus la position compatible est grande.

## Choix faits en cours de route
- **SVG écrit en Python plutôt qu'avec matplotlib** : pas de nouvelle dépendance, un fichier texte comparable dans Git et testable, et un affichage net sur GitHub.
- **Couleurs** : palette de référence de la méthode de visualisation, avec une seule série (bleu), des encres et des filets discrets. Aucune légende, puisque le titre nomme la série. Le seuil du profil prudent est le seul point annoté.
- **Une nouvelle fiche plutôt que réécrire la fiche 015** : c'est la règle 6 du journal.

## Limites et suite
- Le graphique est statique : pas d'infobulle au survol dans un fichier Markdown. Le tableau des valeurs, sous le graphique, en tient lieu.
- Il couvre un seul profil et une seule décision. D'autres courbes, par exemple le plafond tech + crypto du profil audacieux, pourront être ajoutées de la même façon.
