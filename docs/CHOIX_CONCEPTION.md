# Choix de conception de la pipeline agentique

Ce document explique **comment** la pipeline AlphaForge AI est construite et surtout **pourquoi**. Il sert de base à la documentation technique, à la vidéo et au pitch.

> Les références « diapo X » renvoient à la présentation officielle du datathon. Les numéros `#X` renvoient aux issues GitHub. La maquette de référence est dans `docs/maquette/`.

---

## Vue d'ensemble : le Tribunal

```
Décision de l'utilisateur (« 30 % en TSLA ») + Pacte du profil (n'importe lequel)
              │
              ▼
┌──────────────────────────┐
│ 1. Agent Profil          │  LLM : demande → décision structurée | Python : charge le Pacte   (#8, #3)
└────────────┬─────────────┘
             ▼
┌──────────────────────────┐
│ 2. Orchestrateur         │  LLM Bedrock : choisit les outils à appeler   ──►  Outils Python  (#12)
│    (garde-fous Python)   │  ◄── pièces à conviction P1, P2…                   (#4, #5, #6)
└────────────┬─────────────┘
             ▼
┌────────────┴─────────────┐
│ 3. Procureur │ 4. Avocat │  LLM Bedrock, en parallèle : arguments contre / pour, avec pièces  (#11)
└────────────┬─────────────┘
             ▼
┌──────────────────────────┐
│ 5. Greffier              │  Python : règles du Pacte + vérificateur de chiffres              (#10, #11)
└────────────┬─────────────┘
             ▼
     JSON du contrat (+ trace dans S3)  →  Verdict rendu par l'utilisateur             (#2, #12)
```

