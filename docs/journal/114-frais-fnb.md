# #114 — Frais de gestion des FNB

- **Issue** : #114 · **PR** : à venir · **Statut** : en cours (code, données et tests faits ; Lambda à redéployer et procès de démo à refaire)
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
**Le relevé des frais** : `donnees_externes/frais_fnb.json` (nouveau)
- Le ratio des frais de chacun des 9 FNB de l'univers, relevé le 2026-11-15 sur la page ou le document officiel de l'émetteur, avec l'URL, le document, la date de la donnée et le type de ratio (RFG pour les FNB canadiens, *expense ratio* pour les américains) :

| FNB | Ratio | Document lu |
|---|---|---|
| XIU.TO | 0,17 % (frais de gestion 0,15 %) | Fiche iShares, octobre 2026 |
| XBB.TO | 0,10 % (frais de gestion 0,09 %) | Fiche iShares, octobre 2026 |
| ZST.TO | 0,17 % | Aperçu du FNB (ETF Facts) BMO, 2026-01-23 |
| SPY | 0,0945 % (brut) | Page State Street |
| QQQ | 0,18 % | Page Invesco |
| ESGV | 0,09 % | Fiche Vanguard, septembre 2026 |
| AGG | 0,03 % | Page iShares |
| TLT | 0,15 % | Page iShares |
| GLD | 0,40 % (brut) | Page State Street |

