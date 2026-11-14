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
- **API Gateway** (si l'interface doit appeler le pipeline) : expose un point d'accès qui renvoie le JSON du contrat.

Toujours vérifier les consignes logistiques officielles (services permis, crédits, région).

## 2. Règle d'or : Python calcule, le LLM explique

- **Tous les chiffres** (rendement, volatilité, pire baisse, corrélations, poids) sont calculés en **Python** à partir des CSV. Ces fonctions sont les « outils » des agents.
- Le **LLM** reçoit ces chiffres et sert seulement à raisonner sur le profil et à rédiger l'explication.
- **Le LLM n'invente jamais un chiffre ni une source.** Chaque nombre cité dans une explication doit exister dans la sortie d'un outil Python.
- Si une donnée manque, l'agent le **signale** au lieu de deviner.

## 3. Personas (situations de référence)

| Persona | Profil de risque | Horizon | Ce que le persona teste | Décision testée dans la démo |
|---|---|---|---|---|
| **Robert**, 59 ans | Faible à modéré | 3 à 5 ans | Le système sait **contester** une demande incohérente avec le profil au lieu d'acquiescer. | Ajouter 30 % de TSLA |
| **Amira**, 26 ans | Élevé | 15 ans et plus | Le système accepte du risque **sans tout accepter** : il garde une diversification (pas 100 % tech ou crypto). | Tout réallouer vers un panier crypto-tech |
| **Mateo**, 41 ans | Modéré | 8 à 12 ans | Le système intègre des critères **ESG** en plus du rendement et du risque. | Ajouter 10 % de XOM |

Chaque persona a un **Pacte** : ses règles, déclarées à l'avance, converties en contraintes vérifiables (fichiers `personas/<nom>.json`). Les seuils sont des **hypothèses** de l'équipe, pas des recommandations réglementaires.

| Persona | Règles du Pacte |
|---|---|
| Robert | Pire baisse ≥ −12 %, préserver le capital, entreprises établies, crypto exclue |
| Amira | Pire baisse ≥ −45 %, crypto ≤ 25 %, pas exclusivement tech, horizon 15 ans et plus |
| Mateo | Pire baisse ≥ −20 %, exclusion des controverses ESG importantes, pas de spéculation |

## 4. Architecture visée : le Tribunal (simple et vérifiable)

L'utilisateur arrive avec **sa propre décision** (ex. : « 30 % en TSLA »). Le système ne recommande rien : il **fait le procès de cette décision** et l'utilisateur rend le verdict. C'est ce qui garde la solution du côté de l'aide à la décision, pas du conseil personnalisé.

1. **Agent Profil** (LLM + Python) : charge le Pacte du persona et transforme la demande en décision structurée (titre, taille, financement).
2. **Outils de calcul** (Python, voir section 4 bis) : produisent les **pièces à conviction** numérotées (P1, P2…).
3. **Procureur** (LLM) : argumente **contre** la décision, en citant uniquement des pièces.
4. **Avocat** (LLM) : argumente **pour** la décision, honnêtement, en citant uniquement des pièces.
5. **Greffier** (Python, sans LLM) : vérifie le Pacte (conforme, violation, à vérifier) et vérifie que **chaque chiffre cité** par le Procureur et l'Avocat existe dans une pièce. Un argument non prouvé est rejeté.
6. **Verdict** (l'utilisateur) : maintenir, modifier la décision, ou ajuster son Pacte. Le système ne bloque jamais : il archive la décision avec ses pièces.

Correspondance avec l'ancienne architecture : l'agent Gouvernance devient le **Greffier** ; l'agent Explicabilité est remplacé par le **débat Procureur / Avocat**, les pièces et le vérificateur de chiffres ; l'agent Analyse (allocation proposée) est retiré, car le système ne propose plus de portefeuille.

Chaque étape écrit une **trace** (entrée, outil appelé, sortie) affichée dans l'interface et stockée dans S3.

Chaque élément affiché porte une **étiquette** : `fait` (donnée calculée ou règle déclarée, avec sa source), `hypothese` (interprétation ou information à confirmer) ou `fictif` (persona, portefeuille ou scénario simulé).

## 4 bis. Les 6 outils (Python, exécutés dans Lambda)

Socle commun : **`charger_donnees`** lit les CSV (local ou S3), convertit en CAD et aligne les calendriers.

| # | Outil | Rôle | Version |
|---|---|---|---|
| 1 | `indicateurs_actif` | Rendement annualisé, volatilité, pire baisse, rendement 2022, temps de récupération d'un titre | V1 |
| 2 | `simuler_portefeuille` | Indicateurs du portefeuille avant et après la décision (taille + mode de financement), rejeu de 2022 | V1 |
| 3 | `calculer_correlations` | Corrélation entre titres (ex. : BTC/ETH, NVDA/QQQ) | V2 |
| 4 | `taille_max_compatible` | Plus grande taille qui respecte le Pacte (appelle l'outil 2) | Bonus |
| 5 | `verifier_pacte` | Compare les résultats aux règles du Pacte | V1 |
| 6 | `verifier_chiffres` | Vérifie que chaque nombre cité existe dans une pièce | V1 |

Aucun de ces outils n'utilise le LLM. On les développe et teste **en local**, puis le même code est déployé dans Lambda (variable `SOURCE_DONNEES=local|s3`).

## 5. Contrat JSON entre le pipeline et l'interface

Le pipeline produit **exactement** ce format, une réponse par audience. L'équipe interface travaille avec le faux JSON `docs/exemples/contrat_robert.json` en attendant. **Ne changez pas ce format sans prévenir toute l'équipe.**

Conventions : les nombres sont des **décimales** (0.30 = 30 %), en CAD sauf mention contraire. `valeur_affichee` est le texte prêt à afficher, produit par Python (jamais par le LLM).

```json
{
  "persona": "Robert",
  "demande": "Je veux mettre 30 % de mon portefeuille en Tesla",
  "decision": {"ticker": "TSLA", "taille": 0.30, "financement": "proportionnel", "libelle": "30 % en TSLA"},
  "pacte": {
    "profil_risque": "faible_a_modere",
    "horizon_ans": [3, 5],
    "pire_baisse_max": -0.12,
    "plafond_crypto": 0.0,
    "exclusions": ["crypto"],
    "regles": ["Pire baisse tolérée : −12 %", "Préserver mon capital", "Entreprises établies", "Crypto : exclue"]
  },
  "comparaison": {
    "actuel": {"rendement_annuel": 0.093, "volatilite_annuelle": 0.056, "pire_baisse": -0.078, "rendement_2022": -0.026},
    "apres":  {"rendement_annuel": 0.120, "volatilite_annuelle": 0.190, "pire_baisse": -0.290, "rendement_2022": -0.237}
  },
  "taille_max_compatible": 0.09,
  "pieces": [
    {
      "id": "P1",
      "type": "calculee",
      "etiquette": "fictif",
      "titre": "Simulation du portefeuille avec la décision",
      "outil": "simuler_portefeuille",
      "valeurs": {"pire_baisse": -0.290, "rendement_annuel": 0.120},
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
    {"statut": "conforme", "regle": "verifier_chiffres", "message": "Chiffres cités vérifiés contre leurs pièces : 7/7"},
    {"statut": "a_verifier", "regle": "performance_passee", "message": "Performance passée invoquée : elle ne prédit pas l'avenir"}
  ],
  "arguments_rejetes": [],
  "verdict": null,
  "hypotheses": ["Période : 2021-11-12 au 2026-11-12", "Rendements calculés sur adj_close", "Montants convertis en CAD", "Seuils du Pacte choisis par l'équipe"],
  "sources": [{"nom": "Yahoo Finance via yfinance", "fichier": "prices_daily.csv", "date_extraction": "2026-11-13"}],
  "limites": ["Les rendements passés ne garantissent pas les rendements futurs", "Biais du survivant dans l'univers d'actifs"],
  "trace": [
    {"etape": "agent_profil", "outil": "charger_pacte", "entree": "robert", "sortie": "..."},
    {"etape": "outil_calcul", "outil": "simuler_portefeuille", "entree": {"ticker": "TSLA", "taille": 0.30}, "sortie": "P1"}
  ],
  "avertissement": "Simulation éducative. Aucune transaction réelle. Ceci n'est pas un conseil financier personnalisé."
}
```

Règles du contrat :
- `statut` d'un contrôle : `conforme`, `violation` ou `a_verifier`. `etiquette` : `fait`, `hypothese` ou `fictif`. `type` d'une pièce : `calculee` (outil Python) ou `documentaire` (extrait de document, V3).
- Chaque argument cite au moins une pièce. Un argument dont un chiffre est introuvable dans ses pièces va dans `arguments_rejetes` avec la raison.
- `verdict` est rempli par l'interface quand l'utilisateur choisit : `maintenu`, `modifie` ou `pacte_ajuste`.

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

1. **Version 1 — Robert** : socle de données, outils 1, 2, 5 et 6, Procureur, Avocat, Greffier et le JSON complet pour « 30 % en TSLA ».
2. **Version 2 — Amira** : ajouter la crypto (BTC, ETH), l'outil 3 (corrélations) et les règles « crypto ≤ 25 % » et « pas exclusivement tech ».
3. **Version 3 — Mateo** : seulement s'il reste du temps. Source ESG externe documentée (pièce `documentaire`, éventuellement via une base de connaissances Bedrock), comparaison ESGV vs SPY, examen de XOM.
4. **Bonus** : outil 4 (`taille_max_compatible`).

Toujours garder une version qui fonctionne de bout en bout avant d'ajouter quelque chose.

La maquette de référence est dans `docs/maquette/` (lien Figma + prototype interactif).

## 9. Livrables à prévoir

- Prototype et dépôt de code avec un **README** (dépendances, sources, configuration, démarrage).
- **Vidéo** d'environ 5 minutes, idéalement avec deux personas contrastés (ex. : Robert vs Amira).
- **Documentation technique** : méthodes, sources, traitements, mécanisme d'explicabilité avec un exemple relié à la trace, validations et limites.
- **One pager**.

## 10. Conventions de code

- Python 3.11+, `pandas` pour les données, `boto3` pour AWS (S3, Bedrock).
- Les appels au LLM passent par **Amazon Bedrock**, pas par une API externe.
- Développer d'abord en local (CSV locaux), puis brancher S3 et Bedrock. Garder une variable de configuration pour basculer entre les deux.
- Les fonctions de calcul (outils) sont **pures** et **testées** : mêmes entrées, mêmes sorties.
- Une fonction = une responsabilité. Nommer clairement (`calculer_volatilite_annuelle`, pas `calc_v`).
- Chaque membre doit **comprendre le code qu'il garde** : si Claude génère du code, demandez-lui de l'expliquer avant de le garder.
