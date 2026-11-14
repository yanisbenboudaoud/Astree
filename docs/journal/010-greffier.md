# #10 — Greffier : outils 5 (verifier_pacte) et 6 (verifier_chiffres)

- **Issue** : #10 · **PR** : #42 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
Le Greffier est le point de contrôle du Tribunal, en **Python sans LLM** (`CLAUDE.md` section 4).

- **`pipeline/greffier.py`** : outil 5.
  - `verifier_pacte(regles, poids_apres, piece_simulation, id_piece_pacte, pieces)` rend un contrôle par règle, au format `controles` du contrat. Une fonction par type de règle, réunies dans `CONTROLES_PAR_TYPE` :
    - `controler_pire_baisse_max` lit `pire_baisse` dans la pièce de `simuler_portefeuille` ;
    - `controler_plafond` additionne les poids des titres des catégories (`categories_du_titre`, #3). Un titre hors univers donne `a_verifier` ;
    - `controler_critere_documentaire` attend une pièce `documentaire` ; sans elle, `a_verifier` « source manquante » ;
    - `controler_qualitative` rend toujours `a_verifier`.
  - Contrôles du système : `controle_biais_survivant()` (toujours `a_verifier`) et `controle_performance_passee(arguments)` (`a_verifier` si un argument parle de rendement, de performance ou de gain).
- **`pipeline/chiffres.py`** : outil 6, `verifier_chiffres`, qui suit les règles 1 à 9 de `CLAUDE.md` section 4 ter.
  - `extraire_nombres(texte)` : pourcentages, décimaux, entiers, années et dates (ISO, « 14 novembre », « janv. 2022 »). Ne sont pas extraits : les id de pièces, les nombres collés à des lettres et les noms d'actifs (« S&P 500 »).
  - `verifier_argument(argument, dossier)` compare chaque nombre aux pièces citées, à la décision et à la période, avec l'arrondi écrit et la règle du signe. En cas d'échec, il rend un **motif exact**, par exemple « « −29,0 % » introuvable dans P3 (présent dans P1, pièce non citée) ».
  - `trier_arguments(arguments, cote, dossier, corriger)` renvoie **une fois** un argument refusé à son agent, puis le range dans `arguments_rejetes`.
  - `controle_verifier_chiffres(*tris)` produit le contrôle de synthèse : « 17/17 chiffres, 7 arguments ».

## Comment l'utiliser
```python
from pipeline.greffier import verifier_pacte, controle_biais_survivant, controle_performance_passee
from pipeline.chiffres import trier_arguments, controle_verifier_chiffres
from pipeline.debat import corriger_argument

controles = verifier_pacte(profil["pacte"]["regles"], poids_apres, piece_p1, "P3", pieces)
dossier = {"decision": decision, "pieces": pieces, "periode": ["2021-11-12", "2026-11-12"]}
requisitoire = trier_arguments(arguments_procureur, "requisitoire", dossier,
                               lambda arg, motif: corriger_argument("procureur", dossier, arg, motif)[0])
plaidoirie = trier_arguments(arguments_avocat, "plaidoirie", dossier, ...)
controles.append(controle_verifier_chiffres(requisitoire, plaidoirie))
```
L'orchestrateur (#12) branche ces appels et garde la trace des relances.

## Comment vérifier
`pytest tests/test_greffier.py tests/test_chiffres.py`, soit 51 tests :
- **même décision, deux profils** : 30 % en TSLA donne une violation de la pire baisse pour le profil prudent (−29,0 % pour un seuil de −12,0 %), mais aucune pour le profil audacieux (−42,6 % pour −45 %) ;
- **chaque exemple de la section 4 ter** est un test : « −29,0 % » et « −29 % » passent, « −28 % » et « −29,03 % » sont rejetés ; « 2,6 % » est rejeté pour `-0.0259` ; les nombres dérivés et les pièces non citées sont rejetés ;
- **les faux contrats** `contrat_robert.json` et `contrat_amira.json` donnent tous les deux **17/17**, et l'argument rejeté d'Amira (« 4 fois plus ») reste rejeté.

## Choix faits en cours de route
- **`verifier_chiffres` est dans son propre module** (`pipeline/chiffres.py`) pour garder `greffier.py` court.
- **`verifier_pacte` reçoit `poids_apres`** au lieu de calculer lui-même les poids après la décision. C'est `poids_apres_decision` (#9) qui les fournit, et c'est lui qui gérera les réallocations.
- **Mots de baisse** : « chute d'environ 29 % » est lu comme « chute de 29 % ». Les mots d'approximation ne donnent toujours aucune tolérance sur l'arrondi.
- **Une année seule** (« 2022 ») passe si elle correspond à une date des sources, ou à défaut à un nombre.
- **Le motif de rejet donne une piste à l'agent** : la pièce à citer, ou le signe « − » oublié.
- **Format supposé d'une pièce documentaire** (V3) : `valeurs` contient le critère, avec `true` si le titre le remplit.

## Limites et suite
- **Réallocations** : `poids_apres_decision` ne les gère pas encore (#16), donc les plafonds d'une décision « panier » ne sont pas encore contrôlés de bout en bout.
- **Nombres en lettres** : « trois fois » n'est pas extrait. Les consignes du Procureur et de l'Avocat l'interdisent (`pipeline/debat.py`).
- **`controle_performance_passee`** repose sur des mots-clés ; il reste toujours `a_verifier`.
- **Branchement dans le procès** : c'est l'orchestrateur (#12) qui appelle le Greffier et ajoute les arguments rejetés au contrat.
