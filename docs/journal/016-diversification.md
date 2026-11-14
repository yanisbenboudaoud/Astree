# #16 — Cas 2 : diversification (outil 3 et réallocations)

- **Issue** : #16 · **PR** : #39, #41 · **Statut** : en cours
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit

### Outil 3 : corrélations (PR #39)
- **`pipeline/correlations.py`** : l'outil 3, sur le modèle de l'outil 1 (fiche [006](006-indicateurs-actif.md)).
  - `calculer_matrice_correlations(prix)` : fonction de calcul **pure**, la corrélation de Pearson des rendements quotidiens de chaque paire de titres.
  - `calculer_correlations(tickers)` : la **pièce** au format du contrat, **sans `id`** (c'est l'orchestrateur qui numérote les pièces). Prix en CAD (`charger_donnees`), toute la période. Valeurs brutes à 6 décimales : une clé par paire (`correlation_BTC-USD_ETH-USD`), plus `titres`, `nb_rendements_quotidiens` et `periode`. La `valeur_affichee` montre les 3 paires les plus corrélées.
  - `DESCRIPTION_BEDROCK` : la description de l'outil pour l'orchestrateur, avec un seul paramètre, `tickers` (2 à 10 titres).
- **`tests/test_correlations.py`** : 13 tests unitaires et 1 test réel Bedrock.

### Réallocations dans l'Agent Profil (PR #41)
Modifie `pipeline/agent_profil.py` (fiche [008](008-agent-profil.md)) : l'agent produit maintenant aussi des décisions `reallocation` (format du contrat, section 5 : `panier`, `part_reallouee`, `libelle`).
- **Extraction du LLM** : deux champs ajoutés, `panier` (titres de l'univers et leurs poids) et `actifs_hors_univers`. Le champ `taille` sert de part réallouée.
- **Vérifications en Python** (`_decision_reallocation`) : panier non vide, titres dans l'univers et sans doublon, poids positifs dont le total vaut 100 %, part réallouée entre 0 et 100 % (ou calculée depuis un montant, comme une taille). En cas de problème, aucune décision n'est renvoyée et un contrôle `a_verifier` explique quoi préciser.
- La logique des positions n'a pas changé ; elle est seulement passée dans `_decision_position`.
- **`tests/test_agent_profil.py`** : 11 tests unitaires et 3 tests réels ajoutés.

## Comment l'utiliser
```python
from pipeline.correlations import calculer_correlations
from pipeline.agent_profil import lancer_agent_profil

piece = calculer_correlations(["BTC-USD", "ETH-USD", "NVDA", "QQQ", "SHOP.TO"])
piece["valeurs"]["correlation_BTC-USD_ETH-USD"]   # 0.84453

resultat = lancer_agent_profil(
    "Je veux réallouer tout mon portefeuille vers un panier : 30 % Bitcoin, 20 % Ether, "
    "20 % Nvidia, 20 % QQQ et 10 % Shopify", "amira", "P3")
resultat.decision["libelle"]   # « 100 % réalloué vers BTC-USD 30 %, ETH-USD 20 %, NVDA 20 %, QQQ 20 % et SHOP.TO 10 % »
```

## Comment vérifier
```bash
pytest tests/test_correlations.py tests/test_agent_profil.py              # sans réseau
pytest tests/test_correlations.py tests/test_agent_profil.py -m bedrock   # vrais appels
```
- Corrélations : calcul vérifié sur des séries dont on connaît la corrélation (+1, −1) ; valeurs **identiques à la pièce P4 de `docs/exemples/contrat_amira.json`** (BTC/ETH 0,84453 ; NVDA/QQQ 0,765894 ; BTC/NVDA 0,320952).
- Réallocations : la phrase ci-dessus donne **exactement** la `decision_demo` du profil audacieux ; « tout réallouer vers un panier crypto-tech » n'en donne aucune (panier non décrit) ; un panier avec Solana, hors univers, est signalé.

## Choix faits en cours de route
- **Corrélations en CAD**, comme les autres outils. Conséquence, notée dans les `limites` : la conversion ajoute un facteur de change commun aux titres en USD.
- **Une clé par paire**, car le contrat n'accepte pas d'objet imbriqué dans `valeurs`. Les tickers sont écrits tels quels dans la clé (`correlation_NVDA_QQQ`), pour que le modèle les reconnaisse.
- **2 à 10 titres** pour l'outil 3 : au-delà, la pièce serait illisible (45 paires pour 10 titres). Une demande invalide lève `ErreurDonnees` avec un message lisible.
- **Un panier vague n'est jamais complété** : « un panier crypto-tech » ne dit ni les titres ni les poids. L'utilisateur doit les donner, dans sa phrase ou plus tard dans l'interface.
- **Poids ajustés seulement pour les arrondis** : un total entre 99 % et 101 % (ex. : trois tiers écrits 33,33 %) est ramené à exactement 100 %, comme l'exige le contrat, avec une hypothèse qui le dit. Au-delà, la répartition est ambiguë et l'agent demande de la préciser.
- **Pas de financement pour une réallocation** : le contrat la prend au prorata de toutes les lignes. Un « en vendant X » est ignoré et signalé.
- **Test réel de l'outil 3** : avec les outils 1 et 3 et une décision de réallocation crypto-tech, Sonnet 5.5 demande `calculer_correlations` sur les 5 titres du panier. Il demande aussi `indicateurs_actif` pour chacun : 6 appels d'un coup, sur un budget de 8 par procès.

## Limites et suite
- **Orchestrateur (#12)** : ajouter `DESCRIPTION_BEDROCK` de l'outil 3 à sa liste blanche et `calculer_correlations` à ses outils exécutables. Le modèle a tendance à demander un `indicateurs_actif` par titre du panier : son prompt ou son budget devra en tenir compte.
- **Reste de l'issue** : les réallocations dans `simuler_portefeuille` (#9) et `taille_max_compatible` (#21), puis le cas 2 de bout en bout.
- Les corrélations couvrent toujours toute la période : pas de paramètre de période pour l'instant.
