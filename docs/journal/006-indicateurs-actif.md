# #6 — Outil 1 : indicateurs_actif

- **Issue** : #6 · **PR** : à venir · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`pipeline/indicateurs.py`** :
  - Cinq fonctions de calcul **pures**, sur une série de valeurs indexée par date (prix d'un titre ou valeur d'un portefeuille), réutilisables par `simuler_portefeuille` (#9) : `calculer_rendement_annualise`, `calculer_volatilite_annuelle`, `calculer_pire_baisse`, `calculer_rendement_2022`, `calculer_temps_recuperation`.
  - `indicateurs_actif(ticker)` : calcule ces indicateurs en CAD sur toute la période et renvoie une **pièce** au format du contrat (`CLAUDE.md`, section 5), **sans `id`** : c'est l'orchestrateur qui numérote les pièces. Valeurs brutes à 6 décimales, `valeur_affichee` arrondie par Python.
  - `DESCRIPTION_BEDROCK` : la description de l'outil pour l'orchestrateur (#12), faite avec `decrire_outil` (fiche [007](007-client-llm-bedrock.md)) ; un seul paramètre, `ticker`.
- **`pipeline/donnees.py`** : ajout de `date_extraction(nom_fichier)`, qui lit la date d'extraction dans `sources_metadata.csv` (utilisée dans la `source` de la pièce).
- **`tests/test_indicateurs.py`** : 17 tests.

## Comment l'utiliser
```python
from pipeline.indicateurs import indicateurs_actif

piece = indicateurs_actif("TSLA")
piece["valeurs"]["pire_baisse"]   # -0.708806
piece["valeur_affichee"]          # « −70,9 % max · +5,5 %/an · 2,9 ans pour revenir au sommet »
```

## Comment vérifier
```bash
pytest tests/test_indicateurs.py
```
Les tests vérifient chaque fonction sur de petites séries dont on connaît le résultat, que la pièce de TSLA passe le schéma du contrat, et que les chiffres de TSLA correspondent à la pièce P4 de `docs/exemples/contrat_robert.json`.

## Choix faits en cours de route
- **Tout est en CAD**, comme le reste du contrat. **Écart avec la maquette** : la pièce P4 de `contrat_robert.json` calculait le temps de récupération en USD (retour au sommet le 2024-12-10, 2,935 ans). En CAD, TSLA revient à son sommet le 2024-12-05, soit 2,9213 ans. La pire baisse (−0,7088), le sommet (2022-01-03) et le creux (2023-01-03) sont identiques. L'argument « près de 3 ans » reste vrai. `contrat_robert.json` n'a pas été modifié : il reste l'exemple de l'équipe interface.
- **Erreur lisible** : un titre hors univers lève `ErreurDonnees` avec son nom. L'orchestrateur (#12) doit l'attraper et la renvoyer au modèle avec `resultat_outil(..., erreur=True)`, au lieu de planter.
- **Récupération incomplète** : si le titre n'est pas revenu à son sommet, `date_retour_sommet` et `annees_recuperation` valent `None`, et la `valeur_affichee` le dit. Si la série n'a jamais baissé, les quatre champs de récupération valent `None`.

## Limites et suite
- Les indicateurs couvrent toujours toute la période : pas de paramètre de période pour l'instant.
- Une seule chute est mesurée pour le temps de récupération : la pire.
- `contrat_robert.json` (P4) pourra être aligné sur la sortie réelle de l'outil quand l'orchestrateur (#12) produira les pièces.
