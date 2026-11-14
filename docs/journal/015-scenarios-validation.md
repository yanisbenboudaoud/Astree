# #15 — Scénarios de validation et de sensibilité

- **Issue** : #15 · **PR** : #PR_A_RENSEIGNER · **Statut** : terminée (sauf le scénario « panier », en attente de #16)
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
Diapo 8 : « Changez une hypothèse. Changez un scénario. Changez un profil. Votre solution reste-t-elle cohérente ? »

- **`validation/scenarios.py`** : 7 groupes de scénarios, chacun une fonction qui renvoie des `Resultat` (scénario, attendu, obtenu, ok).
  - `juger(profil, decision)` rejoue la **partie calculée** du procès sur les vraies données : `piece_simulation`, `verifier_pacte`, `rechercher_taille_max`. C'est gratuit (sans Bedrock) et toujours reproductible ;
  - les garde-fous de l'orchestrateur sont joués avec les **vrais outils** et un faux modèle (`ModeleScripte`) qui force chaque situation ;
  - `categories_modifiees(...)` change les catégories le temps d'un scénario, sans toucher à `config/categories.json`.
- **`validation/__main__.py`** : `python -m validation` joue tout, réécrit le rapport et sort en erreur si un scénario échoue.
- **`docs/validation/resultats_scenarios.md`** : le tableau des résultats, à reprendre dans la documentation technique.
- **`pipeline/simulation.py`** : nouvelle fonction publique `valeurs_avant_apres(portefeuille, decision)`, qui donne les séries de valeurs pour recalculer les indicateurs sur une sous-période.
- **`tests/test_scenarios.py`** : aucun scénario en échec, et le rapport doit être à jour.

## Comment l'utiliser
```bash
python -m validation        # « 33 réussis, 0 en échec, 1 en attente »
```
Ajouter un scénario = une ligne `Resultat` dans un groupe existant, ou une nouvelle fonction ajoutée à `GROUPES`.

## Comment vérifier
`pytest tests/test_scenarios.py`. Si un seuil, un profil ou une catégorie change, le test du rapport échoue. Il faut alors relancer `python -m validation` et committer le rapport.

Résultats principaux (détail dans le rapport) :
- **Même décision, profils différents** : 30 % en TSLA donne une violation pour le profil prudent (−29,0 %) et le profil ESG (−33,3 %), mais aucune pour le profil audacieux (−42,6 % pour un seuil de −45 %). Avec 10 % de XOM, le profil ESG n'a aucune violation financière, et la règle ESG reste `a_verifier`.
- **Seuil du profil prudent de −10 % à −30 %** : la violation disparaît à −30 %, et la taille maximale croît régulièrement (7 % → 9 % → 13 % → 19 % → 25 % → 30 %).
- **Hypothèse « tech + crypto ≤ 75 % »** : pour le profil audacieux avec 30 % de NVDA, la part tech + crypto est de 65 %. Le verdict bascule donc entre un plafond de 60 % et un plafond de 65 %.
- **Catégories** : retirer QQQ de la tech fait passer cette part de 65 % à 51 %. Ajouter TSLA à la tech fait basculer « 60 % TSLA » de conforme à violation (20 % → 80 %).
- **Période** : la pire baisse est la même sur la période complète et sur 2022 seule. Elle vient entièrement de 2022, et la volatilité de 2022 est plus élevée.
- **Robustesse du Greffier** : un chiffre inventé, un arrondi faux, une mauvaise pièce, un signe manquant ou un nombre dérivé sont tous rejetés, avec leur motif.
- **Garde-fous** : 8 appels au maximum, simulation ajoutée d'office, outil du Greffier refusé, raison avec chiffre refusée.
- **Profil inventé** : un 4e Pacte (4 règles, dont un plafond tech à 20 %) est jugé sans changer le code.

## Choix faits en cours de route
- **Pas de Bedrock dans les scénarios** : ils doivent tourner automatiquement, gratuitement et toujours donner le même résultat. Le comportement réel du modèle est déjà vérifié par les tests `bedrock` de la fiche [012](012-orchestrateur.md) (même décision, deux profils).
- **Hors du dossier `pipeline/`** : `validation/` n'est pas déployé dans Lambda.
- **La période « 2022 seule »** est calculée en recoupant les séries de valeurs avec `valeurs_avant_apres`, au lieu d'ajouter une option de période à `simuler_portefeuille`.
- **Un scénario « en attente »** (⏸) est affiché, pas caché : le panier crypto-tech du profil audacieux dépend de #16.

## Limites et suite
- **Panier crypto-tech** : quand #16 permettra à `simuler_portefeuille` de simuler les réallocations, il faudra remplacer le scénario « en attente » par le vrai test (3 violations attendues).
- **Une seule période de données** (2021-11-12 → 2026-11-12) : on ne peut tester qu'une sous-période, pas une autre crise.
