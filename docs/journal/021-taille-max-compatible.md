# #21 — Outil 4 : taille_max_compatible

- **Issue** : #21 · **PR** : à compléter · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`pipeline/taille_max.py`** : l'outil 4.
  - `rechercher_taille_max(portefeuille, decision, regles)` : simule la décision de 0 jusqu'à la taille demandée, **par pas de 1 point** (`tailles_a_tester`), avec le même financement. À chaque taille, il applique **les contrôles du Greffier** (`verifier_pacte`, fiche du #10) aux règles calculables (`pire_baisse_max`, `plafond`). Il renvoie la plus grande taille compatible, ou `None` si même 0 % viole le Pacte.
  - `piece_taille_max(id_piece, portefeuille, decision, regles)` : la pièce au format du contrat, avec l'étiquette `fictif`, comme P5 de la maquette. Valeurs brutes : `taille_max_compatible`, `taille_demandee`, `pas_de_recherche`, `regles_verifiees`, `regle_limitante`, `pire_baisse_a_taille_max`, `pire_baisse_a_taille_suivante`, et pour chaque plafond `part_<catégories>_a_taille_max` et `_a_taille_suivante`.
  - `decrire_taille_max(tickers_univers, portefeuille)` : la description de l'outil pour l'orchestrateur, avec les paramètres `ticker`, `taille` et `financement`.
- **`pipeline/orchestrateur.py`** (fiche du #12) : l'outil est ajouté à la liste blanche (`outils_du_profil`), et ses consignes citent l'exemple « une règle probablement dépassée rend utile la taille maximale compatible ».
- **`pipeline/tribunal.py`** (fiche du #12) : `taille_max_compatible` du contrat est **toujours** calculé par Python pour une position, que le modèle ait demandé l'outil ou non, car le curseur de l'interface en a besoin. **Le contrat d'une position est maintenant complet et passe le schéma.**
- **`tests/test_taille_max.py`** : 13 tests. Dans `tests/test_orchestrateur.py`, `test_contrat_complet_sauf_taille_max` devient `test_contrat_complet_passe_le_schema`.

## Comment l'utiliser
```python
from pipeline.taille_max import piece_taille_max

piece = piece_taille_max("P5", profil["portefeuille"],
                         {"type": "position", "ticker": "TSLA", "taille": 0.30, "financement": "proportionnel"},
                         profil["pacte"]["regles"])
piece["valeurs"]["taille_max_compatible"]   # 0.09
piece["valeur_affichee"]                    # « 9 % au maximum »
```

## Comment vérifier
```bash
pytest tests/test_taille_max.py tests/test_orchestrateur.py
```
- Cas de démo (profil prudent, 30 % en TSLA, financement proportionnel) : **9 %**, pire baisse −11,22 % à 9 % et −12,09 % à 10 %, règle limitante `pire_baisse_max`. Ce sont les valeurs de l'issue et de la pièce P5 de `contrat_robert.json`.
- Plafond limitant : profil audacieux avec du Bitcoin. Le plafond crypto de 25 % limite à 11 % (calcul vérifié : 0,15 × (1 − t) + t ≤ 0,25).
- **Vrai procès complet** (Bedrock) : l'orchestrateur a demandé l'outil de lui-même, l'Avocat l'a cité (« à 9 % au maximum, la pire baisse simulée est de −11,2 % »), et **le contrat passe `valider_contrat`** (schéma et renvois). Durée : 29,7 s.

## Choix faits en cours de route
- **Les contrôles du Greffier servent de juge** : l'outil ne peut pas dire « compatible » quand le Greffier dirait « violation ». Une règle `a_verifier` (titre hors univers) rend la taille non compatible.
- **Plus grande taille compatible, pas dernière taille avant la première violation** : sans dichotomie, une taille compatible au-delà d'une zone en violation est retenue (test dédié).
- **Taille demandée hors grille** (ex. : 7,69 % tirés d'un montant) : elle est testée en plus des pas de 1 point.
- **Calcul rapide** : 31 simulations en 0,1 s environ (CSV en mémoire), d'où le calcul systématique dans `tribunal.py`.

## Limites et suite
- **Réallocations** : le code traite la part réallouée comme la taille (`_a_la_taille`), mais `simuler_portefeuille` ne simule pas encore les réallocations (#16). Pour une réallocation, `taille_max_compatible` est donc absent du contrat. La suite est suivie dans la #16.
- Seules les règles calculables comptent ; les règles qualitatives et documentaires restent à juger par l'utilisateur.
