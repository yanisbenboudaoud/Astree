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

**Décision.** Le Greffier est du **Python sans LLM**. Il applique les règles du Pacte (`conforme`, `violation`, `a_verifier`) et vérifie que chaque nombre cité par le Procureur et l'Avocat existe dans une pièce. Il vérifie aussi le cadre « simulation seulement » : aucun argument ne conseille une transaction ni ne promet l'avenir (#60). Sans ce contrôle, un agent pourrait écrire « vous devriez vendre » et faire basculer l'outil dans le conseil. Un argument non prouvé ou hors cadre est régénéré une fois, puis retiré et signalé dans `arguments_rejetes`.

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

## Choix 10 bis — Les points de bascule : « Qu'est-ce qui changerait la réponse ? »

**Décision.** Dès qu'une règle calculable du Pacte est en violation, Python ajoute d'office une pièce `points_de_bascule` au dossier, avant le débat (#61). Pour chaque règle en violation, elle donne les deux façons de la rendre conforme : **modifier la décision** (la plus grande taille où *cette* règle est respectée) ou **ajuster le Pacte** (le seuil qui suffirait, c'est-à-dire la valeur simulée après la décision). Exemple : 30 % de TSLA pour le profil prudent serait conforme jusqu'à 9 %, ou avec un seuil de −29,0 % au lieu de −12 %. Le contrat les reprend dans le champ `points_de_bascule`, pour l'écran Verdict.

**Pourquoi.**
- Une explication crédible répond à quatre questions, dont « Qu'est-ce qui changerait la réponse ? » (atelier de la Banque Nationale, « Comprendre l'investisseur », diapo 12). `taille_max_compatible` n'y répondait que pour la taille, et pour toutes les règles à la fois.
- **Une taille par règle** : pour le panier crypto-tech du profil audacieux, la pire baisse serait respectée jusqu'à 36 % réalloués, le plafond crypto jusqu'à 28 %, le plafond tech et crypto jusqu'à 50 %. L'utilisateur voit quelle règle bloque, et de combien.
- **Actionnable sans conseiller** : les deux côtés correspondent aux choix de l'écran Verdict (modifier, ajuster le Pacte). Le système dit ce qui changerait la réponse, pas ce qu'il faut faire.
- **D'office plutôt qu'un outil de l'orchestrateur** : la pièce n'a aucun paramètre à choisir (elle découle de la décision et du Pacte) et doit être présente à chaque violation. En faire un outil aurait été un faux choix, qui consomme le budget d'appels. Elle ne refait aucun calcul : elle relit la recherche de `taille_max_compatible`, jugée par les contrôles du Greffier.
- **Vérifiable** : le seuil suffisant est arrondi du côté permissif. Un test prouve qu'avec ce seuil à la place du sien, le Greffier rend `conforme` (au plus proche, la pire baisse du panier audacieux, −0,6185554, aurait donné −0,618555, qui laissait la règle en violation).

**Alternative écartée.** Laisser le Procureur ou l'Avocat calculer « il faudrait accepter −29 % » : c'est un nombre dérivé, que le Greffier rejetterait (`CLAUDE.md`, section 4 ter, règle 6). C'est Python qui le calcule.

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
| **Lambda Function URL** | Point d'accès de l'interface | Renvoie le JSON du contrat. Préféré à API Gateway, qui coupe la requête après environ 29 s : un procès complet dure de 18 à 33 s (mesuré dans #22). C'est aussi un service de moins |
| *Base de connaissances Bedrock (V3)* | *Pièces documentaires ESG* | *Citations sourcées et datées pour le cas « préférences non financières »* |

**Sécurité.** Aucune clé dans le code ni dans Git, rôle IAM minimal : accès au bucket et `bedrock:InvokeModel` seulement (`deploiement/politique_iam_lambda.json`). Paramètres de la Lambda : `deploiement/README.md`.

---

## Choix 14 — Livrer petit, puis élargir

**Décision.** Chaque version ajoute un **cas général** : V1 = décision incohérente avec le profil, de bout en bout (avec l'orchestrateur et `taille_max_compatible`) ; V2 = diversification ; V3 = préférences non financières, si le temps le permet.

**Pourquoi.** Le cas 1 montre que le système sait contester ; le cas 2 montre qu'il accepte le risque sans tout accepter. Démontrés avec les profils de test prudent et audacieux, ce sont les **deux situations contrastées** recommandées pour la vidéo (diapo 4).

---

## Choix 15 — Le procès-verbal : le procès devient un dossier de décision

**Décision.** Chaque procès peut être exporté en **procès-verbal** imprimable (`pipeline/proces_verbal.py`, #57) : la décision, le Pacte et sa date de signature, la comparaison avant et après, les contrôles du Greffier, les arguments (acceptés et rejetés), les pièces (source, traitement, limites), la trace et le verdict de l'utilisateur. La page est produite **par Python, à partir du contrat JSON seulement** : aucun texte n'est ajouté par un LLM.

**Pourquoi.** Le procès contient déjà tout ce qu'un dossier de décision doit garder. L'exporter rend la décision **vérifiable après coup**, par l'investisseur lui-même ou par une personne qui l'accompagne, sans refaire le procès.

**Le cadre canadien, à présenter avec prudence.** Ce qui suit est notre lecture des sources ci-dessous ; ce n'est pas un avis juridique, et le texte officiel des règles reste à vérifier.
- Les courtiers en placement membres de l'OCRI suivent les *Règles visant les courtiers en placement et règles partiellement consolidées* (Règles CPPC). Pour les comptes **avec conseils**, le courtier doit déterminer la **convenance** d'une opération au profil du client. Les documents de l'OCRI trouvés renvoient à l'article 3402 pour la convenance envers un client de détail, mais nous n'avons pas pu en lire le texte (accès refusé au site de l'OCRI) : **numéro et libellé à vérifier**.
- Pour les comptes **d'exécution d'ordres sans conseils** (courtage en ligne, comme le courtage direct), l'obligation de convenance ne s'applique pas et les **recommandations sont interdites**. Selon BLG (17 avril 2026), la note d'orientation de l'OCRI publiée le 12 mars 2026, qui remplace la note 3400-21-003, permet des « ressources factuelles et informatives ainsi que des aides à la décision, à condition que celles-ci ne soutiennent pas une décision de placement précise », et demande d'éviter toute « impression de personnalisation ou de recommandation ».
- **Conséquence pour Astrée.** Astrée ne recommande rien : l'utilisateur apporte sa propre décision et ses propres règles, et c'est lui qui rend le verdict. Mais un procès porte bien sur **une décision précise** : savoir si un tel outil est admissible comme aide à la décision dans un compte sans conseils est une **question ouverte, à valider avec une équipe de conformité**. Le pitch ne doit donc pas dire qu'Astrée est conforme.

**Angle business (pitch).** Deux usages possibles, à formuler comme des pistes :
- avec un conseiller (compte avec conseils) : le procès-verbal pourrait servir de **pièce du dossier de convenance**, sans remplacer la détermination du conseiller ;
- en courtage en ligne : le procès-verbal est le **journal de décision de l'investisseur**, qui garde la trace de ce qu'il savait, de ses propres règles et de son choix.

Phrase pour le one pager : « Chaque décision jugée par Astrée devient un procès-verbal vérifiable : les règles que l'investisseur s'est fixées, les preuves calculées, les arguments vérifiés et son propre verdict. »

**Sources.**
- BLG, « DIY avec l'EOSC, mais lisez d'abord les lignes directrices mises à jour de l'OCRI », 17 avril 2026 : https://www.blg.com/fr/insights/2026/04/diy-with-oeo-but-first-read-the-updated-ciro-guidance (lu le 2026-11-14).
- OCRI, note d'orientation sur les services et activités d'exécution d'ordres sans conseils (2026) : https://www.ciro.ca/news-room/publications/guidance-order-execution-only-account-services-and-activities (**non lu** : accès refusé, à vérifier dans un navigateur).
- OCRI, lignes directrices sur la connaissance du client et la convenance : https://www.ciro.ca/node/11662 (**non lu** : accès refusé, à vérifier).

---

## Choix 16 — Le pouvoir d'achat : rendement réel et date de publication de l'IPC

**Décision.** Les pièces de `simuler_portefeuille` donnent, en plus du rendement en dollars, l'**inflation du Canada** sur la période et le **rendement réel** avant et après la décision : (1 + rendement) ÷ (1 + inflation) − 1 (#111). L'écran Décision l'affiche à côté du rendement en dollars (#113). Exemple : pour le profil de test prudent, +9,3 % par an en dollars, mais +5,5 % après une inflation de 3,5 % par an ; avec 30 % de TSLA, +8,1 %.

**Pourquoi.**
- L'atelier a insisté sur le **risque d'inflation** : un portefeuille prudent peut perdre bien plus en pouvoir d'achat qu'en dollars. En 2022, le portefeuille actuel du profil prudent fait −2,6 % en dollars, mais −8,4 % après inflation.
- **Calculé par Python, pas par l'agent** : la soustraction naïve (+12,0 − 3,5 = 8,5 %) est fausse, et le Greffier la rejette comme nombre dérivé (`CLAUDE.md`, section 4 ter, règle 6).
- **Aucune valeur avant sa publication** (énoncé, p. 14 ; `CLAUDE.md`, section 6) : le fichier date l'IPC au mois de référence, et Statistique Canada le publie vers le troisième mardi du mois suivant. Hypothèse prudente : l'IPC du mois M est connu le dernier jour du mois M + 1. Une mesure n'utilise que les mois publiés à sa date (l'extraction des données) : pour une période qui finit le 12 novembre 2026, l'inflation s'arrête à septembre 2026, même si le fichier contenait octobre. La période d'inflation est donc décalée de deux mois sur celle des prix, ce que dit le traitement de la pièce.

**Alternatives écartées.** Utiliser le dernier mois du fichier, quel qu'il soit : juste aujourd'hui par hasard, faux dès qu'on ajoute une valeur non encore publiée. Interpoler les mois manquants : ce serait inventer une donnée.

---

## Limites connues de cette conception

- **Les seuils des Pactes sont des hypothèses** choisies par l'équipe, pas des recommandations réglementaires.
- **Indicateurs historiques :** les performances passées ne prédisent pas les performances futures. La pire baisse et la volatilité ne sont que des indicateurs de risque parmi d'autres.
- **Biais du survivant** dans l'univers d'actifs fourni (choisi en 2026) : les arguments de l'Avocat basés sur le rendement passé sont flattés.
- **Une seule période** (2021-2026) : un autre découpage donnerait d'autres chiffres.
- **Données ESG** : aucune n'est fournie ; elles dépendent de sources externes (V3).
- **Simulation uniquement :** aucune transaction réelle, aucun conseil financier personnalisé.
