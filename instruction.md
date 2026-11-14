# CLAUDE.md — Projet AlphaForge AI (Datathon PolyFinances 2026)

Ce fichier donne à Claude le contexte et les règles du projet. Toute l'équipe partage ce fichier via Git : si une règle change, modifiez-la ici et faites un commit.

## 1. But du projet

Nous construisons une **solution agentique auto-explicative** qui utilise des données financières publiques pour aider à la décision d'investissement selon le profil de l'investisseur. Tout se passe **en simulation**.

Le jury évalue surtout :
- **la démarche agentique** : des agents qui utilisent des données et des outils, avec des points de contrôle ;
- **l'auto-explicabilité** : chaque conclusion doit être reliée aux données, aux hypothèses, aux étapes observables et aux limites.

Une démonstration convaincante et des explications fidèles aux données comptent plus que la complexité ou le rendement passé.

## 2. Règle d'or : Python calcule, le LLM explique

- **Tous les chiffres** (rendement, volatilité, pire baisse, corrélations, poids) sont calculés en **Python** à partir des CSV. Ces fonctions sont les « outils » des agents.
- Le **LLM** reçoit ces chiffres et sert seulement à raisonner sur le profil et à rédiger l'explication.
- **Le LLM n'invente jamais un chiffre ni une source.** Chaque nombre cité dans une explication doit exister dans la sortie d'un outil Python.
- Si une donnée manque, l'agent le **signale** au lieu de deviner.

## 3. Personas (situations de référence)

| Persona | Profil de risque | Horizon | Ce que le persona teste |
|---|---|---|---|
| **Robert**, 59 ans | Faible à modéré | 3 à 5 ans | Le système sait **contester** une demande incohérente avec le profil (ex. : TSLA ou NVDA) au lieu d'acquiescer. |
| **Amira**, 26 ans | Élevé | 15 ans et plus | Le système accepte du risque **sans tout accepter** : il garde une diversification (pas 100 % tech ou crypto). |
| **Mateo**, 41 ans | Modéré | 8 à 12 ans | Le système intègre des critères **ESG** en plus du rendement et du risque. |

## 4. Architecture visée (simple et vérifiable)

1. **Agent Profil** : transforme le persona et sa demande en contraintes explicites (risque max, horizon, exclusions, préférences).
2. **Outils d'analyse (Python)** : calculent les indicateurs sur les actifs candidats.
3. **Agent Analyse** : propose une allocation fictive ou une comparaison à partir des indicateurs.
4. **Agent Gouvernance** : vérifie que la proposition respecte les contraintes. Il signale les conflits (ex. : « TSLA dépasse la volatilité acceptable pour Robert ») et les informations manquantes.
5. **Agent Explicabilité** : rédige l'explication finale en citant les chiffres, les sources, les hypothèses et les limites.

Chaque étape écrit une **trace** (entrée, outil appelé, sortie) pour qu'on puisse montrer comment une conclusion a été obtenue.

## 5. Contrat JSON entre le pipeline et l'interface

Le pipeline produit **exactement** ce format. L'équipe interface peut travailler avec un faux JSON de ce format en attendant. **Ne changez pas ce format sans prévenir toute l'équipe.**

```json
{
  "persona": "Robert",
  "demande": "Je veux investir dans TSLA",
  "contraintes": {
    "profil_risque": "faible_a_modere",
    "horizon_ans": [3, 5],
    "volatilite_max": 0.15,
    "exclusions": ["crypto"]
  },
  "proposition": [
    {"ticker": "XIU.TO", "poids": 0.40, "raison": "..."},
    {"ticker": "XBB.TO", "poids": 0.40, "raison": "..."},
    {"ticker": "TSLA",   "poids": 0.00, "raison": "Rejeté : volatilité trop élevée pour le profil"}
  ],
  "indicateurs": {
    "TSLA":   {"rendement_annuel": 0.0, "volatilite_annuelle": 0.0, "pire_baisse": 0.0},
    "XIU.TO": {"rendement_annuel": 0.0, "volatilite_annuelle": 0.0, "pire_baisse": 0.0}
  },
  "alertes": [
    {"niveau": "conflit", "message": "La demande (TSLA) est incohérente avec le profil de risque de Robert."}
  ],
  "explication": "Texte court et compréhensible, qui cite uniquement des chiffres présents dans 'indicateurs'.",
  "hypotheses": ["Période : 2021-11-12 au 2026-11-12", "Rendements calculés sur adj_close", "Montants convertis en CAD"],
  "sources": [
    {"nom": "Yahoo Finance via yfinance", "fichier": "prices_daily.csv", "date_extraction": "2026-11-13"}
  ],
  "limites": ["Les rendements passés ne garantissent pas les rendements futurs", "Biais du survivant dans l'univers d'actifs"],
  "trace": [
    {"etape": "agent_profil", "sortie": "..."},
    {"etape": "outil_indicateurs", "entree": ["TSLA", "XIU.TO"], "sortie": "..."}
  ],
  "avertissement": "Simulation éducative. Ceci n'est pas un conseil financier."
}
```

