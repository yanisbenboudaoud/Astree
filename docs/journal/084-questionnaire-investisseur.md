# #84 — Questionnaire investisseur : les questions, le barème et le Pacte généré

- **Issue** : #84 · **PR** : à renseigner · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
Jusqu'ici, un Pacte n'existait que si quelqu'un écrivait `personas/<id>.json` à la main. Le questionnaire permet à n'importe quel utilisateur de créer le sien : Python, **sans LLM**, transforme ses réponses en fichier profil valide, et chaque règle a une justification qui cite la réponse d'origine.

- **`config/questionnaire.json`** : les 16 questions de l'issue (sections objectif et horizon, capacité, tolérance, connaissances, préférences), avec leurs choix, `nom_court` (affiché dans les contrôles), ce que chaque question alimente, et le **barème** (étiquette `hypothese`, une justification par bloc) :
  - `capacite.plafonds` : un plafond de pire baisse par réponse (`horizon`, `retraits`, `coussin`, `part_patrimoine`, `revenu`) ; `null` = aucune contrainte ;
  - `tolerance.cran_resserrement` (0,25) : si la personne vend, la baisse acceptée est réduite d'un quart ;
  - `arrondi` (dixième de point, vers le plus prudent) et `profil_risque.tranches`.
  - Les 5 cartes de la question `fourchettes` ne contiennent que des portefeuilles (titres et poids), **aucun chiffre**.
