# #167 — L'orchestrateur et le débat mesurés : les preuves changent avec la décision et le Pacte

- **Issue** : #167 · **PR** : #175 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Une évaluation qui relit les procès **réellement tenus** et mesure ce que fait l'orchestrateur Bedrock, ses garde-fous et le débat, sans aucun appel à Bedrock.

- **`validation/evaluation_orchestrateur.py`** (nouveau) :
  - `lire_traces_s3(bucket)` : contrats archivés par la Lambda dans `traces/<date>/<id>.json` (lecture S3 seulement). `nom_bucket_projet()` : `BUCKET_PROJET`, sinon `alphaforge-<compte>` comme `deploiement/deployer.py`.
  - `lire_proces_locaux()` : les procès de `frontend/src/data/proces/`. `rassembler` fait l'union des deux sources, chaque procès une fois (la trace S3 prime).
  - Lecture d'une trace : `appels_du_modele` (étapes `orchestrateur` dont la raison ne commence pas par « Pièce obligatoire ajoutée d'office », refus compris, car ils comptent dans le budget), `simulation_complete_demandee`, `simulation_ajoutee_d_office`, `motif_general` (motif d'un refus sans le titre), `genre_motif` (renvoi du Greffier pour les chiffres, pour le cadre, ou les deux).
  - `mesurer(contrats)` → `Mesures` : outils obtenus par profil et par profil × décision, appels par procès, budget, simulation obligatoire, pièces d'office, refus par motif, débat de chaque côté (`Cote` : proposés, renvoyés, corrigés, rejetés, affichés), contre-interrogatoire (budget de 4), appels Bedrock visibles dans la trace. `outils_reserves` : outils demandés pour certains profils seulement.
  - `rapport(lecture, mesures)` et `executer(options)`.
  - `section_plan` et `outils_obtenus` : la section « Plan de procès » du rapport (outils par répétition, mêmes outils d'une répétition à l'autre, durée).
- **`validation/plan_proces.py`** (nouveau) : `python -m validation.plan_proces` tient le plan sur la Lambda déployée (`POST /tribunal`, vrais appels Bedrock), un procès à la fois, avec `adresse_function_url` et `envoyer` de `deploiement/tester_function_url.py`. `tenir_plan` note chaque envoi (procès, statut HTTP, durée côté client) dans `validation/jeux/plan_proces_resultats.json` et ne rejoue jamais une case déjà réussie : une reprise ne paie pas deux fois. Un échec reste noté.
- **`validation/jeux/plan_proces.json`** (nouveau) : 3 décisions (30 % en TSLA, panier crypto-tech, 10 % en XOM) × 3 profils × 2 répétitions, avec le coût estimé avant et le coût mesuré après.
- **`validation/evaluation.py`** : `main` accepte aussi les évaluations qui lisent des procès tenus au lieu d'un jeu (`_evaluations_sans_jeu`), avec leurs options (`--local`).
- **`docs/validation/evaluation_orchestrateur.md`** (généré) : le rapport, avec la date de lecture, le nombre de procès lus et, en annexe, la liste des procès.
- **`tests/test_evaluation_orchestrateur.py`** (nouveau) : traces synthétiques (simulation d'office, budget dépassé refus compris, refus regroupés, débat renvoyé, corrigé et rejeté, motifs chiffres et cadre, contre-interrogatoire), faux client S3 (seul `traces/` est lu), union des sources, rapport sur les 7 procès de l'interface, reprise du plan sans rejouer une case réussie, section du plan (stabilité, durées). Aucun accès AWS.

## Comment l'utiliser
```bash
aws login   # identifiants de l'équipe, jamais dans le code
python -m validation.evaluation orchestrateur
python -m validation.evaluation orchestrateur --local   # sans AWS : les 7 procès de l'interface
python -m validation.plan_proces   # plan de procès : 18 procès, environ 3 $ de Bedrock
```

## Comment vérifier
```bash
pytest tests/test_evaluation_orchestrateur.py
```

Lecture du 2026-11-15 (201 procès, plan compris) :
- budget de 8 appels respecté dans 201/201 procès, aucun refus de budget (de 4 à 8 appels, médiane 6) ;
- simulation obligatoire demandée par le modèle lui-même dans 201/201 procès, jamais ajoutée d'office ;
- `rechercher_documents` n'est demandé que pour le Pacte de Mateo, le seul qui a une règle `critere_documentaire` ;
- 61 appels refusés sur 1 160, presque tous « source manquante » (recherche ESG sur un titre sans document) ;
- débat : Procureur renvoyé 113 fois sur 785 arguments, corrigé 108 fois ; Avocat renvoyé 33 fois sur 757, corrigé 32 fois. Tous les renvois portaient sur des chiffres, aucun sur le cadre.

Plan de procès (18 procès, tous réussis) :
- **à décision égale, les outils suivent le Pacte** : pour 10 % en XOM, seul Mateo (règle ESG) obtient `rechercher_documents` ; pour 30 % en TSLA, seule Amira (plafond crypto) obtient `calculer_correlations` ;
- mêmes outils d'une répétition à l'autre dans 6 cases sur 9 (IC 95 % : 35 % à 88 %) : le modèle varie surtout sur `mesurer_liquidite` et `indicateurs_actif` ;
- durée d'un procès, côté client : de 32 à 64 s, médiane 44,5 s ;
- coût : environ 0,17 $ par procès estimé avant, environ 0,16 $ mesuré après (CloudWatch : 116 appels Bedrock, 872 730 jetons d'entrée, 118 202 de sortie, soit environ 2,93 $).

## Choix faits en cours de route
- **Pas de date figée** : contrairement à #165, le rapport dépend de ce qui est archivé. Il écrit donc la date de lecture et la liste des procès lus, et son test porte sur les 7 procès de l'interface, qui ne changent pas.
- **Pièces d'office exclues du choix du modèle** : `points_de_bascule` et `composition_fnb` sont ajoutées par Python (#61, #116). Les compter comme des choix ferait croire à une adaptation qui n'en est pas une.
- **Durée et jetons hors de la trace** : la trace archivée n'a ni horodatage ni compteur de jetons, et les tours Bedrock de l'orchestrateur n'y sont pas. Le rapport ne les estime pas pour les procès archivés ; pour le plan, la durée est mesurée côté client et les jetons dans CloudWatch, sur la fenêtre de temps du plan (une borne haute si un coéquipier appelait Bedrock en même temps).
- **Plan tenu par la Lambda déployée**, pas en local : mêmes conditions que l'interface, et les procès sont archivés comme les autres. Le coût a été estimé avant de le lancer (issue), à partir des jetons CloudWatch des jours précédents.

## Limites
- Le plan est petit : 2 répétitions par case ne suffisent pas à dire si un outil est demandé « toujours » ou « souvent ».
- Les procès archivés ne sont pas un échantillon planifié : 111 sur 183 portent sur une position en TSLA du profil prudent (démonstrations et développement), et beaucoup de lignes du tableau profil × décision n'ont qu'un procès.
- Les traces antérieures à une fonctionnalité ne la montrent pas (`cadre_simulation` avant #60, `points_de_bascule` avant #61) : les taux mélangent plusieurs versions du pipeline.
