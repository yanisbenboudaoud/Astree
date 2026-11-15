# #111 — Diversité des sources : toutes les sources d'un procès, et les données macro

- **Issue** : #111 · **PR** : #120 (code), #123 (redéploiement et procès de démo) · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
**Partie B : le pouvoir d'achat dans les pièces de simulation**
- **`pipeline/macro.py`** (nouveau) : lit `macro_rates.csv` comme les autres CSV (en local ou dans S3) et renvoie les séries canadiennes en décimales.
  - `inflation(debut, fin)` : IPC du Canada chaîné par années entières, jusqu'au dernier mois publié avant la fin de la période ;
  - `taux_au(serie, date)`, `taux_moyen(serie, debut, fin)` ;
  - `rendement_reel(rendement, inflation)` : relation de Fisher, (1 + r) / (1 + π) − 1 ;
  - `source_macro()`, `HYPOTHESE_TAUX_SANS_RISQUE`.
- **`pipeline/simulation.py`** : les deux pièces de `simuler_portefeuille` gagnent des valeurs calculées en Python, sur le modèle des comparaisons en dollars de #107. Les agents peuvent les citer, et le Greffier les vérifie comme les autres.
  - période complète : `inflation_annuelle`, `rendement_reel_annuel` et `_actuel`, `taux_sans_risque_moyen`, `ratio_sharpe` et `_actuel` ;
  - rejeu de 2022 : `inflation_2022`, `rendement_reel_2022_actuel` et `_apres`, `taux_directeur_debut_2022`, `_fin_2022`, `_moyen_2022`, `obligation_10_ans_debut_2022` et `_fin_2022` ;
  - la source, le traitement et les limites de la pièce sont complétés (`LIMITES_MACRO`, sans chiffre).
- **`pipeline/debat.py`** : une ligne de consigne, « un rendement réel se compare à un rendement réel ; écris « après inflation » ou « réel » ».
- **`pipeline/tribunal.py`** : l'hypothèse du taux sans risque est ajoutée quand une pièce l'utilise.

