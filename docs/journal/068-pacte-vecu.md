# #68 — Le Pacte vécu : mesurer les limites de l'investisseur sur de vrais jours de marché

- **Issue** : #68 · **PR** : #78 · **Statut** : terminée (mode démonstration vérifié ; mode direct à vérifier une fois la Lambda redéployée et ouverte au navigateur, #14)
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit

**Moteur (Python, sans LLM)**
- `pipeline/calibrage.py` :
  - `episodes_de_baisse(portefeuille)` : un vrai jour de marché par niveau de `config/calibrage.json` (−5 % à −50 %). On prend d'abord le portefeuille du profil, puis une série de référence (XIU.TO, SPY, QQQ, NVDA) s'il n'a jamais baissé autant. L'épisode ne garde l'`historique` que **jusqu'au jour J**.
  - `parcours_dichotomie`, `prochaine_question` : 4 questions de baisse au plus, puis la **capacité** (temps pour revenir au sommet, comparé à l'horizon), la **crypto** (si le portefeuille en contient) et un **arbitrage valeurs** par règle `critere_documentaire`.
  - `calibrer(profil, reponses, date, id_piece, etiquette)` : le seuil est la baisse réelle du **dernier jour où l'utilisateur est resté**. Produit la pièce `declaree`, l'étape de trace `calibrage` et le profil au seuil mesuré (`appliquer_seuil` : `provenance`, `etiquette`, `piece`). S'il vend dès le premier jour, le seuil du Pacte est conservé. Refuse (`ErreurCalibrage`) une réponse manquante, invalide, ou à une question non posée.
  - `reponses_demo(profil)` : réponses préenregistrées du profil de test (`calibrage_demo`, étiquette `fictif`).
- `pipeline/tribunal.py` : `juger_decision(..., calibrage=...)` vérifie les réponses **avant tout appel Bedrock**. P1 est le Pacte (au seuil mesuré), P2 les réponses ; l'orchestrateur numérote à partir de P3. Les hypothèses du contrat disent quel seuil a été mesuré.
- `pipeline/greffier.py` : le contrôle de pire baisse cite aussi la pièce du seuil mesuré. `pipeline/pacte.py` : les limites de la pièce Pacte distinguent seuil mesuré et hypothèses. `pipeline/debat.py` : une phrase des consignes explique la pièce `declaree` au Procureur et à l'Avocat.
- `deploiement/lambda_tribunal.py` : champ facultatif `"calibrage": {"reponses": {...}}` de `/tribunal`, daté du jour (UTC). Corps mal formé ou réponses invalides : 400, sans procès. `python -m pipeline <id> "<demande>" --calibrage-demo` pour un procès local avec les réponses préenregistrées.
- Contrat : pièce de type `declaree`, étape de trace `calibrage`, règle avec `provenance`, `etiquette` et `piece` (`contrat/schema_sortie.json`). `contrat/valider.py` vérifie que `piece` désigne bien une pièce `declaree`. Profils : `calibrage_demo` facultatif (`personas/schema_pacte.json`, et les 3 profils de test).

**Interface**
- `scripts/build_ui_series.py` → `frontend/src/data/generated/calibrage/<id>.json` : les jours, leur courbe en dollars arrêtée au jour J, les questions complémentaires, et les réponses de démonstration avec **le seuil calculé en Python**.
- `frontend/src/domaine/calibrage.ts` : la même dichotomie en TypeScript, `profilAvecCalibrage` (Pacte au seuil mesuré) et `tablePositionCalibree` / `tablePanierCalibree` (statuts et taille maximale rejugés avec le seuil mesuré, comme le Greffier).
- Écran `src/ecrans/Calibrage.tsx` (`/:profil/pacte-vecu`, « Revivez 4 jours »), lien depuis la carte « Votre Pacte » du Portefeuille. `App.tsx` passe le profil calibré à tous les écrans. Le Tribunal envoie les réponses en direct, ou rejoue le procès `*_vecu.json` en démonstration.
- `lib/format.ts` : `seuil()` écrit −12 % pour un seuil rond et −10,2 % pour un seuil mesuré.
- Mode démonstration : le Tribunal ne rejoue un procès calibré que s'il est marqué `"calibrage": true` dans `index.json` et tenu avec exactement les mêmes réponses. `deploiement/tester_function_url.py … --calibrage-demo` enregistre un tel procès sur la Lambda.

## Comment l'utiliser
```python
from pipeline.calibrage import prochaine_question, calibrer
question = prochaine_question(profil, {})            # {"id": "baisse_25", "date_jour": "2022-05-09", "baisse": -0.2539, …}
resultat = calibrer(profil, reponses, "2026-11-15", "P2")
resultat.seuil                                       # -0.101618 pour Robert (réponses de démonstration)
```
Dans l'interface : Portefeuille → carte « Votre Pacte » → « Revivez 4 jours de marché ».

## Comment vérifier
- `pytest tests/test_calibrage.py` (18 tests). Ils couvrent tous les tests demandés par l'issue : même seuil pour les mêmes réponses ; aucune donnée après le jour J ; profil prudent qui reste à −10,2 % et vend à −16,0 % → 30 % TSLA en violation ; profil qui reste jusqu'à −30 % → conforme ; un argument qui cite une réponse passe `verifier_chiffres` (et un chiffre inventé est rejeté) ; procès complet sans Bedrock dont le contrat passe `valider_contrat`. Plus : réponses refusées, crypto, valeurs, capacité.
- `python -m validation` : groupe « 9. Pacte vécu », 6 scénarios (de « vend dès le premier jour » à « reste jusqu'à −60 % »).
- `cd frontend && npm test` : `calibrage.test.ts` vérifie entre autres que **le navigateur trouve le même seuil que Python** pour les 3 profils.
- 3 vrais procès (Bedrock, commande locale `--calibrage-demo`, 2026-11-15) passent `python -m contrat.valider`, avec 0 argument rejeté. Exemple (Robert) : « vous avez répondu « reste » à −10,2 % le 2022-06-13, puis « vend » à −16,0 % le 2022-07-14. La simulation de votre décision atteint −29,0 %. »
- Parcours vérifié dans le navigateur (mode démonstration) : réponses propres → seuil −5,4 % → Portefeuille en violation, curseur « aucune taille compatible », Tribunal qui explique qu'aucun procès n'est enregistré avec ces réponses ; réponses de démonstration → procès calibré rejoué (vérifié avant la fusion avec #71, qui a fait passer les procès de démonstration à des procès archivés dans S3).

## Choix faits en cours de route
- **Le seuil est une baisse réelle, pas un niveau rond** : l'utilisateur est resté devant −10,16 %, pas « −10 % ». Le chiffre est donc vérifiable dans la pièce.
- **Séries de référence** : le portefeuille prudent ne baisse jamais de plus de −7,8 %. Pour lui montrer −20 %, il faut une autre série. On prend des titres de l'univers, des indices larges vers les plus volatils, et la carte nomme toujours la série (« iShares S&P/TSX 60 »). Les montants supposent le capital au sommet, et la carte le dit.
- **La dichotomie existe en Python et en TypeScript** : l'écran doit choisir la question suivante sans appeler la Lambda. Python fait foi (le Tribunal recalcule tout), et un test garde les deux identiques sur les réponses de démonstration.
- **Séances sous la limite** : comptées en Python avec le seuil du fichier, elles ne peuvent pas être recomptées avec le seuil mesuré sans la série quotidienne. Elles ne sont donc plus affichées (le graphique dit « Limite du Pacte » au lieu de « jamais franchie »).
- **Pas d'étape « Pacte vécu » dans la barre de procédure** : l'écran est facultatif et s'ouvre depuis la carte du Pacte.
- **Date des réponses en UTC**, côté navigateur comme côté Lambda : un soir à Montréal, elle peut afficher le lendemain.

## Limites et suite
- **Procès calibrés de démonstration à enregistrer sur la Lambda** : depuis #71, les procès de démonstration viennent de S3 (identifiant utilisable par « Trompez le Greffier »). Les 3 procès tenus en local ne suivent pas ce format et n'ont pas été gardés. Après la fusion et le redéploiement : `tester_function_url.py <profil> "<demande>" --calibrage-demo --sortie …` pour chaque profil, puis ajout dans `frontend/src/data/proces/` et `index.json` (`"calibrage": true`). D'ici là, en démonstration, le Pacte vécu fonctionne jusqu'au Tribunal, qui dit qu'aucun procès n'est enregistré avec ces réponses.
- **Mode direct pas encore vérifié** : la Lambda doit être redéployée avec ce code, et la Function URL ouverte au navigateur (#14).
- Une réponse à un épisode passé ne garantit pas le comportement futur (Bradbury, Hens et Zeisberger, *Review of Finance*, 2015) ; une seule période de données. Ces limites sont dans la pièce et dans le contrat.
- Seule la pire baisse est mesurée. Les réponses sur la capacité, la crypto et les valeurs sont déclarées et citables, mais ne changent aucune règle.
- `e2e/verifier.mjs` n'a pas été relancé (il demande Edge ou Chrome) ; le nouvel écran n'y est pas encore parcouru.
