# #115 — Plusieurs horizons dans un même portefeuille (poches)

- **Issue** : #115 · **PR** : à venir · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Atelier Banque Nationale : « l'horizon ne s'applique pas au portefeuille global ». Un profil peut maintenant déclarer des **poches** (ex. : une mise de fonds dans 3 ans et la retraite), chacune avec son horizon et ses règles. Une décision est jugée **dans une seule poche**.

**Le format** : `personas/schema_pacte.json`
- `poches` (facultatif, au moins deux) : chaque poche a `id`, `objectif`, `horizon_ans`, `part` (du portefeuille global), `portefeuille` (poids dans la poche), `regles` et, facultatifs, `profil_risque` et `reponse_horizon` (profil tiré du questionnaire).
- `pacte.regles` devient la liste des règles **communes** ; une règle de la poche remplace la règle commune de même `id`. `pacte.regles` peut être vide si chaque poche a au moins une règle.
- `decision_demo.poche` (facultatif) : la poche de la décision de démonstration.
- Vérifié au chargement (`pipeline/pacte.py`, `_erreurs_poches`) : id uniques, parts qui totalisent 1, portefeuilles et règles de chaque poche valides, et portefeuille global égal à la somme des poches pondérées par leur part (écart toléré : 0,0001). Sans poches : au moins une règle, et aucune `decision_demo.poche`.

**La projection** : `pipeline/poches.py` (nouveau)
- `profil_de_la_poche(profil, id_poche)` : copie du profil réduite à la poche, **de la même forme qu'un profil sans poches**. Elle prend le portefeuille, l'horizon, le profil de risque, les règles (propres, puis communes non remplacées) et le capital de la poche (capital × part), plus un champ `poche` (`id`, `objectif`, `horizon_ans`, `part`). Tout l'aval du procès lit ce profil sans changement : orchestrateur, simulation, taille maximale, points de bascule, Greffier, Pacte vécu. **La simulation porte donc sur la poche, pas sur le portefeuille global.**
- `poche_la_plus_prudente` (horizon le plus court), `regles_de_la_poche`, `portefeuille_global`, `formater_horizon`, `PocheInconnue`.

