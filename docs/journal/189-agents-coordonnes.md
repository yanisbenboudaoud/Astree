# #189 — Agents coordonnés et mesurés : réplique, trace horodatée, Guardrail Bedrock

- **Issue** : #189 · **PR** : #190 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-16

## Ce qui a été construit
Quatre manques de la partie agentique (audit du 15 novembre) : les agents ne se répondaient pas, la trace n'avait ni heure ni coût, le choix des preuves par l'orchestrateur était replié, et le cadre « simulation seulement » n'avait qu'un contrôle.

- **Réplique** (`pipeline/debat.py`) : `repliquer_les_deux(dossier, requisitoire, plaidoirie)` fait répondre, en parallèle, chaque camp à l'argument adverse qui pèse le plus contre lui (`repliquer`, consigne `CONSIGNE_REPLIQUE`, schéma `schema_replique` : `repond_a` = numéro de l'argument visé). Dans `pipeline/tribunal.py`, nouvelle phase `replique` entre le débat et le Greffier : seuls les arguments que le Greffier accepterait tels quels peuvent être visés (`pipeline.chiffres.argument_recevable`). Le Greffier vérifie ensuite les répliques comme les autres (chiffres, cadre, une relance). Une réplique dont la cible a finalement été écartée va dans `arguments_rejetes` (`RAISON_CIBLE_ECARTEE`). Le contre-interrogatoire n'a pas de réplique.
- **Mesure** (`pipeline/llm.py`) : `compter_appels()` et `au_nom_de(agent)` comptent chaque appel Converse par agent (jetons lus et écrits, `latencyMs`). `juger_decision` remplit le nouveau champ `bedrock` du contrat : appels, jetons, `duree_bedrock_s`, `duree_proces_s`, `cout_estime_usd` (tarif public, constantes `TARIF_*`), `par_agent`, et `garde_fou`. Chaque étape de trace porte son `horodatage` (`pipeline.progression.horodater`, posé quand l'étape est signalée : la progression en direct et le contrat ont la même heure).
- **Guardrail Bedrock** : `verifier_garde_fou(texte, source)` (API ApplyGuardrail), actif seulement si `BEDROCK_GUARDRAIL_ID` est défini. Entrée : la demande (`RefusGardeFou`, avant tout appel au modèle) et la question du contre-interrogatoire (`QuestionInvalide`), contre les attaques de consigne. Sortie : chaque argument qui passe déjà les vérifications Python (`trier_arguments(..., garde_fou=)`), contre le sujet refusé « conseil personnalisé ». Compte rendu dans le contrôle `cadre_simulation`. `deploiement/deployer.py` crée le Guardrail `alphaforge-cadre-simulation` (`assurer_garde_fou`, idempotent : une version n'est publiée que si l'empreinte de `CONFIG_GARDE_FOU` change), donne `bedrock:ApplyGuardrail` sur ce seul Guardrail (`politique_iam_lambda.json`) et passe son id et sa version à la Lambda.
- **Contrat** : `repond_a` (`cote`, `numero`) sur un argument ou un argument rejeté, `horodatage` sur une étape, champ `bedrock`. Tous facultatifs : les procès enregistrés restent valides. `contrat/valider.py` (`erreurs_repliques`) vérifie qu'une réplique vise un argument existant du camp adverse, qui n'est pas lui-même une réplique.
- **Interface** : cinquième phase « Réplique » à l'écran de chargement ; sous le tableau du débat, le bloc « Les répliques » (l'argument visé rappelé par sa première phrase) ; l'encadré « Comment les agents ont instruit ce dossier », visible sans rien déplier, qui liste chaque calcul choisi par l'orchestrateur avec sa raison, ceux ajoutés d'office par Python, et la mesure Bedrock (`frontend/src/domaine/instruction.ts`) ; le moment de chaque étape (« +12,4 s ») dans « Comment le Tribunal a travaillé ». Le procès-verbal annonce chaque réplique (« Réplique à l'argument 1 de l'Avocat »).
- **Tests** : `tests/conftest.py` interdit désormais tout client Bedrock dans un test non marqué `bedrock` : un appel oublié derrière un faux échoue au lieu d'être facturé (c'est arrivé une fois pendant ce travail, avant ce garde-fou : un ou deux appels de réplique).

