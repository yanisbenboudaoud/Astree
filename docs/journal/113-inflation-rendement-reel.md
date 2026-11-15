# #113 — Inflation : rendement réel à partir de `macro_rates.csv`

- **Issue** : #113 · **PR** : #124 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

L'essentiel du calcul a été livré par #111 (fiche [111](111-diversite-des-sources.md)) : lecture de l'IPC, `inflation_annuelle` et `rendement_reel_annuel` (avant / après) dans la pièce de `simuler_portefeuille`, consigne aux agents, vérification par `verifier_chiffres`. Cette fiche décrit ce que #113 ajoute.

## Ce qui a été construit
- **`pipeline/macro.py`** : la règle « jamais avant la publication » (`CLAUDE.md`, section 6) devient explicite au lieu de reposer sur le contenu du fichier.
  - `date_publication_ipc(mois)` : l'IPC du mois M est supposé publié le **dernier jour du mois M + 1** (2026-09 → 2026-10-31) ;
  - `inflation(debut, fin, connu_le=None)` : n'utilise que les mois publiés à `connu_le`, par défaut la date d'extraction de `macro_rates.csv` (mise en cache : un seul accès à `sources_metadata.csv`, même dans S3) ;
  - `Inflation.publie_le` : date de publication supposée du dernier mois utilisé.
- **`pipeline/simulation.py`** : le traitement de la pièce de la période complète dit l'hypothèse (« chaque mois étant supposé publié à la fin du mois suivant »).
- **`pipeline/vues_interface.py`** : `inflation_de_la_periode` et `rendement_reel`. Le profil gagne `inflation` (`annuelle`, `moisDebut`, `moisFin`, `publieLe`) et `actuel.rendementReel` ; chaque entrée des tables de décision et du panier gagne `rendementReel`. Les valeurs sont `null` sans données macro. Fichiers régénérés : `frontend/src/data/generated/` (seuls ces champs changent).
- **Interface** : ligne « Rendement après inflation » sur l'écran Décision, sous le rendement en dollars, avec l'inflation en détail et la bulle ⓘ (`INDICATEURS.rendement_reel`, `domaine/limites.ts`). Elle est absente si le profil n'a pas de données macro (`domaine/decision.ts`, `effetsSurLePacte`). Types `InflationPeriode` et `rendementReel` (`api/types.ts`).
- **Validation** (`validation/scenarios.py`, groupe 10) : rendement réel de la période avant / après ; IPC présent dans le fichier mais pas encore publié.
- **Documentation** : `CLAUDE.md` (section 6 bis), `docs/CHOIX_CONCEPTION.md` (choix 16), carte du `README.md`.

## Comment l'utiliser
```python
from pipeline import macro
mesure = macro.inflation(pd.Timestamp("2021-11-12"), pd.Timestamp("2026-11-12"))
mesure.mois_fin, mesure.publie_le    # ("2026-09", "2026-10-31")
macro.rendement_reel(0.0929, mesure.annuelle)
```
Profil de test prudent : +9,3 % par an en dollars, soit +5,5 % après une inflation de 3,5 % par an. Avec 30 % de TSLA : +12,0 %, soit +8,1 %.

## Comment vérifier
```bash
pytest tests/test_macro.py tests/test_simulation.py tests/test_build_ui_series.py
python -m validation          # groupe 10 : 52/52
cd frontend && npm test       # tests/inflation.test.ts
```
- **Relation de Fisher sur un cas fait à la main** : 10 % en dollars avec 3 % d'inflation, 1,10 ÷ 1,03 − 1 = +6,80 % (et non 7 %).
- **Aucune valeur d'IPC avant sa publication** : un IPC d'octobre 2026 ajouté au fichier est ignoré par une mesure faite le 13 novembre, puis utilisé si la mesure est faite le 30 novembre ; septembre 2026 est utilisé le 31 octobre, pas le 30.
- **Le Greffier** accepte « +5,5 % par an après inflation » et rejette « +8,5 % » (12,0 − 3,5 : nombre dérivé).
- **L'interface affiche le chiffre du Tribunal** : `rendementReel` des tables = `rendement_reel_annuel` de la pièce.
- **Vrais procès** (« terminé quand ») : les 7 procès de démo enregistrés (Bedrock, refaits par la PR #123) ont le rendement réel dans la pièce de simulation et passent le validateur (`test_les_vrais_proces_de_demo_contiennent_le_rendement_reel`). Dans celui du profil audacieux, l'Avocat le cite : « le portefeuille a affiché +16,9 % par an, soit +12,9 % par an après inflation », vérifié par le Greffier. Un procès local de plus (Robert, 30 % en TSLA) passe aussi `python -m contrat.valider`, avec 22 chiffres vérifiés sur 22.

## Choix faits en cours de route
- **Hypothèse prudente de publication** (fin du mois suivant) plutôt que la date exacte de chaque communiqué de Statistique Canada : aucune date de publication n'est fournie, et cette règle ne peut jamais utiliser un mois trop tôt.
- **Date de la mesure = extraction des données**, pas la fin de la période : on mesure après coup le pouvoir d'achat d'une période terminée. L'inflation de 2022 utilise donc l'IPC de décembre 2022, publié en janvier 2023. Les résultats de #111 sont inchangés.
- **Pas de changement du contrat** : le rendement réel reste dans les valeurs des pièces ; l'écran Décision le lit dans ses tables, calculées par les mêmes fonctions. Aucun calcul dans le navigateur.
- **Pas de consigne forçant les agents à citer l'inflation** : ils gardent leurs 2 à 4 arguments les plus forts. La consigne de #111 (« écris « après inflation » ou « réel » ») suffit : l'Avocat du profil audacieux s'en sert.

## Limites et suite
- L'inflation est celle de l'IPC canadien global, pas celle de l'investisseur ; ni frais ni impôts (limites de la pièce).
- **Redéployer la Lambda** pour que les tables d'un profil créé (`/profil`, `/table`) contiennent `rendementReel` ; d'ici là, l'écran Décision n'affiche pas la ligne pour ce profil. Les procès de démo n'ont pas à être refaits : seule la phrase du traitement change.
- Le rendement réel n'apparaît pas encore sur les écrans Portefeuille et Verdict.
