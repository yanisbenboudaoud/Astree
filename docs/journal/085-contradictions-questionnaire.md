# #85 — Tolérance contre capacité : signaler les contradictions du questionnaire

- **Issue** : #85 · **PR** : #93 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Le questionnaire (#84) sépare la **tolérance** (ce que la personne veut accepter) de la **capacité** (ce qu'elle peut se permettre). Quand ses réponses divergent, le système le **montre** au lieu de le cacher dans le seuil retenu.

- **`config/questionnaire.json`** : nouvelle section `contradictions` (étiquette `hypothese`), modifiable sans code :
  - `paires` : réponses incompatibles, par exemple « je ne touche à rien / j'en rachète » contre « j'ai vendu » en 2022, l'inverse, des proches qui vous disent « très prudent » contre 10 ou 25 % de crypto ou une carte Nasdaq-100 / crypto, et des proches qui vous disent « joueur » contre la carte la plus prudente. Chaque message cite les réponses telles qu'affichées ;
  - `ecart_tolerance_capacite` : contradiction si la tolérance déclarée dépasse le plafond de capacité d'au moins `crans_min` (2) tranches de `profil_risque`.
- **`pipeline/questionnaire.py`** :
  - `contradictions(reponses)` renvoie `[{id, questions, message}]`. Fonction pure, sans LLM, qui ne change aucune règle du Pacte ;
  - `piece_questionnaire(profil, id_piece)` produit la **pièce `declaree`** du procès. Ses valeurs : `date_reponses`, `horizon_ans`, `tolerance_declaree`, `pire_baisse_carte`, `capacite_plafond`, `seuil_retenu`, les questions et réponses affichées, et les identifiants des contradictions ;
  - `controles_questionnaire(profil, id_piece, decision, piece_calibrage)` donne :
    - un contrôle `a_verifier` (`coherence_questionnaire`) par contradiction ;
    - un autre si le Pacte vécu (#68) a mesuré un seuil différent du seuil déclaré : « Vous aviez déclaré … ; devant de vrais jours de marché, vous êtes resté jusqu'à …. Le seuil mesuré l'emporte. » ;
    - et `controle_experience` (#84, enfin appelé pendant un procès) si la décision porte sur un type de titre jamais détenu ;
  - `profil_depuis_reponses` garde les réponses dans le profil (champ `questionnaire` : `date`, `etiquette`, `reponses`). Nouveau paramètre `etiquette_reponses` (`fait` par défaut, `fictif` pour des réponses de démonstration).
- **`personas/schema_pacte.json`** : champ facultatif `questionnaire`.
- **`pipeline/tribunal.py`** : si le profil porte `questionnaire`, ses réponses deviennent la pièce qui suit le Pacte (P2, ou P3 après le Pacte vécu), avec une étape de trace `lire_questionnaire`, ses contrôles et une hypothèse sur le barème.
- **`contrat/valider.py`** : `coherence_questionnaire` et `questionnaire` rejoignent les contrôles du système. Mise à jour de **`REFERENCE_DU_PROJET.md`** section 5, et de la phrase sur les pièces `declaree` dans les consignes du Procureur et de l'Avocat (`pipeline/debat.py`).

## Comment l'utiliser
```python
from pipeline.questionnaire import contradictions
contradictions(reponses)   # [{"id": "tolerance_contre_capacite", "questions": [...], "message": "Vous acceptez −32,1 % ..."}]
```
Un profil écrit par `python -m pipeline.questionnaire <reponses.json>` porte ses réponses : son procès (`python -m pipeline <id> "<demande>"`) contient automatiquement la pièce du questionnaire et ses contrôles.

## Comment vérifier
`pytest tests/test_contradictions_questionnaire.py` (20 tests, sans Bedrock) :
- chacun des 3 exemples de l'issue donne **exactement une** contradiction ;
- les réponses « comme » les 3 profils de test, et l'exemple de `docs/exemples/`, n'en donnent **aucune** ;
- être plus prudent que sa situation ne l'exige, ou n'avoir qu'un cran d'écart, n'est pas une contradiction ;
- la pièce `declaree` : sur l'exemple de l'issue, « Tolérance −32,1 % · capacité −10,0 % · seuil retenu −10,0 % · 1 contradiction » ;
- un argument qui la cite (« Le 15 novembre, vous avez déclaré accepter −32,1 %, mais votre capacité est de −10,0 % ») passe `verifier_chiffres`, et un chiffre inventé est rejeté ;
- seuil mesuré différent du seuil déclaré, et type de titre jamais détenu ;
- **procès complet** (faux modèle, faux débat) d'un profil tiré du questionnaire : pièce P2 `declaree`, un contrôle `coherence_questionnaire`, étape de trace, hypothèse, et le contrat passe `valider_contrat`. Un profil écrit à la main n'a ni cette pièce ni ces contrôles.

`pytest` : 692 tests passent. `python -m validation` : 46 réussis.

## Choix faits en cours de route
- **Les réponses sont gardées dans le profil**, sinon le procès ne pourrait ni produire la pièce ni recalculer les contradictions. La route `/profil` (#87) pourra enregistrer ce même profil dans S3.
- **« Plus d'un cran » = 2 tranches de `profil_risque` ou plus**, et seulement quand la tolérance dépasse la capacité. Le cas inverse (plus prudent que nécessaire) n'est pas incohérent.
- **« Proches prudents » ne compte pas comme contradiction, seulement « très prudents »**. Sinon le profil prudent de test (proches « prudent », carte équilibrée) serait signalé à tort.
- **Le seuil retenu ne change pas** : une contradiction informe, elle ne pénalise pas. Le barème appliquait déjà « le vécu de 2022 l'emporte » et « le plus prudent des deux ».

## Limites et suite
- **Aucun vrai procès Bedrock n'a été lancé** pour cette issue (appels payants). Il reste à vérifier sur un vrai procès que le Procureur cite bien l'écart tolérance/capacité : `python -m pipeline.questionnaire <reponses.json>`, puis `python -m pipeline <id> "<demande>"`.
- **L'interface** affiche déjà les contrôles du système tels quels. Un affichage dédié des contradictions relèvera de l'écran du questionnaire (#86).
- **Les règles de contradiction sont des hypothèses de l'équipe** : elles signalent des écarts plausibles, pas des erreurs certaines.