Infrastructure AWS : **Bedrock** (LLM), **Lambda** (outils et orchestration), **S3** (données et traces), **point d'accès de l'interface** (API Gateway ou Lambda Function URL, à trancher à cause du délai de 29 s d'API Gateway : voir l'issue #22). Voir aussi #7 et #13.

---

## Choix 1 — Un procès plutôt qu'une recommandation

**Décision.** L'utilisateur arrive avec **sa propre décision**. Le système ne propose pas de portefeuille : il présente les arguments **contre** (Procureur) et **pour** (Avocat), vérifiés par un Greffier, et l'utilisateur rend le verdict.

**Pourquoi.**
- **Aide à la décision, pas conseil.** L'énoncé interdit de se présenter comme un conseil financier personnalisé (section 4). Un système qui dit « achetez X » s'en approche ; un système qui expose les deux côtés et laisse l'humain trancher reste du bon côté.
- **L'explication devient le produit.** Le débat, avec ses pièces numérotées, *est* l'explication. Elle n'est pas ajoutée après coup.
- **Le cas « décision incohérente avec le profil » devient spectaculaire** : le Procureur confronte l'utilisateur à sa propre règle (ex. : « préserver mon capital » pour le profil de test prudent) avec les chiffres, sans condescendance.
- **Différenciation** : la plupart des équipes construiront un générateur de portefeuille.

**Alternative écartée.** Un agent Analyse qui propose une allocation (ancienne issue #9). Plus classique, plus proche du conseil, et le jury verrait un résultat plutôt qu'un raisonnement.

---

## Choix 2 — « Python calcule, le LLM explique »

**Décision.** Tous les chiffres (rendement, volatilité, pire baisse, corrélations, taille maximale) sont calculés par 6 outils Python testés (`CLAUDE.md`, section 4 bis). Le Procureur et l'Avocat reçoivent ces pièces et ne produisent jamais un chiffre eux-mêmes.

**Pourquoi.**
- Un LLM peut **inventer un chiffre crédible**. Dans un contexte financier, c'est inacceptable.
- L'énoncé demande des explications **fidèles aux données et vérifiables**, qui n'**inventent aucune justification** (section 4 ; diapo 11).
- Un calcul Python donne **toujours le même résultat** : reproductible et testable.

---

## Choix 3 — Des pièces à conviction numérotées

**Décision.** Chaque résultat d'outil devient une **pièce** (P1, P2…) avec sa valeur, sa source, son traitement et ses limites. Chaque argument doit citer au moins une pièce.

**Pourquoi.**
- L'utilisateur peut **remonter de l'argument à la donnée** en un clic : argument → pièce → outil → fichier source.
- C'est ce que l'énoncé demande dans la documentation technique : *un exemple reliant une conclusion aux données ou aux traces observables*.
- Les pièces peuvent être `calculee` (outil Python) ou, en V3, `documentaire` (extrait d'un document ESG, par exemple via une base de connaissances Bedrock).

---

## Choix 4 — Un orchestrateur Bedrock dans des phases fixes

**Décision.** Un **orchestrateur** (LLM via Bedrock) instruit le dossier : il lit la décision et le Pacte, **choisit les outils Python à appeler** et leurs paramètres, et justifie chaque appel par une phrase courte visible dans la trace. Les **phases**, elles, restent fixes et sont imposées par Python : Profil → Orchestrateur → Procureur et Avocat (en parallèle) → Greffier → Verdict (#12). Détails et garde-fous : `CLAUDE.md`, section 4.

**Pourquoi.**
- **Vraiment agentique (20 % de la note).** Avec un ordre d'outils fixé par Python, les LLM ne faisaient que rédiger : le jury aurait vu un pipeline. L'orchestrateur **mobilise** des outils et **adapte** les preuves au cas (diapo 5) : une décision crypto appelle les corrélations, un horizon court appelle le temps de récupération, un seuil dépassé appelle la taille maximale compatible.
- **Toujours vérifiable.** L'orchestrateur ne calcule rien (liste blanche d'outils, budget de 8 appels, pièce obligatoire ajoutée d'office si besoin), et le Greffier déterministe passe toujours en dernier.
- **Prévisible :** les phases fixes restent faciles à déboguer et à montrer dans la vidéo. *Une approche simple, focalisée et vérifiable peut être plus forte qu'une architecture spectaculaire mais impossible à expliquer* (diapo 8).
- **Le contre-interrogatoire de la maquette** a enfin un moteur : la question de l'utilisateur passe par la même boucle.

**Mise en œuvre recommandée.** API Bedrock **Converse** avec *tool use* (`toolConfig`), en boucle dans la Lambda : même code en local et dans AWS, et chaque `toolUse` devient une ligne de trace.

**Alternatives écartées.**
- **Ordre fixe des outils** (version précédente de ce choix) : plus simple, mais pas agentique.
- **Service managé Bedrock Agents** : plus de configuration (groupes d'actions, schémas), une trace moins maîtrisée, et pas d'exécution locale.
- **Orchestrateur qui décide aussi des phases** (par exemple sauter le Procureur) : imprévisible, et rien ne garantirait le contrôle du Greffier.

---

## Choix 5 — Un rôle clair par agent

| Agent | Valeur apportée | Rôle du LLM | Rôle de Python |
|---|---|---|---|
| **Profil** | Transformer une demande en décision structurée | Comprendre le texte (titre, taille) | Charger et valider le Pacte |
| **Orchestrateur** | Rassembler les bonnes preuves pour **ce** cas | Choisir les outils et leurs paramètres, donner une raison courte | Exécuter les outils, imposer la liste blanche, le budget et la pièce obligatoire |
| **Procureur** | Exposer les risques de la décision pour **ce** profil | Rédiger les arguments contre, en citant des pièces | — |
| **Avocat** | Défendre honnêtement la décision | Rédiger les arguments pour, en citant des pièces | — |
| **Greffier** | Garantir que le débat est fidèle et que le Pacte est respecté | Aucun | Règles du Pacte + vérificateur de chiffres |

**Pourquoi.** Si on retire un agent, une fonction précise disparaît. Sans Orchestrateur, les preuves seraient les mêmes pour tous les cas ; sans Avocat, le système devient un censeur ; sans Procureur, il acquiesce ; sans Greffier, rien n'empêche une hallucination.

---

## Choix 6 — Le Greffier : gouvernance déterministe

**Décision.** Le Greffier est du **Python sans LLM**. Il applique les règles du Pacte (`conforme`, `violation`, `a_verifier`) et vérifie que chaque nombre cité par le Procureur et l'Avocat existe dans une pièce. Un argument non prouvé est régénéré une fois, puis retiré et signalé dans `arguments_rejetes`.

**Pourquoi.**
- Une vérification doit être **fiable** : la même situation donne toujours la même réponse.
- Les règles sont **génériques et testables** : elles lisent les seuils du Pacte, quel que soit le profil (ex. : profil de test prudent + 30 % TSLA → au moins une `violation` ; profil audacieux + la même décision → pas de violation sur la pire baisse, avec une marge faible : −42,6 % pour un seuil de −45 %).
- Argument de pitch : *« notre système ne peut pas citer un chiffre inventé sans qu'on le détecte »*.

**Le vérificateur de chiffres a des règles précises** (`CLAUDE.md`, section 4 ter). Sans elles, le « 17/17 » affiché ne serait pas défendable devant le jury :
- un nombre n'est comparé **qu'aux pièces citées** par l'argument (plus la décision et la période) ;
- la valeur brute de la pièce est arrondie **à la précision écrite dans le texte** (« −29 % » valide `-0.2897`, « −28 % » non) ;
- les nombres dérivés (écarts, ratios) sont interdits : si un argument en a besoin, c'est Python qui les calcule ;
- les dates sont vérifiées comme les autres nombres.

---

## Choix 7 — Le Pacte : des règles déclarées à l'avance

**Décision.** Chaque profil a un Pacte (`personas/<nom>.json`) avec une justification par règle (#3). Tous les Pactes suivent **le même format** : une liste de **règles typées** (`pire_baisse_max`, `plafond`, `critere_documentaire`, `qualitative`), chacune avec un `id`, ses paramètres, un `libelle` et une `justification` (`CLAUDE.md`, section 3). Les catégories utilisées par les plafonds (`tech`, `crypto`) sont définies **une seule fois** pour tous les profils dans `config/categories.json`, à partir de `assets_universe.csv`.

**Pourquoi.**
- **Aucune règle propre à un persona.** L'ancien format avait des champs sur mesure (`interdit_exclusivement_tech`, une liste `categories` dans le seul fichier d'Amira, une exclusion `speculatif` définie nulle part). Avec des types génériques, « pas exclusivement tech » devient un simple plafond (tech + crypto ≤ 75 %), et « pas de spéculation » un plafond crypto à 0.
- **Ajouter un profil ne demande aucun code**, et ajouter un type de règle ne demande qu'une fonction du Greffier.
- **Honnêteté sur ce qui n'est pas mesurable** : les règles `qualitative` (« préserver mon capital », « entreprises établies ») sont affichées et rendues `a_verifier`, au lieu d'être ignorées ou devinées.
- Les seuils sont des **hypothèses**, pas des faits. Un fichier séparé les rend visibles et modifiables.
- **Finance comportementale** : quand l'utilisateur s'emballe pour un titre à la mode, le système lui rappelle ses propres mots, écrits à froid.
- On peut **changer une hypothèse sans toucher au code**, ce qui permet les tests de sensibilité (#15).

---

## Choix 7 bis — Des cas généraux, pas des personas codés en dur

**Décision.** Le système gère **trois cas généraux**, pour n'importe quel profil :

| Cas général | Ce que le système doit faire | Profil de test |
|---|---|---|
| 1. Décision incohérente avec le profil | Contester avec des preuves, sans bloquer | Prudent (Robert) |
| 2. Profil tolérant au risque | Accepter du risque, mais faire respecter la diversification | Audacieux (Amira) |
| 3. Préférences non financières | Intégrer ESG, exclusions et valeurs | Équilibré ESG (Mateo) |

Les personas de l'énoncé deviennent des **profils de test**. Le code ne teste jamais un nom de persona : il lit uniquement les règles du Pacte.

**Pourquoi.**
- **C'est ce que demande l'énoncé** : les personas sont des *situations de référence pour concevoir et tester la solution*, pas le produit lui-même.
- **Crédibilité devant le jury** : un système qui marche pour 3 personas codés en dur ne prouve rien. Un système qui marche pour **n'importe quel Pacte**, démontré sur 3 profils de test, prouve qu'il s'adapte vraiment (diapo 8 : « Changez un profil. Votre solution reste-t-elle cohérente ? »).
- **Extensible sans code** : un nouveau profil = un nouveau fichier Pacte.
- **Démonstration plus forte** : la **même décision** jugée pour deux profils différents donne deux procès différents. C'est la preuve visible de l'adaptation.

**Alternative écartée.** Une logique par persona (`if persona == "robert"`). C'est plus rapide à coder pour la démo, mais fragile, non extensible, et le jury pourrait y voir une démonstration « arrangée ».

---

## Choix 8 — L'humain rend le verdict, le système ne bloque jamais

**Décision.** L'utilisateur choisit : maintenir, modifier sa décision ou ajuster son Pacte. Toute décision est archivée avec ses pièces et les avertissements, même si elle viole le Pacte.

**Pourquoi.** Bloquer reviendrait à décider à sa place, donc à conseiller. Archiver garde la responsabilité chez l'humain et rend la décision traçable.

---

## Choix 9 — Faits, hypothèses, fictif : des étiquettes partout

**Décision.** Chaque argument, pièce et chiffre affiché porte une étiquette `fait`, `hypothese` ou `fictif`.

**Pourquoi.** L'énoncé exige de *distinguer faits, hypothèses et scénarios fictifs* (section 4). Une étiquette visible le rend évident pour le jury, sans texte supplémentaire.

---

## Choix 10 — La taille maximale compatible

**Décision.** L'outil `taille_max_compatible` calcule la plus grande position qui respecte toutes les règles calculables du Pacte (ex. : 9 % de TSLA pour le profil de test prudent ; à 10 %, la pire baisse atteint −12,1 %). Recherche par pas de 1 point, avec le même mode de financement. Il fait partie de la **V1**.

**Pourquoi.**
- La réponse utile n'est souvent pas « non », mais « pas à cette taille ». C'est ce qui transforme un refus en aide à la décision.
- **En V1 et non en bonus**, parce que l'interface en dépend déjà : curseur de l'écran Décision (zone compatible / en conflit), plaidoirie (« jusqu'à 9 % ») et faux contrat. C'est une boucle simple autour de `simuler_portefeuille`.

---

## Choix 11 — La trace d'exécution

**Décision.** Chaque étape ajoute à la trace ce qu'elle a reçu, l'outil appelé et ce qu'elle a produit. La trace est affichée dans l'interface et stockée dans S3.

**Pourquoi.** Elle permet de remonter de la conclusion jusqu'aux données : « violation » ← pièce P1 ← `simuler_portefeuille` ← `adj_close` de `prices_daily.csv`. Stockée dans S3, elle donne à AWS un rôle réel dans l'explicabilité (diapo 7).

---

## Choix 12 — Un contrat JSON entre la pipeline et l'interface

**Décision.** La pipeline produit toujours le format défini dans `CLAUDE.md` (section 5). Un faux JSON (`docs/exemples/contrat_robert.json`) permet à l'interface d'avancer en parallèle (#2).

**Pourquoi.** Le format impose `pieces`, `controles`, `hypotheses`, `sources`, `limites` et `avertissement` : l'explicabilité est **structurelle**, elle ne dépend pas de la bonne volonté du LLM.

---

## Choix 13 — Peu de services AWS, chacun justifié

| Service | Rôle | Pourquoi ce service |
|---|---|---|
| **Bedrock** | LLM du Profil, de l'Orchestrateur, du Procureur et de l'Avocat (API Converse avec *tool use*) | Cœur agentique ; rôle d'AWS directement démontrable |
| **Lambda** | Exécute les 6 outils et la boucle de l'orchestrateur | Même code qu'en local ; aucun serveur à gérer |
| **S3** | Données, traces et journal des verdicts | Traces conservées et consultables (explicabilité) |
| **API Gateway ou Lambda Function URL** | Point d'accès de l'interface | Renvoie le JSON du contrat. À trancher : API Gateway coupe après environ 29 s, ce qu'un procès peut dépasser (issue #22) |
| *Base de connaissances Bedrock (V3)* | *Pièces documentaires ESG* | *Citations sourcées et datées pour le cas « préférences non financières »* |

**Sécurité.** Aucune clé dans le code ni dans Git, rôle IAM minimal (accès au bucket et `bedrock:InvokeModel` seulement).

---

## Choix 14 — Livrer petit, puis élargir

**Décision.** Chaque version ajoute un **cas général** : V1 = décision incohérente avec le profil, de bout en bout (avec l'orchestrateur et `taille_max_compatible`) ; V2 = diversification ; V3 = préférences non financières, si le temps le permet.

**Pourquoi.** Le cas 1 montre que le système sait contester ; le cas 2 montre qu'il accepte le risque sans tout accepter. Démontrés avec les profils de test prudent et audacieux, ce sont les **deux situations contrastées** recommandées pour la vidéo (diapo 4).

---

## Limites connues de cette conception

- **Les seuils des Pactes sont des hypothèses** choisies par l'équipe, pas des recommandations réglementaires.
- **Indicateurs historiques :** les performances passées ne prédisent pas les performances futures. La pire baisse et la volatilité ne sont que des indicateurs de risque parmi d'autres.
- **Biais du survivant** dans l'univers d'actifs fourni (choisi en 2026) : les arguments de l'Avocat basés sur le rendement passé sont flattés.
- **Une seule période** (2021-2026) : un autre découpage donnerait d'autres chiffres.
- **Données ESG** : aucune n'est fournie ; elles dépendent de sources externes (V3).
- **Simulation uniquement :** aucune transaction réelle, aucun conseil financier personnalisé.
