# Guide complet du projet AlphaForge AI : le Tribunal des décisions d'investissement

Ce guide explique **tout le projet**, du « pourquoi » jusqu'au dernier dossier du code. Il est écrit pour être compris par n'importe qui : il commence sans aucun mot technique et descend petit à petit dans les détails.

**Comment le lire :**

| Vous êtes… | Lisez |
|---|---|
| Curieux, jury, nouveau dans l'équipe, pas technique | Parties **1 et 2** (15 minutes) |
| Vous voulez savoir où se trouve chaque chose | Ajoutez la partie **3** |
| Vous allez toucher au code | Tout, surtout les parties **4 et 5** |

Les mots techniques sont expliqués dans le **glossaire** (section 2.1) la première fois qu'ils servent vraiment.

> Simulation éducative. Aucune transaction réelle. Ceci n'est pas un conseil financier personnalisé.

---

# Partie 1 — Le projet, sans aucun mot technique

## 1.1 Le problème

Imaginez Robert, 59 ans. Il prend sa retraite dans 3 à 5 ans et il a toujours été prudent. Un soir, il voit Tesla monter en flèche et se dit : « Je mets 30 % de mes économies dedans. »

Ce genre de décision se prend souvent **à chaud** : sous le coup de l'émotion, de la peur de rater quelque chose, ou d'un article lu en vitesse. Et pourtant, Robert s'était fixé des règles quand il était calme, par exemple « je ne veux jamais perdre plus de 12 % ».

**Notre projet aide à confronter une décision prise à chaud aux règles qu'on s'était fixées à froid.**

## 1.2 L'idée : faire un procès à la décision