- **Les frais sont déjà dans `adj_close`** (question de l'issue) : un FNB prélève ses frais sur son actif, chaque jour ; sa valeur liquidative, donc son cours, en est déjà nette. Le fichier cite trois preuves des émetteurs : l'aperçu de ZST (« You don't pay these expenses directly. They affect you because they reduce the ETF's returns. »), l'objectif de XIU (« … net of expenses. ») et GLD, qui vend de l'or pour payer ses frais. **Conclusion : on ne les déduit pas une seconde fois ; on affiche leur coût annuel.**
- `sans_frais_de_gestion` : une action ou un cryptoactif détenu en direct (`asset_class` `equity` ou `crypto`) n'a pas de frais de gestion de fonds, donc 0. Ce n'est pas une estimation.

**Le calcul** : `pipeline/frais.py` (nouveau)
- `charger_frais()` : lit et vérifie le relevé (un ratio par FNB entre 0 et 5 %, une URL et une date pour chacun). Sinon : `ErreurDonnees`.
- `ratio_frais(ticker)` : le ratio du relevé pour un FNB, 0 pour un titre détenu en direct, `None` sinon. **Un ratio inconnu n'est jamais deviné.**
- `cout_frais(poids)` : moyenne des ratios pondérée par les poids ; `CoutFrais(None, inconnus)` dès qu'un titre est inconnu.
- `contexte_frais(poids_actuels, poids_apres, capital)` : les valeurs de la pièce et la phrase de méthode.
- `HYPOTHESE_FRAIS`, `LIMITES_FRAIS` (sans chiffre), `source_frais()`.

**Branchement**
- `pipeline/simulation.py` : la pièce de simulation **complète** de `simuler_portefeuille` gagne `frais_annuels` (après la décision) et `frais_annuels_actuels`, en décimales. Avec le capital, elle gagne aussi `frais_annuels_cad`, `frais_annuels_cad_actuels` (arrondis au dollar) et `ecart_frais_annuels_cad`. Si un titre est inconnu, ce côté n'a pas de valeur et `frais_inconnus` liste le titre. La source, le traitement et les limites de la pièce sont complétés. Le rejeu de 2022 ne change pas. Sans relevé, la pièce reste produite sans les frais (même règle que les données macro, #111). `LIMITES_MACRO` dit maintenant « impôts non comptés » : les rendements, eux, sont déjà nets des frais des fonds.
- `pipeline/sources.py` : nouvelle source « Pages et documents des émetteurs des FNB : ratio des frais, relevé par l'équipe », datée du relevé, reliée aux pièces de simulation qui ont des frais.
- `pipeline/tribunal.py` : l'hypothèse « Frais de gestion des FNB : déjà prélevés dans les cours (adj_close), affichés sans être déduits une seconde fois » est ajoutée quand une pièce en parle.
- `pipeline/debat.py` : une consigne demande aux agents de ne jamais retrancher les frais d'un rendement et de citer le coût tel que la pièce le donne. La règle des nombres dérivés du Greffier rejette de toute façon un rendement « après frais » calculé par l'agent.

Résultats pour les profils de test :

| Profil, décision | Frais annuels avant | Après la décision |
|---|---|---|
| Robert, 30 % en TSLA | 0,105 %, 682 $ | 0,0735 %, 478 $ |
| Mateo, 10 % en XOM | 0,106 %, 191 $ | 0,0954 %, 172 $ |
| Amira, panier crypto-tech | 0,0922 %, 37 $ | 0,036 %, 14 $ |

Une action ou un cryptoactif n'a pas de frais de gestion : ces décisions font donc baisser les frais. Cet argument est honnête pour l'Avocat, et il ne dit rien du risque.

## Comment l'utiliser
```python
from pipeline import frais
frais.cout_frais({"XIU.TO": 0.5, "XBB.TO": 0.3, "RY.TO": 0.2})   # CoutFrais(ratio=0.00115, inconnus=())

from pipeline.simulation import piece_simulation
piece = piece_simulation("P2", portefeuille, decision, capital=650_000)
piece["valeurs"]["frais_annuels_cad_actuels"]   # 682 pour Robert
```
Pour mettre à jour un ratio : modifier `donnees_externes/frais_fnb.json` (ratio, document, URL, `date_donnee`, et `date_releve`), puis redéployer la Lambda : le fichier est dans le zip.

## Comment vérifier
```bash
pytest tests/test_frais.py tests/test_simulation.py tests/test_sources.py tests/test_orchestrateur.py
python -m validation     # groupe 11 : frais de gestion des FNB
```
Les tests vérifient :
- un coût pondéré calculé à la main sur un petit portefeuille (50 % × 0,20 % + 30 % × 0,10 % + action = 0,13 %) ;
- l'action et le cryptoactif à zéro ;
- un FNB absent du relevé et un titre hors univers jamais devinés (`frais_inconnus`, aucune valeur de ce côté) ;
- les montants en dollars et leur écart ;
- un relevé invalide refusé (doublon, ratio impossible, source manquante) ;
- chaque FNB de l'univers présent dans le relevé avec sa source ;
- la pièce de Robert ;
- le rejeu de 2022 sans frais ;
- une pièce produite même sans relevé ;
- un coût cité qui passe `verifier_chiffres`, et un rendement « après frais » calculé par l'agent qui est rejeté ;
- la source « frais » et l'hypothèse dans le contrat.

## Choix faits en cours de route
- **Afficher, ne pas déduire** : les cours des FNB sont déjà nets de frais (preuves des émetteurs dans le relevé). Les déduire fausserait les rendements à la baisse.
- **Seulement la pièce de simulation complète** : le coût des frais dépend de la composition du portefeuille, pas de la période. Le répéter dans le rejeu de 2022 n'apporterait rien.
- **Montants en dollars**, comme les comparaisons de #107 : « 682 $ par an » se comprend mieux que « 0,105 % ».
- **Ratios bruts pour SPY et GLD** : State Street publie le ratio brut. Aucune renonciation n'est affichée pour ces fonds.
- **Fichier local, livré dans le zip**, comme le corpus ESG : même code en local et dans Lambda, aucun service de plus.
- Les pages iShares Canada et Vanguard sont chargées en JavaScript : les ratios viennent des fiches PDF des mêmes émetteurs.

## Limites et suite
- **À faire** : redéployer la Lambda (`deploiement/deployer.py --sans-donnees`) et refaire les 7 procès de démo, pour qu'un procès réel contienne le coût des frais (critère de l'issue).
- Les ratios sont ceux d'aujourd'hui : certains ont pu changer pendant la période simulée (la limite de la pièce le dit, sans chiffre).
- Commissions de courtage, écart entre prix d'achat et de vente, frais de garde et impôts ne sont pas comptés.
- Mettre à jour le relevé demande une intervention manuelle : aucune lecture automatique des pages des émetteurs.
