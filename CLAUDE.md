# CLAUDE.md — Projet AlphaForge AI (Datathon PolyFinances 2026)

Ce fichier donne à Claude le contexte et les règles du projet. Toute l'équipe partage ce fichier via Git : si une règle change, modifiez-la ici et faites un commit.

## 1. But du projet

Nous construisons une **solution agentique auto-explicative** qui utilise des données financières publiques pour aider à la décision d'investissement selon le profil de l'investisseur. Tout se passe **en simulation**.

Le jury évalue surtout :
- **la démarche agentique** : des agents qui utilisent des données et des outils, avec des points de contrôle ;
- **l'auto-explicabilité** : chaque conclusion doit être reliée aux données, aux hypothèses, aux étapes observables et aux limites.

Une démonstration convaincante et des explications fidèles aux données comptent plus que la complexité ou le rendement passé.

### Grille d'évaluation (présentation officielle, diapo 10)

| Critère | Poids |
|---|---|
| Solution (pertinence, innovation, prototype) | 20 % |
| Agentique (architecture et explicabilité) | 20 % |
| Données (rigueur, validation, visualisation) | 20 % |
| AWS (qualité de l'intégration) | 15 % |
| Pitch (présentation, business, marketing) | 15 % |
| UX/UI | 10 % |

## 1 bis. ⚠️ AWS est OBLIGATOIRE (condition d'admissibilité)

Source : présentation officielle, diapo 7. **Sans intégration réelle d'AWS, le projet n'est pas admissible à l'évaluation finale.**

- AWS doit contribuer **réellement et de façon démontrable** au fonctionnement de la solution (pas juste héberger une page).
- Choisir peu de services, chacun **justifié**. Ne pas multiplier les services pour impressionner.
- Montrer le rôle d'AWS dans le flux (schéma d'architecture dans la doc et la vidéo).
- Bonnes pratiques : aucune clé AWS dans le code ni dans Git, permissions IAM minimales, surveiller les coûts.