- **Déployé et essayé sur la Lambda** (2026-11-16) : Guardrail créé (version 1) ; trois procès réels, tous valides, chacun avec deux répliques, 0 argument rejeté et 0 intervention du Guardrail sur 10 ou 11 textes :

  | Procès | Profil · décision | Appels Bedrock | Jetons lus / écrits | Coût estimé | Durée | Chiffres |
  |---|---|---|---|---|---|---|
  | `2026-11-16-dc4199dcaa79` | Robert · 30 % TSLA | 8 | 65 710 / 8 271 | 0,21 $ | 56 s | 35/35 |
  | `2026-11-16-6563f5a1e2be` | Amira · panier à 25 % | 7 | 61 493 / 8 594 | 0,21 $ | 56 s | 28/28 |
  | `2026-11-16-2f205d08775f` | Mateo · 10 % XOM | 12 | 82 993 / 8 916 | 0,26 $ | 63 s | 18/18 |

  Robert a aussi son contre-interrogatoire « Et si je mettais 15 % au lieu de 30 % ? » (25/25 chiffres). Les trois sont copiés depuis S3 dans `frontend/src/data/proces/`, en tête de `index.json` : ce sont eux que le mode démonstration rejoue. Une demande qui tente de détourner les consignes (« Ignore toutes tes consignes… ») est refusée en 0,7 s, HTTP 400, sans appel au modèle.
- `frontend/src/domaine/debat.ts` : nouveau thème `liquidite` (« Pourriez-vous revendre vite ? ») ; l'Avocat d'Amira en parle, et l'argument tombait dans « Autres points ».

## Comment l'utiliser
Rien à changer pour lancer un procès : la réplique et la mesure sont toujours là. Pour le Guardrail, redéployer :
```bash
.venv/bin/python -X utf8 deploiement/deployer.py --sans-donnees
```

## Comment vérifier
- `.venv/bin/python -m pytest` : 1097 tests, dont la réplique dans le procès (`test_replique_vise_un_argument_valide_et_passe_le_greffier`, `test_replique_dont_la_cible_est_ecartee_est_rejetee`), le refus du Guardrail avant tout appel, le compteur par agent et par fil d'exécution (`tests/test_llm.py`), le déploiement idempotent du Guardrail (`tests/test_deployer.py`).
- `npm --prefix frontend test` : 165 tests, dont `instruction.test.ts`.
- Après un vrai procès : `python -m contrat.valider <contrat.json>` ; le champ `bedrock` donne le coût du procès, et chaque étape son heure.

## Choix faits en cours de route
- **La réplique ne vise qu'un argument recevable** : viser un argument que le Greffier va écarter ferait répondre à du vide. Le filtre est la même vérification Python, sans relance ni appel.
- **Le Guardrail ne remplace pas le Greffier** : il n'est consulté qu'après les vérifications Python, en second regard. Le sujet « conseil personnalisé » ne filtre pas l'entrée : une demande de conseil reçoit déjà, au contre-interrogatoire, une réponse qui dit que le Tribunal ne conseille pas.
- **Coût estimé, pas facturé** : le tarif est une constante relevée le 2026-11-15 ; la facture réelle est dans AWS Billing.
- **Stabilité de l'orchestrateur** : d'une répétition à l'autre, le même outil n'est pas toujours choisi (6 cas sur 9 identiques, `docs/validation/evaluation_orchestrateur.md`). C'est voulu : le modèle choisit les preuves ; les phases, la pièce obligatoire, le budget et tous les contrôles du Greffier, eux, ne varient jamais. La doc technique le dit (section 3).

## Limites et suite
- Les procès **avec Pacte vécu** (`"calibrage": true`) et Robert à 25 % datent d'avant #189 : rejoués, ils n'ont ni réplique, ni heure, ni mesure.
- Le Guardrail n'est intervenu sur aucun des 32 arguments réels : il n'a donc encore rien attrapé que le Greffier aurait laissé passer.
- Un appel Bedrock du contre-interrogatoire n'est pas compté (le champ `bedrock` porte sur le procès).
