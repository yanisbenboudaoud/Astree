# #55 — Contre-interrogatoire : question libre de l'utilisateur

- **Issue** : #55 · **PR** : #72 · **Statut** : en cours (branchement dans l'interface à suivre)
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
- **`pipeline/contre_interrogatoire.py`** :
  - `interroger(contrat, question)` : répond à une question posée après le procès et renvoie une copie du contrat complétée. Les nouvelles pièces sont ajoutées à `pieces`, et un échange est ajouté à `contre_interrogatoire`. Même boucle que le procès (`CLAUDE.md`, section 4) : l'orchestrateur choisit les outils, le Procureur et l'Avocat répondent en citant les pièces, puis le Greffier vérifie chaque chiffre (`verifier_cote`, une relance puis rejet).
  - `verifier_question` (500 caractères au plus, espaces normalisés), `prochain_numero` (numérotation à la suite) et `pieces_de_l_echange`.
  - `QuestionInvalide` : question vide ou trop longue, ou procès sans décision, refusés **avant tout appel au modèle**.
- **`pipeline/orchestrateur.py`** : `instruire_question` reprend la boucle de `instruire_dossier`, mise en commun dans `_jouer`, avec ses propres consignes (`CONSIGNES_QUESTION`). Le budget est plus petit (`BUDGET_APPELS_QUESTION = 4`), les pièces déjà au dossier sont montrées au modèle pour qu'il ne les recalcule pas, et aucune pièce n'est ajoutée d'office. `instruire_dossier` ne change pas.
- **`pipeline/debat.py`** : si le dossier porte une `question`, `construire_message` l'ajoute avec la consigne de réponse (`CONSIGNE_QUESTION`) : 1 à 3 arguments, et une demande de conseil reçoit un seul argument, sans chiffre, qui le dit. Sans question, le message est identique.
- **`contrat/schema_sortie.json`** et **`contrat/valider.py`** : champ facultatif `contre_interrogatoire` (définition `echange_contre_interrogatoire`) et ses renvois : pièces ajoutées présentes dans `pieces` et jamais ajoutées deux fois, pièces citées existantes, sorties de l'orchestrateur valides, `controle_chiffres` portant sur `verifier_chiffres`. Les contrats sans ce champ restent valides.
- **`deploiement/lambda_tribunal.py`** : route `POST /question` `{"id", "question"}`. Elle relit `traces/<date>/<id>.json`, appelle `interroger`, réarchive le contrat complété au même endroit et renvoie `{"id", "echange", "pieces"}`. Erreurs : 400 (identifiant ou question invalide), 404 (procès ou profil inconnu), 422 (Pacte ou données inutilisables), 500 (erreur inattendue, détail dans CloudWatch).
- **Tests** : `tests/test_contre_interrogatoire.py` (17 tests avec un faux modèle, plus 1 test réel `bedrock`) et 6 tests de la route dans `tests/test_lambda_tribunal.py`.

## Comment l'utiliser
```python
from pipeline.contre_interrogatoire import interroger

complete = interroger(contrat, "Et si je mettais 15 % au lieu de 30 % ?")
echange = complete["contre_interrogatoire"][-1]   # réponses du Procureur et de l'Avocat
```
Sur la Lambda : `POST /question` `{"id": "<x-proces-id>", "question": "…"}`.

## Comment vérifier
```bash
pytest tests/test_contre_interrogatoire.py tests/test_lambda_tribunal.py
pytest -m bedrock tests/test_contre_interrogatoire.py   # vrai appel, payant
```
Les tests vérifient la numérotation à la suite, le budget de 4 appels, l'absence de pièce d'office, le rejet d'un chiffre inventé (« −99,0 % »), l'enchaînement de deux questions, une demande de conseil sans outil, et la validité du contrat complété (`contrat.valider`).

## Choix faits en cours de route
- **Nouvelles pièces dans `pieces`**, plutôt que dans l'échange : les identifiants restent uniques, une question suivante peut les citer, et l'interface les affiche comme les autres pièces.
- **Trace de l'échange dans l'échange** : la trace du procès reste celle du procès.
- **Pas de pièce obligatoire** : la simulation de la décision est déjà au dossier. Une question « hors outils » (demande de conseil) peut n'ajouter aucune pièce.
- **Question traitée comme une donnée**, pas comme une consigne : les deux consignes le disent, l'orchestrateur reste limité à sa liste blanche, et le Greffier vérifie toujours les chiffres.
- **Contrat réarchivé au même endroit** (`traces/<date>/<id>.json`) : `/verdict` archive ensuite le procès avec ses échanges.

## Limites et suite
- **Interface** (#14) : en mode direct, la case de question libre de l'écran Tribunal doit appeler `/question` et afficher l'échange. Le format est à valider avec Yanis ; à faire dans une deuxième PR.
- **Déploiement** : redéployer avec `deploiement/deployer.py` pour que la route existe sur la Lambda.
- Le test réel `bedrock` n'a pas encore été lancé.
