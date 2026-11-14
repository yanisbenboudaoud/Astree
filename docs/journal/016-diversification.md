# #16 — Cas 2 : diversification (outil 3 et réallocations)

- **Issue** : #16 · **PR** : à compléter · **Statut** : en cours
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`pipeline/correlations.py`** : l'outil 3, sur le modèle de l'outil 1 (fiche [006](006-indicateurs-actif.md)).
  - `calculer_matrice_correlations(prix)` : fonction de calcul **pure**, la corrélation de Pearson des rendements quotidiens de chaque paire de titres.
  - `calculer_correlations(tickers)` : la **pièce** au format du contrat, **sans `id`** (c'est l'orchestrateur qui numérote les pièces). Prix en CAD (`charger_donnees`), toute la période. Valeurs brutes à 6 décimales : une clé par paire (`correlation_BTC-USD_ETH-USD`), plus `titres`, `nb_rendements_quotidiens` et `periode`. La `valeur_affichee` montre les 3 paires les plus corrélées.
  - `DESCRIPTION_BEDROCK` : la description de l'outil pour l'orchestrateur, avec un seul paramètre, `tickers` (2 à 10 titres).
- **`tests/test_correlations.py`** : 13 tests unitaires et 1 test réel Bedrock.

## Comment l'utiliser
```python
from pipeline.correlations import calculer_correlations

piece = calculer_correlations(["BTC-USD", "ETH-USD", "NVDA", "QQQ", "SHOP.TO"])
piece["valeurs"]["correlation_BTC-USD_ETH-USD"]   # 0.84453
piece["valeur_affichee"]   # « BTC-USD/ETH-USD 0,84 · NVDA/QQQ 0,77 · QQQ/SHOP.TO 0,57 · 10 paires en tout »
```

## Comment vérifier
```bash
pytest tests/test_correlations.py              # 13 tests, sans réseau
pytest tests/test_correlations.py -m bedrock   # le modèle demande-t-il l'outil pour une décision crypto ?
```
Les tests vérifient le calcul sur des séries dont on connaît la corrélation (+1, −1), que la pièce passe le schéma du contrat, et que les valeurs sont **identiques à la pièce P4 de `docs/exemples/contrat_amira.json`** (BTC/ETH 0,84453 ; NVDA/QQQ 0,765894 ; BTC/NVDA 0,320952).

## Choix faits en cours de route
- **Tout est en CAD**, comme les autres outils. Conséquence, notée dans les `limites` : la conversion ajoute un facteur de change commun aux titres en USD.
- **Une clé par paire**, car le contrat n'accepte pas d'objet imbriqué dans `valeurs`. Les tickers sont écrits tels quels dans la clé (`correlation_NVDA_QQQ`), pour que le modèle les reconnaisse.
- **2 à 10 titres** : au-delà, la pièce serait illisible (45 paires pour 10 titres). Une demande invalide lève `ErreurDonnees` avec un message lisible, que l'orchestrateur renvoie au modèle comme résultat en erreur.
- **Test réel** : avec les outils 1 et 3 et une décision de réallocation crypto-tech, Sonnet 5.5 demande `calculer_correlations` sur les 5 titres du panier. Il demande aussi `indicateurs_actif` pour chacun : 6 appels d'un coup, sur un budget de 8 par procès.

## Limites et suite
- **Orchestrateur (#12)** : ajouter `DESCRIPTION_BEDROCK` à sa liste blanche et `calculer_correlations` à ses outils exécutables. Le modèle a tendance à demander un `indicateurs_actif` par titre du panier : son prompt ou son budget devra en tenir compte.
- **Reste de l'issue** : les réallocations dans l'Agent Profil, `simuler_portefeuille` (#9) et `taille_max_compatible` (#21), et le cas 2 de bout en bout.
- Les corrélations couvrent toujours toute la période : pas de paramètre de période pour l'instant.