- **`pipeline/questionnaire.py`** :
  - `cartes_fourchettes()` : pour chaque carte, la pire baisse réelle, le pire moment et la valeur finale pour 100 000 $, du 2021-11-12 au 2026-11-12 (mêmes calculs que `simuler_portefeuille` : `valeurs_avant_apres` puis `calculer_pire_baisse`) ;
  - `questions()` : la liste prête à afficher, avec les cartes calculées ;
  - `profil_depuis_reponses(reponses, capital, portefeuille, date, *, identifiant, nom, decision=None)` : le fichier profil, validé par `erreurs_profil` ; `ReponsesInvalides` (une erreur par motif) sinon ;
  - `detail_bareme(reponses, date)` : quelle réponse a produit quelle règle (étiquette `fait` pour une réponse déclarée, `hypothese` quand c'est le barème qui décide), la tolérance, la capacité, le seuil retenu, les contrôles `a_verifier` et les limites à afficher ;
  - `controle_experience(experience, decision)` : contrôle `a_verifier` si la décision porte sur un type de titre jamais détenu (`asset_class` relié aux choix par leurs `classes`) ;
  - commande `python -m pipeline.questionnaire`.
- **`config/categories.json`** : nouvelle catégorie `energie_fossile` (secteur `Energy` : XOM, CNQ.TO, ENB.TO), pour la réponse « Énergies fossiles » à `exclusions`. Données de l'interface régénérées (`frontend/src/data/generated/categories.json` et `univers.json`).
- **`personas/schema_pacte.json`** et **`pipeline/pacte.py`** : `decision_demo` devient facultative (un vrai utilisateur n'a pas de décision de démonstration).
- **`docs/exemples/reponses_questionnaire.json`** : exemple de réponses (profil générique, sans nom de profil de test).

## Comment l'utiliser
```bash
python -m pipeline.questionnaire --questions                          # questions et cartes, en JSON
python -m pipeline.questionnaire docs/exemples/reponses_questionnaire.json   # écrit personas/investisseur_exemple.json
python -m pipeline.questionnaire reponses.json --sortie profil.json   # ailleurs ; --forcer pour remplacer
```
Format d'entrée : `{id, nom, date, capital_cad, portefeuille, reponses, decision?}`. La commande refuse de remplacer un fichier existant sans `--forcer`.

## Comment vérifier
- `pytest tests/test_questionnaire.py` (28 tests) : fonction pure ; chaque profil passe `erreurs_profil` ; réponses « comme » les trois profils de test (mêmes types de règles, même `profil_risque`) ; tolérance de −38,3 % avec un horizon de moins de 3 ans → seuil = plafond de capacité (−10 %) ; « J'ai vendu » en 2022 resserre le seuil même avec « J'en rachète » ; chiffres des cartes égaux à ceux de `simuler_portefeuille` (et d'`indicateurs_actif` pour une carte d'un seul titre) ; exclusion des énergies fossiles + 10 % de XOM → `violation` ; réponse manquante → aucune règle et un contrôle `a_verifier` ; réponses et saisies invalides refusées ; commande.
- **Bout en bout** (vrais appels Bedrock, 2026-11-14) : le profil écrit à partir de `docs/exemples/reponses_questionnaire.json`, jugé sur « Je veux ajouter 10 % d'Exxon Mobil à mon portefeuille », donne un contrat qui passe `python -m contrat.valider` : `exclusion_energie_fossile` en violation (10,0 % au lieu de 0), les autres règles calculables conformes, `taille_max_compatible` 0, point de bascule sur l'exclusion, 23/23 chiffres et 8 arguments vérifiés. Le profil généré n'est pas versionné.

## Choix faits en cours de route
- **Cinq cartes au lieu de quatre** : obligations à très court terme (ZST.TO), 60/40 XBB.TO–XIU.TO, S&P 500 (SPY), Nasdaq-100 (QQQ), et 50 % QQQ, 25 % BTC-USD, 25 % XIU.TO. XBB.TO seul, cité en exemple dans l'issue, est écarté : sa pire baisse (−15,5 %) est pire que celle du 60/40 (−13,2 %), ce qui brouillerait l'ordre du plus prudent au plus audacieux. La carte audacieuse donne une tolérance proche de celle du profil de test audacieux.
- **Les cartes de plusieurs titres** passent par le calcul de `simuler_portefeuille` (rééquilibrage quotidien) : `indicateurs_actif` ne traite qu'un titre. Un test vérifie l'égalité pour les cartes d'un seul titre.
- **Écarts avec les Pactes écrits à la main** (barème non retouché pour coller aux profils de test) : seuil −13,1 % au lieu de −12 % (prudent), −22,2 % au lieu de −20 % (ESG), −38,2 % au lieu de −45 % (audacieux). Les tranches d'horizon donnent 5 à 10 ans au lieu de 8 à 12 (ESG). La question `concentration` porte sur un seul secteur : elle donne « tech ≤ 75 % », pas « tech + crypto ≤ 75 % ». Le questionnaire ajoute une règle qualitative `objectif`.
- **Étiquette du profil** : le schéma impose `fictif` (outil éducatif, rien n'est réel). La provenance fine (`fait` pour une réponse, `hypothese` pour le barème) est dans `detail_bareme` et dans le texte de chaque `justification`.
- **Arrondi vers le prudent** (−13,24 % devient −13,2 %) : le seuil affiché ne dépasse jamais ce que les réponses permettent.
- **Contrôles du questionnaire** (`regle: "questionnaire"`, dans `detail_bareme`) : réponses manquantes, quiz sur la baisse raté (aucune pénalité). Ils ne vont pas encore dans le contrat.
- **Hors périmètre, laissé à #85** : les contradictions entre réponses (`regard_proches` et `reaction` sont enregistrées pour ça), la pièce `declaree` du questionnaire dans le procès et le contrôle `coherence_questionnaire`.

## Limites et suite
- Un questionnaire mesure ce que la personne **dit** ; le Pacte vécu (#68) mesure ce qu'elle **choisit** devant de vrais jours de marché. Les deux restent des indices, pas des garanties.
- Les barèmes sont des hypothèses de l'équipe, pas une méthode réglementaire.
- `controle_experience` n'est pas encore appelé pendant un procès : il le sera quand les réponses deviendront une pièce du procès (#85) ou passeront par la route `/profil` (#87). Écran du questionnaire : #86.
- Les cartes reposent sur une seule période de 5 ans, avec le biais du survivant de l'univers.
