# #100 — Retirer la question « fourchettes » du questionnaire : seuil tiré de la capacité

- **Issue** : #100 · **PR** : #102 · **Statut** : terminée (Lambda à redéployer après la fusion)
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
La question 7 du questionnaire (`fourchettes` : cinq cartes de portefeuilles réels, « Lequel auriez-vous choisi ? ») est retirée. Elle donnait la tolérance déclarée (fiche 084). La baisse vraiment acceptée se mesure au Pacte vécu (fiche 068).

- **`config/questionnaire.json`** : 15 questions. Le barème `tolerance` devient `resserrement` (même cran : la baisse acceptée est réduite d'un quart). `capital_reference_cad`, qui ne servait qu'aux cartes, est retiré. Les règles de contradiction `proches_prudents_contre_carte`, `proches_joueur_contre_carte` et `ecart_tolerance_capacite` (fiche 085) sont retirées ; les trois autres paires restent.
- **`pipeline/questionnaire.py`** :
  - `resserrement(reponses)` remplace `tolerance_declaree` : la personne vend-elle quand ça baisse ? Le vécu de 2022 décide quand elle investissait, sinon la réaction imaginée.
  - `analyser` : seuil de `pire_baisse_max` = plafond de capacité (`plafond_capacite`, inchangé), multiplié par 0,75 en cas de vente, puis arrondi vers le prudent. La règle est étiquetée `hypothese`. Sa justification nomme les réponses décisives et renvoie au Pacte vécu.
  - `cartes_fourchettes` et le type de question `cartes` sont retirés ; `questions()` renvoie une copie de la config.
  - `detail_bareme` renvoie `resserrement` au lieu de `tolerance` ; `seuil_retenu` vaut `{valeur, brut, resserre}`.
  - `piece_questionnaire` : plus de `tolerance_declaree` ni de `pire_baisse_carte` ; `seuil_resserre` (booléen) dit si le seuil a été resserré. Exemple : « Capacité −10,0 % · seuil retenu −7,5 % (resserré) · 1 contradiction ».
- **Interface** (fiche 086) : le type `CarteFourchette` et le rendu des cartes sont retirés de `ConstruireMonPacte.tsx` (et de son CSS). Le type `Bareme` suit le nouveau `detail_bareme`. L'écran d'entrée affiche `QUESTIONS.length` au lieu de « 16 questions » écrit en dur. `frontend/src/data/generated/questionnaire.json` est régénéré (`scripts/build_ui_series.py --profils robert` : seul ce fichier change).
- `docs/exemples/reponses_questionnaire.json`, `CLAUDE.md` (section 3), `README.md`, `frontend/README.md`, `deploiement/README.md`.

## Comment l'utiliser
```python
from pipeline.questionnaire import detail_bareme
detail = detail_bareme(reponses, "2026-11-15")
detail["capacite"]["plafond"], detail["resserrement"]["resserre"], detail["seuil_retenu"]["valeur"]
```
Une réponse `fourchettes` est maintenant refusée (« Question inconnue »).

## Comment vérifier
`pytest tests/test_questionnaire.py tests/test_contradictions_questionnaire.py tests/test_route_profil.py`, puis `npm test` dans `frontend/`. Les tests prouvent :
- la question n'est plus posée (15 questions, aucune de type `cartes`), et une réponse `fourchettes` est refusée ;
- les seuils des profils de test : prudent −15 %, audacieux −40 %, ESG −25 %, avec le même profil de risque que `personas/` ;
- horizon de moins de 3 ans : seuil −10 % ; « J'ai vendu » en 2022 resserre le seuil (−40 % devient −30 %) même avec « J'en rachète » ;
- les règles de contradiction ne citent que des questions posées ;
- la pièce du questionnaire et `verifier_chiffres` (« votre capacité était de −10,0 %, et le seuil retenu de −7,5 % » passe ; « −35,0 % » est rejeté).

Résultats : 761 pytest, 81 vitest, `npm run verifier` sans problème (23 écrans). Dans le navigateur, le questionnaire va de 1 à 15. La 7ᵉ question est « Votre portefeuille de 100 000 $ vaut 82 000 $… », et aucune carte ne s'affiche. L'aperçu du Pacte de l'exemple donne « Pire baisse tolérée : −20,0 % » (Hypothèse), « parce que vous avez répondu » horizon, retraits, coussin, part de l'épargne, revenu, réaction et vécu de 2022. Aucune violation axe-core.

## Choix faits en cours de route
- **Capacité seule** plutôt qu'une tolérance tirée d'une autre question (ex. : le regard des proches) : choix de l'utilisateur. Le questionnaire décrit ce que la situation permet ; le Pacte vécu mesure ce que la personne accepte vraiment, et son seuil l'emporte déjà (#68).
- **Le resserrement est gardé** : la réaction et le vécu de 2022 restent le seul signal de comportement du questionnaire.
- **La règle de pire baisse est toujours créée** : la question `horizon` est obligatoire et chacune de ses réponses donne un plafond. Sans plafond de capacité, un contrôle « à vérifier » le dirait.
- Les fiches 084, 085 et 086 ne sont pas réécrites : elles décrivent leur issue à sa date.

## Limites et suite
- **Lambda à redéployer après la fusion** : la Lambda en ligne a encore besoin de la question pour calculer le seuil. D'ici là, un Pacte créé en mode direct n'aurait pas de règle de pire baisse.
- Le questionnaire ne mesure plus de tolérance déclarée : l'idée « tolérance ≠ capacité » de la fiche 084 repose maintenant sur le Pacte vécu, qui compare le seuil du questionnaire au seuil mesuré (contrôle `coherence_questionnaire`).
- Les écarts de seuil avec les Pactes écrits à la main (−12 %, −45 %, −20 %) restent des hypothèses de barème.
