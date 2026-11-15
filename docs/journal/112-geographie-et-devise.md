# #112 — Diversification géographique et risque de devise

- **Issue** : #112 · **PR** : #125 · **Statut** : terminée (Lambda à redéployer pour l'interface en direct)
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Atelier Banque Nationale : « diversifier, c'est varier les expositions », y compris la **géographie**, et le **risque de devise** d'un investisseur qui vit en CAD. Avant cette issue, les plafonds ne couvraient que `tech`, `crypto` et `energie_fossile`.

- **`config/categories.json`** : trois catégories géographiques, définies par le champ `market` de `assets_universe.csv`, chacune avec sa justification :
  - `canada` : marché `TSX` (10 actions et 3 FNB de titres canadiens) ;
  - `etats_unis` : marchés NASDAQ, NYSE, NYSE Arca et Cboe BZX, **sauf GLD** (coté à New York, mais de l'or physique, qui n'a pas de pays) ; la crypto n'en fait pas partie non plus ;
  - `hors_canada` : tout ce qui n'est pas coté à Toronto, y compris l'or et la crypto. Dans cet univers, ce sont exactement les titres en USD.
  - Deux champs facultatifs pour toutes les catégories : `marches` et `retraits` (un titre retiré n'appartient jamais à la catégorie, même si sa classe, son secteur ou son marché y figurent).
- **`pipeline/categories.py`** : `_appartient` lit aussi `market` et applique les `retraits`. `erreurs_config_categories` vérifie les marchés et les retraits contre l'univers, et signale un titre à la fois ajouté et retiré. Aucun nom de persona.
- **`pipeline/simulation.py`** : la pièce de la période complète gagne `part_cad`, `part_usd`, `part_cad_actuelle` et `part_usd_actuelle` (valeurs brutes). Fonctions publiques `exposition_devises(poids)` (une part par devise de cotation, toutes les devises présentes, même à 0 ; titre hors univers → `ErreurDonnees`) et `valeurs_exposition_devises`. Traitement et limites complétés (`TRAITEMENT_DEVISES`, `LIMITES_DEVISES`, sans chiffre). La description de l'outil pour l'orchestrateur mentionne la part en USD.
- **`pipeline/debat.py`** : une consigne explique `part_usd` (risque de devise, distinct du risque des titres ; une part s'écrit sans signe).
- **`pipeline/greffier.py`** : `nom_categories` garde un libellé seul tel quel (« États-Unis », « Placements hors du Canada » au lieu de « États-unis »).
- **Questionnaire** (`config/questionnaire.json`, `pipeline/questionnaire.py`) : question facultative `hors_canada`, « Quelle part maximale de votre portefeuille accepteriez-vous hors du Canada ? » (un quart, la moitié, les trois quarts, pas de limite). Elle donne la règle `plafond_hors_canada` (catégorie `hors_canada`). Passée ou « pas de limite » : ni règle ni contrôle. Texte d'aide dans `frontend/src/ecrans/ConstruireMonPacte.tsx` ; réponse « la moitié » ajoutée à `docs/exemples/reponses_questionnaire.json`.
- **`frontend/src/data/generated/`** régénéré (`scripts/build_ui_series.py`) : les catégories des titres (`univers.json`), les libellés (`categories.json`), les 16 questions et l'exemple de démonstration (`questionnaire.json`, `decisions/investisseur_exemple/`). Les tables des trois profils de test ne changent pas.
- **`CLAUDE.md`** : tableau des catégories (section 3), outil 2 (section 4 bis), méthode de l'exposition en devise (section 6 bis). **`docs/GUIDE_DU_PROJET.md`** : liste des catégories.

## Comment l'utiliser
```python
from pipeline.categories import categories_du_titre
categories_du_titre("GLD")      # frozenset({"hors_canada"})
categories_du_titre("XIU.TO")   # frozenset({"canada"})

from pipeline.simulation import piece_simulation
v = piece_simulation("P1", portefeuille, decision)["valeurs"]
v["part_usd_actuelle"], v["part_usd"]   # Robert, 30 % en TSLA : 0.10 → 0.37
```
Dans un Pacte : `{"id": "plafond_etats_unis", "type": "plafond", "categories": ["etats_unis"], "max": 0.40, …}`.

## Comment vérifier
```bash
pytest tests/test_categories.py tests/test_greffier.py tests/test_simulation.py tests/test_questionnaire.py
```
Les tests demandés par l'issue :
- un plafond `etats_unis` est en `violation` quand la décision le dépasse (Robert, 40 % de SPY : 46,0 % > 40 %) et `conforme` sinon (30 % de SPY : 37 %) ;
- un titre absent de l'univers (XSP.TO) donne `a_verifier` ;
- `verifier_chiffres` accepte « la part cotée en dollars américains passerait de 10 % à 37 % » en citant la pièce ; une part inventée (45 %) ou dérivée (« 27 points de plus ») est rejetée.

Autres tests : Canada et hors Canada se partagent l'univers sans recouvrement ; hors Canada = titres en USD ; GLD et la crypto ne comptent pas aux États-Unis ; un retrait l'emporte sur le marché (cas d'un FNB comme XSP) ; un marché mal écrit est signalé ; la question `hors_canada` crée le plafond, et rien quand elle est passée.

**Procès réel** (Bedrock, 2026-11-15), profil créé par le questionnaire de l'exemple (`docs/exemples/reponses_questionnaire.json` : XIU.TO 35 %, SPY 25 %, XBB.TO 30 %, ZST.TO 10 %, plafond hors du Canada de 50 %), demande « Je veux mettre 40 % de mon portefeuille dans le S&P 500 (SPY) » :
- `plafond_hors_canada` en **violation** : « Placements hors du Canada : 55,0 % du portefeuille après la décision, au-delà du plafond de 50,0 % » ; les autres règles calculables sont conformes ;
- `taille_max_compatible` : 0,33 ; point de bascule : « Conforme jusqu'à 33 % en SPY, ou avec un plafond de 55,0 % au lieu de 50,0 % » ;
- la pièce de simulation contient `part_usd_actuelle` 0,25 et `part_usd` 0,55 ; la raison de l'orchestrateur cite « l'exposition aux devises » ;
- `verifier_chiffres` : 24/24 chiffres, 8 arguments ; **le contrat passe `contrat.valider`**.

## Choix faits en cours de route
- **Région = place de cotation**, plutôt qu'une table de pays à la main : c'est vrai pour les 31 titres de l'univers (les FNB cotés à Toronto ne détiennent que des titres canadiens, ceux de New York que des titres américains). Le cas contraire (XSP, coté à Toronto, 98 % États-Unis) se règle dans la configuration avec `retraits` et `ajouts`, sans code.
- **L'or et la crypto n'ont pas de région** : ils ne sont ni au Canada ni aux États-Unis, mais ils sont hors du Canada. D'où `hors_canada`, distincte de `etats_unis`, pour la question du questionnaire.
- **Géographie et devise séparées** : la part en USD vient du champ `currency`, et pas des catégories. XSP (couvert en CAD) serait américain mais sans risque de change ; GLD est sans pays mais en USD.
- **Toutes les devises dans la pièce** (`part_cad` et `part_usd`) : un agent qui écrit « 45 % en CAD » cite une valeur au lieu de faire une soustraction, ce que le Greffier rejetterait (section 4 ter, règle 6).
- **Exposition en devise seulement dans la pièce de la période complète**, la pièce obligatoire : elle est toujours au dossier.
- **Question facultative sans contrôle « réponse manquante »** : les profils créés avant cette issue n'y ont pas répondu, et un contrôle « à vérifier » de plus pour chacun serait du bruit.
- **Les trois profils de test ne changent pas** : leurs procès de démonstration restent valides.

## Limites et suite
- **Redéployer la Lambda** (`deploiement/deployer.py`) pour que l'interface en direct ait la nouvelle question et les nouvelles catégories ; non fait dans cette PR.
- L'exposition est mesurée par la **devise de cotation** : un FNB coté en CAD non couvert qui détiendrait des titres américains serait sous-estimé (aucun dans l'univers actuel).
- La région est celle de la cotation et du siège, pas celle des revenus : Apple vend dans le monde entier.
- La part de la performance due au taux USD/CAD (effet de change sur le rendement) n'est pas encore calculée : ce serait une pièce de plus, calculée en Python.
- L'interface n'affiche pas encore `part_usd` à part : elle se lit en ouvrant la pièce de simulation.
