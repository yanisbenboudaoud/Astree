# Évaluation : l'orchestrateur et le débat mesurés sur les procès tenus

> Généré par `python -m validation.evaluation orchestrateur --archive` (issue #167). **Lu le 2026-11-16** : 218 procès distincts, tenus du 2026-11-14 au 2026-11-16, lus dans `validation/proces_tenus.tar.gz`, copie de `s3://alphaforge-908027376963/traces/` (218 procès) et `frontend/src/data/proces/` (15 procès, dont 0 absents de S3). Aucun appel à Bedrock : les traces sont relues telles qu'archivées. Le rapport change quand de nouveaux procès sont archivés.

**Limite** : ces procès ne sont pas un échantillon planifié. Ce sont les procès lancés pendant le développement et les démonstrations, dominés par quelques décisions répétées (voir le tableau profil × décision). Les taux décrivent ces procès, pas le comportement du modèle sur toutes les décisions possibles. Le plan de procès, plus bas, est un petit échantillon planifié : la même décision jugée pour chaque profil.

## En bref

- **Budget de 8 appels respecté** : 218/218 (100,0 % ; IC 95 % : 98,3 % à 100,0 %) ; refus pour budget dépassé : 0. Appels demandés par procès : min. 4, médiane 6, max. 8.
- **Simulation obligatoire demandée par le modèle lui-même** : 218/218 (100,0 % ; IC 95 % : 98,3 % à 100,0 %) ; oubliée puis ajoutée d'office par Python : 0/218.
- **Appels refusés** : 65 sur 1269 appels demandés (détail plus bas).
- **Procureur** : 851 arguments proposés ; renvoyés par le Greffier : 117/851 (13,7 % ; IC 95 % : 11,6 % à 16,2 %) ; corrigés après renvoi : 112/117 (95,7 % ; IC 95 % : 90,4 % à 98,2 %) ; rejetés : 5.
- **Avocat** : 821 arguments proposés ; renvoyés par le Greffier : 35/821 (4,3 % ; IC 95 % : 3,1 % à 5,9 %) ; corrigés après renvoi : 34/35 (97,1 % ; IC 95 % : 85,5 % à 99,5 %) ; rejetés : 1.

## Les outils changent avec le Pacte et la décision

Part des procès où le modèle a obtenu au moins une pièce de chaque outil (appels refusés exclus ; pièces ajoutées d'office par Python exclues). « — » : jamais demandé.

### Par profil (Pacte)

| Profil | Procès | `simuler_portefeuille` | `indicateurs_actif` | `calculer_correlations` | `taille_max_compatible` | `consulter_jurisprudence` | `rechercher_documents` | `mesurer_liquidite` |
|---|---|---|---|---|---|---|---|---|
| robert | 138 | 138/138 (100,0 %) | 138/138 (100,0 %) | 53/138 (38,4 %) | 135/138 (97,8 %) | 129/138 (93,5 %) | — | 32/138 (23,2 %) |
| mateo | 45 | 45/45 (100,0 %) | 44/45 (97,8 %) | 23/45 (51,1 %) | 29/45 (64,4 %) | 39/45 (86,7 %) | 19/45 (42,2 %) | 5/45 (11,1 %) |
| amira | 33 | 33/33 (100,0 %) | 8/33 (24,2 %) | 33/33 (100,0 %) | 31/33 (93,9 %) | 30/33 (90,9 %) | — | 7/33 (21,2 %) |
| questionnaire | 2 | 2/2 (100,0 %) | 2/2 (100,0 %) | 1/2 (50,0 %) | 2/2 (100,0 %) | 2/2 (100,0 %) | — | — |

Demandés pour certains profils seulement : `rechercher_documents` (mateo) ; `mesurer_liquidite` (amira, mateo, robert).

### Par profil et par décision

| Profil · décision | Procès | `simuler_portefeuille` | `indicateurs_actif` | `calculer_correlations` | `taille_max_compatible` | `consulter_jurisprudence` | `rechercher_documents` | `mesurer_liquidite` |
|---|---|---|---|---|---|---|---|---|
| robert · position TSLA | 124 | 124/124 (100,0 %) | 124/124 (100,0 %) | 43/124 (34,7 %) | 124/124 (100,0 %) | 121/124 (97,6 %) | — | 28/124 (22,6 %) |
| amira · réallocation BTC-USD, ETH-USD, NVDA, QQQ | 24 | 24/24 (100,0 %) | — | 24/24 (100,0 %) | 24/24 (100,0 %) | 24/24 (100,0 %) | — | 7/24 (29,2 %) |
| mateo · position XOM | 19 | 19/19 (100,0 %) | 19/19 (100,0 %) | 1/19 (5,3 %) | 7/19 (36,8 %) | 18/19 (94,7 %) | 19/19 (100,0 %) | — |
| mateo · position NVDA | 10 | 10/10 (100,0 %) | 10/10 (100,0 %) | 10/10 (100,0 %) | 9/10 (90,0 %) | 8/10 (80,0 %) | — | — |
| mateo · position TSLA | 8 | 8/8 (100,0 %) | 8/8 (100,0 %) | 4/8 (50,0 %) | 8/8 (100,0 %) | 8/8 (100,0 %) | — | 2/8 (25,0 %) |
| robert · position NVDA | 4 | 4/4 (100,0 %) | 4/4 (100,0 %) | 2/4 (50,0 %) | 4/4 (100,0 %) | 4/4 (100,0 %) | — | — |
| robert · position XOM | 4 | 4/4 (100,0 %) | 4/4 (100,0 %) | 4/4 (100,0 %) | 3/4 (75,0 %) | — | — | 1/4 (25,0 %) |
| mateo · réallocation ETH-USD, QQQ | 3 | 3/3 (100,0 %) | 3/3 (100,0 %) | 3/3 (100,0 %) | 3/3 (100,0 %) | 3/3 (100,0 %) | — | 1/3 (33,3 %) |
| amira · position TSLA | 2 | 2/2 (100,0 %) | 2/2 (100,0 %) | 2/2 (100,0 %) | 2/2 (100,0 %) | 2/2 (100,0 %) | — | — |
| amira · position XOM | 2 | 2/2 (100,0 %) | 2/2 (100,0 %) | 2/2 (100,0 %) | — | — | — | — |
| mateo · réallocation BTC-USD, ETH-USD, NVDA, QQQ | 2 | 2/2 (100,0 %) | 1/2 (50,0 %) | 2/2 (100,0 %) | 2/2 (100,0 %) | 2/2 (100,0 %) | — | 2/2 (100,0 %) |
| robert · réallocation BTC-USD, ETH-USD, NVDA, QQQ | 2 | 2/2 (100,0 %) | 2/2 (100,0 %) | 2/2 (100,0 %) | 2/2 (100,0 %) | 2/2 (100,0 %) | — | 2/2 (100,0 %) |
| amira · position SHOP.TO | 1 | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | — | — |
| amira · réallocation BTC-USD, ETH-USD, NVDA | 1 | 1/1 (100,0 %) | — | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | — | — |
| amira · réallocation BTC-USD, ETH-USD, NVDA, QQQ, SHOP.TO | 1 | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | — | — | — |
| amira · réallocation NVDA, QQQ | 1 | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | — | — |
| amira · réallocation QQQ, SHOP.TO | 1 | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | — | — |
| mateo · position AAPL | 1 | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | — | — | — | — |
| mateo · position AMZN | 1 | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | — | — | — | — |
| mateo · position PG | 1 | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | — | — | — | — |
| questionnaire · position NVDA | 1 | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | — | — |
| questionnaire · position TSLA | 1 | 1/1 (100,0 %) | 1/1 (100,0 %) | — | 1/1 (100,0 %) | 1/1 (100,0 %) | — | — |
| robert · position AMZN | 1 | 1/1 (100,0 %) | 1/1 (100,0 %) | — | 1/1 (100,0 %) | 1/1 (100,0 %) | — | — |
| robert · position BTC-USD | 1 | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | — | — |
| robert · position ESGV | 1 | 1/1 (100,0 %) | 1/1 (100,0 %) | 1/1 (100,0 %) | — | — | — | — |
| robert · position ZST.TO | 1 | 1/1 (100,0 %) | 1/1 (100,0 %) | — | — | — | — | 1/1 (100,0 %) |

## Plan de procès : même décision, profils différents

Échantillon planifié, en plus des procès archivés : chaque décision est jugée pour chaque profil, deux fois, par la Lambda déployée (POST /tribunal, Bedrock). Il montre si les outils choisis par l'orchestrateur changent avec le Pacte à décision égale, et s'ils restent stables d'une répétition à l'autre. Plan : `validation/jeux/plan_proces.json` ; tenu par `python -m validation.plan_proces`. Coût estimé avant de le tenir : environ 0,17 $ par procès au plus (jetons Bedrock mesurés dans CloudWatch le 2026-11-14 et le 2026-11-15, rapportés aux procès archivés : 51 000 jetons d'entrée et 7 000 de sortie au plus, au tarif Sonnet 5.5 de 2 $ et 10 $ par million de jetons), soit environ 3 $ pour 18 procès. Coût mesuré, ajouté après le plan : de 22 h 09 à 22 h 26 UTC le 2026-11-15, CloudWatch compte 116 appels Bedrock (profil global.anthropic.claude-sonnet-5-5), 872 730 jetons d'entrée et 118 202 de sortie, soit environ 2,93 $ au tarif Sonnet 5.5 (0,16 $ par procès, 6,4 appels Bedrock par procès, tours de l'orchestrateur compris). Borne haute : un appel d'un coéquipier dans cette fenêtre serait compté aussi.

18 procès sur 18 lus ; envois en échec : 0.

| Décision | Profil | Outils, répétition 1 | Outils, répétition 2 | Mêmes outils | Durée (s) |
|---|---|---|---|---|---|
| Je veux mettre 30 % de mon portefeuille en Tesla (TSLA) | robert | `simuler_portefeuille`, `indicateurs_actif`, `taille_max_compatible`, `consulter_jurisprudence`, `mesurer_liquidite` | `simuler_portefeuille`, `indicateurs_actif`, `taille_max_compatible`, `consulter_jurisprudence`, `mesurer_liquidite` | oui | 32,2 ; 32,6 |
| Je veux mettre 30 % de mon portefeuille en Tesla (TSLA) | amira | `simuler_portefeuille`, `indicateurs_actif`, `calculer_correlations`, `taille_max_compatible`, `consulter_jurisprudence` | `simuler_portefeuille`, `indicateurs_actif`, `calculer_correlations`, `taille_max_compatible`, `consulter_jurisprudence` | oui | 63,7 ; 47,3 |
| Je veux mettre 30 % de mon portefeuille en Tesla (TSLA) | mateo | `simuler_portefeuille`, `indicateurs_actif`, `taille_max_compatible`, `consulter_jurisprudence`, `mesurer_liquidite` | `simuler_portefeuille`, `indicateurs_actif`, `taille_max_compatible`, `consulter_jurisprudence`, `mesurer_liquidite` | oui | 61,1 ; 44,5 |
| Je veux tout réallouer vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 % | robert | `simuler_portefeuille`, `indicateurs_actif`, `calculer_correlations`, `taille_max_compatible`, `consulter_jurisprudence`, `mesurer_liquidite` | `simuler_portefeuille`, `indicateurs_actif`, `calculer_correlations`, `taille_max_compatible`, `consulter_jurisprudence`, `mesurer_liquidite` | oui | 57,5 ; 44,5 |
| Je veux tout réallouer vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 % | amira | `simuler_portefeuille`, `calculer_correlations`, `taille_max_compatible`, `consulter_jurisprudence`, `mesurer_liquidite` | `simuler_portefeuille`, `calculer_correlations`, `taille_max_compatible`, `consulter_jurisprudence` | non | 41,2 ; 39,7 |
| Je veux tout réallouer vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 % | mateo | `simuler_portefeuille`, `indicateurs_actif`, `calculer_correlations`, `taille_max_compatible`, `consulter_jurisprudence`, `mesurer_liquidite` | `simuler_portefeuille`, `calculer_correlations`, `taille_max_compatible`, `consulter_jurisprudence`, `mesurer_liquidite` | non | 56,9 ; 57,4 |
| Je veux mettre 10 % de mon portefeuille en Exxon Mobil (XOM) | robert | `simuler_portefeuille`, `indicateurs_actif`, `calculer_correlations`, `taille_max_compatible` | `simuler_portefeuille`, `indicateurs_actif`, `calculer_correlations`, `taille_max_compatible`, `mesurer_liquidite` | non | 54,8 ; 44,3 |
| Je veux mettre 10 % de mon portefeuille en Exxon Mobil (XOM) | amira | `simuler_portefeuille`, `indicateurs_actif`, `calculer_correlations` | `simuler_portefeuille`, `indicateurs_actif`, `calculer_correlations` | oui | 61,9 ; 44,2 |
| Je veux mettre 10 % de mon portefeuille en Exxon Mobil (XOM) | mateo | `simuler_portefeuille`, `indicateurs_actif`, `consulter_jurisprudence`, `rechercher_documents` | `simuler_portefeuille`, `indicateurs_actif`, `consulter_jurisprudence`, `rechercher_documents` | oui | 41,2 ; 44,6 |

- Mêmes outils d'une répétition à l'autre : 6/9 (66,7 % ; IC 95 % : 35,4 % à 87,9 %).
- Durée d'un procès, mesurée côté client (envoi → contrat) : min. 32,2, médiane 44,5, max. 63,7 s.
- Ces procès sont aussi comptés dans les tableaux ci-dessus, avec les procès archivés.

## Garde-fous de l'orchestrateur

- Appels exécutés : 1204 ; refusés : 65.
- Pièces ajoutées d'office par Python : `composition_fnb` 13, `points_de_bascule` 164. `points_de_bascule` est ajoutée dès qu'une règle calculable est en violation (#61), `composition_fnb` quand un plafond porte sur une catégorie lue par transparence (#116).
- Procès avec Pacte vécu (étape `calibrage`) : 28/218.
- Contre-interrogatoire : 8 questions ; budget de 4 appels respecté : 8/8.

### Appels refusés, par motif

| Motif | Appels |
|---|---|
| Aucun document sur <titre> pour le critère « controverse_esg_importante » : source manquante, le critère reste à vérifier | 62 |
| La raison doit faire au plus 160 caractères | 2 |
| Aucun document sur <titre> pour le critère « methodologie_fonds_esg » : source manquante, le critère reste à vérifier | 1 |

## Le débat

Un argument renvoyé l'est une fois à son agent avec le motif exact (`REFERENCE_DU_PROJET.md`, sections 4 ter et 4 quater) ; s'il échoue encore, il va dans `arguments_rejetes`.

| Côté | Proposés | Renvoyés | Corrigés après renvoi | Rejetés | Affichés | Motifs des renvois |
|---|---|---|---|---|---|---|
| Procureur | 851 | 117/851 (13,7 % ; IC 95 % : 11,6 % à 16,2 %) | 112/117 (95,7 % ; IC 95 % : 90,4 % à 98,2 %) | 5 | 854 | chiffres 117 |
| Avocat | 821 | 35/821 (4,3 % ; IC 95 % : 3,1 % à 5,9 %) | 34/35 (97,1 % ; IC 95 % : 85,5 % à 99,5 %) | 1 | 828 | chiffres 35 |

## Appels Bedrock et durée

- Appels Bedrock visibles dans la trace (Agent Profil, Procureur, Avocat et leurs relances) : min. 3, médiane 4, max. 7 par procès, 822 en tout.
- Non mesurables ici : les tours de conversation de l'orchestrateur (la trace garde les appels d'outils, pas les tours Bedrock, et un tour peut demander plusieurs outils) et les jetons consommés. La trace archivée ne contient ni horodatage ni compteur de jetons : la durée n'est mesurée que pour les procès du plan, côté client.

## Méthode

- Un appel « demandé par le modèle » est une étape `orchestrateur` de la trace dont la raison ne commence pas par « Pièce obligatoire ajoutée d'office » ; les refus en font partie, car ils comptent dans le budget.
- Simulation obligatoire : `simuler_portefeuille` sur la période complète, réussie.
- Débat : arguments proposés = sortie du premier appel Bedrock de chaque côté ; renvoyés = étapes `bedrock_correction` ; corrigés = renvoyés moins rejetés.
- Intervalles : Wilson à 95 % (`validation.evaluation.intervalle_wilson`).

<details><summary>Procès lus</summary>

- `2026-11-14-052f0a1f12e6` (S3) : robert, 30 % en TSLA
- `2026-11-14-0d0adc2c01bf` (S3) : amira, 100 % réalloué vers BTC-USD 30 %, ETH-USD 20 %, NVDA 20 %, QQQ 20 % et SHOP.TO 10 %
- `2026-11-14-51c84bd19c16` (S3) : mateo, 10 % en XOM
- `2026-11-14-a323f14f1d45` (S3) : robert, 30 % en TSLA
- `2026-11-15-01e174599335` (S3) : robert, 30 % en TSLA
- `2026-11-15-01f7f56cc313` (S3) : mateo, 10 % en NVDA
- `2026-11-15-032ec3367b19` (S3, interface) : robert, 25 % en TSLA
- `2026-11-15-04ad0146615f` (S3) : amira, 30 % en TSLA
- `2026-11-15-0678e8c05ecf` (S3) : robert, 30 % en TSLA
- `2026-11-15-084a901cdff8` (S3) : robert, 30 % en TSLA
- `2026-11-15-086e627bf4bd` (S3) : robert, 30 % en TSLA
- `2026-11-15-09b2fa5995f4` (S3) : robert, 30 % en TSLA
- `2026-11-15-0afe216146e2` (S3) : robert, 30 % en TSLA
- `2026-11-15-0b3c6bb6c893` (S3) : robert, 12 % en TSLA
- `2026-11-15-0fdb528f521d` (S3) : robert, 10 % en NVDA
- `2026-11-15-1257db85803b` (S3) : robert, 30 % en TSLA
- `2026-11-15-13325b58d2b9` (S3) : robert, 30 % en TSLA
- `2026-11-15-140a7f7dc9cf` (S3) : investisseur_22c8053eb316, 17 % en NVDA
- `2026-11-15-1965ff1e9e48` (S3) : mateo, 30 % en TSLA
- `2026-11-15-197e95e16d83` (S3) : robert, 40 % en ZST.TO
- `2026-11-15-1b59a098a64c` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-1dd88ba617d1` (S3) : robert, 30 % en TSLA
- `2026-11-15-1e35809282d3` (S3) : robert, 30 % en TSLA
- `2026-11-15-1e7b912cbaf9` (S3) : robert, 30 % en TSLA
- `2026-11-15-1f58fc9dfbf0` (S3) : robert, 30 % en TSLA
- `2026-11-15-1f822476623a` (S3) : robert, 12 % en TSLA
- `2026-11-15-201192346556` (S3) : robert, 30 % en TSLA
- `2026-11-15-203a6427776c` (S3) : robert, 25 % en TSLA
- `2026-11-15-20b5513fd69c` (S3) : mateo, 100 % réalloué vers QQQ 50 % et ETH-USD 50 %
- `2026-11-15-22aa10c7edac` (S3) : robert, 30 % en TSLA
- `2026-11-15-27349f8e56c6` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-284531dfdba4` (S3) : robert, 30 % en TSLA
- `2026-11-15-29219c7251d9` (S3) : robert, 30 % en TSLA
- `2026-11-15-293e756c8c74` (S3) : amira, 10 % en XOM
- `2026-11-15-2a7b5ce951aa` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-2b1775e64696` (S3) : robert, 10 % en BTC-USD
- `2026-11-15-2b79c4d7de2b` (S3) : mateo, 27 % en TSLA
- `2026-11-15-2f397d8ab470` (S3) : robert, 30 % en TSLA
- `2026-11-15-2f9e4a550bcc` (S3) : mateo, 3 % en NVDA
- `2026-11-15-2fc5e3a9dba5` (S3) : investisseur_13fdf2a7a62d, 30 % en TSLA
- `2026-11-15-30993c3a1ebf` (S3, interface) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-3186de284847` (S3) : robert, 12 % en TSLA
- `2026-11-15-32fef925cbc9` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-344e1013cdc1` (S3) : mateo, 10 % en TSLA
- `2026-11-15-3744915171c2` (S3) : robert, 10 % en NVDA
- `2026-11-15-374a62d31558` (S3) : mateo, 10 % en XOM
- `2026-11-15-378fa50c5752` (S3) : mateo, 10 % en NVDA
- `2026-11-15-388cb2bcc830` (S3) : robert, 30 % en TSLA
- `2026-11-15-395e2efcc54d` (S3) : robert, 30 % en TSLA
- `2026-11-15-39a6b77883c7` (S3) : mateo, 10 % en XOM
- `2026-11-15-3a3d049e2179` (S3) : robert, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-3a4e5079009f` (S3) : mateo, 100 % réalloué vers QQQ 50 % et ETH-USD 50 %
- `2026-11-15-3b72df224c77` (S3) : mateo, 10 % en XOM
- `2026-11-15-3c3e303149d8` (S3) : mateo, 30 % en TSLA
- `2026-11-15-3da0fd68f5e4` (S3, interface) : robert, 30 % en TSLA
- `2026-11-15-40dc9b8189af` (S3) : robert, 30 % en TSLA
- `2026-11-15-41031d7304bc` (S3) : mateo, 28 % en NVDA
- `2026-11-15-4115de24169d` (S3) : robert, 10 % en XOM
- `2026-11-15-4165e5f24166` (S3) : robert, 30 % en TSLA
- `2026-11-15-41dd523df266` (S3) : robert, 12 % en TSLA
- `2026-11-15-42e95279def3` (S3) : mateo, 10 % en XOM
- `2026-11-15-449f913437d8` (S3) : robert, 25 % en TSLA
- `2026-11-15-44b157725146` (S3) : robert, 30 % en TSLA
- `2026-11-15-45a43b09b1f3` (S3) : mateo, 18 % en NVDA
- `2026-11-15-45ea287afecf` (S3) : robert, 30 % en TSLA
- `2026-11-15-46840c1eb51b` (S3) : robert, 30 % en TSLA
- `2026-11-15-46e0edfd53b7` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-47365d1ebfcd` (S3) : robert, 12 % en TSLA
- `2026-11-15-4d25fab26751` (S3) : robert, 25 % en TSLA
- `2026-11-15-4de42aa92551` (S3) : robert, 30 % en TSLA
- `2026-11-15-4f3a7e924c33` (S3) : robert, 30 % en TSLA
- `2026-11-15-537f2b8e2d49` (S3, interface) : amira, 100 % réalloué vers QQQ 50 % et NVDA 50 %
- `2026-11-15-55016d988f16` (S3) : robert, 12 % en TSLA
- `2026-11-15-582fdb9011be` (S3) : robert, 30 % en TSLA
- `2026-11-15-58fbcefc6629` (S3) : robert, 30 % en TSLA
- `2026-11-15-5944335b5a5c` (S3) : robert, 25 % en TSLA
- `2026-11-15-5a8b7e8d54e0` (S3) : robert, 30 % en TSLA
- `2026-11-15-5ba5343b2165` (S3, interface) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-5d805fa5ce01` (S3) : robert, 30 % en TSLA
- `2026-11-15-5dac4e82f963` (S3) : mateo, 10 % en TSLA
- `2026-11-15-5e63d614ecf4` (S3) : robert, 30 % en TSLA
- `2026-11-15-604e7f53e9ca` (S3) : robert, 30 % en TSLA
- `2026-11-15-6084a70f6dee` (S3) : robert, 12 % en TSLA
- `2026-11-15-62c7cce7e38b` (S3) : robert, 30 % en TSLA
- `2026-11-15-62d58dbc4649` (S3) : mateo, 10 % en AAPL
- `2026-11-15-648546b5401b` (S3) : robert, 30 % en TSLA
- `2026-11-15-651ad5c7f489` (S3) : mateo, 10 % en XOM
- `2026-11-15-6773e89bd739` (S3) : robert, 30 % en TSLA
- `2026-11-15-68e6f1533066` (S3) : mateo, 10 % en XOM
- `2026-11-15-6a1ec1fd4960` (S3) : robert, 30 % en TSLA
- `2026-11-15-6a3e7e0d18e0` (S3) : robert, 30 % en TSLA
- `2026-11-15-6aa9abc6fb95` (S3) : robert, 30 % en TSLA
- `2026-11-15-6cbe9f2a8b37` (S3) : robert, 12 % en TSLA
- `2026-11-15-6d8845d00f9f` (S3) : mateo, 10 % en XOM
- `2026-11-15-6e41db2c6933` (S3) : robert, 12 % en TSLA
- `2026-11-15-6e4909122c29` (S3) : robert, 30 % en TSLA
- `2026-11-15-6f16a95962c3` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-705847d0132b` (S3) : amira, 100 % réalloué vers ETH-USD 40 %, NVDA 30 % et BTC-USD 30 %
- `2026-11-15-7063b5a644e5` (S3) : robert, 30 % en TSLA
- `2026-11-15-728fbb7a628e` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-741f038b00f1` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-768c999040c2` (S3) : robert, 30 % en TSLA
- `2026-11-15-78210ebf41ab` (S3) : mateo, 10 % en XOM
- `2026-11-15-78308b3b8a87` (S3) : robert, 30 % en TSLA
- `2026-11-15-797511c5aa15` (S3) : robert, 30 % en TSLA
- `2026-11-15-7a3ced437852` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-7d53592d84da` (S3) : mateo, 10 % en PG
- `2026-11-15-7f7aa38e02dc` (S3) : robert, 30 % en TSLA
- `2026-11-15-7fa3d460d3d9` (S3) : robert, 30 % en TSLA
- `2026-11-15-8171e1a8331f` (S3) : robert, 12 % en TSLA
- `2026-11-15-838edc06636a` (S3) : mateo, 10 % en NVDA
- `2026-11-15-8515ba8de493` (S3) : robert, 30 % en TSLA
- `2026-11-15-8675e97ab622` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-8aee71b708b0` (S3) : robert, 12 % en TSLA
- `2026-11-15-8b17e77d1389` (S3) : robert, 30 % en TSLA
- `2026-11-15-8eca78d5fea0` (S3) : robert, 12 % en TSLA
- `2026-11-15-903fac254ef1` (S3) : amira, 10 % en SHOP.TO
- `2026-11-15-93121ce521d8` (S3) : robert, 10 % en XOM
- `2026-11-15-936f0f5659e5` (S3) : robert, 30 % en TSLA
- `2026-11-15-95f3d7392461` (S3) : robert, 12 % en TSLA
- `2026-11-15-97661df6ea3a` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-97eb693fa981` (S3) : robert, 30 % en TSLA
- `2026-11-15-97fe1973acab` (S3) : robert, 30 % en TSLA
- `2026-11-15-9901fb12277b` (S3) : mateo, 10 % en TSLA
- `2026-11-15-9c273b4e1dab` (S3) : robert, 30 % en TSLA
- `2026-11-15-9ef77e91e564` (S3) : robert, 30 % en TSLA
- `2026-11-15-a09c5b03ff9d` (S3) : mateo, 10 % en TSLA
- `2026-11-15-a0b657de74e4` (S3) : robert, 12 % en TSLA
- `2026-11-15-a0faa9d01cfd` (S3) : robert, 30 % en TSLA
- `2026-11-15-a25802fb5604` (S3) : robert, 30 % en TSLA
- `2026-11-15-a27b42997c6c` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-a346a21a858f` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-a4dd947162d5` (S3) : robert, 30 % en TSLA
- `2026-11-15-a567d2f00fda` (S3) : robert, 30 % en TSLA
- `2026-11-15-a6fbcac9fa9a` (S3) : robert, 12 % en TSLA
- `2026-11-15-a77ec687ad53` (S3) : robert, 30 % en TSLA
- `2026-11-15-aac185ff8df7` (S3) : robert, 30 % en TSLA
- `2026-11-15-ab22b023ca6c` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-ac60cbdafbad` (S3) : amira, 10 % en XOM
- `2026-11-15-ac6781b7cec8` (S3) : robert, 12 % en TSLA
- `2026-11-15-ad682d0b7caf` (S3) : mateo, 29 % en NVDA
- `2026-11-15-ae15683a63ec` (S3) : robert, 30 % en TSLA
- `2026-11-15-afc03f45c6c1` (S3) : robert, 30 % en TSLA
- `2026-11-15-b04a4cbd233e` (S3, interface) : mateo, 10 % en XOM
- `2026-11-15-b195b3e20530` (S3) : robert, 12 % en TSLA
- `2026-11-15-b1ab8fd948b8` (S3) : robert, 10 % en XOM
- `2026-11-15-b41c6410bc1a` (S3) : robert, 12 % en TSLA
- `2026-11-15-b646dd9306a0` (S3) : robert, 30 % en TSLA
- `2026-11-15-b6795c03a385` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-b8a8e17f796b` (S3) : mateo, 10 % en NVDA
- `2026-11-15-beccd3378b0c` (S3) : robert, 12 % en TSLA
- `2026-11-15-bf35f3959b58` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-c00b812adab5` (S3) : mateo, 18 % en XOM
- `2026-11-15-c0230b4fd6cb` (S3) : robert, 30 % en TSLA
- `2026-11-15-c1600201b123` (S3) : robert, 25 % en TSLA
- `2026-11-15-c39eeacb2366` (S3) : robert, 30 % en TSLA
- `2026-11-15-c58472b7bee8` (S3) : mateo, 100 % réalloué vers QQQ 50 % et ETH-USD 50 %
- `2026-11-15-c65e5186b6f9` (S3) : robert, 22 % en NVDA
- `2026-11-15-c6adf5094e76` (S3) : mateo, 10 % en XOM
- `2026-11-15-c76d3a1a36ac` (S3) : robert, 30 % en TSLA
- `2026-11-15-c7c4bcc1736b` (S3, interface) : mateo, 10 % en XOM
- `2026-11-15-c96a8185f784` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-cd9914bdb1af` (S3) : robert, 30 % en TSLA
- `2026-11-15-d06c4c8fd94c` (S3) : mateo, 27 % en TSLA
- `2026-11-15-d1ae47e7189a` (S3) : robert, 30 % en TSLA
- `2026-11-15-d2cbba0748d2` (S3) : robert, 50 % en AMZN
- `2026-11-15-d3bca0bad2c9` (S3) : robert, 30 % en TSLA
- `2026-11-15-d41d5e896349` (S3) : mateo, 10 % en NVDA
- `2026-11-15-d5ab7e027894` (S3) : robert, 10 % en NVDA
- `2026-11-15-d60e97d1cbf1` (S3) : robert, 30 % en TSLA
- `2026-11-15-d6a76adf6cd9` (S3) : robert, 30 % en TSLA
- `2026-11-15-d6b68c21715f` (S3) : mateo, 10 % en XOM
- `2026-11-15-d7092e52bf75` (S3) : robert, 12 % en TSLA
- `2026-11-15-dbb3730924fb` (S3) : robert, 12 % en TSLA
- `2026-11-15-dc79b28b2214` (S3) : robert, 12 % en TSLA
- `2026-11-15-dd0046c496e3` (S3) : robert, 25 % en TSLA
- `2026-11-15-dd412c702126` (S3) : mateo, 10 % en XOM
- `2026-11-15-dd5e2e1526e7` (S3) : robert, 30 % en TSLA
- `2026-11-15-ddc9d6954367` (S3) : mateo, 9 % en NVDA
- `2026-11-15-de8799e1b290` (S3) : amira, 100 % réalloué vers SHOP.TO 50 % et QQQ 50 %
- `2026-11-15-de97f8d1bd1b` (S3) : robert, 10 % en XOM
- `2026-11-15-dfa3739ea663` (S3) : robert, 30 % en TSLA
- `2026-11-15-dfad1e96d34e` (S3) : robert, 30 % en TSLA
- `2026-11-15-e07be49d4cdc` (S3) : robert, 12 % en TSLA
- `2026-11-15-e14c56d5ab29` (S3) : robert, 12 % en TSLA
- `2026-11-15-e17d8a2cb213` (S3) : robert, 12 % en TSLA
- `2026-11-15-e1cc019aed05` (S3) : robert, 12 % en TSLA
- `2026-11-15-e3800bd7a4b4` (S3) : amira, 30 % en TSLA
- `2026-11-15-e58fb632f023` (S3) : mateo, 10 % en XOM
- `2026-11-15-e79cef530bc9` (S3, interface) : robert, 30 % en TSLA
- `2026-11-15-eb26d0c1aab8` (S3) : mateo, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-ebbfea19b096` (S3) : robert, 12 % en TSLA
- `2026-11-15-ed26356d7b57` (S3) : robert, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-f26705c0c2f7` (S3) : robert, 15 % en ESGV
- `2026-11-15-f3561b9d0484` (S3) : robert, 30 % en TSLA
- `2026-11-15-f398c08b7b51` (S3) : robert, 30 % en TSLA
- `2026-11-15-f3fa97cb1d25` (S3) : robert, 30 % en TSLA
- `2026-11-15-f59548b2fdd9` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-f7793d9d088e` (S3) : robert, 12 % en TSLA
- `2026-11-15-f7bcfd08604d` (S3) : mateo, 9 % en AMZN
- `2026-11-15-f8f9eb150c08` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-facef9ea3176` (S3) : mateo, 10 % en XOM
- `2026-11-15-fb125d20a367` (S3) : robert, 30 % en TSLA
- `2026-11-15-fb4c22680f5f` (S3) : mateo, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-15-fb50c36b3abb` (S3) : robert, 30 % en TSLA
- `2026-11-15-fb56bb1dbaa1` (S3) : robert, 30 % en TSLA
- `2026-11-15-fcb6ce39f184` (S3, interface) : robert, 30 % en TSLA
- `2026-11-15-fe7e9832703a` (S3) : robert, 30 % en TSLA
- `2026-11-15-ff29917fdfd4` (S3) : robert, 30 % en TSLA
- `2026-11-15-ff6ca217d1de` (S3) : robert, 30 % en TSLA
- `2026-11-16-2e2faa67372b` (S3, interface) : robert, 30 % en TSLA
- `2026-11-16-2f205d08775f` (S3, interface) : mateo, 10 % en XOM
- `2026-11-16-4c1f1ca81fd9` (S3, interface) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-16-6563f5a1e2be` (S3, interface) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-16-9b710b346da7` (S3) : robert, 30 % en TSLA
- `2026-11-16-a1a71679be7a` (S3, interface) : mateo, 10 % en XOM
- `2026-11-16-bfd65308abc2` (S3) : amira, 100 % réalloué vers BTC-USD 25 %, ETH-USD 25 %, NVDA 25 % et QQQ 25 %
- `2026-11-16-dc4199dcaa79` (S3, interface) : robert, 30 % en TSLA

</details>