**Le choix de la poche** : `pipeline/agent_profil.py`
- `lancer_agent_profil(…, poche=None)` et `choisir_poche` : la poche **imposée** par l'utilisateur, sinon celle que le modèle **déduit** de la demande (nouveau champ `poche` de l'extraction, limité aux id du profil), sinon la plus prudente. Dans ce dernier cas, et si la poche déduite contredit la poche imposée, l'agent ajoute un contrôle `interpretation_demande` à `a_verifier`. Étape de trace `choisir_poche`. Une poche inconnue lève `PocheInconnue` avant tout appel Bedrock.
- Taille, montant (converti avec le capital de la poche) et financement se lisent dans la poche ; le libellé devient « 20 % en TSLA (poche « Mise de fonds d'une maison ») ».
- **Sans poches, le prompt et le schéma envoyés au modèle sont inchangés.**

**Le procès** : `pipeline/tribunal.py`
- `juger_decision(…, poche=None)` et `verifier_avant_proces(…, poche=None)`. Pacte vécu d'un profil à poches : la poche est obligatoire (les questions viennent du portefeuille de la poche), sinon `ErreurCalibrage` avant Bedrock.
- Limite ajoutée au contrat : « Seule la poche concernée est simulée… ».
- `pipeline/orchestrateur.py` et `pipeline/debat.py` : le dossier du modèle porte la poche, et une consigne rappelle aux agents qu'un chiffre de la poche n'est pas un chiffre du portefeuille global. Les deux ne s'appliquent que s'il y a une poche.
- `pipeline/contre_interrogatoire.py` : une question après le procès porte sur la même poche (`decision.poche`).

**Le contrat** (`contrat/schema_sortie.json`, `contrat/valider.py`) : `decision.poche` et `pacte.poche` (`id`, `objectif`, `horizon_ans`, `part`) ; `pacte.horizon_ans` et `pacte.regles` sont ceux de la poche ; la pièce Pacte gagne `part_poche`. `valider` vérifie que `decision.poche` = `pacte.poche.id`. Champs absents sans poches : les contrats existants restent valides.

**Le questionnaire** (#84, `pipeline/questionnaire.py`, `pipeline/profils.py`)
- `profil_depuis_reponses(…, objectifs=[…])` : au moins deux objectifs `{id?, objectif, horizon, part, portefeuille}` donnent une poche chacun (`poche_depuis_objectif`). Chaque poche reçoit sa propre `pire_baisse_max`, calculée avec le même barème et l'horizon de la poche. Les préférences (crypto, concentration, exclusions, objectif, règle personnelle) restent communes. Sans portefeuille global, il est calculé à partir des poches.
- `detail_bareme(…, objectifs)` : `poches` donne la capacité et le seuil de chaque poche.
- `appliquer_modifications` : une règle de poche se modifie par la clé `"<poche>/<règle>"`.
- Projeté sur une poche, le profil remplace sa réponse « horizon » par celle de la poche : la pièce du questionnaire et ses contrôles partent de l'horizon de la poche.

**Lambda** (`deploiement/lambda_tribunal.py`) : `/tribunal` accepte `"poche"` (avec et sans progression ; 400 si inconnue ou mal formée, sans Bedrock) ; `/profil` accepte `"objectifs"` (5 au plus).

**Profil de test** : `personas/sofia.json` (fictif), 100 000 $.

| Poche | Part | Horizon | Portefeuille | Règles propres |
|---|---|---|---|---|
| `mise_de_fonds` | 30 % | 3 ans | ZST.TO 70 %, XBB.TO 20 %, XIU.TO 10 % | pire baisse −8 % ; « mise de fonds disponible à la date prévue » (qualitative) |
| `retraite` | 70 % | 25 ans et plus | XIU.TO 30 %, SPY 40 %, QQQ 15 %, XBB.TO 15 % | pire baisse −40 % |

Règle commune : crypto exclue.

## Comment l'utiliser
```
python -m pipeline sofia "Je veux mettre 20 % en Tesla" --poche=mise_de_fonds   # vrai procès Bedrock
POST /tribunal {"profil": "sofia", "demande": "…", "poche": "retraite"}
```

## Comment vérifier
- `pytest tests/test_poches.py` (47 tests) : format, projection, choix de la poche, procès complets sans Bedrock dans chaque poche, contrat, contre-interrogatoire, questionnaire. Le test `test_meme_decision_violation_court_terme_et_conforme_long_terme` reprend le critère de l'issue. Tests des routes dans `test_lambda_tribunal.py` et `test_route_profil.py`. Suite complète : 941 tests.
- **Un profil sans poches donne exactement le même contrat** : les contrats de Robert, Amira et Mateo (procès sans Bedrock, faux modèles des tests) produits avant et après le changement sont identiques octet pour octet (`diff`). Le test `test_sans_poches_aucune_trace_de_poche_dans_le_contrat` le garde.
- **Procès réels** (Bedrock, en local avec `python -m pipeline`), le 2026-11-15, profil `sofia`. Les trois contrats passent `contrat.valider`, sans aucun argument rejeté :

| Demande | Poche | Pire baisse de la poche, avant → après | `pire_baisse_max` | Taille max | Chiffres |
|---|---|---|---|---|---|
| « Je veux mettre 20 % en Tesla », `--poche=mise_de_fonds` | imposée | −4,0 % → −20,5 % (seuil −8 %) | violation | 6 % | 20/20 |
| la même, `--poche=retraite` | imposée | −18,7 % → −28,5 % (seuil −40 %) | conforme | 20 % | 21/21 |
| « Je veux mettre 20 % de mon épargne retraite en Tesla », sans poche | déduite : `retraite` | −18,7 % → −28,5 % | conforme | 20 % | 21/21 |

- Les agents parlent bien de la poche, en dollars de la poche (capital 30 000 $ ou 70 000 $), par exemple « Au pire moment, votre poche aurait perdu 6 142 $, contre 1 209 $ sans cette position » ou « votre poche « Retraite » de 70 000 $ aurait perdu 19 937 $ ».
- Le premier procès est copié tel quel dans `docs/exemples/contrat_sofia.json`, testé par `test_contrat.py`.
- On y voit un défaut **antérieur à cette issue** : le modèle a écrit « x » comme raison de son premier appel d'outil, et le garde-fou (raison courte et sans chiffre) l'a laissée passer. Le défaut est signalé, pas corrigé ici.

## Choix faits en cours de route
- **Projeter plutôt que réécrire** : la poche devient un profil ordinaire. Aucun outil, ni le Greffier, ni la taille maximale ne connaît les poches. Seuls l'Agent Profil (qui choisit) et la sortie du Pacte (qui l'affiche) les lisent.
- **Règles communes + règles propres** plutôt que des règles seulement par poche : une exclusion (crypto, ESG) vaut pour tout le portefeuille sans la recopier. Une règle commune est vérifiée dans la poche jugée ; un plafond respecté dans chaque poche l'est aussi globalement.
- **Poche par défaut = la plus prudente**, avec un contrôle « à vérifier », plutôt que de refuser la demande : le système ne bloque jamais (section 4).
- **Portefeuille global gardé** dans le fichier (l'interface l'affiche) et vérifié contre les poches, plutôt que calculé au chargement.
- Questionnaire : seul l'horizon change d'une poche à l'autre. Les autres facteurs de capacité (coussin, revenu…) restent communs et peuvent rester plus contraignants (ex. : coussin de 3 à 6 mois → −20 % même pour la retraite).

## Limites et suite
- **Interface (à prévenir)** : afficher la poche jugée (`pacte.poche`) et laisser choisir la poche avant le procès (`poche` de `/tribunal`) ; l'écran « Construire mon Pacte » ne propose pas encore plusieurs objectifs (`objectifs` de `/profil`). Les tables précalculées de l'écran Décision (`pipeline/vues_interface.py`) portent encore sur le portefeuille global.
- Seule la poche jugée est simulée : l'effet sur le portefeuille global n'est pas jugé (limite écrite dans le contrat). Une décision qui déplace de l'argent d'une poche à l'autre n'existe pas.
- La jurisprudence (#56) mélange les verdicts de toutes les poches d'un profil.
- Pacte vécu d'un profil à poches : une poche par calibrage ; `calibrage_demo` n'est pas lu pour un profil à poches.
