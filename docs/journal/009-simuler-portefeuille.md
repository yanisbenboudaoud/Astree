# #9 — Outil 2 : simuler_portefeuille (avant / après la décision)

- **Issue** : #9 · **PR** : #37 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`pipeline/simulation.py`** :
  - `poids_apres_decision(portefeuille, decision)` : poids cibles une fois la décision appliquée. Financement `proportionnel` (toutes les lignes × (1 − taille)) ou `depuis_<ticker>` (seule cette ligne est réduite ; vidée, elle disparaît). Un titre déjà en portefeuille s'ajoute à sa ligne.
  - `simuler_portefeuille(portefeuille, decision)` : `{"actuel", "apres"}` avec `rendement_annuel`, `volatilite_annuelle`, `pire_baisse` et `rendement_2022`. C'est le format de `comparaison` du contrat. Les indicateurs viennent des fonctions de `pipeline/indicateurs.py` (fiche [006](006-indicateurs-actif.md)), appliquées à la série de valeurs du portefeuille.
  - `piece_simulation(id_piece, portefeuille, decision, periode)` : la pièce au format du contrat, étiquette `fictif`. `periode="complete"` donne P1 (pire baisse, rendement et volatilité, avant et après) ; `periode="2022"` donne P2 (rejeu de l'année de crise, avec ses deux dates).
  - `decrire_simuler_portefeuille(tickers_univers, portefeuille)` : description de l'outil pour l'orchestrateur Bedrock (#12), avec les paramètres `ticker`, `taille`, `financement` et `periode`.
  - `formater_pourcentage` (`−29,0 %`, `+12,0 %`) et `source_des_prix` (avec `date_extraction` de `pipeline/donnees.py`).
  - `ErreurSimulation` : décision ou portefeuille impossible à simuler. Les données absentes lèvent toujours `ErreurDonnees`.
- **`tests/test_simulation.py`** : 32 tests.

## Comment l'utiliser
```python
from pipeline.simulation import piece_simulation, simuler_portefeuille

decision = {"type": "position", "ticker": "TSLA", "taille": 0.30, "financement": "proportionnel"}
comparaison = simuler_portefeuille(profil["portefeuille"], decision)          # champ « comparaison »
p1 = piece_simulation("P1", profil["portefeuille"], decision)                  # période complète
p2 = piece_simulation("P2", profil["portefeuille"], decision, periode="2022")  # rejeu de 2022
```

## Comment vérifier
```bash
pytest tests/test_simulation.py
```
Les tests retrouvent les 8 chiffres de `comparaison` de `docs/exemples/contrat_robert.json`. Ils retrouvent aussi les pièces P1 et P2 (textes identiques, valeurs égales à 4 décimales, conformes au schéma du contrat), et la pire baisse à 9 % et à 10 % de la pièce P5 (−0,1122 et −0,1209), dont `taille_max_compatible` (#21) aura besoin. Une taille de 0 redonne le portefeuille actuel.

## Choix faits en cours de route
- **Série de valeurs du portefeuille** : elle part de 1 à la première séance, puis suit les rendements rééquilibrés chaque jour. Les fonctions de #6 s'y appliquent comme à la série de prix d'un titre. Le point de départ compte comme un sommet possible pour la pire baisse.
- **Rapidité pour #21** : les rendements quotidiens en CAD sont mis en cache par ensemble de titres (`_rendements_quotidiens`). Mesuré en local : environ 90 ms pour le premier appel (lecture des CSV), puis environ 110 ms pour 31 simulations de 0 à 30 %.
- **Avant et après sur les mêmes séances** : les deux portefeuilles sont simulés sur les mêmes rendements (titre ajouté à poids nul dans le portefeuille actuel).
- **Paramètre `periode`** : une seule fonction pour P1 et P2, comme dans la trace de l'exemple (`"periode": "2022"`). `calculer_rendement_2022` ne renvoie que le rendement : `_bornes_2022` donne les deux dates affichées dans P2.
- **Arrondi** : les valeurs des pièces sont arrondies à `DECIMALES_VALEURS` (6), comme celles de `indicateurs_actif`. `simuler_portefeuille` renvoie des valeurs non arrondies, pour les calculs de #21.
- **Schéma Bedrock sans bornes numériques** : la taille n'a ni minimum ni maximum dans le schéma, et c'est Python qui la vérifie. Les listes `enum` limitent le titre à l'univers et le financement aux titres du portefeuille, comme le fait l'Agent Profil.

## Limites et suite
- Décisions de type `reallocation` refusées avec une erreur claire : elles arrivent avec #16.
- Trois fonctions de mise en forme se ressemblent : `formater_pourcentage` (ici), `_pourcentage` de `pipeline/indicateurs.py` (qui écrit `+0,0 %` pour zéro) et `formater_part` de `pipeline/agent_profil.py` (sans signe). Elles pourraient être regroupées.