## 6. Pièges des données de départ (dossier `alphaforge_starter/`)

- **Utiliser `adj_close` pour les rendements** (ajusté pour dividendes et fractionnements). `close` n'est ajusté que pour les fractionnements.
- **Ne pas réappliquer les fractionnements** : les lignes `split` de `corporate_actions.csv` sont seulement informatives.
- **Devises** : les titres `.TO` sont en CAD, le reste en USD. Convertir avec `fx_usdcad_daily.csv`, en reportant le dernier taux connu pour les jours fériés canadiens.
- **Calendriers différents** : la crypto se négocie 7 jours sur 7, les actions 5 jours sur 7, et les jours fériés diffèrent entre la TSX et les États-Unis. Aligner les calendriers explicitement et **documenter la méthode** (ex. : jours ouvrables communs).
- **CNQ.TO** : le « split » de 1,021 du 2022-08-22 est probablement une distribution spéciale, pas un vrai fractionnement.
- **Macro mensuelle** : datée au mois de référence, pas à la date de publication. Ne jamais utiliser une valeur avant sa publication réelle.
- **Biais du survivant** : l'univers a été choisi en 2026, donc les résultats passés paraissent meilleurs que la réalité.
- **Aucune donnée ESG, nouvelle ou fondamentale** n'est fournie. Toute donnée ajoutée doit être documentée (source, date, traitement, limites, conditions d'utilisation).

## 7. Encadrement responsable (obligatoire)

- Aucune transaction réelle. Aucun conseil financier personnalisé.
- Toujours distinguer **faits**, **hypothèses** et **scénarios fictifs**.
- Les explications restent courtes, vérifiables et fidèles aux sources. Elles n'inventent aucune justification.
- Le passé ne prédit pas le futur. Expliquer les indicateurs et leurs limites (la volatilité n'est qu'un indicateur de risque parmi d'autres).

## 8. Plan de livraison (petit d'abord, puis on élargit)

1. **Version 1 — Robert** : 5 ou 6 actifs (ex. : TSLA, NVDA, XIU.TO, SPY, XBB.TO, JNJ), les indicateurs de base, l'agent gouvernance qui conteste TSLA et le JSON complet.
2. **Version 2 — Amira** : ajouter la crypto (BTC, ETH) et une règle de diversification.
3. **Version 3 — Mateo** : seulement s'il reste du temps. Données ESG externes documentées, comparaison ESGV vs SPY, examen de ENB, CNQ et XOM.

Toujours garder une version qui fonctionne de bout en bout avant d'ajouter quelque chose.

## 9. Livrables à prévoir

- Prototype et dépôt de code avec un **README** (dépendances, sources, configuration, démarrage).
- **Vidéo** d'environ 5 minutes, idéalement avec deux personas contrastés (ex. : Robert vs Amira).
- **Documentation technique** : méthodes, sources, traitements, mécanisme d'explicabilité avec un exemple relié à la trace, validations et limites.
- **One pager**.

## 10. Conventions de code

- Python 3.11+, `pandas` pour les données.
- Les fonctions de calcul (outils) sont **pures** et **testées** : mêmes entrées, mêmes sorties.
- Une fonction = une responsabilité. Nommer clairement (`calculer_volatilite_annuelle`, pas `calc_v`).
- Chaque membre doit **comprendre le code qu'il garde** : si Claude génère du code, demandez-lui de l'expliquer avant de le garder.
