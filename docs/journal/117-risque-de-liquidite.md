# #117 — Risque de liquidité à partir des volumes

- **Issue** : #117 · **PR** : #134 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
- **`pipeline/liquidite.py`** (nouveau) : outil 9 `mesurer_liquidite`, appelé par l'orchestrateur.
  - `valeur_echangee_moyenne(volumes, prix_cloture, taux_cad, volume_en_devise)` : montant moyen échangé par séance, en CAD ; `None` (jamais 0) si aucun volume n'est connu ou si rien ne s'est échangé ;
  - `jours_pour_vendre(position, valeur_echangee, part_max)` : position ÷ (part max × valeur échangée) ;
  - `piece_liquidite(id, portefeuille, decision, capital, titres)` : pour chaque ligne du portefeuille **après la décision**, `poids_`, `valeur_position_cad_`, `valeur_echangee_moyenne_cad_` (et `_millions_cad_`), `part_volume_quotidien_`, `jours_pour_vendre_` ; puis `jours_pour_vendre_max`, `titre_le_moins_liquide`, `part_max_volume`, `capital`, `periode`, et `titres_sans_volume` s'il y en a ;
  - `decrire_mesurer_liquidite(titres)`, `titres_apres_decision(portefeuille, decision)`.
- **`pipeline/donnees.py`** : `charger_volumes(tickers)` (volume et close, sur les séances du titre lui-même, sans report) et `taux_usdcad_aux_dates(dates)` (repris de `convertir_en_cad`). Le CSV des prix n'est toujours lu qu'une fois (`_lignes_prix`).
- **`pipeline/orchestrateur.py`** : l'outil entre dans la liste blanche, et les consignes donnent un exemple (« un titre peu échangé, une grosse ligne ou un horizon court rend utile la liquidité »), y compris pour le contre-interrogatoire. Le modèle choisit seulement les lignes à examiner : Python tire la taille de chaque position de la décision du dossier.
- **`pipeline/sources.py`** : nouvelle source « Yahoo Finance via yfinance (volumes et prix de clôture) », fichier `prices_daily.csv`, reliée aux pièces de liquidité avec le change et l'univers.
- **`pipeline/debat.py`** : une phrase de consigne, « les montants échangés existent aussi en millions : « 1,6 million $ par jour » ; n'écris jamais « milliard » ».
- **Interface** : libellé de l'étape dans la trace (`api/adaptateur.ts`).
- **Validation** (`validation/scenarios.py`, groupe 12) : ligne la plus longue à revendre, volume crypto, titre sans volume (58/58).
- **Documentation** : `CLAUDE.md` (section 4 bis, outil 9), carte du `README.md`, `docs/GUIDE_DU_PROJET.md`.

## Comment l'utiliser
```python
from pipeline.liquidite import piece_liquidite
piece = piece_liquidite("P5", profil["portefeuille"], decision, profil["capital_fictif_cad"])
piece["valeurs"]["titre_le_moins_liquide"]       # "ZST.TO" pour Robert avec 30 % de TSLA
piece["valeurs"]["jours_pour_vendre_ZST.TO"]     # 0,83 jour de bourse
```
Profil prudent avec 30 % de TSLA : la ligne la plus longue à revendre n'est pas TSLA, qui s'échange pour environ 34,6 G$ CAD par jour, mais le petit FNB obligataire ZST.TO. Ses 136 500 $ pèsent 8,3 % de ce qui s'en échange en une séance, soit 0,83 jour de bourse à 10 % des échanges.

## Comment vérifier
```bash
pytest tests/test_liquidite.py
python -m validation          # groupe 12
```
- **Calcul à la main** : 1 000 × 10 $ + 2 000 × 11 $ + (volume absent, ignoré) + 0 × 13 $ = 32 000 $ sur 3 séances ; 5 000 $ à 10 % des échanges = 4,6875 jours. Conversion au taux de chaque séance ; volume crypto non multiplié par le prix.
- **Titre sans volume** : valeur absente (`None`), listé dans `titres_sans_volume`, sans aucune clé, jamais 0 ; tous les titres sans volume → erreur d'outil, sans pièce.
- **ZST.TO et BTC-USD refaits directement depuis le CSV.**
- **Le Greffier** accepte « 136 500 $ […] +8,3 % de ce qui s'en échange […] 1,6 million $ […] 0,8 jour de bourse » et rejette un pourcentage calculé par l'agent.
- **Vrais procès** (« terminé quand », Bedrock en local, 2026-11-15) : l'orchestrateur a demandé la liquidité de lui-même dans les deux procès essayés, et les deux contrats passent `python -m contrat.valider`.
  - Robert, 30 % en TSLA : « Horizon court : vérifier le temps nécessaire pour revendre les lignes après la décision » ; 23/23 chiffres vérifiés.
  - Robert, 40 % en ZST.TO : le Procureur cite la pièce, « ZST.TO pèserait 58 % du portefeuille, et sa revente prendrait 2,3 jours de bourse », vérifié par le Greffier (22/22).

## Choix faits en cours de route
- **`close`, pas `adj_close`** : la valeur échangée est le prix réellement payé ce jour-là ; `adj_close` baisse les prix passés du montant des dividendes. Le volume et `close` sont tous deux ajustés des fractionnements.
- **Volume crypto en dollars** : Yahoo le publie en dollars US échangés (27,9 G$ pour BTC le 2024-05-13), pas en unités ; le multiplier par le prix donnerait plus d'un million de milliards de dollars par jour. La règle lit la classe d'actifs de l'univers (`crypto`), jamais un ticker.
- **Séances du titre, sans report** : reporter le dernier volume connu sur un jour férié inventerait des échanges.
- **10 % des échanges par jour** : hypothèse prudente de l'équipe, écrite dans la pièce (`part_max_volume`), pas une règle officielle.
- **Lignes après la décision, pas une taille choisie par le modèle** : pour une réallocation, le modèle aurait dû multiplier le poids du panier par la part réallouée, c'est-à-dire calculer.
- **Chiffres significatifs** pour les parts et les jours (2,5e-07 pour BTC chez le profil audacieux), pour ne jamais écrire 0 à la place d'une petite valeur.
- **Montants aussi en millions** : le Greffier ne lit pas « million », et un agent qui veut écrire « 1,6 million $ » doit trouver 1,6 dans la pièce.

## Limites et suite
- Moyenne sur toute la période : un jour de crise, les échanges peuvent se tarir. Volumes crypto agrégés par Yahoo sur plusieurs plateformes. Un FNB s'échange aussi par création et rachat de parts : son volume en bourse ne mesure pas toute sa liquidité. Seul le volume de la bourse de cotation est compté. Ni frais ni écart entre prix acheteur et vendeur. Tout cela est écrit dans les limites de la pièce.
- Le Greffier ne vérifie pas les unités : « 1,64 milliard » passerait avec la valeur en millions 1,644524. La consigne interdit « milliard ».
- **Lambda à redéployer depuis `main` une fois la PR fusionnée** (pas depuis la branche : un déploiement remplace tout le code).
