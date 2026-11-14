# #12 — Orchestrateur du Tribunal, trace et sortie JSON validée

- **Issue** : #12 · **PR** : #40, #43, à venir · **Statut** : en cours
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
Partie de l'issue qui ne dépend que d'issues fermées (#2, #7, #8, #9) : l'orchestrateur et l'enchaînement Profil → Orchestrateur. (Une première version, PR #35, a été annulée par la PR #38 ; celle-ci repart de zéro.)

- **`pipeline/orchestrateur.py`** :
  - `instruire_dossier(decision, profil, premier_numero, outils=None, converser=...)` : boucle Bedrock Converse avec outils (`converser_avec_outils`, fiche [007](007-client-llm-bedrock.md)). Le modèle choisit les outils et leurs paramètres ; Python exécute chaque appel et numérote les pièces. Renvoie un `ResultatInstruction` : `pieces`, `trace` (étapes `orchestrateur`), `appels`.
  - `outils_du_profil(profil)` : la liste blanche, décrite pour le portefeuille du profil : `indicateurs_actif` (fiche [006](006-indicateurs-actif.md)) et `simuler_portefeuille` (fiche [009](009-simuler-portefeuille.md)).
  - `construire_dossier(decision, profil)` : ce que lit le modèle (décision, profil de risque, horizon, règles sans justification, portefeuille). Le nom du profil n'est pas transmis.
  - `raison_valide(raison)` : une phrase non vide, d'au plus 160 caractères, sans chiffre.
- **`pipeline/tribunal.py`** : `juger_decision(identifiant_profil, demande)` enchaîne `lancer_agent_profil` (Pacte en P1), `instruire_dossier` (pièces P2, P3…) et assemble un **contrat partiel** : `persona`, `demande`, `decision`, `pacte`, `comparaison`, `pieces`, `controles` (ceux de l'Agent Profil), `verdict: null`, `hypotheses`, `sources`, `limites`, `trace`, `avertissement`.
- **`pipeline/__main__.py`** : la commande locale.
- **Greffier branché** (2e PR, fiche [010](010-greffier.md)) : `juger_decision` appelle `verifier_pacte` après l'orchestrateur. Chaque règle du Pacte reçoit son contrôle, plus `biais_survivant`, et la trace gagne une étape `greffier` (« 1 violation, 1 conforme, 2 à vérifier »). `ResultatInstruction.piece_simulation` donne au Greffier la pièce obligatoire, qu'elle vienne du modèle ou de Python.
- **Débat et vérification des chiffres branchés** (3e PR, fiches [011](011-procureur-avocat.md) et [010](010-greffier.md)) : après l'orchestrateur, `juger_decision` appelle `debattre` (Procureur et Avocat en parallèle). Le Greffier passe en dernier : `verifier_pacte`, puis `verifier_cote` applique `trier_arguments` à chaque côté avec **une** relance par argument refusé (`corriger_argument`, étape `bedrock_correction` dans la trace). Le contrat reçoit `requisitoire`, `plaidoirie`, `arguments_rejetes` et les contrôles `verifier_chiffres` et `performance_passee`. **Seul `taille_max_compatible` (#21) manque** pour que le contrat passe le schéma.
- **`tests/test_orchestrateur.py`** : 20 tests avec un faux modèle (`FauxModele`), plus 2 tests réels marqués `bedrock`.

## Comment l'utiliser
```bash
python -m pipeline robert "Je veux mettre 30 % de mon portefeuille en Tesla"   # vrais appels Bedrock
```
```python
from pipeline.tribunal import juger_decision
contrat = juger_decision("robert", "Je veux mettre 30 % de mon portefeuille en Tesla")
```

## Comment vérifier
```bash
pytest tests/test_orchestrateur.py                    # faux modèle, gratuit
pytest -m bedrock tests/test_orchestrateur.py -s      # vrais appels Bedrock (payants)
```
Les tests vérifient la numérotation des pièces, le paramètre `raison` ajouté à chaque outil, et chaque garde-fou : budget de 8 appels (même dans un seul tour), outil hors liste blanche refusé, raison avec chiffre, vide ou trop longue refusée, erreur d'outil (titre inconnu, taille impossible) renvoyée au modèle sans planter, simulation ajoutée d'office et pas en double. Avec les vrais outils, les pièces passent le schéma du contrat et la simulation d'office retrouve la pire baisse de la maquette (−0,2897). `juger_decision` est testé avec l'Agent Profil simulé, avec et sans décision.

**Vrais appels (Sonnet 5.5, 2026-11-14)** : les 2 tests `bedrock` passent. `python -m pipeline robert "Je veux mettre 30 % de mon portefeuille en Tesla"` produit P1 (Pacte), le rejeu 2022 (−2,6 % → −23,7 %), les indicateurs de TSLA et la simulation complète (−29,0 % max · +12,0 %/an), soit les chiffres de la maquette. Pour la même décision, le profil audacieux reçoit un autre dossier (le modèle insiste sur le risque propre du titre « malgré un horizon long »).

## Choix faits en cours de route
- **La raison est un paramètre de chaque outil** : `_avec_raison` ajoute un champ `raison` obligatoire au schéma envoyé à Bedrock. Python le retire avant d'appeler l'outil et le place dans la trace.
- **Tout refus compte dans le budget** : un modèle qui insiste ne peut pas boucler.
- **Motif précis** (`probleme_raison`) : raison absente, avec un chiffre, ou trop longue. Lors des premiers vrais appels, le modèle écrivait souvent un chiffre (une année, un seuil) dans sa première raison ; la consigne le précise maintenant (« ni seuil, ni pourcentage, ni année »), et deux procès de suite n'ont plus eu de refus.
- **Pièce obligatoire** : la simulation `periode: "complete"` de la décision demandée (même titre, taille et financement). Une simulation d'une autre taille ou du rejeu 2022 ne compte pas.
- **Numérotation** : le Pacte est P1 (créé par l'Agent Profil), l'orchestrateur numérote à partir de P2.
- **`comparaison`** est calculée directement par `simuler_portefeuille` dans `juger_decision` : ce n'est pas un choix du modèle.
- **`persona`** contient l'identifiant du profil (`robert`), comme le dit `CLAUDE.md` section 5 (l'exemple `contrat_robert.json` écrit `Robert`).
- **Commande** : `python -m pipeline <id> "<demande>"` au lieu de `python -m alphaforge personas/robert.json "…"` prévu dans l'issue : il n'y a pas de paquet `alphaforge`, et l'Agent Profil charge un profil par identifiant (fiche 008).

**Procès complet, vrai appel** (profil prudent, « 30 % en TSLA ») : environ 22 s ; 8 arguments (4 de chaque côté), **29/29 chiffres vérifiés**, aucun rejet ; `valider_contrat` ne signale que l'absence de `taille_max_compatible`.

**Greffier, vrai appel** : pour « 30 % en TSLA » et le profil prudent, les contrôles sont ceux de `contrat_robert.json` : `pire_baisse_max` en violation (« Pire baisse −29,0 % au-delà du seuil −12,0 % »), `plafond_crypto` conforme, les deux règles qualitatives à vérifier.

## Limites et suite
- **Reste de #12** : `taille_max_compatible` (#21), puis la validation du contrat complet par `contrat/schema_sortie.json`. D'ici là, le contrat renvoyé est partiel et ne passe pas le schéma.
- **Réallocations (#16)** : l'Agent Profil peut maintenant renvoyer une décision `reallocation`, mais `simuler_portefeuille` ne sait pas encore la simuler. L'orchestrateur instruit quand même le dossier ; la trace indique « Pièce obligatoire indisponible », `comparaison` est absente et chaque règle du Pacte est `a_verifier` (jamais « conforme » par défaut). L'outil 3 `calculer_correlations` (#16) n'est pas encore dans la liste blanche.
- **Champ `duree` de la trace** : demandé par l'issue, mais refusé par le schéma du contrat (`additionalProperties: false`). À ajouter au schéma avec l'accord de l'équipe.
