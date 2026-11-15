# #168 — Validation externe : nos rendements comparés à ceux publiés par les émetteurs

- **Issue** : #168 · **PR** : #179 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Toutes les pièces du Tribunal partent de `adj_close` (Yahoo Finance via yfinance). Ces données sont maintenant **confrontées à une source indépendante** : les rendements totaux par année civile publiés par les émetteurs des FNB.

- **`donnees_externes/rendements_emetteurs.json`** (nouveau) :
  - `seuil_acceptation` : **0,25 point de pourcentage** par FNB et par année, avec la règle et la justification. Écrit et **commité avant le code de calcul** (commit « Rendements publiés par les émetteurs et seuil d'acceptation, fixés avant le calcul ») : l'historique Git le prouve.
  - `fnb` : 27 rendements de 7 FNB (2022 à 2025). Chacun a sa valeur telle que publiée (en décimale), sa base (`cours`, `valeur_liquidative` ou `fonds_base_non_precisee`), le document, l'adresse et la **ligne citée mot pour mot**.
  - `non_releves` : QQQ et GLD, avec le motif.
- **`pipeline/donnees.py`** : `charger_adj_close_cotation(ticker)`, l'`adj_close` d'un titre dans sa devise de cotation, à ses seules séances (ni conversion en CAD, ni report).
- **`validation/externe.py`** (nouveau) :
  - `rendement_annee_civile` : de la dernière séance de l'année précédente à la dernière séance de l'année ;
  - `base_de_comparaison` : le cours si l'émetteur le publie, sinon la valeur liquidative, sinon le rendement du fonds sans base précisée ;
  - `comparer`, `Comparaison` (écart signé en points, `dans_le_seuil`) et `rapport`.
- **`docs/validation/validation_externe.md`** (généré) : le seuil, le résultat, le tableau de 2022, le tableau complet (nos séances, notre rendement, celui de l'émetteur, l'écart), les écarts hors seuil avec leur explication, les sources et la méthode.
- **`tests/test_validation_externe.py`** (nouveau) : calcul sur une série construite à la main, année sans séance signalée, ordre des bases, seuil inclusif et écart absolu, contenu du relevé (seuil, au moins 6 FNB dont XIU, XBB et ZST, source et citation de chaque chiffre), rapport régénéré à l'identique et identique au fichier du dépôt, écart hors seuil sans explication signalé.

## Comment l'utiliser
```bash
python -m validation.externe
```

## Comment vérifier
```bash
pytest tests/test_validation_externe.py
```
Résultat :
- **27/27 rendements annuels dans le seuil** (IC 95 % : 87,5 % à 100 %), sur 7 FNB ; **2022 : 7/7**.
- Écart absolu moyen : 0,028 point ; écart maximal : 0,12 point (XBB en 2022 et en 2024).
- Là où l'émetteur publie les deux bases (AGG, TLT, ESGV en 2024), notre rendement s'écarte en moyenne de 0,005 point du cours et de 0,094 point de la valeur liquidative (jusqu'à 0,21 pour TLT) : `adj_close` suit le cours, comme attendu.

## Choix faits en cours de route
- **Seuil de 0,25 point, choisi avant le calcul** : plus large que l'arrondi publié et que l'écart habituel entre cours et valeur liquidative en fin d'année, mais plus petit qu'une distribution mensuelle d'un FNB obligataire (environ 0,3 %). Une distribution oubliée par Yahoo serait donc vue.
- **Devise de cotation, pas CAD** : l'émetteur publie dans la devise du fonds. La validation porte sur la donnée de départ ; la conversion en CAD est un autre traitement (#5).
- **Sources d'émetteur seulement**, aucun site tiers (Morningstar, Yahoo). Les pages des émetteurs chargent leurs tableaux de performance en JavaScript : les chiffres viennent donc des **fiches PDF** (iShares Canada et États-Unis), de l'**aperçu du FNB** de BMO, des **prospectus** de SPY déposés à la SEC (rendement « Past One Year » au 31 décembre de chaque année) et du **prospectus** de Vanguard (graphique « Annual Total Returns »).
- **SPY 2023** : le texte du dépôt coupe chaque nombre du tableau à la même place (« 26.1 2% », « 15.5 2% », « 11.8 9% »). La valeur 26,12 % est lue ainsi et la coupure est notée dans la citation.
- **ZST** : l'aperçu du FNB arrondit à une décimale, soit une incertitude d'arrondi de ±0,05 point, bien sous le seuil.
- **XIU et XBB** : la fiche iShares Canada publie le rendement « Fund » sans en préciser la base. Ce rendement n'est pas étiqueté « valeur liquidative » sans preuve.

## Limites et suite
- **ESGV 2025** n'est pas relevé : le prospectus de décembre 2025 s'arrête à 2024, et la fiche de Vanguard ne donne pas de rendements par année civile. **QQQ et GLD** ne publient pas de rendements par année civile dans les documents lus. Rien n'est estimé.
- La validation couvre les FNB (7 sur 9) : les actions et les cryptoactifs n'ont pas d'émetteur qui publie un rendement total officiel.
- Elle valide les rendements annuels, pas chaque cours quotidien. Une erreur qui s'annule dans l'année passerait.
- #172 affichera ce résultat dans l'interface (tiroir d'une pièce de simulation).
