# #5 — Conversion USD → CAD

- **Issue** : #5 · **PR** : #31 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`pipeline/donnees.py`** (complète la fiche [004](004-charger-donnees.md)) :
  - `convertir_en_cad(prix, devises)` : multiplie chaque colonne en USD par le taux USD/CAD du jour. Une colonne en CAD reste inchangée.
  - `charger_donnees(tickers)` : `charger_prix` suivi de `convertir_en_cad`, avec la devise de chaque titre lue dans `assets_universe.csv`. C'est l'entrée de tous les outils : prix `adj_close` en CAD, alignés sur les séances américaines.
  - `HYPOTHESES_DONNEES` : ajout de « Montants convertis en CAD ».
  - `ErreurDonnees` est aussi levée pour une devise manquante ou non prise en charge (autre que CAD et USD), ou pour une date sans taux connu.
- **`tests/test_donnees.py`** : 9 tests de plus (23 au total).

## Comment l'utiliser
```python
from pipeline.donnees import charger_donnees

prix_cad = charger_donnees(["RY.TO", "TSLA", "BTC-USD"])   # tout en CAD
```
`charger_prix` reste disponible pour les prix dans leur devise de cotation (ex. : temps de récupération de TSLA calculé en USD, pièce P4).

## Comment vérifier
```bash
pytest tests/test_donnees.py
```
Les tests vérifient qu'un titre CAD ne change pas, qu'un titre USD est multiplié par le taux du jour, et que le dernier taux est reporté les jours fériés canadiens. Ils retrouvent aussi les chiffres de la maquette (`docs/exemples/contrat_robert.json`) : la pire baisse de TSLA en CAD (−0,7088, pièce P4), et le rendement annualisé (0,0929), la volatilité (0,0559) et la pire baisse (−0,0776) du portefeuille actuel de Robert. La méthode de la section 6 bis de `REFERENCE_DU_PROJET.md` est donc reproduite.

## Choix faits en cours de route
- **Report du taux** : le fichier de la Banque du Canada n'a pas de taux les jours fériés canadiens. Le dernier taux connu est reporté sur toutes les dates, puis on ne garde que les séances américaines (même méthode que pour les prix, fiche 004).
- **`charger_prix` garde la devise d'origine** et `charger_donnees` ajoute la conversion : les deux restent utiles, et `convertir_en_cad` se teste seule.

## Limites et suite
- Un seul taux par jour (publié vers 16 h 30, heure de l'Est), appliqué aussi à la crypto, dont la ligne du jour couvre la journée UTC : léger décalage horaire, sans effet notable sur des indicateurs sur 5 ans.
- `pipeline/univers.py` (issue #8) a aussi une fonction `charger_univers`, qui renvoie une liste de dictionnaires au lieu d'un DataFrame. Les deux pourraient être fusionnées.
