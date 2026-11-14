# #17 — Cas 3 : préférences non financières (ESG, pièces documentaires)

- **Issue** : #17 · **PR** : à compléter · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`donnees_externes/documents_esg.json`** : le corpus ESG, seule source extra-financière du système, puisque le jeu de départ n'en contient aucune. Trois documents publics, lus dans leur version originale le 2026-11-14 :
  - **XOM, `controverse_esg_importante: true`** : fiche « Commonwealth v. Exxon Mobil Corp. » du Sabin Center (Columbia Law School). L'État du Massachusetts poursuit Exxon pour pratiques trompeuses sur les risques climatiques ; le 2022-05-24, la Cour suprême de l'État a seulement refusé de rejeter la poursuite ; des actes de procédure datent du 2026-04-15.
  - **ESGV, `methodologie_fonds_esg`** :
    - le prospectus simplifié de Vanguard ESG U.S. Stock ETF (2025-12-19, SEC) : il suit le FTSE US All Cap Choice, qui exclut notamment « coal, oil, or gas » ;
    - les règles FTSE Global Choice (v5.0, août 2026) : exclusion dès 50 % de réserves fossiles détenues ou 5 % de revenus du pétrole et du gaz, et pour les controverses liées aux principes 7 à 9 du Pacte mondial de l'ONU (données Sustainalytics).

  Chaque document donne sa source, sa date de consultation, des extraits mot pour mot, un résumé et une qualification écrits par l'équipe, son traitement et ses limites.
- **`pipeline/documents.py`** :
  - `rechercher_documents(ticker, critere)` : rassemble les documents du corpus sur un titre et un critère en une pièce `documentaire` (étiquette `fait`). Les valeurs portent le `ticker`, la valeur du critère si un document la donne, les dates et les seuils (nombres et dates ISO, que `verifier_chiffres` accepte), les résumés et les extraits (que `verifier_chiffres` n'utilise pas comme sources de chiffres).
  - Sans document, l'outil lève `ErreurDonnees` (« source manquante ») : la règle reste `a_verifier`. Si deux documents se contredisent, le critère n'est pas tranché.
  - `charger_corpus` refuse un document incomplet (sans source, date ou limites). `decrire_rechercher_documents` décrit l'outil à l'orchestrateur.
- **`pipeline/orchestrateur.py`** (fiche [012](012-orchestrateur.md)) : l'outil rejoint la liste blanche. Ses consignes ajoutent l'exemple « un critère non financier du Pacte rend utile la recherche documentaire ».
- **`pipeline/greffier.py`** (fiche [010](010-greffier.md)) : `controler_critere_documentaire` ne retient une pièce qui nomme un titre que si ce titre est dans le portefeuille après la décision. Sinon, une controverse sur un autre titre ferait condamner la décision à tort. Le message nomme le titre (« rempli pour XOM selon P4 »).
- **Tests** : `tests/test_documents.py` (11 tests) et un test ajouté dans `tests/test_greffier.py`.

## Comment l'utiliser
```python
from pipeline.documents import rechercher_documents

piece = rechercher_documents("XOM", "controverse_esg_importante")
piece["valeurs"]["controverse_esg_importante"]   # True
piece["source"]   # « Sabin Center for Climate Change Law (…), https://climatecasechart.com/… (consulté le 2026-11-14) »
```

## Comment vérifier
```bash
pytest tests/test_documents.py tests/test_greffier.py
```
**Critère de fin atteint, vrai procès complet** (Bedrock, profil ESG, 10 % en XOM) :
- l'orchestrateur demande lui-même `rechercher_documents` pour XOM ;
- **financièrement, XOM améliore tout** : pire baisse de −15,1 % à −10,0 %, rejeu 2022 de −10,1 % à −2,1 %, rendement de +11,5 % à +13,5 %. Les règles financières sont conformes ;
- **seule la règle ESG est en violation**, d'après la pièce documentaire : « Critère « controverse_esg_importante » rempli pour XOM selon P4 » ;
- l'Avocat reconnaît qu'il ne peut pas plaider cette règle ; les deux côtés précisent « allégations contestées par l'entreprise, sans jugement sur le fond » ;
- `verifier_chiffres` valide tout (15/15) et `valider_contrat` passe.

**Comparaison ESGV / SPY** (outils 1 et 3, en CAD, du 2021-11-12 au 2026-11-12) :

| | ESGV | SPY |
|---|---|---|
| Rendement annualisé | +12,9 % | +14,5 % |
| Volatilité | 18,0 % | 16,7 % |
| Pire baisse | −26,9 % | −22,2 % |
| 2022 | −18,9 % | −12,6 % |

Corrélation entre les deux : 0,99. Sur cette période, le filtre ESG a coûté du rendement, ce qui est cohérent avec l'exclusion de l'énergie, qui a bien résisté en 2022. L'orchestrateur peut demander ces pièces lui-même (`indicateurs_actif`, `calculer_correlations`).

## Choix faits en cours de route
- **Corpus local plutôt qu'une base de connaissances Bedrock** : même code en local et dans Lambda, sources entièrement maîtrisées et relues, aucun service de plus à configurer sur un compte de 48 h. Une base de connaissances n'apporterait rien pour trois documents.
- **Sources primaires seulement** : décision de justice résumée par une base universitaire, prospectus réglementaire, règles officielles de l'indice. Les articles de presse ont servi à trouver les sources, pas comme sources.
- **La qualification « importante » est une hypothèse de l'équipe**, écrite dans le `traitement` et les `limites` de la pièce, car il n'existe pas de note publique et réutilisable d'une agence ESG. Aucune source ne dit mot pour mot « XOM est exclu d'ESGV » : les pièces d'ESGV décrivent des règles, pas la liste de ses titres.
- **Formulation corrigée après un essai** : le résumé disait que la Cour « a confirmé le refus de rejeter » la poursuite, et un agent a écrit « poursuite […] confirmée par la Cour suprême », ce qui est trompeur. Le résumé dit maintenant que la Cour a seulement refusé de rejeter la poursuite, sans se prononcer sur le fond.

## Limites et suite
- Trois documents seulement : tout autre titre ou critère donne « source manquante », par conception.
- L'affaire du Massachusetts peut avoir évolué depuis le 2026-11-14.
- `taille_max_compatible` ne tient compte que des règles calculables : pour XOM, il vaut 10 % alors que la règle ESG est enfreinte. L'interface doit donc afficher les contrôles à côté du curseur.
- Pour ajouter un document : une entrée complète dans `donnees_externes/documents_esg.json`, sans code.
