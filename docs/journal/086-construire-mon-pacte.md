# #86 — « Construire mon Pacte » : écran du questionnaire, aperçu et signature

- **Issue** : #86 · **PR** : #97 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
L'écran d'entrée ne proposait que les 3 profils de démonstration. Il a maintenant une carte **« Construire mon Pacte »** : n'importe qui répond au questionnaire (#84), relit son Pacte, le signe, puis le fait vivre comme un profil de démonstration (« Revivez 4 jours », Portefeuille, Décision, Tribunal).

### Interface (`frontend/`)
- **`src/ecrans/ConstruireMonPacte.tsx`** (route `/construire`), trois étapes :
  1. **questions**, une par écran : sections (Horizon · Capacité · Tolérance · Expérience · Préférences), barre de progression (`role="progressbar"`), compteur en `aria-live`, focus sur le titre à chaque question ; réponse obligatoire signalée (seul l'horizon l'est), « Passer cette question » sinon, « Précédente » garde les réponses. Les cartes de la question « fourchettes » montrent le pire moment et la valeur finale en dollars, étiquette Fait et période des prix ;
  2. **portefeuille** : titres de l'univers (liste par classe d'actifs), poids en %, total affiché, capital fictif, prénom facultatif ;
  3. **aperçu et signature** : profil de risque, horizon, chaque règle avec « Parce que vous avez répondu : … » (relu dans le barème de Python), étiquette Fait ou Hypothèse, justification complète ; contradictions (#85) et réponses manquantes en « À vérifier » ; limites ; en direct, un autre seuil peut être choisi (« Choisi par vous »). La signature mène à « Revivez 4 jours ».
  - Mention visible : « Simulation éducative. Ce questionnaire décrit vos propres règles ; il ne constitue pas un conseil financier. » Brouillon gardé dans sessionStorage.
- **`src/api/questionnaire.ts`** : types, `QUESTIONS`, `apercuPacte`, `signerPacte`, `saisieDemo`, `estSaisieDemo`, erreurs `PacteNonDisponible` et `ReponsesRefusees`.
- **`src/domaine/questionnaire.ts`** (pur, testé) : `sections`, `blocage`, `basculerChoixMultiple` (« aucune » exclut le reste), `reponsesNettoyees`, `raisonsRegle`, `seuilModifiable`, `valeurDepuisPoints`, `erreurPortefeuille`.
- **`src/api/donnees.ts`** : registre des profils créés (`enregistrerProfilCree`, `profilsCrees`, gardé dans sessionStorage) ; `profil`, `donneesCalibrage` et `chargerTablePosition` les trouvent ; en direct, une table absente est demandée à `POST /table`.
- **`src/api/config.ts`** : `MODE_DIRECT`, `URL_API` et `lireErreur`, sortis de `tribunal.ts` pour servir aussi au questionnaire et aux tables.
- `Decision.tsx` affiche « Simulation indisponible : … » si une table calculée par la Lambda échoue ; `Entree.tsx` : la carte, et « Reprendre » pour les profils créés pendant la session.

### Pipeline et Lambda
- **`pipeline/vues_interface.py`** : les calculs de `scripts/build_ui_series.py` (profil affiché, tables de décision, « Revivez 4 jours ») déplacés dans le pipeline, plus `vues_profil(profil)`. Le script les importe ; **sa sortie est identique octet pour octet** à celle d'avant le déplacement.
- **`POST /profil`** : `"apercu": true` construit le Pacte sans rien ranger (200) ; signé (201), la réponse porte aussi `vues`.
- **`POST /table`** `{profil, ticker}` : la table de l'écran Décision pour un titre, sans Bedrock (environ 0,1 s).
- **`scripts/build_ui_series.py`** écrit aussi `generated/questionnaire.json` (questions, et l'exemple `docs/exemples/reponses_questionnaire.json` rejoué comme la Lambda : aperçu, profil signé, vues) et les 31 tables de `decisions/investisseur_exemple/`.

## Comment l'utiliser
`npm run dev`, écran d'entrée, « Construire mon Pacte ». En démonstration : « Remplir comme un profil de test ». En direct (`VITE_USE_MOCKS=false`) : toute saisie, après redéploiement de la Lambda (`python deploiement/deployer.py`).

## Comment vérifier
```bash
cd frontend && VITE_USE_MOCKS=true npx vitest run     # 67 tests, dont 13 dans src/test/questionnaire.test.tsx
.venv/bin/python -m pytest                            # 739 tests
```
- `questionnaire.test.tsx` : 16 questions en 5 sections, cartes chiffrées par Python, réponse obligatoire signalée, retour arrière qui garde la réponse, « Passer », exemple → aperçu (« Parce que vous avez répondu : Cryptoactifs : Aucune ») → signature → « Revivez 4 jours » ; en démonstration, toute autre saisie est refusée.
- `test_route_profil.py` : aperçu sans rangement, vues à la signature, `/table` (et refus) ; la table de `/table` pour Robert est **identique** à `generated/decisions/robert/TSLA.json`.
- `test_build_ui_series.py` : les vues renvoyées par la Lambda pour Robert sont identiques aux fichiers précalculés.
- Navigateur (mode démonstration) : parcours complet jusqu'au Tribunal, axe-core sans violation sur les trois étapes, aucun débordement à 375 px.
- **En direct, le 2026-11-15**, Lambda redéployée depuis la branche de cette PR (`deployer.py --sans-donnees`), puis de nouveau après le rebase sur #90, dont le déploiement avait retiré `/table` :
  - routes : `/questionnaire` 200 (16 questions, 5,5 s au démarrage à froid), `/profil` en aperçu 200 en 0,1 s sans rien ranger, `/profil` signé 201 en 0,6 s (`profils/<id>.json`, seuil « Choisi par vous »), `/table` 200 en 0,9 s, réponse inconnue 400 avec son motif ;
  - parcours dans l'interface (`localhost:5173`, mode direct) : réponses refusées par Python affichées avec leur motif ; aperçu avec deux contradictions et la capacité plus prudente que la tolérance ; seuil changé de −10 % à −12 % (« Choisi par vous ») ; signature → « Revivez 4 jours » ; Portefeuille et Décision (table de TSLA venue de `/table`) ; procès de « 30 % en TSLA » en 55 s environ (1 violation, 6 à vérifier, 4 conformes ; le questionnaire est la pièce P2) ; verdict signé, archivé dans `verdicts/<id>/`.

## Choix faits en cours de route
- **Le barème ne tourne jamais dans le navigateur** : en démonstration, seul l'exemple calculé d'avance devient un Pacte, comme les procès enregistrés. Inventer un Pacte pour une autre saisie aurait contredit « Python calcule ».
- **Les tables d'un profil créé viennent de la Lambda** (`/table`), pas d'un calcul dans le navigateur, et des mêmes fonctions que les tables précalculées : c'est pour cela que les calculs ont été déplacés dans `pipeline/vues_interface.py`.
- **Sélection du titre par une liste native** plutôt que le composant `Recherche.tsx`, qui est lié au lancement d'une décision.
- Les seuils ne se modifient qu'en direct : la nouvelle règle (libellé, justification) est écrite par Python.

## Limites et suite
- La Lambda n'accepte que l'origine `http://localhost:5173` (CORS) : servie ailleurs, l'interface affiche « Le Tribunal est injoignable ».
- Le Tribunal en direct reste figé pendant l'attente du procès (environ 55 s ici) : c'est #90.
- En démonstration, aucun procès n'est enregistré pour le profil d'exemple : le Tribunal l'indique. On peut en enregistrer un avec `deploiement/tester_function_url.py --creer-profil docs/exemples/reponses_questionnaire.json "…"`, puis le copier dans `src/data/proces/`.
- Un profil créé vit dans la session du navigateur (sessionStorage) ; il reste dans S3, mais l'interface ne sait pas encore le recharger par son identifiant.
- Les 2 tests de `domaine.test.ts` qui échouaient sans raison apparente échouent parce que `frontend/.env.local` met les tests en mode direct ; avec `VITE_USE_MOCKS=true`, tout passe.
