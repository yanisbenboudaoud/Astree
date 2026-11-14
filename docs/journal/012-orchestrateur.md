# #12 — Orchestrateur du Tribunal, trace et sortie JSON validée

- **Issue** : #12 · **PR** : #35 · **Statut** : en cours
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
Première partie de l'issue : l'**orchestrateur** qui instruit le dossier (`CLAUDE.md`, section 4).

- **`pipeline/orchestrateur.py`** :
  - `instruire_dossier(decision, profil, outils=None, converser=..., premier_numero=1)` : boucle Bedrock Converse avec outils (via `converser_avec_outils`, fiche [007](007-client-llm-bedrock.md)). Le modèle choisit les outils et leurs paramètres ; Python exécute chaque appel et numérote les pièces (P1, P2…). Renvoie un `ResultatInstruction` : `pieces`, `trace` (étapes `orchestrateur` au format du contrat) et `appels`.
  - `Outil(nom, description_bedrock, executer)` et `OUTILS_DISPONIBLES` : la liste blanche. Aujourd'hui seulement `indicateurs_actif` (fiche [006](006-indicateurs-actif.md)).
  - `construire_dossier(decision, profil)` : ce que lit le modèle (décision, profil de risque, horizon, règles du Pacte sans justification, portefeuille). Le nom du profil n'est pas transmis.
  - `raison_valide(raison)` : une phrase non vide, d'au plus 160 caractères, sans chiffre.
- **`tests/test_orchestrateur.py`** : 17 tests avec un faux modèle (`FauxModele`) qui rejoue des tours écrits à l'avance, plus 1 test réel marqué `bedrock`.

## Comment l'utiliser
```python
import json
from pipeline.orchestrateur import instruire_dossier

profil = json.load(open("personas/robert.json", encoding="utf-8"))
decision = {"type": "position", "ticker": "TSLA", "taille": 0.3,
            "financement": "proportionnel", "libelle": "30 % en TSLA"}
resultat = instruire_dossier(decision, profil)      # appelle Bedrock
resultat.pieces, resultat.trace
```

## Comment vérifier
```bash
pytest tests/test_orchestrateur.py              # faux modèle, gratuit
pytest -m bedrock tests/test_orchestrateur.py -s   # vrai appel Bedrock (payant)
```
Les tests vérifient la numérotation des pièces, le paramètre `raison` ajouté à chaque outil, et chaque garde-fou : budget de 8 appels (même dans un seul tour), outil hors liste blanche refusé, raison avec chiffre, vide ou trop longue refusée, erreur d'outil renvoyée au modèle sans planter, simulation ajoutée d'office (et pas en double).

## Choix faits en cours de route
- **La raison est un paramètre de chaque outil** : `_avec_raison` ajoute un champ `raison` obligatoire au schéma envoyé à Bedrock. Python le retire avant d'appeler l'outil et le place dans la trace. Une raison invalide fait refuser l'appel : le modèle reçoit le motif.
- **Tout refus compte dans le budget** : un modèle qui insiste ne peut pas boucler.
- **Pièce obligatoire** : si `simuler_portefeuille` n'a pas été demandé, Python l'appelle avec la décision (sans `libelle`) et la raison « Pièce obligatoire ajoutée d'office ». Tant que l'outil n'existe pas, la trace l'indique (« Pièce obligatoire indisponible ») et aucune pièce n'est créée.
- **Erreur d'outil** : `ErreurDonnees` est attrapée et renvoyée au modèle avec `resultat_outil(..., erreur=True)` ; la trace garde le motif, aucune pièce n'est créée.
- **Pièces sans `id` côté outils** : chaque outil renvoie une pièce sans `id` ; l'orchestrateur la numérote. `premier_numero` permet de réserver des numéros (ex. : pièce du Pacte créée avant).

## Limites et suite
- **Pas encore fait dans #12** : `juger_decision`, Procureur et Avocat en parallèle (#11), boucle du Greffier (#10), champs `hypotheses`, `sources`, `limites`, la validation finale par le schéma, et la commande `python -m alphaforge`.
- **Outils à brancher** dans `OUTILS_DISPONIBLES` : `taille_max_compatible` (#21).
- **Champ `duree` de la trace** : demandé par l'issue, mais refusé par `contrat/schema_sortie.json` (`additionalProperties: false`). À ajouter au schéma, avec l'accord de l'équipe, avant de le remplir.
- Le test réel `bedrock` n'a pas encore été lancé (il demande `aws login`).
