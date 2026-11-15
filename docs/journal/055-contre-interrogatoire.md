# #55 — Contre-interrogatoire : question libre de l'utilisateur

- **Issue** : #55 · **PR** : #72, #74, #80 · **Statut** : terminée (route branchée dans l'interface)
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`pipeline/contre_interrogatoire.py`** :
  - `interroger(contrat, question)` : répond à une question posée après le procès et renvoie une copie du contrat complétée. Les nouvelles pièces sont ajoutées à `pieces`, et un échange est ajouté à `contre_interrogatoire`. Même boucle que le procès (`CLAUDE.md`, section 4) : l'orchestrateur choisit les outils, le Procureur et l'Avocat répondent en citant les pièces, puis le Greffier vérifie chaque chiffre (`verifier_cote`, une relance puis rejet).
  - `verifier_question` (500 caractères au plus, espaces normalisés), `prochain_numero` (numérotation à la suite) et `pieces_de_l_echange`.
  - `QuestionInvalide` : question vide ou trop longue, ou procès sans décision, refusés **avant tout appel au modèle**.
- **`pipeline/orchestrateur.py`** : `instruire_question` reprend la boucle de `instruire_dossier`, mise en commun dans `_jouer`, avec ses propres consignes (`CONSIGNES_QUESTION`). Le budget est plus petit (`BUDGET_APPELS_QUESTION = 4`), les pièces déjà au dossier sont montrées au modèle pour qu'il ne les recalcule pas, et aucune pièce n'est ajoutée d'office. `instruire_dossier` ne change pas.
- **`pipeline/debat.py`** : si le dossier porte une `question`, `construire_message` l'ajoute avec la consigne de réponse (`CONSIGNE_QUESTION`) : 1 à 3 arguments, et une demande de conseil reçoit un seul argument, sans chiffre, qui le dit. Sans question, le message est identique.
- **`pipeline/simulation.py`** (complète la fiche [009](009-simuler-portefeuille.md)) : les pièces de simulation disent quelle décision elles simulent. Le titre devient « Simulation du portefeuille avec 15 % en TSLA » ou « Rejeu de 2022 avec 15 % en TSLA » (`decision_simulee`), et les `valeurs` contiennent la taille simulée (`taille`, ou `part_reallouee` pour une réallocation). Sans cela, avec plusieurs simulations au dossier, les agents ne savaient pas laquelle correspondait à la question et ne pouvaient pas écrire « 15 % », que le Greffier aurait refusé. Les chiffres ne changent pas.
- **`contrat/schema_sortie.json`** et **`contrat/valider.py`** : champ facultatif `contre_interrogatoire` (définition `echange_contre_interrogatoire`) et ses renvois : pièces ajoutées présentes dans `pieces` et jamais ajoutées deux fois, pièces citées existantes, sorties de l'orchestrateur valides, `controle_chiffres` portant sur `verifier_chiffres`. Les contrats sans ce champ restent valides.
- **`deploiement/lambda_tribunal.py`** : route `POST /question` `{"id", "question"}`. Elle relit `traces/<date>/<id>.json`, appelle `interroger`, réarchive le contrat complété au même endroit et renvoie `{"id", "echange", "pieces"}`. Erreurs : 400 (identifiant ou question invalide), 404 (procès ou profil inconnu), 422 (Pacte ou données inutilisables), 500 (erreur inattendue, détail dans CloudWatch).
- **Interface** (`frontend/`, PR #80) : la case de question libre de l'écran Tribunal appelle `/question`.
  - `poserQuestion(procesId, question)` (`src/api/tribunal.ts`) envoie `{"id", "question"}` à la Lambda ; `adapterEchange` (`src/api/adaptateur.ts`) transforme la réponse en réponses affichées : un argument du Procureur ou de l'Avocat par réponse, puis le compte rendu du Greffier (`controle_chiffres`, et le motif de chaque argument rejeté). Type `EchangeContrat` dans `src/api/contrat.ts`.
  - Les nouvelles pièces (`pieces` de la réponse) rejoignent « Pièces à conviction » (`nouvellesPieces` d'une `Reponse`, `src/domaine/questions.ts`), citées par « Contre-interrogatoire · <question> ».
  - Les questions suggérées restent calculées dans le navigateur, sans Bedrock. Le texte libre passe par la Lambda dès que `VITE_API_URL` est défini et que le procès a un identifiant S3, y compris pour un procès enregistré rejoué en démonstration (comme « Trompez le Greffier »). Pendant l'appel (environ 30 s), le champ est désactivé et un message d'attente s'affiche ; en cas d'erreur, le motif s'affiche et la question est remise dans le champ.
- **Tests** : `tests/test_contre_interrogatoire.py` (17 tests avec un faux modèle, plus 1 test réel `bedrock`) et 6 tests de la route dans `tests/test_lambda_tribunal.py`.

## Comment l'utiliser
```python
from pipeline.contre_interrogatoire import interroger

complete = interroger(contrat, "Et si je mettais 15 % au lieu de 30 % ?")
echange = complete["contre_interrogatoire"][-1]   # réponses du Procureur et de l'Avocat
```
Sur la Lambda : `POST /question` `{"id": "<x-proces-id>", "question": "…"}`.

Dans l'interface : après un procès, taper une question dans « Une question pour les agents ? » puis « Envoyer ».

## Comment vérifier
```bash
pytest tests/test_contre_interrogatoire.py tests/test_lambda_tribunal.py
pytest -m bedrock tests/test_contre_interrogatoire.py   # vrai appel, payant
```
**Vérifié dans l'interface** (2026-11-14, mode direct) : procès de Robert sur « 30 % en TSLA », puis « Comment TSLA a-t-il évolué en 2022 ? ». Réponse en environ 35 s : 2 arguments du Procureur et 3 de l'Avocat, qui citent P3 et P4 ; le Greffier affiche « 23/23 chiffres, 5 arguments ». L'orchestrateur n'a ajouté aucune pièce : celles du dossier suffisaient.

Les tests vérifient la numérotation à la suite, le budget de 4 appels, l'absence de pièce d'office, le rejet d'un chiffre inventé (« −99,0 % »), l'enchaînement de deux questions, une demande de conseil sans outil, et la validité du contrat complété (`contrat.valider`).

**Vérifié avec Bedrock** (2026-11-15, compte de l'événement), sur le faux contrat du cas 1 : « Et si je mettais 15 % au lieu de 30 % ? ». L'orchestrateur simule 15 % en TSLA sur toute la période et en 2022 (P6, P7). Le Procureur et l'Avocat écrivent 6 arguments, du type « Avec 15 % en TSLA, la pire baisse simulée passe de −29,0 % (à 30 %) à −16,4 %, ce qui dépasse encore la règle […] −12 % ». Le Greffier vérifie 33 chiffres sur 33, et le contrat complété passe `contrat.valider`. Avant la correction des titres de simulation, les mêmes agents écrivaient « si la simulation la plus récente correspond à une position réduite… ».

## Choix faits en cours de route
- **Nouvelles pièces dans `pieces`**, plutôt que dans l'échange : les identifiants restent uniques, une question suivante peut les citer, et l'interface les affiche comme les autres pièces.
- **Trace de l'échange dans l'échange** : la trace du procès reste celle du procès.
- **Pas de pièce obligatoire** : la simulation de la décision est déjà au dossier. Une question « hors outils » (demande de conseil) peut n'ajouter aucune pièce.
- **Question traitée comme une donnée**, pas comme une consigne : les deux consignes le disent, l'orchestrateur reste limité à sa liste blanche, et le Greffier vérifie toujours les chiffres.
- **Contrat réarchivé au même endroit** (`traces/<date>/<id>.json`) : `/verdict` archive ensuite le procès avec ses échanges.

## Limites et suite
- **Interface** : chaque question libre coûte des appels Bedrock. Les réponses restent dans la session du navigateur ; le contrat archivé dans S3, lui, garde tous les échanges.
- **Déploiement** : redéployer avec `deploiement/deployer.py` pour que la route existe sur la Lambda.
- Le Procureur cite parfois le profil de risque sous sa forme brute (« faible_a_modere ») : à reformuler dans les consignes du débat (#11).
