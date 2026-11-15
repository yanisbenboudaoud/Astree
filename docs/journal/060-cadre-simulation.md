# #60 — Greffier : contrôle du cadre « simulation seulement » (aucun conseil personnalisé)

- **Issue** : #60 · **PR** : #77 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
Le case demande à la gouvernance de vérifier le cadre « simulation seulement » (p. 9) et interdit de se présenter comme du conseil financier personnalisé (p. 17). Jusqu'ici, rien n'empêchait un argument d'écrire « vous devriez acheter » ou « TSLA va continuer à monter ». Les règles sont dans `CLAUDE.md`, section 4 quater.

- **`pipeline/cadre_simulation.py`** (nouveau, Python sans LLM) :
  - `detecter_infractions(texte)` : expressions régulières fixes, en deux familles :
    - **conseil** : « vous devriez », « je recommande », « il faut vendre », « Robert devrait alléger », impératif d'une action (« achetez », « ne vendez pas ») ;
    - **promesse** : « va monter », futur simple d'un mouvement de prix (« rapportera », « se répétera »), « devrait rebondir », « garanti », « à coup sûr », « prédit ».
  - Ne sont pas visés : les citations entre guillemets (le Pacte cité), une promesse **niée** dans la même proposition (`est_niee` : « rien ne garantit », « ne prédit pas »), une interrogation indirecte (`est_interrogation_indirecte` : « le Tribunal ne dit pas s'il faut vendre », « savoir si TSLA va remonter »), le conditionnel, le passé et « il peut ».
  - `verifier_cadre_simulation(argument)` rend les infractions et le motif renvoyé à l'agent, par exemple : « Conseil personnalisé : « Vous devriez » (le Tribunal ne recommande aucune transaction : exposer ce que montrent les pièces et laisser l'utilisateur décider) ».
  - `controle_cadre_simulation(*tris)` : contrôle du système `cadre_simulation`, par exemple « Aucun conseil personnalisé ni promesse sur l'avenir : 7 arguments vérifiés ; 1 argument rejeté après une relance ».
