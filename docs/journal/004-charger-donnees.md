# #4 — charger_donnees : prix adj_close et calendrier

- **Issue** : #4 · **PR** : #28 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`pipeline/donnees.py`** : le socle de données commun à tous les outils.
  - `charger_prix(tickers)` : prix `adj_close` des titres demandés, une ligne par séance américaine, une colonne par titre, dans la devise de cotation.
  - `charger_univers()` : le contenu de `assets_universe.csv` (ticker, classe d'actifs, marché, devise, secteur).
  - `seances_americaines()` : les dates de séance de la bourse américaine.
  - `lire_csv(nom_fichier)` : lit un CSV en local ou dans S3, selon `SOURCE_DONNEES`.
  - `ErreurDonnees` : levée quand une donnée manque (titre absent de l'univers, titre sans prix au début de la période). L'outil signale au lieu de deviner.
  - `HYPOTHESES_DONNEES` : les hypothèses à reprendre dans le champ `hypotheses` du contrat.
- **`tests/test_donnees.py`** : 14 tests.
- **`requirements-dev.txt`** : ajout de `pandas`.

## Comment l'utiliser
```python
from pipeline.donnees import charger_prix

prix = charger_prix(["RY.TO", "SPY", "BTC-USD"])   # DataFrame, index « date »
```

## Comment vérifier
```bash
pytest tests/test_donnees.py
```
Les tests couvrent un mélange d'actions CAD et USD, de FNB et de crypto sans trou, des dates triées et sans doublon, l'erreur pour un titre inconnu, le report aux jours fériés de la TSX, la crypto du week-end cumulée dans le lundi, et la pire baisse de TSLA de la maquette (−0,7297, pièce P4) reproduite.

## Choix faits en cours de route
- **Calendrier** : séances américaines, définies par les titres cotés sur `MARCHES_AMERICAINS`. Le dernier prix connu est reporté sur toutes les dates **avant** de ne garder que les séances : le rendement crypto du week-end tombe donc dans le lundi (`REFERENCE_DU_PROJET.md`, section 6 bis).
- **Fractionnements** : jamais réappliqués, ils sont déjà dans `adj_close`.

## Limites et suite
- Les prix restent dans leur devise : la conversion en CAD est l'issue #5.
- `SOURCE_DONNEES=s3` renvoie une erreur explicite en attendant #13.
- Dans Lambda, pandas viendra de la couche gérée « AWS SDK for pandas » (#22).