**Partie A : toutes les sources d'un procès, reliées aux pièces**
- **`pipeline/sources.py`** (nouveau) : `sources_du_proces(contrat)` construit le champ `sources` à partir du dossier. Une source n'y figure que si une pièce ou un contrôle s'en sert : Pacte, réponses de l'investisseur, prix, change, univers d'actifs, données macro, documents ESG, archives des verdicts.
  - Chaque source a `nom`, `fichier` (sauf des réponses), `date_extraction`, `format`, `usage` ;
  - `pieces` : chaque pièce qui l'utilise, avec la **raison de l'orchestrateur** reprise de la trace (ou une raison d'office pour le Pacte, le questionnaire et le Pacte vécu) ;
  - `controles` : les règles du Pacte contrôlées grâce à elle (plafonds → univers, critère documentaire → documents).
- **`pipeline/tribunal.py`** : `sources()` (deux sources fixes) remplacée par `sources_du_proces`, appelée à la fin du procès. **`pipeline/contre_interrogatoire.py`** : la liste est recalculée après chaque question (les dates déjà calculées sont gardées).
- **`contrat/schema_sortie.json`** : `fichier` devient facultatif ; `format`, `usage`, `pieces` et `controles` facultatifs. **`contrat/valider.py`** : `erreurs_sources` (pièces existantes, règles contrôlées, pas de source en double). Les anciens contrats restent valides.
- **`pipeline/proces_verbal.py`** : tableau « Source | Utilisée par (et pourquoi) ». Les procès-verbaux de démo sont régénérés.
- **Interface** : bloc repliable « D'où viennent les données » sur l'écran Tribunal (`ecrans/Tribunal.tsx`). Chaque source montre ses pièces en pastilles cliquables et la raison de chacune ; une raison n'est écrite qu'une fois, sous la première source qui utilise la pièce (`domaine/sources.ts`). Types `SourceContrat` (`api/contrat.ts`) et `SourceDossier` (`api/types.ts`), adaptateur `adapterSource`.

**Sur AWS**
- **Lambda redéployée** (`deploiement/deployer.py --sans-donnees`) : `pipeline/macro.py` et `pipeline/sources.py` sont dans le zip. `macro_rates.csv` était déjà dans `donnees/` du bucket depuis #13 (même taille que le fichier du dépôt) : la Lambda le lit dans S3 comme les autres CSV. Aucun service ni droit IAM de plus.
- **Les 7 procès de démonstration refaits** sur la Lambda redéployée et copiés tels quels depuis `traces/2026-11-15/` du bucket dans `frontend/src/data/proces/` (`index.json` mis à jour), avec leurs procès-verbaux (`python -m pipeline.proces_verbal --demo`). Ils remplacent ceux de la fiche 107. Chaque copie S3 est identique à la réponse reçue.

| Procès | Profil, décision | Sources | Ce qu'il montre |
|---|---|---|---|
| `2026-11-15-13325b58d2b9` | Robert, 30 % en TSLA | 6 | archives des verdicts → P6, avec la raison de l'orchestrateur ; inflation et rendement réel dans P2 et P3 ; une correction du Greffier |
| `2026-11-15-4d25fab26751` | Robert, 25 % en TSLA | 6 | deux arguments renvoyés par le Greffier puis corrigés |
| `2026-11-15-6f16a95962c3` | Amira, panier crypto-tech | 6 | l'Avocat cite le rendement après inflation (+12,9 %/an), vérifié par le Greffier |
| `2026-11-15-78210ebf41ab` | Mateo, 10 % en XOM | 7 | documents ESG ; un argument sans signe « − » renvoyé, puis rejeté |
| `2026-11-15-9c273b4e1dab` | Robert, Pacte vécu | 7 | réponses de l'investisseur parmi les sources |
| `2026-11-15-c96a8185f784` | Amira, Pacte vécu | 7 | idem, rendement après inflation cité |
| `2026-11-15-dd412c702126` | Mateo, Pacte vécu | 8 | les 8 sources possibles : Pacte, réponses, prix, change, univers, macro, documents ESG, archives |

Tous passent `python -m contrat.valider` ; 100 % des chiffres affichés sont vérifiés.
- Tests ajustés au contenu des nouveaux procès : `frontend/src/test/*.test.ts` (identifiants, nombre d'arguments, motifs des corrections), `tests/test_sources.py` (les procès de démo contiennent maintenant les données macro). `domaine/debat.ts` range aussi « varié presque indépendamment de… » dans le point « diversification ».

## Comment l'utiliser
```python
from pipeline.simulation import piece_simulation
piece = piece_simulation("P3", portefeuille, decision, periode="2022")
piece["valeurs"]["rendement_reel_2022_actuel"]   # −0,0837 pour Robert

from pipeline.sources import sources_du_proces
contrat["sources"] = sources_du_proces(contrat)  # fait par juger_decision et interroger
```

## Comment vérifier
```bash
pytest tests/test_macro.py tests/test_simulation.py tests/test_sources.py tests/test_proces_verbal.py
python -m validation     # groupe 10 : pouvoir d'achat et taux
cd frontend && npm test  # tests/sources.test.ts
```
Les tests vérifient : l'inflation de 2022 (6,3 %) et de la période complète (septembre 2021 → septembre 2026, 3,54 %/an) ; la relation de Fisher ; le ratio de Sharpe refait à partir de la pièce (Robert, 30 % en TSLA : 1,09 → 0,46) ; qu'un rendement réel cité passe `verifier_chiffres` et qu'une soustraction (−2,6 − 6,3 = −8,9 %) est rejetée ; qu'une pièce sans données macro reste valide ; les sources de Robert, Mateo (documents ESG) et du Pacte vécu (réponses) ; que chaque outil de l'orchestrateur a ses sources.

## Choix faits en cours de route
- **Taux sans risque : taux directeur moyen de la Banque du Canada** (l'équivalent d'un placement liquide en CAD), plutôt que l'obligation à 2 ans. Écrit dans les hypothèses du procès.
- **Ratio de Sharpe avec le rendement annualisé composé** de la pièce, pour qu'un lecteur puisse le refaire à la main ; la moyenne arithmétique des rendements quotidiens donnerait un chiffre un peu différent, que la pièce n'affiche pas.
- **Publication de l'IPC** (`CLAUDE.md`, section 6) : on mesure après coup le pouvoir d'achat d'une période terminée, avec des valeurs publiées avant l'extraction des données. Pour la période complète, l'inflation s'arrête au dernier mois publié (septembre 2026) : la période d'inflation est décalée de deux mois sur celle des prix, ce que dit le traitement de la pièce.
- **Données macro facultatives** : si `macro_rates.csv` manque (par exemple dans le bucket), la pièce reste celle des prix seuls et le message va dans CloudWatch. La pièce obligatoire du procès ne doit pas échouer pour une donnée de contexte.
- **La raison vient de la trace**, pas d'un nouvel appel à Bedrock : elle a été écrite au moment de choisir l'outil, avant le calcul.
- **Univers d'actifs relié à toutes les pièces de prix** : il donne la devise de chaque titre (conversion en CAD), en plus des catégories des plafonds.
- **`valeur_affichee` inchangée** : les nouveaux chiffres se lisent en ouvrant la pièce.

## Limites et suite
- La Lambda a été déployée depuis la branche de #120 (identique à `main` plus ce travail) : la redéployer depuis `main` après la fusion ne change rien au code.
- Les procès archivés avant #111 (S3, `traces/`) n'ont ni données macro ni sources reliées : relus, le bloc de l'interface montre leurs deux sources, sans pièces.
- Le Greffier rejette « aurait perdu 3 819 $ » sans signe : « perdu » n'est pas dans la liste des mots de baisse de la règle 4 (section 4 ter). Le rejet est fidèle à la règle ; l'élargir serait une décision d'équipe.
- Dans l'interface, une question libre ajoute des pièces sans mettre à jour le bloc des sources (la route `/question` ne renvoie pas les sources) ; elles sont à jour dans le contrat archivé et le procès-verbal.
- Rendre « Préserver mon capital » mesurable (nouveau type de règle) et chiffrer l'incertitude (plusieurs périodes, fourchettes) restent hors périmètre.
