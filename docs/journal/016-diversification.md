# #16 — Cas 2 : diversification (outil 3 et réallocations)

- **Issue** : #16 · **PR** : #39, #41, à compléter · **Statut** : terminée
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

### Réallocations dans la simulation, la taille maximale, l'orchestrateur et le procès (PR à compléter)
- **`pipeline/simulation.py`** (fiche [009](009-simuler-portefeuille.md)) : `poids_apres_decision` simule aussi les **réallocations**. La part réallouée est retirée de chaque ligne au prorata, puis répartie selon les poids du panier (`_poids_apres_reallocation`). Panier vide, titre en double, poids nul ou total différent de 1 lèvent `ErreurSimulation`. `decrire_simuler_reallocation()` : variante de l'outil où le modèle ne choisit que `part_reallouee` et `periode`.
- **`pipeline/taille_max.py`** (fiche [021](021-taille-max-compatible.md)) : `decrire_taille_max_reallocation()`, la variante avec le seul paramètre `part_reallouee`. Le calcul traitait déjà la part réallouée comme la taille.
- **`pipeline/orchestrateur.py`** (fiche [012](012-orchestrateur.md)) :
  - `outils_du_profil(profil, decision)` décrit la simulation et la taille maximale **pour le panier de la décision** quand il s'agit d'une réallocation ;
  - **l'outil 3 `calculer_correlations` rejoint la liste blanche** ;
  - la pièce obligatoire est ajoutée d'office pour une réallocation comme pour une position (`RAISON_INDISPONIBLE` disparaît).
- **`pipeline/tribunal.py`** (fiche [012](012-orchestrateur.md)) : `comparaison`, `taille_max_compatible` et `verifier_pacte` fonctionnent pour une réallocation. **Le contrat est complet pour les deux types de décisions.**
- **Tests** : `tests/test_simulation.py` (réallocation au prorata, valeurs de la maquette, erreurs), `tests/test_taille_max.py` (28 %, outils d'une réallocation, outil 3 dans la liste blanche) et `tests/test_orchestrateur.py` (pièce obligatoire d'une réallocation, contrat complet).

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
- Simulation et taille maximale de la réallocation de démo : **identiques aux pièces P1, P2 et P5 de `contrat_amira.json`**. Exemples : pire baisse −0,618555, rejeu 2022 −0,524972, 28 % au maximum limités par le plafond crypto (part crypto 0,248 à 28 %, 0,2515 à 29 %).
- **Critère de fin atteint, vrai procès complet (Bedrock)** :
  - l'orchestrateur a choisi lui-même la simulation, le rejeu de 2022, la taille maximale **et les corrélations** ;
  - le Greffier relève **3 violations** : pire baisse −61,9 % (seuil −45 %), crypto à 50 % (plafond 25 %), tech et crypto à 100 % (plafond 75 %) ;
  - le Procureur cite les corrélations (« 0,84 entre BTC-USD et ETH-USD […] la diversification apparente protège moins que prévu ») ;
  - `verifier_chiffres` valide 32 chiffres sur 32, et `valider_contrat` passe. Durée : 39,4 s.
  - **Contraste avec le cas 1** : profil prudent et 30 % en TSLA donnent 1 violation et 9 % au maximum.

## Choix faits en cours de route
- **Corrélations en CAD**, comme les autres outils. Conséquence, notée dans les `limites` : la conversion ajoute un facteur de change commun aux titres en USD.
- **Une clé par paire**, car le contrat n'accepte pas d'objet imbriqué dans `valeurs`. Les tickers sont écrits tels quels dans la clé (`correlation_NVDA_QQQ`), pour que le modèle les reconnaisse.
- **2 à 10 titres** pour l'outil 3 : au-delà, la pièce serait illisible (45 paires pour 10 titres). Une demande invalide lève `ErreurDonnees` avec un message lisible.
- **Un panier vague n'est jamais complété** : « un panier crypto-tech » ne dit ni les titres ni les poids. L'utilisateur doit les donner, dans sa phrase ou plus tard dans l'interface.
- **Poids ajustés seulement pour les arrondis** : un total entre 99 % et 101 % (ex. : trois tiers écrits 33,33 %) est ramené à exactement 100 %, comme l'exige le contrat, avec une hypothèse qui le dit. Au-delà, la répartition est ambiguë et l'agent demande de la préciser.
- **Pas de financement pour une réallocation** : le contrat la prend au prorata de toutes les lignes. Un « en vendant X » est ignoré et signalé.
- **Test réel de l'outil 3** : avec les outils 1 et 3 et une décision de réallocation crypto-tech, Sonnet 5.5 demande `calculer_correlations` sur les 5 titres du panier. Il demande aussi `indicateurs_actif` pour chacun : 6 appels d'un coup, sur un budget de 8 par procès.

- **Outils d'une réallocation** : le panier est celui de la décision, lu par Python. Le modèle ne peut donc pas simuler un autre panier ; il choisit seulement la part réallouée (et la période).

## Limites et suite
- **Hypothèse à valider par l'équipe** : « ne pas miser exclusivement sur la tech » est traduit par tech et crypto à 75 % au plus (`personas/amira.json`). C'est un seuil choisi par l'équipe, pas une citation de l'énoncé.
- Dans un essai isolé (outils 1 et 3 seulement), le modèle avait demandé un `indicateurs_actif` par titre du panier. Dans le vrai procès, avec les quatre outils, il ne l'a pas fait (4 appels).
- Les corrélations couvrent toujours toute la période : pas de paramètre de période pour l'instant.
- Le panier d'une demande vague doit venir de l'interface (#14) : sélection des titres et des poids.
