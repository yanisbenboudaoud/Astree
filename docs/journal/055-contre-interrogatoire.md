# #55 — Contre-interrogatoire : question libre de l'utilisateur

- **Issue** : #55 · **PR** : #72, #74, #80 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
- **`pipeline/contre_interrogatoire.py`** :
  - `interroger(contrat, question)` : répond à une question posée après le procès et renvoie une copie du contrat complétée. Les nouvelles pièces sont ajoutées à `pieces`, et un échange est ajouté à `contre_interrogatoire`. Même boucle que le procès (`REFERENCE_DU_PROJET.md`, section 4) : l'orchestrateur choisit les outils, le Procureur et l'Avocat répondent en citant les pièces, puis le Greffier vérifie chaque chiffre (`verifier_cote`, une relance puis rejet).
  - `verifier_question` (500 caractères au plus, espaces normalisés), `prochain_numero` (numérotation à la suite) et `pieces_de_l_echange`.
  - `QuestionInvalide` : question vide ou trop longue, ou procès sans décision, refusés **avant tout appel au modèle**.
- **`pipeline/orchestrateur.py`** : `instruire_question` reprend la boucle de `instruire_dossier`, mise en commun dans `_jouer`, avec ses propres consignes (`CONSIGNES_QUESTION`). Le budget est plus petit (`BUDGET_APPELS_QUESTION = 4`), les pièces déjà au dossier sont montrées au modèle pour qu'il ne les recalcule pas, et aucune pièce n'est ajoutée d'office. `instruire_dossier` ne change pas.
- **`pipeline/debat.py`** : si le dossier porte une `question`, `construire_message` l'ajoute avec la consigne de réponse (`CONSIGNE_QUESTION`) : 1 à 3 arguments, et une demande de conseil reçoit un seul argument, sans chiffre, qui le dit. Sans question, le message est identique.
- **`pipeline/simulation.py`** (complète la fiche [009](009-simuler-portefeuille.md)) : les pièces de simulation disent quelle décision elles simulent. Le titre devient « Simulation du portefeuille avec 15 % en TSLA » ou « Rejeu de 2022 avec 15 % en TSLA » (`decision_simulee`), et les `valeurs` contiennent la taille simulée (`taille`, ou `part_reallouee` pour une réallocation). Sans cela, avec plusieurs simulations au dossier, les agents ne savaient pas laquelle correspondait à la question et ne pouvaient pas écrire « 15 % », que le Greffier aurait refusé. Les chiffres ne changent pas.
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

**Vérifié avec Bedrock** (2026-11-15, compte de l'événement), sur le faux contrat du cas 1 : « Et si je mettais 15 % au lieu de 30 % ? ». L'orchestrateur simule 15 % en TSLA sur toute la période et en 2022 (P6, P7). Le Procureur et l'Avocat écrivent 6 arguments, du type « Avec 15 % en TSLA, la pire baisse simulée passe de −29,0 % (à 30 %) à −16,4 %, ce qui dépasse encore la règle […] −12 % ». Le Greffier vérifie 33 chiffres sur 33, et le contrat complété passe `contrat.valider`. Avant la correction des titres de simulation, les mêmes agents écrivaient « si la simulation la plus récente correspond à une position réduite… ».

## Choix faits en cours de route
- **Nouvelles pièces dans `pieces`**, plutôt que dans l'échange : les identifiants restent uniques, une question suivante peut les citer, et l'interface les affiche comme les autres pièces.
- **Trace de l'échange dans l'échange** : la trace du procès reste celle du procès.
- **Pas de pièce obligatoire** : la simulation de la décision est déjà au dossier. Une question « hors outils » (demande de conseil) peut n'ajouter aucune pièce.
- **Question traitée comme une donnée**, pas comme une consigne : les deux consignes le disent, l'orchestrateur reste limité à sa liste blanche, et le Greffier vérifie toujours les chiffres.
- **Contrat réarchivé au même endroit** (`traces/<date>/<id>.json`) : `/verdict` archive ensuite le procès avec ses échanges.

## Interface (troisième PR)
- **`frontend/src/ecrans/Tribunal.tsx`** : en mode direct, une question libre part au vrai Tribunal (`poserQuestion` dans `src/api/tribunal.ts`, `POST /question`). Pendant l'instruction, l'écran affiche le temps écoulé. L'échange s'affiche ensuite : les réponses du Procureur et de l'Avocat avec leur provenance et leurs pièces, le contrôle du Greffier, les arguments écartés et les pièces ajoutées (P7, P8…), qui s'ouvrent dans le tiroir et peuvent être citées dans « Trompez le Greffier ». En démonstration, aucune question libre n'est envoyée (appels payants) ; les questions suggérées restent calculées par le Greffier.
- **`src/api/adaptateur.ts`** : `adapterEchange` (échange du contrat → écran) et `adapterPiece`. Un procès relu avec des questions déjà archivées (`contre_interrogatoire`) les affiche, et ses pièces disent quelle réponse les cite.
- Les pièces calculées dans l'interface par le Greffier pour les questions suggérées s'appellent désormais G1, G2… : les P<n> restent ceux du Tribunal, qui numérote à la suite du procès.
- **Démarrage à froid** : l'écran Tribunal réveille la Lambda à l'ouverture (`reveillerLambda`, une vérification sans chiffre, gratuite). Une réponse 429 (concurrence réservée de 2 atteinte) affiche « Le Tribunal est occupé… Réessayez dans un instant ».
- **Vérifié en direct le 2026-11-15** (`frontend/e2e/direct.mjs`, Lambda redéployée depuis `main`) : pour Robert et « 30 % en TSLA », la question « Et si je mettais 15 % au lieu de 30 % ? » a reçu sa réponse en 15 s. Elle a ajouté P7 (« Simulation du portefeuille avec 15 % en TSLA », −16,4 %) et P8 (rejeu 2022 à 15 %), et le Greffier a vérifié 31 chiffres sur 31. Le contrat réarchivé dans S3 passe `contrat.valider`.

## Limites et suite
- Le Procureur cite parfois le profil de risque sous sa forme brute (« faible_a_modere ») : à reformuler dans les consignes du débat (#11).