Architecture AWS visée (simple) :
- **Amazon S3** : stocke les CSV de données et les traces d'exécution.
- **Amazon Bedrock** : fournit le LLM des agents (ex. : un modèle Claude via Bedrock). C'est le cœur agentique, donc la contribution la plus visible d'AWS.
- **AWS Lambda** : exécute le pipeline (outils Python + appels Bedrock).
- **Point d'accès** pour l'interface : **Lambda Function URL** (tranché dans #22). Il renvoie le JSON du contrat.

Toujours vérifier les consignes logistiques officielles (services permis, crédits, région).

**Pièges AWS connus**, réglés dans l'issue #22. Les paramètres exacts sont dans `deploiement/README.md` :
- **Délai** : API Gateway coupe la requête après environ 29 s, et un procès complet dure de 18 à 33 s (mesuré). Décision : **Lambda Function URL** (jusqu'à 15 min), avec le Procureur et l'Avocat appelés en parallèle.
- **Délai et mémoire de Lambda** : 3 s et 128 Mo par défaut, bien trop peu. Délai de 300 s, mémoire d'au moins 1024 Mo.
- **pandas et Python** : runtime **`python3.14`** (la version de l'équipe) et couche gérée **`AWSSDKPandas-Python314:12`** (pandas 3.1.0, numpy 2.5.4, pyarrow 24.0.0). Les mêmes versions sont épinglées dans `requirements-dev.txt`. boto3 est embarqué dans le zip : celui du runtime peut être trop ancien pour la sortie JSON structurée de Bedrock.
- **Bedrock** : région `us-east-1`, profil d'inférence `us.anthropic.claude-sonnet-5-5`, dans `BEDROCK_MODEL_ID`, avec des relances adaptatives (#7). Le profil répartit les appels sur us-east-1, us-east-2 et us-west-2 : le rôle IAM doit autoriser les trois (`deploiement/politique_iam_lambda.json`).
- **Coûts** : un point d'accès public déclenche des appels Bedrock payants. Concurrence réservée de 2 ; Function URL en `NONE` avec CORS limité à l'interface (`http://localhost:5173`, réglé par `deploiement/deployer.py`, #14) ; alerte de budget active (100 $ par mois) ; point d'accès coupé après le jury.

## 2. Règle d'or : Python calcule, le LLM explique

- **Tous les chiffres** (rendement, volatilité, pire baisse, corrélations, poids) sont calculés en **Python** à partir des CSV. Ces fonctions sont les « outils » des agents.
- Le **LLM** reçoit ces chiffres et sert seulement à raisonner sur le profil et à rédiger l'explication.
- **Le LLM n'invente jamais un chiffre ni une source.** Chaque nombre cité dans une explication doit exister dans la sortie d'un outil Python.
- Si une donnée manque, l'agent le **signale** au lieu de deviner.

## 3. Cas généraux et profils de test

Le système est conçu pour **n'importe quel investisseur**, pas pour trois personas codés en dur. Il doit gérer **trois cas généraux**. Les personas de l'énoncé servent de **profils de test** pour prouver que chaque cas fonctionne (l'énoncé les présente comme des « situations de référence pour concevoir et tester la solution »).

| Cas général | Ce que le système doit faire | Profil de test | Décision testée dans la démo |
|---|---|---|---|
| **1. Décision incohérente avec le profil** | **Contester** la décision avec des preuves, au lieu d'acquiescer, sans bloquer l'utilisateur | Prudent : Robert, 59 ans, risque faible à modéré, 3 à 5 ans | Ajouter 30 % de TSLA |
| **2. Profil tolérant au risque** | Accepter du risque **sans tout accepter** : faire respecter la diversification (plafonds par classe d'actifs ou par secteur) | Audacieux : Amira, 26 ans, risque élevé, 15 ans et plus | Tout réallouer vers un panier crypto-tech |
| **3. Préférences non financières** | Intégrer des critères **autres que le rendement et le risque** (ESG, exclusions, valeurs) | Équilibré ESG : Mateo, 41 ans, risque modéré, 8 à 12 ans | Ajouter 10 % de XOM |

### Le Pacte : un format générique

Chaque profil a un **Pacte** : ses règles, déclarées à l'avance, converties en contraintes vérifiables. Tous les Pactes suivent **le même format** (fichiers `personas/<nom>.json`), donc **ajouter un nouveau profil ne demande aucun code**. Le code ne doit jamais tester un nom de persona (`if persona == "robert"` est interdit) : il lit uniquement les règles du Pacte.

Les seuils sont des **hypothèses** de l'équipe, pas des recommandations réglementaires. Exception : la **pire baisse** peut être **mesurée** par le Pacte vécu (#68) : l'utilisateur revit de vrais jours de baisse, sans la suite, et répond « je reste » ou « je vends » ; le seuil devient la baisse réelle du dernier jour où il est resté (`pipeline/calibrage.py`, paramètres dans `config/calibrage.json`).

**Format d'un fichier profil** : `id`, `nom`, `etiquette` (`fictif`), `profil_risque`, `horizon_ans`, `capital_fictif_cad`, `portefeuille` (liste `ticker` + `poids`), `decision_demo`, `pacte` et, facultatif, `calibrage_demo` (réponses préenregistrées du Pacte vécu, étiquette `fictif`, pour une démo reproductible). Le `pacte` contient `date_signature` et une liste `regles`. Chaque règle a :
- `id` : identifiant unique, repris dans `controles[].regle` du contrat ;
- `type` : un des types du tableau ci-dessous ;
- les paramètres de son type ;
- `libelle` : texte affiché à l'utilisateur ;
- `justification` : pourquoi ce seuil (hypothèse de l'équipe ou citation de l'énoncé).

| `type` | Paramètres | Contrôle du Greffier |
|---|---|---|
| `pire_baisse_max` | `seuil` (ex. : `-0.12`) | `violation` si la pire baisse simulée après la décision est plus basse que le seuil |
| `plafond` | `categories` (liste), `max` | `violation` si la part totale des titres de ces catégories dépasse `max`. `max: 0` = exclusion |
| `critere_documentaire` | `critere` (ex. : `controverse_esg_importante`) | `violation` ou `conforme` selon une pièce `documentaire` ; `a_verifier` (« source manquante ») sans pièce |
| `qualitative` | aucun | toujours `a_verifier` : règle déclarée, non mesurable par calcul, à juger par l'utilisateur |

Les **catégories** (`tech`, `crypto`…) sont définies une seule fois, pour tous les profils, dans `config/categories.json`, à partir des champs `asset_class` et `sector` de `assets_universe.csv` (plus des ajouts justifiés). Un titre absent de l'univers n'est jamais classé au hasard : le contrôle rend `a_verifier`.

Ajouter un profil = un fichier JSON. Ajouter un type de règle = une fonction dans le Greffier + une ligne dans ce tableau.

| Profil de test | Règles du Pacte |
|---|---|
| Prudent (Robert) | Pire baisse ≥ −12 % ; crypto exclue ; qualitatives : préserver le capital, entreprises établies |
| Audacieux (Amira) | Pire baisse ≥ −45 % ; crypto ≤ 25 % ; tech + crypto ≤ 75 % (« pas exclusivement tech ») |
| Équilibré ESG (Mateo) | Pire baisse ≥ −20 % ; crypto exclue (« pas de spéculation ») ; controverses ESG importantes exclues (source externe) ; qualitative : équilibre croissance et stabilité |

## 4. Architecture visée : le Tribunal (simple et vérifiable)

L'utilisateur arrive avec **sa propre décision** (ex. : « 30 % en TSLA »). Le système ne recommande rien : il **fait le procès de cette décision** et l'utilisateur rend le verdict. C'est ce qui garde la solution du côté de l'aide à la décision, pas du conseil personnalisé.

0. **Pacte vécu** (Python, sans LLM, facultatif, #68) : si l'utilisateur a répondu aux jours de marché revécus, ses réponses sont vérifiées **avant tout appel Bedrock**, la règle de pire baisse prend le seuil mesuré, et ses réponses deviennent la pièce P2, de type `declaree`.
1. **Agent Profil** (LLM Bedrock + Python) : charge le Pacte du profil (n'importe lequel) et transforme la demande en décision structurée (titre, taille, financement).
2. **Orchestrateur** (LLM Bedrock, encadré par Python) : **instruit le dossier**. Il lit la décision et le Pacte, **choisit lui-même quels outils Python appeler** (section 4 bis) et avec quels paramètres, et donne une raison courte pour chaque appel. Chaque résultat d'outil devient une **pièce à conviction** numérotée (P1, P2…).
3. **Procureur** (LLM Bedrock) : argumente **contre** la décision, en citant uniquement des pièces.
4. **Avocat** (LLM Bedrock) : argumente **pour** la décision, honnêtement, en citant uniquement des pièces. Le Procureur et l'Avocat sont appelés **en parallèle** ; ils ne calculent rien et n'appellent aucun outil.
5. **Greffier** (Python, sans LLM) : vérifie le Pacte (conforme, violation, à vérifier), vérifie que **chaque chiffre cité** par le Procureur et l'Avocat existe dans une pièce (règles en section 4 ter) et qu'**aucun argument ne conseille ni ne promet** (section 4 quater). Un argument non prouvé ou hors cadre est renvoyé une fois à son agent, puis rejeté.
6. **Verdict** (l'utilisateur) : maintenir, modifier la décision, ou ajuster son Pacte. Le système ne bloque jamais : il archive la décision avec ses pièces.

### L'orchestrateur Bedrock et ses garde-fous

L'orchestrateur est ce qui rend le système agentique : c'est un LLM qui **décide quelles preuves rassembler** selon la décision et le Pacte. Exemples : une décision crypto le pousse vers `calculer_correlations` ; un horizon court, vers le temps de récupération (`indicateurs_actif`) ; un seuil probablement dépassé, vers `taille_max_compatible`. Il reste encadré par des garde-fous écrits en Python :

- **Il ne calcule rien** : il ne peut qu'appeler les outils 1 à 4 de la liste blanche (section 4 bis). Les outils 5 et 6 appartiennent au Greffier et ne sont jamais appelés par un LLM.
- **Pièce obligatoire** : la simulation avant / après de la décision (`simuler_portefeuille`). Si l'orchestrateur ne l'a pas demandée, Python l'ajoute d'office et le note dans la trace.
- **Points de bascule** (#61) : dès qu'une règle calculable du Pacte est en violation, Python ajoute d'office la pièce `points_de_bascule` après l'orchestrateur et avant le débat. Elle répond à « Qu'est-ce qui changerait la réponse ? ». Ce n'est pas un outil de l'orchestrateur : elle n'a aucun paramètre à choisir et doit toujours être là.
- **Budget** : 8 appels d'outils au maximum par procès (hypothèse à ajuster), puis passage au débat.
- **Phases fixes** : Profil → Orchestrateur → Procureur et Avocat → Greffier → Verdict. L'orchestrateur choisit les outils, jamais l'ordre des phases ni le verdict. Le Greffier passe toujours en dernier.
- **Raison visible, courte et sans chiffre** : une phrase par appel, affichée dans la trace. Ce n'est pas le raisonnement interne détaillé du modèle, que l'énoncé demande de ne pas exposer.
- **Contre-interrogatoire** (question libre de l'utilisateur dans l'interface, #55) : même boucle. La question va à l'orchestrateur, qui choisit les outils (budget de 4 appels, pas de pièce obligatoire) ; les nouvelles pièces vont au Procureur et à l'Avocat, puis au Greffier. Une demande de conseil reçoit une réponse qui le dit, sans conseil. Code : `pipeline/contre_interrogatoire.py` (`interroger`) ; route `POST /question` de la Lambda ; champ `contre_interrogatoire` du contrat (section 5).

**Mise en œuvre recommandée** : une boucle de l'API Bedrock **Converse** avec `toolConfig` (*tool use*), codée dans la Lambda. Chaque outil Python est décrit à Bedrock par son nom, sa description et le schéma JSON de ses paramètres. Chaque demande d'outil du modèle (`toolUse`) est exécutée par Python, puis ajoutée à la trace. Le service managé Bedrock Agents est écarté : plus de configuration, une trace moins maîtrisée, et le même code ne tournerait pas en local.

Correspondance avec l'ancienne architecture : l'agent Gouvernance devient le **Greffier** ; l'agent Explicabilité est remplacé par le **débat Procureur / Avocat**, les pièces et le vérificateur de chiffres ; l'agent Analyse (allocation proposée) est retiré, car le système ne propose plus de portefeuille ; l'ordre fixe des outils est remplacé par l'**orchestrateur**.

Chaque étape écrit une **trace** (entrée, outil appelé, sortie, et la raison pour les appels de l'orchestrateur) affichée dans l'interface et stockée dans S3.

Chaque élément affiché porte une **étiquette** : `fait` (donnée calculée ou règle déclarée, avec sa source), `hypothese` (interprétation ou information à confirmer) ou `fictif` (profil de test, portefeuille ou scénario simulé).

## 4 bis. Les 6 outils (Python, exécutés dans Lambda)

Socle commun : **`charger_donnees`** lit les CSV (local ou S3), convertit en CAD et aligne les calendriers.

| # | Outil | Rôle | Appelé par | Version |
|---|---|---|---|---|
| 1 | `indicateurs_actif` | Rendement annualisé, volatilité, pire baisse, rendement 2022, temps de récupération d'un titre | Orchestrateur | V1 |
| 2 | `simuler_portefeuille` | Indicateurs du portefeuille avant et après la décision (taille + mode de financement), rejeu de 2022 | Orchestrateur | V1 |
| 3 | `calculer_correlations` | Corrélation entre titres (ex. : BTC/ETH, NVDA/QQQ) | Orchestrateur | V2 |
| 4 | `taille_max_compatible` | Plus grande taille qui respecte le Pacte (appelle l'outil 2) | Orchestrateur | V1 |
| 5 | `verifier_pacte` | Compare les résultats aux règles du Pacte | Greffier | V1 |
| 6 | `verifier_chiffres` | Vérifie que chaque nombre cité existe dans une pièce (section 4 ter) | Greffier | V1 |
| 7 | `consulter_jurisprudence` | Verdicts passés du même profil (archives `verdicts/<profil>/` de S3) : violations par règle et choix de l'utilisateur (#56) | Orchestrateur | Bonus |
| 8 | `points_de_bascule` | Pour chaque règle calculable en violation : la taille où elle serait conforme, et le seuil qui suffirait (la valeur simulée après la décision). Relit la recherche de l'outil 4 (#61) | Python, d'office | Bonus |
| — | `calibrer_pacte` | Pacte vécu : seuil de pire baisse mesuré sur les réponses de l'utilisateur, pièce `declaree` (#68) | Tribunal, avant le procès | Bonus |

Aucun de ces outils n'utilise le LLM. On les développe et teste **en local**, puis le même code est déployé dans Lambda (variable `SOURCE_DONNEES=local|s3`). Les outils 1 à 4 sont décrits à l'orchestrateur comme outils Bedrock (nom, description, schéma JSON des paramètres).

**`taille_max_compatible` est en V1** : le curseur de l'écran Décision (zone compatible / en conflit), la plaidoirie (« jusqu'à 9 % ») et le faux contrat l'utilisent déjà. Méthode : appeler `simuler_portefeuille` de 0 jusqu'à la taille demandée, par pas de 1 point, avec le même mode de financement. Le résultat est la plus grande taille qui respecte **toutes les règles calculables** du Pacte (`pire_baisse_max` et `plafond`). Pour une réallocation, la « taille » est la part réallouée. Si même 0 % viole le Pacte (portefeuille de départ déjà hors Pacte), l'outil le signale au lieu de renvoyer une taille.

Les **valeurs des pièces sont brutes** (non arrondies, au moins 4 décimales, ex. : `-0.2897`, `2.935`). Seul `valeur_affichee` est arrondi. C'est nécessaire pour `verifier_chiffres`.

## 4 ter. Règles de `verifier_chiffres` (Greffier)

Ce vérificateur porte la promesse du pitch : « aucun chiffre inventé ne passe ». Ses règles sont fixes et testées.

1. **Ce qui est vérifié** : chaque nombre écrit dans le texte d'un argument (Procureur, Avocat, réponse au contre-interrogatoire) : pourcentages, décimaux, entiers, années, dates. Ne sont pas extraits : les identifiants de pièces (`P1`), les nombres collés à des lettres et les nombres faisant partie du nom d'un actif (« S&P/TSX 60 », « Nasdaq-100 », « S&P 500 »). Attention, en français la virgule est aussi le séparateur décimal : « 29,0 » est un décimal, mais dans « en 2022, TSLA… » la virgule est une ponctuation (une virgule n'est décimale que si un chiffre la suit immédiatement).
2. **Contre quoi** : uniquement les **pièces citées par l'argument**, plus deux sources toujours admises : la `decision` (ex. : « 30 % ») et la période d'analyse (2021-11-12 → 2026-11-12). Un chiffre qui n'existe que dans une pièce non citée est rejeté : l'argument doit citer la bonne pièce.
3. **Correspondance par arrondi** : la valeur de la pièce est convertie dans l'unité du texte (× 100 pour un « % »), puis arrondie au **nombre de décimales écrit dans le texte**. Pour `-0.2897` : « −29,0 % » et « −29 % » passent ; « −28 % » et « −29,03 % » sont rejetés. « Près de 3 ans » passe pour `2.935`. Les mots d'approximation (« près de », « environ », « ≈ ») ne donnent aucune tolérance de plus.
4. **Signe** : si le texte écrit un signe (+ ou −), il doit correspondre. Sans signe, le nombre est lu comme **positif**, sauf s'il suit directement un mot de baisse (« chute de », « baisse de », « perte de », « recul de ») : on compare alors à la valeur absolue. Ainsi « une chute de 29 % » passe pour `-0.2897`, mais « le portefeuille ferait 2,6 % » est rejeté pour `-0.0259`. Les prompts demandent d'écrire le signe.
5. **Dates** : une année, ou un mois et une année (« janv. 2022 »), ou un jour et un mois (« 14 novembre »), doit correspondre à une date ISO d'une pièce citée, de la décision ou de la période.
6. **Aucun nombre dérivé** : un écart, un ratio ou une somme (« 21 points de plus », « 4 fois plus ») est rejeté s'il n'existe pas tel quel dans une pièce. Si un argument en a besoin, c'est un outil Python qui le calcule et l'ajoute à une pièce.
7. **Plages et listes** : chaque nombre est vérifié séparément (« 3 à 5 ans » ↔ `horizon_ans: [3, 5]`). Les listes de valeurs d'une pièce sont aplaties.
8. **Échec** : l'argument est renvoyé **une fois** à son agent avec le motif exact (nombre fautif, pièces citées). S'il échoue encore, il va dans `arguments_rejetes` avec ce motif ; il n'est jamais affiché comme un argument valide.
9. **Compte rendu** : le contrôle `verifier_chiffres` affiche « nombres vérifiés / nombres extraits » et le nombre d'arguments (ex. : « 17/17 chiffres, 7 arguments »). Une date compte pour un nombre.
10. **Tests obligatoires** : au minimum, chaque exemple de cette section (cas qui passent et cas rejetés) est un test unitaire.

## 4 quater. Cadre « simulation seulement » : `cadre_simulation` (Greffier)

Le case demande à la gouvernance de vérifier le cadre du défi (p. 9) et interdit de se présenter comme du conseil financier personnalisé (p. 17). Le Greffier vérifie donc aussi, en Python sans LLM (`pipeline/cadre_simulation.py`), qu'aucun argument (Procureur, Avocat, réponse au contre-interrogatoire) ne contient :
1. **un conseil** : recommandation ou ordre (« vous devriez », « je recommande », « il faut vendre », « Robert devrait alléger », impératif comme « achetez » ou « ne vendez pas ») ;
2. **une promesse ou une prévision** sur l'avenir, à la hausse comme à la baisse (« va monter », « rapportera », « devrait rebondir », « se répétera », « garanti », « à coup sûr »).

Ne sont pas visés : les citations entre guillemets (le Pacte cité : « Préserver mon capital »), une prévision **niée** dans la même proposition (« le passé ne prédit pas l'avenir », « rien ne garantit ») le conditionnel d'un scénario (« si 2022 se répétait, le portefeuille ferait… ») et une interrogation indirecte (« le Tribunal ne dit pas s'il faut vendre », la réponse attendue à une demande de conseil au contre-interrogatoire). Un conseil nié reste un conseil. Même boucle que la règle 8 de la section 4 ter, dans la même relance : renvoyé une fois avec le motif, puis `arguments_rejetes`. Compte rendu : le contrôle `cadre_simulation` (« Aucun conseil personnalisé ni promesse sur l'avenir : 7 arguments vérifiés ») ; au contre-interrogatoire, une étape `verifier_cadre_simulation` de la trace de l'échange.

## 5. Contrat JSON entre le pipeline et l'interface

Le pipeline produit **exactement** ce format, une réponse par audience, quel que soit le profil. Le champ `persona` contient l'identifiant du Pacte utilisé (n'importe quel profil, pas seulement les profils de test). L'exemple ci-dessous illustre le cas général 1 avec le profil de test prudent. L'équipe interface travaille avec le faux JSON `docs/exemples/contrat_robert.json` en attendant. **Ne changez pas ce format sans prévenir toute l'équipe.**

Conventions : les nombres sont des **décimales** (0.30 = 30 %), en CAD sauf mention contraire. `valeur_affichee` est le texte prêt à afficher, produit par Python (jamais par le LLM).

```json
{
  "persona": "Robert",
  "demande": "Je veux mettre 30 % de mon portefeuille en Tesla",
  "decision": {"type": "position", "ticker": "TSLA", "taille": 0.30, "financement": "proportionnel", "libelle": "30 % en TSLA"},
  "pacte": {
    "id": "robert",
    "profil_risque": "faible_a_modere",
    "horizon_ans": [3, 5],
    "date_signature": "2026-11-14",
    "regles": [
      {"id": "pire_baisse_max", "type": "pire_baisse_max", "seuil": -0.12, "libelle": "Pire baisse tolérée : −12 %"},
      {"id": "plafond_crypto", "type": "plafond", "categories": ["crypto"], "max": 0.0, "libelle": "Crypto : exclue"},
      {"id": "preserver_capital", "type": "qualitative", "libelle": "Préserver mon capital"}
    ]
  },
  "comparaison": {
    "actuel": {"rendement_annuel": 0.0929, "volatilite_annuelle": 0.0559, "pire_baisse": -0.0776, "rendement_2022": -0.0259},
    "apres":  {"rendement_annuel": 0.1198, "volatilite_annuelle": 0.1897, "pire_baisse": -0.2897, "rendement_2022": -0.2371}
  },
  "taille_max_compatible": 0.09,
  "points_de_bascule": [
    {"regle": "pire_baisse_max", "type": "pire_baisse_max", "seuil_actuel": -0.12, "seuil_suffisant": -0.289679, "taille_max": 0.09, "message": "Conforme jusqu'à 9 % en TSLA, ou avec un seuil de −29,0 % au lieu de −12,0 %", "pieces": ["P6"]}
  ],
  "pieces": [
    {
      "id": "P1",
      "type": "calculee",
      "etiquette": "fictif",
      "titre": "Simulation du portefeuille avec la décision",
      "outil": "simuler_portefeuille",
      "valeurs": {"pire_baisse": -0.2897, "rendement_annuel": 0.1198},
      "valeur_affichee": "−29,0 % max · +12,0 %/an",
      "source": "Yahoo Finance via yfinance (adj_close), extrait le 2026-11-13 ; USD/CAD Banque du Canada",
      "traitement": "Rendements quotidiens en CAD, calendrier des séances américaines, rééquilibrage quotidien",
      "limites": "Une seule période de 5 ans ; biais du survivant ; le passé ne prédit pas l'avenir"
    }
  ],
  "requisitoire": [
    {"etiquette": "fait", "texte": "Avec 30 % en TSLA, la pire chute observée passe de −7,8 % à −29,0 %.", "pieces": ["P1"]}
  ],
  "plaidoirie": [
    {"etiquette": "fait", "texte": "Sur la période, le rendement annualisé aurait été de +12,0 % contre +9,3 %.", "pieces": ["P1"]}
  ],
  "controles": [
    {"statut": "violation", "regle": "pire_baisse_max", "message": "Pire baisse −29,0 % au-delà du seuil −12,0 %", "pieces": ["P1", "P3"]},
    {"statut": "a_verifier", "regle": "preserver_capital", "message": "Règle déclarée, non mesurable par calcul : à juger par l'utilisateur", "pieces": ["P3"]},
    {"statut": "conforme", "regle": "verifier_chiffres", "message": "Chiffres cités vérifiés contre leurs pièces : 17/17 chiffres, 7 arguments"},
    {"statut": "conforme", "regle": "cadre_simulation", "message": "Aucun conseil personnalisé ni promesse sur l'avenir : 7 arguments vérifiés"},
    {"statut": "a_verifier", "regle": "performance_passee", "message": "Performance passée invoquée : elle ne prédit pas l'avenir"}
  ],
  "arguments_rejetes": [
    {"cote": "requisitoire", "etiquette": "fait", "texte": "…", "pieces": ["P1"], "raison": "« −31 % » introuvable dans P1"}
  ],
  "verdict": null,
  "hypotheses": ["Période : 2021-11-12 au 2026-11-12", "Rendements calculés sur adj_close", "Montants convertis en CAD", "Seuils du Pacte choisis par l'équipe"],
  "sources": [{"nom": "Yahoo Finance via yfinance", "fichier": "prices_daily.csv", "date_extraction": "2026-11-13"}],
  "limites": ["Les rendements passés ne garantissent pas les rendements futurs", "Biais du survivant dans l'univers d'actifs"],
  "trace": [
    {"etape": "agent_profil", "outil": "charger_pacte", "entree": "robert", "sortie": "P3"},
    {"etape": "orchestrateur", "outil": "simuler_portefeuille", "raison": "Pièce obligatoire : comparer le portefeuille avant et après la décision", "entree": {"ticker": "TSLA", "taille": 0.30, "financement": "proportionnel"}, "sortie": "P1"},
    {"etape": "orchestrateur", "outil": "taille_max_compatible", "raison": "Seuil de pire baisse probablement dépassé : chercher la plus grande taille compatible", "entree": {"ticker": "TSLA", "financement": "proportionnel"}, "sortie": "P5"}
  ],
  "avertissement": "Simulation éducative. Aucune transaction réelle. Ceci n'est pas un conseil financier personnalisé."
}
```

Règles du contrat :
- Le contrat est vérifiable automatiquement : schéma `contrat/schema_sortie.json`, renvois entre champs dans `contrat/valider.py` (`python -m contrat.valider <fichier.json>`). Exemples valides : `docs/exemples/contrat_robert.json` (cas 1) et `docs/exemples/contrat_amira.json` (cas 2).
- `decision.type` vaut `position` (`ticker`, `taille`, `financement` : `proportionnel` ou `depuis_<ticker>`) ou `reallocation` (`panier` : liste `ticker` + `poids` totalisant 1, `part_reallouee`, prise au prorata de toutes les lignes). Même format que `decision_demo` des fichiers profils, plus `libelle`.
- `taille_max_compatible` vaut `null` si même 0 % viole le Pacte. Pour une réallocation, c'est la plus grande part réallouée compatible.
- `points_de_bascule` (#61) : un objet par règle calculable (`pire_baisse_max`, `plafond`) en violation, et seulement pour elles ; liste vide sans violation. `taille_max` est la plus grande taille (ou part réallouée) où **cette** règle est conforme (`null` si même 0 % la viole) ; `seuil_suffisant` est la valeur simulée après la décision (pire baisse, ou part des catégories du plafond), arrondie du côté permissif ; `message` est écrit par Python ; `pieces` cite la pièce `points_de_bascule`. Champ facultatif dans le schéma, pour que les contrats antérieurs restent valides ; le pipeline le produit toujours.
- `statut` d'un contrôle : `conforme`, `violation` ou `a_verifier`. `etiquette` : `fait`, `hypothese` ou `fictif`. `type` d'une pièce : `calculee` (outil Python), `documentaire` (extrait de document, V3) ou `declaree` (réponses de l'utilisateur au Pacte vécu, horodatées, #68).
- `pacte.regles` reprend les règles du fichier profil (section 3), sans les justifications. Une règle au seuil mesuré par le Pacte vécu porte aussi `provenance` (texte), `etiquette` et `piece` (la pièce `declaree` qui le prouve). `controles[].regle` est l'`id` d'une règle du Pacte, ou l'un des contrôles du système : `verifier_chiffres`, `cadre_simulation` (Greffier : aucun conseil ni promesse dans les arguments affichés, section 4 quater ; absent des contrats archivés avant #60), `performance_passee`, `biais_survivant`, `interpretation_demande` (Agent Profil : demande incomplète ou ambiguë, toujours `a_verifier`).
- Chaque argument cite au moins une pièce. Un argument dont un chiffre est introuvable dans ses pièces (section 4 ter), ou qui conseille ou promet (section 4 quater), va dans `arguments_rejetes`, avec `cote` (`requisitoire` ou `plaidoirie`), son texte, ses pièces et la `raison` du rejet.
- Dans `trace`, les appels de l'orchestrateur ont `etape: "orchestrateur"` et une `raison` courte, sans chiffre. Une pièce ajoutée d'office par Python a la raison « Pièce obligatoire ajoutée d'office ». Un appel refusé ou en erreur (outil non autorisé, raison invalide, titre hors univers, source manquante…) ne crée pas de pièce : sa `sortie` est « Erreur : <motif> ». La simulation obligatoire, elle, doit avoir produit une pièce. L'étape `calibrage` (Pacte vécu) donne les questions posées et les réponses, et sa `sortie` est la pièce `declaree`.
- Les valeurs des pièces et de `comparaison` sont brutes (au moins 4 décimales) ; seul `valeur_affichee` est arrondi.
- `verdict` est rempli par l'interface quand l'utilisateur choisit : `maintenu`, `modifie` ou `pacte_ajuste`.
- `contre_interrogatoire` (facultatif, #55) : une entrée par question posée après le procès, avec `question`, `pieces_ajoutees`, `requisitoire`, `plaidoirie`, `arguments_rejetes`, `controle_chiffres` (contrôle `verifier_chiffres` de la réponse) et `trace`. Les pièces créées pour répondre sont ajoutées au champ `pieces`, numérotées à la suite : une question suivante peut les citer.

## 6. Pièges des données de départ (dossier `alphaforge_starter/`)

- **Utiliser `adj_close` pour les rendements** (ajusté pour dividendes et fractionnements). `close` n'est ajusté que pour les fractionnements.
- **Ne pas réappliquer les fractionnements** : les lignes `split` de `corporate_actions.csv` sont seulement informatives.
- **Devises** : les titres `.TO` sont en CAD, le reste en USD. Convertir avec `fx_usdcad_daily.csv`, en reportant le dernier taux connu pour les jours fériés canadiens.
- **Calendriers différents** : la crypto se négocie 7 jours sur 7, les actions 5 jours sur 7, et les jours fériés diffèrent entre la TSX et les États-Unis. Aligner les calendriers explicitement et **documenter la méthode** (ex. : jours ouvrables communs).
- **CNQ.TO** : le « split » de 1,021 du 2022-08-22 est probablement une distribution spéciale, pas un vrai fractionnement.
- **Macro mensuelle** : datée au mois de référence, pas à la date de publication. Ne jamais utiliser une valeur avant sa publication réelle.
- **Biais du survivant** : l'univers a été choisi en 2026, donc les résultats passés paraissent meilleurs que la réalité.
- **Aucune donnée ESG, nouvelle ou fondamentale** n'est fournie. Toute donnée ajoutée doit être documentée (source, date, traitement, limites, conditions d'utilisation).

## 6 bis. Méthode de calcul retenue (à documenter dans la doc technique)

Ces choix ont servi à produire les chiffres de la maquette. Le code doit les reproduire, ou toute différence doit être documentée.

- **Prix** : `adj_close`, convertis en CAD avec `usdcad` (dernier taux connu reporté).
- **Calendrier** : séances de la bourse américaine. Les prix TSX et crypto sont reportés au dernier prix connu ; les rendements crypto du week-end sont donc cumulés dans le lundi.
- **Rendement annualisé** : taux composé entre la première et la dernière date de la période.
- **Volatilité annualisée** : écart type des rendements quotidiens × √252.
- **Pire baisse** : plus forte chute depuis un sommet sur la série de valeurs.
- **Rendement 2022** : dernière valeur de 2021 → dernière valeur de 2022.
- **Simulation de portefeuille** : rééquilibrage quotidien aux poids cibles. Financement `proportionnel` (tous les titres réduits au prorata) ou `depuis_<ticker>` (une seule ligne réduite).
- **Temps de récupération** : du sommet précédant la pire baisse jusqu'au retour à ce sommet.

## 7. Encadrement responsable (obligatoire)

- Aucune transaction réelle. Aucun conseil financier personnalisé.
- Toujours distinguer **faits**, **hypothèses** et **scénarios fictifs**.
- Les explications restent courtes, vérifiables et fidèles aux sources. Elles n'inventent aucune justification.
- Le passé ne prédit pas le futur. Expliquer les indicateurs et leurs limites (la volatilité n'est qu'un indicateur de risque parmi d'autres).

## 8. Plan de livraison (petit d'abord, puis on élargit)

Chaque version ajoute un **cas général**, pas un persona. Le profil de test sert à le démontrer.

1. **Version 1 — Cas 1 : décision incohérente avec le profil** : socle de données, outils 1, 2, 4, 5 et 6, orchestrateur Bedrock, Procureur, Avocat, Greffier, règles `pire_baisse_max`, `plafond` et `qualitative`, et le JSON complet. Démontré avec le profil prudent et « 30 % en TSLA ».
2. **Version 2 — Cas 2 : diversification** : ajouter la crypto (BTC, ETH), l'outil 3 (corrélations), les plafonds sur plusieurs catégories et les décisions de type réallocation (panier). Démontré avec le profil audacieux (« crypto ≤ 25 % », « tech + crypto ≤ 75 % »).
3. **Version 3 — Cas 3 : préférences non financières** : seulement s'il reste du temps. Règles `critere_documentaire`, source ESG externe documentée (pièce `documentaire`, éventuellement via une base de connaissances Bedrock). Démontré avec le profil équilibré ESG (ESGV vs SPY, examen de XOM). Sans source ESG, XOM améliore tous les indicateurs financiers de ce profil : le cas 3 dépend donc entièrement de la pièce documentaire.

Toujours garder une version qui fonctionne de bout en bout avant d'ajouter quelque chose.

La maquette de référence est dans `docs/maquette/` (lien Figma + prototype interactif).

## 9. Livrables à prévoir

- Prototype et dépôt de code avec un **README** (dépendances, sources, configuration, démarrage).
- **Vidéo** d'environ 5 minutes, idéalement avec **la même décision** jugée pour deux profils contrastés (ex. : profil prudent vs profil audacieux), pour montrer que le système s'adapte au Pacte et non à un persona codé en dur.
- **Documentation technique** : méthodes, sources, traitements, mécanisme d'explicabilité avec un exemple relié à la trace, validations et limites. Elle part de `docs/CHOIX_CONCEPTION.md` (le pourquoi) et du journal `docs/journal/` (ce qui a été construit, issue par issue).
- **One pager**.

## 10. Conventions de code

- Python 3.11+, `pandas` pour les données, `boto3` pour AWS (S3, Bedrock).
- Les appels au LLM passent par **Amazon Bedrock**, pas par une API externe.
- Développer d'abord en local (CSV locaux), puis brancher S3 et Bedrock. Garder une variable de configuration pour basculer entre les deux.
- Les fonctions de calcul (outils) sont **pures** et **testées** : mêmes entrées, mêmes sorties.
- **Aucun nom de persona dans le code** : la logique lit les règles du Pacte. Les noms des profils de test n'apparaissent que dans les fichiers `personas/` et dans les tests.
- Une fonction = une responsabilité. Nommer clairement (`calculer_volatilite_annuelle`, pas `calc_v`).
- Chaque membre doit **comprendre le code qu'il garde** : si Claude génère du code, demandez-lui de l'expliquer avant de le garder.

## 11. Pull requests et issues

- Chaque PR qui termine une issue écrit **`Closes #N`** dans sa description (une ligne par issue). GitHub ferme alors l'issue **automatiquement quand la PR est fusionnée dans `main`**. Le modèle `.github/pull_request_template.md` le rappelle.
- Une PR qui ne fait qu'avancer une issue écrit **`Avance #N`** : l'issue reste ouverte.
- Une PR fermée **sans fusion** ne ferme aucune issue : le travail n'est pas arrivé dans `main`.
- Aucune mention de Claude dans les commits ni dans les PR.

### Journal de construction (obligatoire)

Pour que n'importe qui puisse s'y retrouver dans le dépôt, chaque issue laisse une trace de ce qui a été construit.

- **Chaque PR qui termine ou avance une issue** ajoute ou met à jour la fiche `docs/journal/NNN-titre-court.md` (NNN = numéro de l'issue sur 3 chiffres, ex. : `007-client-llm-bedrock.md`). Le modèle et les règles sont dans `docs/journal/README.md`.
- La fiche est écrite **dans la même PR que le code**, avant de l'ouvrir. Elle décrit ce qui existe vraiment : fichiers, fonctions publiques, comment l'utiliser, comment le vérifier, choix faits en cours de route, limites.
- Une PR qui ajoute, déplace ou supprime un fichier ou un dossier important met aussi à jour la **carte du dépôt** dans `README.md`.
- Une PR sans issue qui ne touche que la configuration ou la documentation n'a pas de fiche. Si elle construit du code, on crée d'abord l'issue.
