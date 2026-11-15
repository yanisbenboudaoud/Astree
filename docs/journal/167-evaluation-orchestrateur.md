# #167 — L'orchestrateur et le débat mesurés : les preuves changent avec la décision et le Pacte

- **Issue** : #167 · **PR** : à venir · **Statut** : terminée (sans le plan de procès facultatif)
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Une évaluation qui relit les procès **réellement tenus** et mesure ce que fait l'orchestrateur Bedrock, ses garde-fous et le débat, sans aucun appel à Bedrock.

- **`validation/evaluation_orchestrateur.py`** (nouveau) :
  - `lire_traces_s3(bucket)` : contrats archivés par la Lambda dans `traces/<date>/<id>.json` (lecture S3 seulement). `nom_bucket_projet()` : `BUCKET_PROJET`, sinon `alphaforge-<compte>` comme `deploiement/deployer.py`.
  - `lire_proces_locaux()` : les procès de `frontend/src/data/proces/`. `rassembler` fait l'union des deux sources, chaque procès une fois (la trace S3 prime).
  - Lecture d'une trace : `appels_du_modele` (étapes `orchestrateur` dont la raison ne commence pas par « Pièce obligatoire ajoutée d'office », refus compris, car ils comptent dans le budget), `simulation_complete_demandee`, `simulation_ajoutee_d_office`, `motif_general` (motif d'un refus sans le titre), `genre_motif` (renvoi du Greffier pour les chiffres, pour le cadre, ou les deux).
  - `mesurer(contrats)` → `Mesures` : outils obtenus par profil et par profil × décision, appels par procès, budget, simulation obligatoire, pièces d'office, refus par motif, débat de chaque côté (`Cote` : proposés, renvoyés, corrigés, rejetés, affichés), contre-interrogatoire (budget de 4), appels Bedrock visibles dans la trace. `outils_reserves` : outils demandés pour certains profils seulement.
  - `rapport(lecture, mesures)` et `executer(options)`.
- **`validation/evaluation.py`** : `main` accepte aussi les évaluations qui lisent des procès tenus au lieu d'un jeu (`_evaluations_sans_jeu`), avec leurs options (`--local`).
- **`docs/validation/evaluation_orchestrateur.md`** (généré) : le rapport, avec la date de lecture, le nombre de procès lus et, en annexe, la liste des procès.
- **`tests/test_evaluation_orchestrateur.py`** (nouveau) : traces synthétiques (simulation d'office, budget dépassé refus compris, refus regroupés, débat renvoyé, corrigé et rejeté, motifs chiffres et cadre, contre-interrogatoire), faux client S3 (seul `traces/` est lu), union des sources, et rapport sur les 7 procès de l'interface. Aucun accès AWS.

## Comment l'utiliser
```bash
aws login   # identifiants de l'équipe, jamais dans le code
python -m validation.evaluation orchestrateur
python -m validation.evaluation orchestrateur --local   # sans AWS : les 7 procès de l'interface
```

## Comment vérifier
```bash
pytest tests/test_evaluation_orchestrateur.py
```

Première lecture (2026-11-15, 183 procès) :
- budget de 8 appels respecté dans 183/183 procès, aucun refus de budget (de 4 à 8 appels, médiane 6) ;
- simulation obligatoire demandée par le modèle lui-même dans 183/183 procès, jamais ajoutée d'office ;
- `rechercher_documents` n'est demandé que pour le Pacte de Mateo, le seul qui a une règle `critere_documentaire`. `calculer_correlations` est demandé dans tous les procès de réallocation crypto d'Amira, et `indicateurs_actif` dans seulement 4 procès d'Amira sur 24 ;
- 56 appels refusés sur 1 051 : 54 « source manquante » (recherche ESG sur un titre sans document) et 2 raisons trop longues ;
- débat : Procureur renvoyé 98 fois sur 717 arguments, corrigé 93 fois ; Avocat renvoyé 28 fois sur 687, corrigé 27 fois. Tous les renvois portaient sur des chiffres, aucun sur le cadre.

## Choix faits en cours de route
- **Pas de date figée** : contrairement à #165, le rapport dépend de ce qui est archivé. Il écrit donc la date de lecture et la liste des procès lus, et son test porte sur les 7 procès de l'interface, qui ne changent pas.
- **Pièces d'office exclues du choix du modèle** : `points_de_bascule` et `composition_fnb` sont ajoutées par Python (#61, #116). Les compter comme des choix ferait croire à une adaptation qui n'en est pas une.
- **Durée et jetons non mesurés** : la trace archivée n'a ni horodatage ni compteur de jetons, et les tours Bedrock de l'orchestrateur n'y sont pas (seulement ses appels d'outils). Le rapport le dit au lieu de les estimer.
- **Plan de procès non tenu** : l'issue le propose « si on a le temps ». Il coûte des appels Bedrock et demande l'accord de l'équipe ; il n'a pas été lancé.

## Limites
- Les procès archivés ne sont pas un échantillon planifié : 111 sur 183 portent sur une position en TSLA du profil prudent (démonstrations et développement), et beaucoup de lignes du tableau profil × décision n'ont qu'un procès.
- Les traces antérieures à une fonctionnalité ne la montrent pas (`cadre_simulation` avant #60, `points_de_bascule` avant #61) : les taux mélangent plusieurs versions du pipeline.
