# Validation externe : nos rendements comparés à ceux publiés par les émetteurs

> Généré par `python -m validation.externe` à partir de `donnees_externes/rendements_emetteurs.json` (relevé du 2026-11-15) et de `alphaforge_starter/prices_daily.csv` (extrait le 2026-11-13). Ne pas modifier à la main : relancer la commande.

Toutes les pièces du Tribunal partent de `adj_close` (Yahoo Finance via yfinance). Ce rapport confronte ces données à une source indépendante : les rendements totaux par année civile publiés par les émetteurs des FNB de l'univers.

## Seuil d'acceptation, fixé avant le calcul

- **Écart maximal : 0,25 point de pourcentage** par FNB et par année (fixé le 2026-11-15, commité avec les relevés avant le code de calcul : voir l'historique Git de `donnees_externes/rendements_emetteurs.json`).
- Règle : Pour chaque FNB et chaque année, l'écart absolu entre notre rendement (adj_close, devise de cotation, dernière séance de l'année précédente → dernière séance de l'année) et le rendement publié par l'émetteur doit être d'au plus 0,25 point de pourcentage. Base de comparaison : le cours de marché si l'émetteur le publie (adj_close est un cours), sinon la valeur liquidative, sinon le rendement du fonds publié sans base précisée. Un écart au-delà du seuil est expliqué dans le rapport, jamais retouché.
- Justification : Hypothèse de l'équipe, écrite avant tout calcul. Les deux séries mesurent le même rendement total (cours et distributions réinvesties) ; les écarts attendus sont petits : arrondi publié (0,01 point), réinvestissement d'une distribution au cours de la veille de la date ex chez Yahoo plutôt qu'à la date ex, et, si seule la valeur liquidative est publiée, la prime ou l'escompte du cours sur la valeur liquidative aux deux fins d'année (quelques centièmes de point pour des FNB aussi liquides). Le seuil reste plus petit qu'une distribution mensuelle d'un FNB obligataire de l'univers (environ 0,3 % du prix) : une distribution oubliée par Yahoo dépasserait le seuil et serait donc vue.

## Résultat

- **Rendements annuels dans le seuil** : 27/27 (100,0 % ; IC 95 % : 87,5 % à 100,0 %), sur 7 FNB.
- **2022**, l'année de crise rejouée par chaque procès : 7/7 (100,0 % ; IC 95 % : 64,6 % à 100,0 %).
- Écart absolu moyen : 0,028 point ; écart maximal : 0,12 point.
- Écarts au-delà du seuil : aucun.
- **Cours ou valeur liquidative** : sur les 9 rendements où l'émetteur publie les deux (AGG, TLT, ESGV), notre rendement s'écarte en moyenne de 0,005 point du cours de marché (au plus 0,02) et de 0,094 point de la valeur liquidative (au plus 0,21) : `adj_close` suit le cours, d'où le cours comme base quand il est publié.

## 2022, l'année au centre des procès

| FNB | Année | Séances (adj_close) | Notre rendement | Publié par l'émetteur | Écart (points) | Dans le seuil |
|---|---|---|---|---|---|---|
| XIU.TO | 2022 | 2021-12-31 → 2022-12-30 | −6,35 % | −6,36 % (fonds, base non précisée) | +0,01 | oui |
| XBB.TO | 2022 | 2021-12-31 → 2022-12-30 | −11,66 % | −11,78 % (fonds, base non précisée) | +0,12 | oui |
| ZST.TO | 2022 | 2021-12-31 → 2022-12-30 | +1,22 % | +1,20 % (valeur liquidative) | +0,02 | oui |
| AGG | 2022 | 2021-12-31 → 2022-12-30 | −13,02 % | −13,03 % (cours de marché) ; −13,06 % (valeur liquidative) | +0,01 | oui |
| TLT | 2022 | 2021-12-31 → 2022-12-30 | −31,23 % | −31,25 % (cours de marché) ; −31,41 % (valeur liquidative) | +0,02 | oui |
| SPY | 2022 | 2021-12-31 → 2022-12-30 | −18,18 % | −18,17 % (valeur liquidative) | −0,01 | oui |
| ESGV | 2022 | 2021-12-31 → 2022-12-30 | −24,04 % | −24,02 % (valeur liquidative) | −0,02 | oui |

## Tous les FNB, toutes les années

| FNB | Année | Séances (adj_close) | Notre rendement | Publié par l'émetteur | Écart (points) | Dans le seuil |
|---|---|---|---|---|---|---|
| XIU.TO | 2022 | 2021-12-31 → 2022-12-30 | −6,35 % | −6,36 % (fonds, base non précisée) | +0,01 | oui |
| XIU.TO | 2023 | 2022-12-30 → 2023-12-29 | +11,85 % | +11,82 % (fonds, base non précisée) | +0,03 | oui |
| XIU.TO | 2024 | 2023-12-29 → 2024-12-31 | +20,73 % | +20,77 % (fonds, base non précisée) | −0,04 | oui |
| XIU.TO | 2025 | 2024-12-31 → 2025-12-31 | +28,89 % | +28,89 % (fonds, base non précisée) | +0,00 | oui |
| XBB.TO | 2022 | 2021-12-31 → 2022-12-30 | −11,66 % | −11,78 % (fonds, base non précisée) | +0,12 | oui |
| XBB.TO | 2023 | 2022-12-30 → 2023-12-29 | +6,64 % | +6,61 % (fonds, base non précisée) | +0,03 | oui |
| XBB.TO | 2024 | 2023-12-29 → 2024-12-31 | +4,00 % | +4,12 % (fonds, base non précisée) | −0,12 | oui |
| XBB.TO | 2025 | 2024-12-31 → 2025-12-31 | +2,59 % | +2,57 % (fonds, base non précisée) | +0,02 | oui |
| ZST.TO | 2022 | 2021-12-31 → 2022-12-30 | +1,22 % | +1,20 % (valeur liquidative) | +0,02 | oui |
| ZST.TO | 2023 | 2022-12-30 → 2023-12-29 | +5,38 % | +5,30 % (valeur liquidative) | +0,08 | oui |
| ZST.TO | 2024 | 2023-12-29 → 2024-12-31 | +5,21 % | +5,30 % (valeur liquidative) | −0,09 | oui |
| ZST.TO | 2025 | 2024-12-31 → 2025-12-31 | +3,09 % | +3,10 % (valeur liquidative) | −0,01 | oui |
| AGG | 2022 | 2021-12-31 → 2022-12-30 | −13,02 % | −13,03 % (cours de marché) ; −13,06 % (valeur liquidative) | +0,01 | oui |
| AGG | 2023 | 2022-12-30 → 2023-12-29 | +5,66 % | +5,65 % (cours de marché) ; +5,58 % (valeur liquidative) | +0,01 | oui |
| AGG | 2024 | 2023-12-29 → 2024-12-31 | +1,31 % | +1,31 % (cours de marché) ; +1,37 % (valeur liquidative) | +0,00 | oui |
| AGG | 2025 | 2024-12-31 → 2025-12-31 | +7,19 % | +7,19 % (cours de marché) ; +7,19 % (valeur liquidative) | +0,00 | oui |
| TLT | 2022 | 2021-12-31 → 2022-12-30 | −31,23 % | −31,25 % (cours de marché) ; −31,41 % (valeur liquidative) | +0,02 | oui |
| TLT | 2023 | 2022-12-30 → 2023-12-29 | +2,77 % | +2,77 % (cours de marché) ; +2,96 % (valeur liquidative) | +0,00 | oui |
| TLT | 2024 | 2023-12-29 → 2024-12-31 | −8,05 % | −8,06 % (cours de marché) ; −7,84 % (valeur liquidative) | +0,01 | oui |
| TLT | 2025 | 2024-12-31 → 2025-12-31 | +4,25 % | +4,25 % (cours de marché) ; +4,17 % (valeur liquidative) | +0,00 | oui |
| SPY | 2022 | 2021-12-31 → 2022-12-30 | −18,18 % | −18,17 % (valeur liquidative) | −0,01 | oui |
| SPY | 2023 | 2022-12-30 → 2023-12-29 | +26,18 % | +26,12 % (valeur liquidative) | +0,06 | oui |
| SPY | 2024 | 2023-12-29 → 2024-12-31 | +24,89 % | +24,87 % (valeur liquidative) | +0,02 | oui |
| SPY | 2025 | 2024-12-31 → 2025-12-31 | +17,72 % | +17,73 % (valeur liquidative) | −0,01 | oui |
| ESGV | 2022 | 2021-12-31 → 2022-12-30 | −24,04 % | −24,02 % (valeur liquidative) | −0,02 | oui |
| ESGV | 2023 | 2022-12-30 → 2023-12-29 | +30,79 % | +30,76 % (valeur liquidative) | +0,03 | oui |
| ESGV | 2024 | 2023-12-29 → 2024-12-31 | +24,69 % | +24,69 % (cours de marché) ; +24,68 % (valeur liquidative) | +0,00 | oui |

Écart = notre rendement moins celui de l'émetteur, sur la base de comparaison (la première citée).

## Écarts au-delà du seuil

Aucun.

## Sources

| FNB | Émetteur | Base publiée | Document | Adresse |
|---|---|---|---|---|
| XIU.TO | BlackRock Canada (iShares) | Rendement « Fund » sans base précisée (la fiche ne publie aucun rendement au cours de marché) | Fiche du fonds (octobre 2026), « CALENDAR YEAR PERFORMANCE (% CAD) », données au 31 octobre 2026 | <https://www.blackrock.com/ca/investors/en/literature/fact-sheet/xiu-ishares-s-p-tsx-60-index-etf-fund-fact-sheet-en-ca.pdf> |
| XBB.TO | BlackRock Canada (iShares) | Rendement « Fund » sans base précisée (la fiche ne publie aucun rendement au cours de marché) | Fiche du fonds (octobre 2026), « CALENDAR YEAR PERFORMANCE (% CAD) », données au 31 octobre 2026 | <https://www.blackrock.com/ca/investors/en/literature/fact-sheet/xbb-ishares-core-canadian-universe-bond-index-etf-fund-fact-sheet-en-ca.pdf> |
| ZST.TO | BMO Gestion mondiale d'actifs | Valeur liquidative (« Returns are calculated using the ETF's net asset value (NAV) »), après frais, parts en CAD | Aperçu du FNB (ETF Facts), parts en CAD, 23 janvier 2026, « Year-by-year returns » | <https://fundfacts.bmo.com/EtfEnglish/BMO_Ultra_Short-Term_Bond_ETF-EN-CAD_Units.pdf> |
| AGG | BlackRock (iShares) | Valeur liquidative et cours de marché (« market price returns are calculated using the closing price ») | Fiche du fonds (Fact Sheet as of September 30, 2026), « CALENDAR YEAR PERFORMANCE (%) » | <https://www.ishares.com/us/literature/fact-sheet/agg-ishares-core-u-s-aggregate-bond-etf-fund-fact-sheet-en-us.pdf> |
| TLT | BlackRock (iShares) | Valeur liquidative et cours de marché (« market price returns are calculated using the closing price ») | Fiche du fonds (Fact Sheet as of September 30, 2026), « CALENDAR YEAR PERFORMANCE (%) » | <https://www.ishares.com/us/literature/fact-sheet/tlt-ishares-20-year-treasury-bond-etf-fund-fact-sheet-en-us.pdf> |
| SPY | State Street Global Advisors (SPDR) | Valeur liquidative (« net asset value per Unit ('NAV') ») : rendement sur un an au 31 décembre, colonne « Past One Year », ligne « Return Before Taxes » du prospectus de l'année suivante | Prospectus (formulaire 485BPOS) du 27 janvier 2023, « Average Annual Total Returns (for periods ending December 31, 2022) » | <https://www.sec.gov/Archives/edgar/data/884394/000119312523017786/d449477d485bpos.htm> |
| SPY | State Street Global Advisors (SPDR) | Valeur liquidative (« net asset value per Unit ('NAV') ») : rendement sur un an au 31 décembre, colonne « Past One Year », ligne « Return Before Taxes » du prospectus de l'année suivante | Prospectus (formulaire 485BPOS) du 26 janvier 2024, « Average Annual Total Returns (for periods ending December 31, 2023) » | <https://www.sec.gov/Archives/edgar/data/884394/000119312524016801/d109104d485bpos.htm> |
| SPY | State Street Global Advisors (SPDR) | Valeur liquidative (« net asset value per Unit ('NAV') ») : rendement sur un an au 31 décembre, colonne « Past One Year », ligne « Return Before Taxes » du prospectus de l'année suivante | Prospectus (formulaire 485BPOS) du 27 janvier 2025, « Average Annual Total Returns (for periods ending December 31, 2024) » | <https://www.sec.gov/Archives/edgar/data/884394/000119312525013181/d875286d485bpos.htm> |
| SPY | State Street Global Advisors (SPDR) | Valeur liquidative (« net asset value per Unit ('NAV') ») : rendement sur un an au 31 décembre, colonne « Past One Year », ligne « Return Before Taxes » du prospectus de l'année suivante | Prospectus (formulaire 485BPOS) du 26 janvier 2026, « Average Annual Total Returns (for periods ending December 31, 2025) » | <https://www.sec.gov/Archives/edgar/data/884394/000119312526022316/d77353d485bpos.htm> |
| ESGV | Vanguard | Valeur liquidative (« performance of the Fund's ETF shares (based on NAV) ») ; cours de marché seulement pour 2024 (tableau des rendements annuels moyens sur 1 an au 31 décembre 2024) | Prospectus du 19 décembre 2025 (complété le 30 juin 2026), « Annual Total Returns — Vanguard ESG U.S. Stock ETF Shares » ; 2025 n'y figure pas encore | <https://fund-docs.vanguard.com/p4393.pdf> |

Non relevés :

- **QQQ**, Invesco : Aucun rendement par année civile publié dans les pages lues (page du fonds, page de performance, perspectives trimestrielles au 30 septembre 2026 : rendements cumulés et annualisés seulement) ; la fiche PDF américaine n'a pas pu être obtenue.
- **GLD**, State Street Global Advisors (SPDR) : La fiche (septembre 2026) et la page du fonds ne publient que des rendements par période (trimestre, depuis le début de l'année, 1, 3, 5 et 10 ans), pas par année civile.

## Méthode

- Notre rendement : `adj_close` de `prices_daily.csv`, dans la devise de cotation du FNB, de la dernière séance de l'année précédente à la dernière séance de l'année, sur les seules séances du titre (`pipeline.donnees.charger_adj_close_cotation` : ni conversion en CAD, ni report, ni alignement sur les séances américaines). Le pipeline, lui, convertit en CAD : cette validation porte sur la donnée de départ, avant conversion.
- Rendement de l'émetteur : relevé tel que publié (arrondi à 1 ou 2 décimales), avec la citation de la ligne du document dans `donnees_externes/rendements_emetteurs.json`.
- Intervalle de confiance du taux : Wilson à 95 % (`validation.evaluation.intervalle_wilson`).
- Un écart n'est jamais retouché : il est expliqué. Le seuil ne change pas après le calcul.