Au lieu de dire à Robert quoi faire (ce serait du conseil financier, et ce n'est pas notre rôle), le système **fait le procès de sa décision**. C'est Robert qui rend le verdict à la fin.

Chaque personnage du tribunal a un équivalent dans le projet :

| Au tribunal | Dans le projet | Qui le joue |
|---|---|---|
| La loi | Le **Pacte** : les règles que l'investisseur a lui-même écrites à l'avance (« jamais plus de −12 % ») | Un fichier |
| Les preuves | Les **pièces à conviction** (P1, P2…) : des calculs faits sur de vraies données de marché | Un programme de calcul |
| Le juge d'instruction | L'**Orchestrateur** : il décide quelles preuves rassembler | Une intelligence artificielle |
| Le procureur | Le **Procureur** : il argumente **contre** la décision, preuves à l'appui | Une intelligence artificielle |
| L'avocat | L'**Avocat** : il défend la décision, **honnêtement** | Une intelligence artificielle |
| Le greffier | Le **Greffier** : il vérifie que les règles du Pacte sont respectées, et que **chaque chiffre cité existe vraiment** dans une preuve | Un programme de calcul, sans intelligence artificielle |
| Le jury | **L'investisseur lui-même** : il maintient sa décision, la modifie, ou change son Pacte | Un humain |

## 1.3 La règle la plus importante : la machine qui calcule n'est pas celle qui parle

Les intelligences artificielles qui écrivent du texte peuvent se tromper, et même **inventer des chiffres** qui ont l'air vrais. C'est le plus grand danger en finance.

Le projet suit donc une règle stricte :

- **Les chiffres** sont tous calculés par un programme classique, sur de vraies données. Ce programme ne se trompe pas et donne toujours le même résultat.
- **L'intelligence artificielle** ne fait que lire ces chiffres et les expliquer en français.
- **Le Greffier relit tout** : si un argument cite un chiffre qui n'existe dans aucune preuve, l'argument est renvoyé une fois pour correction, puis **rejeté** s'il est encore faux.

C'est la promesse du projet : **aucun chiffre inventé ne passe**.

## 1.4 Un exemple raconté de bout en bout

Robert demande : « Je veux mettre 30 % de mon portefeuille en Tesla. »

1. Le système lit **son Pacte** : pire baisse tolérée −12 %, pas de crypto, préserver son capital, préférer des entreprises établies.
2. L'Orchestrateur décide de calculer, entre autres, ce qu'aurait donné son portefeuille **avec** Tesla sur les 5 dernières années.
3. Le calcul montre que sa pire chute serait passée de **−7,8 %** à **−29,0 %**. C'est bien au-delà de sa limite de −12 %.
4. Le système calcule aussi la **plus grande part de Tesla qui respecte son Pacte** : **9 %**.
5. Le **Procureur** dit : « Votre pire baisse passerait de −7,8 % à −29,0 %, au-delà du seuil de −12 % que vous avez signé. »
6. L'**Avocat** répond honnêtement : « Le rendement annuel aurait été de +12,0 % contre +9,3 %, et une version à 9 % respecte votre Pacte. »
7. Le **Greffier** vérifie chaque chiffre de ces phrases contre les preuves, et constate la violation de la règle de −12 %.
8. **Robert décide** : garder 30 %, descendre à 9 %, ou modifier son Pacte. Le système ne le bloque jamais : il archive simplement sa décision avec ses preuves.

Et si Robert revient plus tard avec une décision semblable, le système **s'en souvient** : « Le 15 novembre, vous aviez déjà maintenu une décision qui violait cette règle. » C'est la **jurisprudence** (voir le [guide de la jurisprudence](guide_jurisprudence.md)).

## 1.5 Trois profils de test, trois situations

Le système fonctionne pour **n'importe quel investisseur**. Pour le prouver, on le teste avec trois profils fictifs, chacun dans une situation différente :

| Profil (fictif) | Qui | La décision testée | Ce que le système doit montrer |
|---|---|---|---|
| **Robert**, 59 ans | Prudent, horizon de 3 à 5 ans | Mettre 30 % en Tesla | **Contester** une décision incohérente avec le profil, sans bloquer |
| **Amira**, 26 ans | Audacieuse, horizon de 15 ans et plus | Tout réallouer vers un panier crypto + technologie | Accepter du risque **sans tout accepter** : la diversification reste exigée (crypto ≤ 25 %, technologie + crypto ≤ 75 %) |
| **Mateo**, 41 ans | Équilibré, sensible aux critères ESG (environnement, social, gouvernance) | Ajouter 10 % d'ExxonMobil | Tenir compte de **valeurs** et pas seulement de chiffres : une controverse environnementale documentée |

Ajouter un quatrième profil ne demande **aucun code** : on écrit seulement un nouveau fichier de Pacte.

## 1.6 Ce que le système ne fait pas

- Il ne passe **aucun ordre réel** : tout est simulé.
- Il ne **recommande** rien : il instruit le dossier, l'humain décide.
- Il ne **prédit** pas l'avenir : toutes les preuves portent sur le passé (novembre 2021 à novembre 2026), et le passé ne garantit rien.

---

# Partie 2 — Comment ça marche, sans lire de code

## 2.1 Glossaire

| Mot | Ce que ça veut dire ici |
|---|---|
| **LLM** (grand modèle de langage) | Une intelligence artificielle qui lit et écrit du texte. Ici : Claude, d'Anthropic. |
| **Agent** | Un LLM à qui on donne un rôle précis (Procureur, Avocat…) et des règles. |
| **Python** | Le langage de programmation de tous les calculs et du Greffier. |
| **Outil** | Une fonction Python que l'Orchestrateur a le droit de demander (ex. : « simule ce portefeuille »). |
| **Pièce** (P1, P2…) | Le résultat d'un outil, numéroté, avec sa source et ses limites. Les agents n'ont le droit de citer que des pièces. |
| **Pacte** | Les règles de l'investisseur, écrites dans un fichier, vérifiables par le Greffier. |
| **Contrat JSON** | Le « rapport de procès » complet, dans un format fixe que l'interface sait lire. JSON est un format de texte structuré. |
| **Trace** | Le journal de chaque étape du procès : qui a fait quoi, avec quoi, et pourquoi. |
| **CSV** | Un tableau de données en texte (comme un fichier Excel simple). Les prix du marché sont dans des CSV. |
| **AWS** (Amazon Web Services) | Les services infonuagiques d'Amazon. Obligatoires pour le datathon. |
| **Amazon Bedrock** | Le service AWS qui donne accès au LLM. |
| **AWS Lambda** | Le service AWS qui exécute notre code Python quand on lui envoie une demande, sans serveur à gérer. |
| **Function URL** | L'adresse web de la Lambda, que l'interface appelle. |
| **Amazon S3** | Le service AWS de stockage de fichiers : nos données, les traces des procès et les verdicts. |
| **Interface** (ou *frontend*) | Le site web que l'utilisateur voit. Le nôtre s'appelle **Astrée**. |
| **Dépôt** (ou *repo*) | Le dossier du projet sur GitHub, avec tout son historique. |
| **Issue** | Une tâche à faire, numérotée sur GitHub (#14, #56…). |
| **PR** (*pull request*) | Une proposition de modification du code, relue avant d'être fusionnée dans la branche principale `main`. |
| **Test** | Un petit programme qui vérifie automatiquement qu'une fonction donne le bon résultat. |

## 2.2 La vue d'ensemble

```
   ┌──────────────────────────┐
   │  Interface web « Astrée » │   ce que voit l'utilisateur (dossier frontend/)
   └────────────┬─────────────┘
                │ « Fais le procès de : 30 % en Tesla, pour Robert »
                ▼
   ┌──────────────────────────┐
   │  Function URL (adresse)  │
   └────────────┬─────────────┘
                ▼
   ┌───────────────────────────────────────────────────────────┐
   │  AWS Lambda : notre code Python (dossiers pipeline/ etc.) │
   │                                                           │
   │   1. Agent Profil ──┐                                     │
   │   2. Orchestrateur ─┼──► Amazon Bedrock (le LLM Claude)   │
   │   3. Procureur ─────┤                                     │
   │      Avocat ────────┘                                     │
   │   4. Greffier (Python seul)                               │
   │                                                           │
   │   Les outils de calcul lisent les prix ──► Amazon S3      │
   └────────────┬──────────────────────────────────────────────┘
                │ le contrat JSON (le rapport du procès)
                ▼
   L'interface affiche le procès ; l'utilisateur rend son verdict,
   qui est archivé dans Amazon S3.
```

## 2.3 Un procès, étape par étape : qui fait quoi

| Étape | Qui | LLM ? | Ce qui se passe |
|---|---|---|---|
| 1. **Agent Profil** | `pipeline/agent_profil.py` | Oui | Charge le Pacte (pièce P1) et transforme la phrase de l'utilisateur en décision précise : quel titre, quelle taille, comment c'est financé. Si la phrase est ambiguë, il le signale. |
| 2. **Orchestrateur** | `pipeline/orchestrateur.py` | Oui | Choisit lui-même les outils à appeler (au plus 8 appels) et donne une raison courte, sans chiffre, pour chacun. Chaque résultat devient une pièce. Python ajoute d'office la simulation de la décision si le LLM l'a oubliée. |
| 3. **Procureur et Avocat** | `pipeline/debat.py` | Oui | Deux LLM, appelés en même temps, écrivent 2 à 4 arguments chacun, contre et pour, en citant les pièces. Ils n'ont accès à aucun outil. |
| 4. **Greffier** | `pipeline/greffier.py`, `pipeline/chiffres.py`, `pipeline/cadre_simulation.py` | **Non** | Contrôle chaque règle du Pacte (conforme, violation, à vérifier), puis chaque chiffre de chaque argument, et vérifie qu'aucun argument ne conseille une transaction ni ne promet l'avenir. Un argument faux est renvoyé une fois, puis rejeté. |
| 5. **Contrat** | `pipeline/tribunal.py` | Non | Assemble tout dans le contrat JSON. |
| 6. **Verdict** | L'utilisateur, dans l'interface | — | Maintenir, modifier ou ajuster le Pacte. Le choix est archivé. |

## 2.4 Les 7 outils de calcul

Les outils sont les seules sources de chiffres. Aucun n'utilise de LLM.

| # | Outil | En clair | Fichier |
|---|---|---|---|
| 1 | `indicateurs_actif` | Les chiffres clés d'un titre : rendement par an, volatilité, pire chute, résultat en 2022, temps pour s'en remettre | `pipeline/indicateurs.py` |
| 2 | `simuler_portefeuille` | Le portefeuille avant et après la décision, sur 5 ans ou en rejouant 2022 | `pipeline/simulation.py` |
| 3 | `calculer_correlations` | Est-ce que deux titres montent et baissent ensemble ? (ex. : Bitcoin et Ethereum) | `pipeline/correlations.py` |
| 4 | `taille_max_compatible` | La plus grande part du titre qui respecte le Pacte (ex. : 9 %) | `pipeline/taille_max.py` |
| — | `rechercher_documents` | Des documents publics sur les critères ESG (ex. : controverses d'ExxonMobil) | `pipeline/documents.py` |
| 5 | `verifier_pacte` | Le Pacte est-il respecté ? (réservé au Greffier) | `pipeline/greffier.py` |
| 6 | `verifier_chiffres` | Chaque chiffre cité existe-t-il dans une pièce citée ? (réservé au Greffier) | `pipeline/chiffres.py` |
| 7 | `consulter_jurisprudence` | Les verdicts passés du même profil | `pipeline/jurisprudence.py` |

## 2.5 Le Pacte : des règles que la machine peut vérifier

Chaque règle d'un Pacte a un **type**. Le Greffier sait vérifier chaque type :

| Type de règle | Exemple | Comment le Greffier la vérifie |
|---|---|---|
| `pire_baisse_max` | « Jamais plus de −12 % » | Compare la pire chute simulée au seuil |
| `plafond` | « Crypto : 25 % au plus », « Crypto : exclue » (plafond de 0 %) | Additionne la part des titres de ces catégories |
| `critere_documentaire` | « Pas de controverse ESG importante » | Cherche une pièce documentaire ; sans document, la règle reste « à vérifier » (rien n'est deviné) |
| `qualitative` | « Préserver mon capital » | Ne se mesure pas : toujours « à vérifier », c'est l'utilisateur qui juge |

Les catégories (`tech`, `crypto`) sont définies une seule fois pour tous les profils, dans `config/categories.json`.

## 2.6 L'interface « Astrée »

Le site web suit l'utilisateur en 5 écrans :

1. **Entrée** : choisir un profil.
2. **Portefeuille** : ses positions, ses chiffres clés et son Pacte.
3. **Décision** : choisir un titre et une taille avec un curseur. La zone compatible avec le Pacte est visible tout de suite.
4. **Tribunal** : la trace, les arguments du Procureur et de l'Avocat, les contrôles du Greffier et les pièces, qu'on peut ouvrir une par une.
5. **Verdict** : maintenir, modifier ou ajuster le Pacte.

L'interface a **deux modes** :

- **Mode démonstration** (par défaut) : elle rejoue des procès **réellement tenus** par le système et enregistrés (`frontend/src/data/proces/`). Elle n'en invente aucun : si la décision choisie n'a pas été enregistrée, l'écran le dit.
- **Mode direct** : elle appelle la Lambda pour un vrai procès. Il faut pour cela que la Function URL soit ouverte au navigateur (voir la partie 6).

Les chiffres des écrans Portefeuille et Décision (courbes, curseur) sont **calculés à l'avance par le même code Python que le Tribunal** (`scripts/build_ui_series.py`). L'interface affiche donc exactement les chiffres que le Tribunal citerait.

## 2.7 AWS : quoi, et pourquoi

AWS est **obligatoire** pour être admissible au datathon. On utilise peu de services, chacun pour une vraie raison :

| Service | Son rôle | Pourquoi lui |
|---|---|---|
| **Amazon Bedrock** | Le LLM des 4 agents | Le cœur agentique du projet |
| **AWS Lambda** | Exécute tout le procès en Python | Le même code qu'en local, aucun serveur à gérer |
| **Function URL** | L'adresse web de la Lambda | Un procès dure de 25 à 45 secondes ; l'alternative habituelle (API Gateway) coupe à 29 secondes |
| **Amazon S3** | Les données de marché, la trace de chaque procès, les verdicts | Chaque procès peut être relu, et les verdicts nourrissent la jurisprudence |
| **CloudWatch** | Les journaux de la Lambda | Comprendre une erreur |

Garde-fous de coût : 2 procès en même temps au maximum, une alerte de budget, et aucune clé AWS dans le code.

---

# Partie 3 — Visite du dépôt, dossier par dossier

## 3.1 Le plan général

```
Datathon2026/
├── CLAUDE.md               les règles du projet (la référence)
├── README.md               démarrage rapide et carte du dépôt
├── alphaforge_starter/     les données de marché fournies par le datathon
├── personas/               les profils et leurs Pactes (un fichier par profil)
├── config/                 les catégories (tech, crypto) communes à tous
├── donnees_externes/       les documents ESG ajoutés par l'équipe
├── pipeline/               ★ le cœur : le procès et ses outils (Python)
├── contrat/                le format du rapport de procès, et son vérificateur
├── deploiement/            tout ce qu'il faut pour mettre le code sur AWS
├── frontend/               l'interface web « Astrée »
├── scripts/                le calcul à l'avance des chiffres de l'interface
├── validation/             des scénarios pour tester le système sous tous les angles
├── tests/                  les tests automatiques du code Python
└── docs/                   la documentation (dont ce guide)
```

## 3.2 Les fichiers à la racine

| Fichier | Rôle |
|---|---|
| `CLAUDE.md` | **Les règles du projet** : le but, l'architecture, le format du contrat, les pièges des données. En cas de doute, c'est lui qui fait foi. |
| `README.md` | Comment démarrer, et la **carte du dépôt** : une ligne par fichier important. |
| `requirements.txt` | Les bibliothèques Python embarquées dans la Lambda. |
| `requirements-dev.txt` | Les bibliothèques Python du poste de travail (dont pandas, aux mêmes versions que sur AWS). |
| `pyproject.toml` | La configuration des tests. |
| `.env.example` | Le modèle du fichier `.env`, qui contient la configuration locale (région AWS, modèle). On le copie en `.env`, qui n'est jamais envoyé sur GitHub. |
| `.gitignore` | La liste des fichiers que Git doit ignorer (`.env`, `archives/`…). |
| `.github/pull_request_template.md` | Le modèle de description d'une PR. |
| `.claude/settings.json` | La configuration de l'assistant de code de l'équipe. |

## 3.3 `alphaforge_starter/` : les données de départ

Fournies par le datathon, du 2021-11-12 au 2026-11-12. On ne les modifie pas.

| Fichier | Contenu |
|---|---|
| `assets_universe.csv` | Les **31 titres** autorisés : actions canadiennes (`.TO`) et américaines, fonds indiciels, or, obligations, Bitcoin et Ethereum |
| `prices_daily.csv` | Le prix de chaque titre, chaque jour (on utilise `adj_close`, corrigé des dividendes et des fractionnements) |
| `fx_usdcad_daily.csv` | Le taux de change dollar américain / dollar canadien, chaque jour (Banque du Canada) |
| `macro_rates.csv` | Des taux et indicateurs économiques (Banque du Canada, FRED) |
| `corporate_actions.csv` | Dividendes et fractionnements, à titre d'information seulement |
| `sources_metadata.csv`, `README.md`, `data_quality_warnings.txt`, `build_dataset.py` | D'où viennent les données, leurs défauts connus, et le script qui les a produites |

**Pièges connus** (détaillés dans `CLAUDE.md`, section 6) : les prix sont en deux devises, la crypto se négocie aussi la fin de semaine, et l'univers a été choisi en 2026, ce qui fait paraître le passé plus beau qu'il n'était (biais du survivant).

## 3.4 `personas/`, `config/`, `donnees_externes/` : ce que le système lit

| Fichier | Contenu |
|---|---|
| `personas/robert.json`, `amira.json`, `mateo.json` | Un profil fictif : âge, risque, horizon, capital, portefeuille, décision de démonstration, et **son Pacte** (chaque règle avec son libellé et sa justification) |
| `personas/schema_pacte.json` | Le format obligatoire d'un fichier profil. Un profil mal écrit est refusé avec un message clair. |
| `config/categories.json` | Quels titres sont `tech` et lesquels sont `crypto` |
| `donnees_externes/documents_esg.json` | Trois documents publics sur les critères ESG, lus par l'équipe, avec source, date et limites (le jeu de départ ne contient aucune donnée ESG) |

## 3.5 `pipeline/` : le cœur du projet

Tout le procès est ici. Chaque fichier a une seule responsabilité.

**Les données**

| Fichier | Rôle |
|---|---|
| `donnees.py` | Lit les CSV (sur le disque ou dans S3), convertit tout en dollars canadiens et aligne les calendriers. Tous les outils passent par lui. |
| `univers.py` | La liste des 31 titres, sous une forme simple pour les agents. |
| `categories.py` | Dit si un titre est `tech`, `crypto`… Un titre inconnu n'est jamais classé au hasard. |
| `pacte.py` | Charge un fichier profil, vérifie qu'il est valide, et en fait la pièce P1. |

**Les outils** (voir la section 2.4) : `indicateurs.py`, `simulation.py`, `correlations.py`, `taille_max.py`, `documents.py`, `jurisprudence.py`.

**Les agents et le Greffier**

| Fichier | Rôle |
|---|---|
| `llm.py` | Le seul point de contact avec Amazon Bedrock. Tous les agents passent par lui (relances automatiques en cas de surcharge). |
| `agent_profil.py` | Étape 1 : de la phrase de l'utilisateur à une décision précise. |
| `orchestrateur.py` | Étape 2 : la boucle où le LLM choisit les outils, avec ses garde-fous (liste d'outils permis, budget de 8 appels, raison sans chiffre, simulation obligatoire). |
| `debat.py` | Étape 3 : le Procureur et l'Avocat, et la correction d'un argument refusé. |
| `greffier.py` | Étape 4 : une fonction par type de règle du Pacte. |
| `chiffres.py` | Étape 4 : le vérificateur de chiffres (gère les virgules françaises, les signes, les dates, les arrondis). |
| `tribunal.py` | Le chef d'orchestre : enchaîne les étapes et assemble le contrat. Fonction principale : `juger_decision`. |
| `__main__.py` | Permet de lancer un procès depuis le terminal : `python -m pipeline robert "…"`. |

## 3.6 `contrat/` : le format du rapport de procès

| Fichier | Rôle |
|---|---|
| `schema_sortie.json` | La forme exacte du contrat JSON : champs obligatoires, valeurs permises |
| `valider.py` | Vérifie un contrat : le schéma, plus les renvois entre champs (chaque pièce citée existe, chaque règle du Pacte a son contrôle…) |

Des exemples valides sont dans `docs/exemples/`. Ce format est **partagé avec l'équipe interface** : on ne le change jamais sans prévenir.

## 3.7 `deploiement/` : mettre le code sur AWS

| Fichier | Rôle |
|---|---|
| `lambda_tribunal.py` | La porte d'entrée sur AWS : deux routes, `/tribunal` (faire un procès, archivé dans `traces/`) et `/verdict` (archiver le verdict dans `verdicts/<profil>/`) |
| `construire_zip.py` | Prépare le paquet de code envoyé à la Lambda |
| `deployer.py` | Crée ou met à jour toute l'infrastructure AWS en une commande (S3, permissions, Lambda, adresse). On peut le relancer sans risque. |
| `tester_function_url.py` | Lance un vrai procès sur la Lambda depuis le terminal, et peut envoyer un verdict |
| `politique_iam_lambda.json` | Les permissions **minimales** de la Lambda : appeler le modèle, écrire ses journaux, lire et écrire dans son propre bucket |
| `README.md` | Tous les réglages vérifiés (version de Python, mémoire, délai) et les pièges rencontrés |

## 3.8 `frontend/` : l'interface « Astrée »

Écrite en React et TypeScript (des technologies web courantes). Son propre guide est dans `frontend/README.md`.

| Dossier | Rôle |
|---|---|
| `src/ecrans/` | Les 5 écrans : `Entree`, `Portefeuille`, `Decision`, `Tribunal`, `Verdict` |
| `src/components/` | Les morceaux réutilisés : gabarit de page, étiquettes, boutons, tiroir d'une pièce, graphiques |
| `src/api/` | Le lien avec le Tribunal : `tribunal.ts` (démonstration ou direct), `adaptateur.ts` (traduit le contrat pour les écrans), `contrat.ts` (le contrat en TypeScript) |
| `src/domaine/` | La logique d'affichage, testée : le Pacte, la décision, le verdict |
| `src/data/generated/` | Les chiffres calculés à l'avance par `scripts/build_ui_series.py` (une table par titre pour le curseur) |
| `src/data/proces/` | Les 3 procès réels enregistrés pour le mode démonstration |
| `src/lib/`, `src/state/`, `src/styles/` | Formats français des nombres, recherche, mémoire de l'écran, couleurs et polices de la maquette |
| `src/test/`, `e2e/` | Les tests de l'interface, et une vérification complète des parcours (accessibilité comprise) |

## 3.9 `scripts/`, `validation/`, `tests/`

| Dossier | Rôle |
|---|---|
| `scripts/build_ui_series.py` | Calcule à l'avance, avec le code du pipeline, tous les chiffres des écrans Portefeuille et Décision |
| `validation/` | Des scénarios de validation : la même décision pour plusieurs profils, des seuils modifiés, un profil inventé, la robustesse du Greffier… Résultats dans `docs/validation/resultats_scenarios.md`. Lancement : `python -m validation`. |
| `tests/` | **Un fichier de test par fichier du pipeline** (`test_donnees.py` ↔ `pipeline/donnees.py`). Ils tournent en quelques secondes, sans AWS. Ceux marqués `bedrock` font de vrais appels payants et ne tournent que si on le demande. |

## 3.10 `docs/` : la documentation

| Fichier | Pour quoi |
|---|---|
| `GUIDE_DU_PROJET.md` | Ce guide : tout le projet, pour tous les niveaux |
| `CHOIX_CONCEPTION.md` | **Pourquoi** chaque choix d'architecture (14 choix, et leurs limites) |
| `architecture.md` | Le schéma AWS détaillé, pour la documentation et la vidéo |
| `guide_jurisprudence.md` | La mémoire des verdicts, expliquée pas à pas |
| `journal/` | **Une fiche par issue** : ce qui a été construit, comment l'utiliser et le vérifier, les choix faits. Lues dans l'ordre, elles racontent la construction du projet. |
| `exemples/` | Des contrats JSON valides (Robert et Amira) |
| `maquette/` | Le lien vers la maquette Figma, le prototype et la spécification de l'interface |
| `validation/` | Les résultats des scénarios de validation |

---

# Partie 4 — Suivre une demande dans le code

Pour qui veut lire le code : voici le chemin exact d'une demande, fonction par fonction. Ouvrez les fichiers à côté.

```
Interface : POST /tribunal {"profil": "robert", "demande": "30 % en Tesla"}
│
└─ deploiement/lambda_tribunal.py · handler → _tribunal
   │
   └─ pipeline/tribunal.py · juger_decision                    le chef d'orchestre
      │
      ├─ 1. pipeline/agent_profil.py · lancer_agent_profil
      │      ├─ pipeline/pacte.py · charger_pacte               → pièce P1
      │      └─ pipeline/llm.py · appeler_llm                   → la décision structurée
      │
      ├─ 2. pipeline/orchestrateur.py · instruire_dossier
      │      ├─ outils_du_profil                                la liste des outils permis
      │      ├─ boucle : pipeline/llm.py · converser_avec_outils
      │      │     le LLM demande un outil → Python l'exécute → pièce P2, P3…
      │      └─ ajouter_simulation_obligatoire                   si le LLM l'a oubliée
      │
      ├─ pipeline/taille_max.py · rechercher_taille_max         toujours calculée (curseur)
      │
      ├─ 3. pipeline/debat.py · debattre                        Procureur ∥ Avocat
      │
      ├─ 4. pipeline/greffier.py · verifier_pacte               un contrôle par règle
      │     pipeline/chiffres.py · trier_arguments              chaque chiffre vérifié
      │        └─ si refusé : pipeline/debat.py · corriger_argument (une seule fois)
      │
      └─ le contrat JSON est assemblé
   │
   └─ archivé dans S3 (traces/<date>/<id>.json), renvoyé à l'interface
      avec l'identifiant du procès dans l'en-tête x-proces-id

Interface : POST /verdict {"id": "...", "verdict": "maintenu"}
└─ archivé dans S3 (verdicts/<profil>/<id>.json), relu plus tard par la jurisprudence
```

---

# Partie 5 — Travailler sur le projet

## 5.1 Les commandes utiles

Les commandes ci-dessous sont pour Linux et macOS. Les versions Windows (PowerShell) sont dans le `README.md` : remplacer `.venv/bin/python` par `.venv\Scripts\python`.

**Installer** (une fois) :

```bash
python3.14 -m venv .venv
```
```bash
.venv/bin/pip install -r requirements-dev.txt
```
```bash
cp .env.example .env
```

**Lancer les tests** (quelques secondes, sans AWS) :

```bash
.venv/bin/python -m pytest
```

**Faire un vrai procès en local** (appelle Bedrock, payant ; il faut d'abord `aws login`) :

```bash
.venv/bin/python -m pipeline robert "Je veux mettre 30 % de mon portefeuille en Tesla"
```

**Vérifier un contrat** :

```bash
.venv/bin/python -m contrat.valider docs/exemples/contrat_robert.json
```

**Lancer l'interface** (il faut Node 20 ou plus), puis ouvrir http://localhost:5173 :

```bash
cd frontend && npm install && npm run dev
```

**Déployer sur AWS** après une fusion dans `main` :

```bash
.venv/bin/python -X utf8 deploiement/deployer.py --sans-donnees
```

**Tester la Lambda déployée** (payant) :

```bash
.venv/bin/python -X utf8 deploiement/tester_function_url.py robert "Je veux mettre 30 % de mon portefeuille en Tesla"
```

## 5.2 La façon de travailler de l'équipe

```
 Issue sur GitHub (#N)          « quoi faire, et quand c'est fini »
   ▼
 Nouvelle branche               jamais de travail directement sur main
   ▼
 Code + tests                   chaque fonction de calcul est testée
   ▼
 Fiche du journal               docs/journal/NNN-titre.md, dans la même PR
 + carte du README              si un fichier important est ajouté
   ▼
 PR avec « Closes #N »          (ou « Avance #N » si l'issue n'est pas finie)
   ▼
 Relecture, puis fusion         GitHub ferme l'issue tout seul
   ▼
 Redéployer la Lambda           pour qu'AWS tourne avec le code de main
```

Deux règles d'équipe : aucune mention de l'assistant de code dans les commits ni les PR, et **chacun doit comprendre le code qu'il garde**.

## 5.3 « Je veux… » : par où commencer

| Je veux… | Ce qu'il faut faire |
|---|---|
| **Ajouter un profil** | Écrire `personas/<id>.json` (copier un profil existant). Aucun code. Puis, pour l'interface, régénérer ses chiffres depuis la racine : `.venv/bin/python -X utf8 scripts/build_ui_series.py` (sous Windows : `npm run series` dans `frontend/`). |
| **Changer un seuil du Pacte** | Modifier le fichier du profil, et la `justification` de la règle. |
| **Ajouter un type de règle** | Une fonction dans `pipeline/greffier.py`, une ligne dans le tableau de `CLAUDE.md` (section 3), et le schéma `personas/schema_pacte.json`. |
| **Ajouter un outil** | Un fichier dans `pipeline/` (sans LLM, avec ses tests), une entrée dans `outils_du_profil` (`pipeline/orchestrateur.py`), une ligne dans `CLAUDE.md` (section 4 bis). |
| **Changer le contrat JSON** | **Prévenir toute l'équipe d'abord.** Puis `contrat/schema_sortie.json`, `contrat/valider.py`, `docs/exemples/`, et `frontend/src/api/contrat.ts`. |
| **Changer ce que dit un agent** | Ses consignes : `pipeline/debat.py` (Procureur, Avocat), `pipeline/orchestrateur.py` (`CONSIGNES`), `pipeline/agent_profil.py`. |
| **Comprendre pourquoi une chose est ainsi** | `docs/CHOIX_CONCEPTION.md`, puis la fiche du journal indiquée dans la carte du `README.md`. |

---

# Partie 6 — Où en est le projet (15 novembre 2026)

**Ce qui fonctionne de bout en bout :**

- Les 3 cas généraux (décision incohérente, diversification, critères ESG), démontrés avec les 3 profils.
- Les 7 outils, le Greffier (Pacte et chiffres), l'Orchestrateur, le Procureur et l'Avocat.
- La jurisprudence (#56) : la mémoire des verdicts.
- Le déploiement AWS : Lambda, Bedrock, S3, Function URL, vérifiés avec de vrais procès.
- L'interface Astrée : en mode démonstration avec 3 procès réels enregistrés, ou en direct sur la Lambda (#14).

**Ce qui reste ouvert** (issues sur GitHub) :

| Issue | Sujet |
|---|---|
| #18 | Livrables : README final, documentation technique, vidéo, one pager |
| #55 | Contre-interrogatoire : poser une question libre au Tribunal |
| #57 | Export du procès-verbal (dossier de convenance) |
| #58 | Démo : montrer le Greffier qui rejette un chiffre inventé |
| #59, #61, #68, #69 | Améliorations proposées (scénarios, points de bascule, « Pacte vécu », « Trompez le Greffier ») |

La liste à jour est toujours sur GitHub, onglet *Issues*.

---

# Partie 7 — Les limites, honnêtement

- **Le passé ne prédit pas l'avenir.** Toutes les preuves portent sur une seule période de 5 ans.
- **Biais du survivant** : les 31 titres ont été choisis en 2026, parmi ceux qui existent encore.
- **La volatilité et la pire baisse ne sont que deux mesures du risque** parmi d'autres.
- **Les seuils des Pactes sont des hypothèses de l'équipe**, pas des recommandations réglementaires.
- **Le critère ESG dépend entièrement des documents ajoutés par l'équipe** : sans document, la règle reste « à vérifier ».
- **Les agents restent des LLM** : ils choisissent leurs outils et leurs arguments, donc deux procès identiques peuvent différer. Le Greffier garantit les chiffres, pas le choix des arguments.

---

# Partie 8 — Pour aller plus loin

| Pour… | Lire |
|---|---|
| Les règles complètes | `CLAUDE.md` |
| Le pourquoi de chaque choix | `docs/CHOIX_CONCEPTION.md` |
| L'architecture AWS en détail | `docs/architecture.md`, `deploiement/README.md` |
| L'histoire de chaque morceau | `docs/journal/` (une fiche par issue) |
| L'interface | `frontend/README.md`, `docs/maquette/spec_interface_astree.md` |
| La mémoire des verdicts | `docs/guide_jurisprudence.md` |