- **`pipeline/chiffres.py`** : `trier_arguments` vérifie maintenant chaque argument deux fois, pour ses chiffres et pour le cadre. Un argument fautif est renvoyé **une seule fois**, avec les deux motifs joints par « ; », puis rangé dans `arguments_rejetes`. `TriArguments` compte les rejets de chaque contrôle (`rejetes_chiffres`, `rejetes_cadre`) : un conseil rejeté n'est pas compté comme un chiffre faux.
- **`pipeline/tribunal.py`** : ajoute le contrôle `cadre_simulation` juste après `verifier_chiffres`, et une étape `greffier` / `verifier_cadre_simulation` dans la trace.
- **`pipeline/contre_interrogatoire.py`** (#55) : les réponses passent déjà par `verifier_cote`, donc par le nouveau contrôle. Son compte rendu est ajouté comme étape `verifier_cadre_simulation` de la trace de l'échange, sans changer le format de l'échange.
- **`pipeline/debat.py`** : règles A (aucun conseil) et B (aucune promesse ni prévision) dans `REGLES_COMMUNES`, plus une consigne dans le mode correction.
- **Contrat** : `cadre_simulation` est ajouté à `CONTROLES_SYSTEME` (`contrat/valider.py`), donc il devient aussi un id de règle réservé (`pipeline/pacte.py`). Il est aussi ajouté à la description du schéma, aux deux faux contrats de `docs/exemples/` et à l'exemple de `CLAUDE.md`, section 5.
- **`validation/scenarios.py`**, groupe 5 : les arguments passent maintenant par `trier_arguments`, avec 6 cas de plus (conseil, impératif, promesse, futur, promesse niée, citation du Pacte). Le rapport est régénéré : 40 réussis.

## Comment l'utiliser
```python
from pipeline.cadre_simulation import verifier_cadre_simulation
verifier_cadre_simulation({"texte": "TSLA va continuer à monter.", "pieces": ["P2"]}).motif
# « Promesse ou prévision sur l'avenir : « va continuer à monter » (le passé ne prédit pas l'avenir : …) »
```
Dans un procès, rien à brancher : `trier_arguments` l'applique déjà, et `juger_decision` ajoute le contrôle au contrat.

## Comment vérifier
- `pytest tests/test_cadre_simulation.py` (76 tests) :
  - les exemples de l'issue : « Vous devriez acheter TSLA » est rejeté, « Vous avez écrit : « Préserver mon capital » » est accepté ; « TSLA va continuer à monter » est rejeté, « Le passé ne prédit pas l'avenir » est accepté ;
  - 30 tournures fautives, 29 tournures correctes (négations, interrogations indirectes, conditionnel, indicatif « si vous vendez », « la décision va doubler la part crypto », « le seuil recommandé de −12 % ») ;
  - la relance unique et le rejet ;
  - tous les arguments des faux contrats et des 3 procès réels enregistrés de l'interface passent.
- `pytest tests/test_orchestrateur.py -k conseille` : un conseil glissé dans le réquisitoire est renvoyé une fois, puis rejeté. Il n'est jamais affiché, et le contrat passe `contrat.valider`.
- `pytest tests/test_contre_interrogatoire.py -k conseil` : au contre-interrogatoire, « le Tribunal ne vous dit pas s'il faut vendre » passe, et « vous devriez vendre » est rejeté après une relance.
- `python -m validation` : 40 réussis, 0 en échec.
- Suite complète : 520 tests.
- Faux positifs, vérifiés le 2026-11-14 : 0 sur les 38 arguments distincts produits par Bedrock dans les procès archivés (S3 `traces/` et `verdicts/`, premiers jets compris) et dans les procès enregistrés de l'interface.
- Deux vrais débats Bedrock (`pytest -m bedrock tests/test_debat.py -k faux_contrat`), avec les nouvelles consignes : les 14 arguments passent les deux contrôles du premier coup.

## Choix faits en cours de route
- **Une seule relance pour les deux contrôles** : relancer une fois pour les chiffres, puis encore une fois pour le cadre, aurait donné deux relances par argument. Un texte corrigé pour le cadre aurait aussi pu casser ses chiffres sans être revérifié.
- **Les prévisions à la baisse sont aussi refusées** (« TSLA va chuter », « le portefeuille perdra ») : le passé ne prédit pas l'avenir, dans un sens comme dans l'autre (`CLAUDE.md`, section 7). Une simulation se dit au passé, et un scénario au conditionnel avec l'étiquette `hypothese`.
- **La précision passe avant le rappel** : un faux positif coûte une relance Bedrock et peut faire rejeter un argument juste. Les verbes courants dans une argumentation sont donc écartés (« il faut rappeler », « gardez à l'esprit », « attendre », « passer », « dépasser »). Les verbes aussi transitifs (« doubler », « augmenter ») ne comptent que sans complément d'objet, et « le verdict vous reviendra » n'est pas une prévision.
- **Un conseil nié reste un conseil** (« ne vendez pas », « vous ne devriez pas »). Seules les promesses tiennent compte de la négation.
- **Une interrogation indirecte n'est ni un conseil ni une promesse** (« si », « s'il », « quand », « ce qu'… » dans la même proposition). Le contre-interrogatoire demande à l'agent de répondre à une demande de conseil que le Tribunal ne tranche pas : « le Tribunal ne dit pas s'il faut vendre » doit passer. « Je pense qu'il faut vendre » reste un conseil.
- **`cadre_simulation` n'est pas obligatoire dans `contrat.valider`**, contrairement à `verifier_chiffres` : les contrats archivés avant #60 (S3, procès enregistrés de l'interface) restent valides.
- `controle_performance_passee` n'est pas modifié : il signale encore, à partir de mots-clés, qu'un rendement passé est cité.

## Limites et suite
- **Détection par expressions régulières** : une tournure absente des listes passe (« je vous engage à vendre », une promesse sans verbe au futur). Les consignes des agents restent la première barrière ; ajouter une tournure se fait dans `ACTIONS`, `IMPERATIFS` ou `MOUVEMENTS`, avec un test.
- **Négation par proposition** : « Même sans dividendes TSLA va monter », sans virgule, est lu comme nié. C'est rare dans un texte de LLM.
- **Lambda à redéployer** (`deploiement/deployer.py`) pour que le mode direct de l'interface produise le contrôle. Les 3 procès enregistrés de l'interface ne l'ont pas encore : il apparaîtra quand ils seront rejoués.
- L'interface affiche le nouveau contrôle dans la liste des contrôles sans rien changer, comme les autres contrôles du système.
- **« Trompez le Greffier » (#69)** ne vérifie encore que les chiffres (`detailler_argument`, route `POST /verifier`). Y ajouter le cadre (« Vous devriez acheter » rejeté) demanderait d'étendre le format de sa réponse et le composant de l'interface, avec l'équipe interface.
