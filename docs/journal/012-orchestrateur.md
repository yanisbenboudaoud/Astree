# #12 — Orchestrateur du Tribunal, trace et sortie JSON validée

- **Issue** : #12 · **PR** : à venir · **Statut** : en cours
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

## Choix faits en cours de route
- **La raison est un paramètre de chaque outil** : `_avec_raison` ajoute un champ `raison` obligatoire au schéma envoyé à Bedrock. Python le retire avant d'appeler l'outil et le place dans la trace.
- **Tout refus compte dans le budget** : un modèle qui insiste ne peut pas boucler.
- **Pièce obligatoire** : la simulation `periode: "complete"` de la décision demandée (même titre, taille et financement). Une simulation d'une autre taille ou du rejeu 2022 ne compte pas.
- **Numérotation** : le Pacte est P1 (créé par l'Agent Profil), l'orchestrateur numérote à partir de P2.
- **`comparaison`** est calculée directement par `simuler_portefeuille` dans `juger_decision` : ce n'est pas un choix du modèle.
- **`persona`** contient l'identifiant du profil (`robert`), comme le dit `CLAUDE.md` section 5 (l'exemple `contrat_robert.json` écrit `Robert`).
- **Commande** : `python -m pipeline <id> "<demande>"` au lieu de `python -m alphaforge personas/robert.json "…"` prévu dans l'issue : il n'y a pas de paquet `alphaforge`, et l'Agent Profil charge un profil par identifiant (fiche 008).

## Limites et suite
- **Reste de #12** : débat Procureur et Avocat (#11), boucle du Greffier avec une relance (#10), `taille_max_compatible` (#21), puis la validation du contrat complet par `contrat/schema_sortie.json`. D'ici là, le contrat renvoyé est partiel et ne passe pas le schéma.
- **Champ `duree` de la trace** : demandé par l'issue, mais refusé par le schéma du contrat (`additionalProperties: false`). À ajouter au schéma avec l'accord de l'équipe.
- Les tests réels `bedrock` n'ont pas encore été lancés.
