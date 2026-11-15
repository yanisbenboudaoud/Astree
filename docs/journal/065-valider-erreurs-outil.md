# #65 — contrat.valider refuse un contrat dont la trace contient un appel d'outil refusé

- **Issue** : #65 · **PR** : #66 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
- `contrat/valider.py` :
  - `est_erreur_outil(sortie)` et `PREFIXE_ERREUR_OUTIL` : une étape `orchestrateur` peut avoir pour `sortie` « Erreur : <motif> » (motif non vide) au lieu d'un id de pièce. C'est la trace d'un appel refusé ou en erreur (#12) : le procès continue sans pièce.
  - Toute autre sortie qui n'est pas une pièce reste rejetée, avec le message « n'est ni une pièce ni une erreur d'outil ».
  - La pièce obligatoire `simuler_portefeuille` doit avoir **réussi** : une simulation demandée mais en erreur ne compte plus.
- `pipeline/orchestrateur.py` : constante `PREFIXE_ERREUR`, utilisée par `_refuser`. Un test vérifie qu'elle est identique à celle du validateur.
- `CLAUDE.md`, section 5 : règle ajoutée pour la trace.

## Comment vérifier
- `pytest tests/test_contrat.py` : un appel refusé est accepté ; « P99 », « Erreur : » sans motif et « rien » sont rejetés ; une simulation obligatoire en erreur est rejetée ; les deux préfixes sont identiques.
- Le contrat du procès « 25 % en TSLA » du profil prudent, renvoyé par la Lambda le 2026-11-15 (avec un appel `rechercher_documents` sans document sur TSLA), passe maintenant `python -m contrat.valider`. Il était refusé avant.

## Choix faits en cours de route
- Le validateur n'importe pas `pipeline` : le paquet `contrat` reste indépendant du pipeline (l'équipe interface s'en sert seule). La constante est donc copiée, et un test garde les deux copies identiques.

## Limites et suite
- L'interface (#14) devrait afficher ces étapes comme des appels refusés (motif visible), pas comme des pièces.
