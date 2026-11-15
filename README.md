# AlphaForge AI - le Tribunal des décisions d'investissement

Projet du Datathon PolyFinances 2026. L'utilisateur arrive avec **sa propre décision** (ex. : « 30 % de mon portefeuille en Tesla »). Des agents Amazon Bedrock en font le **procès** à partir de pièces calculées en Python : un Procureur argumente contre, un Avocat pour, un Greffier vérifie le Pacte de l'investisseur et chaque chiffre cité. L'utilisateur rend le verdict.

> Simulation éducative. Aucune transaction réelle. Ceci n'est pas un conseil financier personnalisé.

## Par où commencer

| Pour… | Lire |
|---|---|
| **Tout comprendre, quel que soit votre niveau** | [`docs/GUIDE_DU_PROJET.md`](docs/GUIDE_DU_PROJET.md) |
| Comprendre le projet, ses règles et son architecture | [`CLAUDE.md`](CLAUDE.md) |
| Savoir **pourquoi** l'architecture est ainsi | [`docs/CHOIX_CONCEPTION.md`](docs/CHOIX_CONCEPTION.md) |
| Savoir **ce qui a été construit**, issue par issue | [`docs/journal/`](docs/journal/) |
| Voir l'interface visée, ou la lancer | [`docs/maquette/`](docs/maquette/), [`frontend/`](frontend/README.md) |
| Connaître le format de sortie du pipeline | `CLAUDE.md` section 5, et [`docs/exemples/`](docs/exemples/) |

## Démarrage

**Essayer sans rien installer** : l'interface est hébergée sur AWS (S3 + CloudFront, #135) à l'adresse **https://d15khh2djw55mh.cloudfront.net**. Pour l'instant, elle rejoue des procès réellement tenus par les agents (mode démonstration) ; le mode direct suivra (#141). Pour la mettre à jour : `deploiement\deployer_interface.py` ([`deploiement/README.md`](deploiement/README.md), « Interface hébergée »).

Prérequis : **Python 3.14**, la version du runtime Lambda (`python3.14`, #22). Commandes pour PowerShell, sous Windows. Après une mise à jour de `requirements-dev.txt`, relancer la commande `pip install` ci-dessous.

```powershell
py -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
Copy-Item .env.example .env
.venv\Scripts\python -m pytest          # tests unitaires, sans réseau ni AWS
```

Pour appeler Bedrock (une fois par poste) :

```powershell
winget install Amazon.AWSCLI            # puis ouvrir un nouveau terminal
aws login                               # région us-east-1 ; ne crée aucune clé
.venv\Scripts\python -m pytest -m bedrock   # vrais appels Bedrock (payants, quelques cents)
```

Valider un contrat JSON (`-X utf8` est nécessaire sous Windows pour afficher ✓ et ✗) :

```powershell
.venv\Scripts\python -X utf8 -m contrat.valider docs\exemples\contrat_robert.json docs\exemples\contrat_amira.json docs\exemples\contrat_sofia.json
```

### Configuration (`.env`)

| Variable | Rôle | Valeur |
|---|---|---|
| `AWS_REGION` | Région Bedrock | `us-east-1` |
| `BEDROCK_MODEL_ID` | Modèle des agents (profil d'inférence) | `global.anthropic.claude-sonnet-5-5` ; `global.anthropic.claude-haiku-5-5` pour les tests |
| `SOURCE_DONNEES` | Où lire les CSV | `local` (par défaut) ; `s3` dans la Lambda (#13), avec `BUCKET_PROJET` = nom du bucket |

Aucune clé AWS dans le code ni dans `.env` : les identifiants viennent de `aws login`.

## Carte du dépôt

État actuel du dépôt. La colonne « Fiche » renvoie à la fiche du journal qui raconte comment le fichier a été construit.

| Chemin | Rôle | Fiche |
|---|---|---|
| `CLAUDE.md` | Règles du projet, architecture du Tribunal, contrat JSON. Lu automatiquement par Claude Code | [000](docs/journal/000-fondations.md) |
| `alphaforge_starter/` | Données de départ fournies (prix, USD/CAD, macro, univers d'actifs). Ne pas modifier | — |
| `pipeline/donnees.py` | Socle de données : `charger_donnees` (prix `adj_close` en CAD sur le calendrier américain), `charger_prix` (devise d'origine), `convertir_en_cad`, `charger_univers`, `charger_volumes` (volume et close, séances du titre, #117) ; lecture des CSV en local ou dans S3 (`SOURCE_DONNEES`) | [004](docs/journal/004-charger-donnees.md), [005](docs/journal/005-conversion-cad.md), [013](docs/journal/013-deploiement-aws.md) |
| `pipeline/macro.py` | Données macro du Canada (`macro_rates.csv`, Banque du Canada) : `inflation` (IPC, années entières jusqu'au dernier mois publié à la date de la mesure), `date_publication_ipc` (fin du mois suivant), `taux_au`, `taux_moyen`, `rendement_reel` (relation de Fisher) | [111](docs/journal/111-diversite-des-sources.md), [113](docs/journal/113-inflation-rendement-reel.md) |
| `pipeline/frais.py` | Frais de gestion des FNB (`donnees_externes/frais_fnb.json`) : `ratio_frais`, `cout_frais` (moyenne pondérée ; un titre inconnu n'est jamais deviné), `contexte_frais` (coût annuel avant et après, en dollars), ajouté à la pièce de simulation sans être déduit | [114](docs/journal/114-frais-fnb.md) |
| `pipeline/sources.py` | `sources_du_proces` : les sources réellement utilisées par un procès, chacune avec les pièces qui l'utilisent, la raison de l'orchestrateur (ou d'office) et les règles du Pacte contrôlées grâce à elle | [111](docs/journal/111-diversite-des-sources.md) |
| `pipeline/indicateurs.py` | Outil 1 `indicateurs_actif` (pièce d'un titre) et fonctions de calcul pures : rendement annualisé, volatilité, pire baisse, rendement 2022, temps de récupération | [006](docs/journal/006-indicateurs-actif.md) |
| `pipeline/documents.py` | Recherche documentaire `rechercher_documents` : pièce `documentaire` sur un titre et un critère extra-financier, tirée du corpus ESG ; sans document, « source manquante » | [017](docs/journal/017-preferences-non-financieres.md) |
| `donnees_externes/documents_esg.json` | Corpus ESG constitué par l'équipe : documents publics sourcés et datés, extraits mot pour mot, limites | [017](docs/journal/017-preferences-non-financieres.md) |
| `donnees_externes/frais_fnb.json` | Ratio des frais des 9 FNB de l'univers, relevé sur les pages et documents des émetteurs (source, date, conditions d'utilisation), et preuve que ces frais sont déjà dans les cours | [114](docs/journal/114-frais-fnb.md) |
| `pipeline/liquidite.py` | Outil 9 `mesurer_liquidite` : jours de bourse pour revendre chaque ligne après la décision sans dépasser 10 % des montants échangés par jour (volume × close en CAD, volume crypto déjà en dollars) ; fonctions pures `valeur_echangee_moyenne` et `jours_pour_vendre` | [117](docs/journal/117-risque-de-liquidite.md) |
| `pipeline/jurisprudence.py` | Outil 7 `consulter_jurisprudence` : relit les verdicts archivés du profil jugé (`verdicts/<profil>/`, local ou S3) et compte, par règle du Pacte, les violations passées et le verdict choisi ; sans archive, « aucun procès archivé » | [056](docs/journal/056-jurisprudence.md) |
| `pipeline/calibrage.py` | Pacte vécu : `episodes_de_baisse` (un vrai jour de marché par niveau, sans la suite), `prochaine_question` (dichotomie), `calibrer` (seuil mesuré, pièce `declaree`, profil au seuil mesuré), `reponses_demo` | [068](docs/journal/068-pacte-vecu.md) |
| `config/calibrage.json` | Niveaux de baisse proposés (−5 % à −50 %) et séries de référence du Pacte vécu | [068](docs/journal/068-pacte-vecu.md) |
| `pipeline/questionnaire.py` | Questionnaire investisseur : `questions()` (prêtes à afficher), `profil_depuis_reponses` (réponses → fichier profil valide, sans LLM), `detail_bareme` (quelle réponse a produit quelle règle), `controle_experience` ; `python -m pipeline.questionnaire <reponses.json>` ; `contradictions` (réponses incompatibles), `piece_questionnaire` (pièce `declaree` du procès) et `controles_questionnaire` (contrôles `coherence_questionnaire`) | [084](docs/journal/084-questionnaire-investisseur.md), [085](docs/journal/085-contradictions-questionnaire.md) |
| `config/questionnaire.json` | Les 16 questions (dont « hors du Canada », facultative, #112), leurs choix et le barème (plafonds de capacité, resserrement, arrondi, tranches de `profil_risque`) et les règles de contradiction ; étiquette `hypothese` | [084](docs/journal/084-questionnaire-investisseur.md), [085](docs/journal/085-contradictions-questionnaire.md), [112](docs/journal/112-geographie-et-devise.md) |
| `pipeline/correlations.py` | Outil 3 `calculer_correlations` (pièce : corrélation de chaque paire de titres) et `calculer_matrice_correlations` (calcul pur) | [016](docs/journal/016-diversification.md) |
| `pipeline/llm.py` | Client Bedrock commun : `appeler_llm` (texte ou JSON validé), `converser_avec_outils` (*tool use*) | [007](docs/journal/007-client-llm-bedrock.md) |
| `pipeline/debat.py` | Procureur et Avocat : `debattre` (les deux en parallèle), `corriger_argument` (mode correction) ; consignes d'écriture des plaidoiries | [011](docs/journal/011-procureur-avocat.md), [107](docs/journal/107-lisibilite-plaidoiries.md) |
| `pipeline/contre_interrogatoire.py` | Contre-interrogatoire : `interroger(contrat, question)` rejoue la boucle (orchestrateur, Procureur et Avocat, Greffier) sur une question posée après le procès ; route `POST /question` de la Lambda | [055](docs/journal/055-contre-interrogatoire.md), [060](docs/journal/060-cadre-simulation.md) |
| `pipeline/greffier.py` | Greffier, outil 5 `verifier_pacte` : un contrôle par règle du Pacte (une fonction par type de règle ; plafonds par transparence des FNB), contrôles `biais_survivant` et `performance_passee` | [010](docs/journal/010-greffier.md), [116](docs/journal/116-composition-fnb.md) |
| `pipeline/chiffres.py` | Greffier, outil 6 `verifier_chiffres` : chaque nombre cité doit exister dans une pièce citée (`CLAUDE.md` §4 ter) ; `trier_arguments` (chiffres et cadre, une relance, puis rejet), `controle_verifier_chiffres` ; `detailler_argument` (nombre par nombre, pour « Trompez le Greffier ») | [010](docs/journal/010-greffier.md), [060](docs/journal/060-cadre-simulation.md), [069](docs/journal/069-trompez-le-greffier.md) |
| `pipeline/cadre_simulation.py` | Greffier, cadre « simulation seulement » : aucun argument ne conseille une transaction ni ne promet l'avenir (`CLAUDE.md` §4 quater) ; `verifier_cadre_simulation`, `controle_cadre_simulation` | [060](docs/journal/060-cadre-simulation.md) |
| `pipeline/agent_profil.py` | Agent Profil (phase 1) : `lancer_agent_profil` charge et valide le Pacte, puis transforme la demande en `decision` du contrat (`position` ou `reallocation` vers un panier explicite). Demande ambiguë → contrôle `a_verifier` | [008](docs/journal/008-agent-profil.md), [016](docs/journal/016-diversification.md) |
| `pipeline/simulation.py` | Outil 2 `simuler_portefeuille` : portefeuille avant et après la décision (`position` ou `reallocation` vers un panier), pièce de la période complète ou du rejeu de 2022, avec ses comparaisons en dollars quand le capital est connu, le pouvoir d'achat (inflation, rendement réel, taux, ratio de Sharpe) et l'exposition en devise (`part_usd`, `exposition_devises`) | [009](docs/journal/009-simuler-portefeuille.md), [016](docs/journal/016-diversification.md), [107](docs/journal/107-lisibilite-plaidoiries.md), [111](docs/journal/111-diversite-des-sources.md), [112](docs/journal/112-geographie-et-devise.md) |
| `pipeline/orchestrateur.py` | Orchestrateur (phase 2) : `instruire_dossier`, le modèle choisit parmi les outils 1 à 4 (décrits pour une position ou pour le panier d'une réallocation) ; garde-fous (liste blanche, budget, raison sans chiffre, simulation obligatoire), pièces numérotées et trace | [012](docs/journal/012-orchestrateur.md), [016](docs/journal/016-diversification.md) |
| `pipeline/tribunal.py` | `juger_decision` : enchaîne les phases du procès et assemble le contrat : Profil, Orchestrateur, débat Procureur / Avocat, puis Greffier (`verifier_pacte`, `verifier_chiffres` et `cadre_simulation` avec une relance), `taille_max_compatible` et les points de bascule calculés par Python. Contrat complet pour une position comme pour une réallocation. Avec `signaler`, publie chaque étape réelle au moment où elle a lieu ; `verifier_avant_proces` contrôle la demande sans Bedrock | [012](docs/journal/012-orchestrateur.md), [021](docs/journal/021-taille-max-compatible.md), [016](docs/journal/016-diversification.md), [061](docs/journal/061-points-de-bascule.md), [090](docs/journal/090-progression-en-direct.md) |
| `pipeline/progression.py` | Progression d'un procès en cours (#90) : `Progression` cumule les signaux de `juger_decision` (phase, étape, activité) dans le document que la Lambda publie dans `progression/<id>.json` ; sûr entre fils d'exécution | [090](docs/journal/090-progression-en-direct.md) |
| `pipeline/taille_max.py` | Outil 4 `taille_max_compatible` : plus grande taille qui respecte les règles calculables du Pacte, recherche par pas de 1 point jugée par `verifier_pacte` | [021](docs/journal/021-taille-max-compatible.md) |
| `pipeline/points_de_bascule.py` | « Qu'est-ce qui changerait la réponse ? » : pour chaque règle calculable en violation, la taille où elle serait conforme et le seuil qui suffirait. Pièce ajoutée d'office avant le débat, et champ `points_de_bascule` du contrat | [061](docs/journal/061-points-de-bascule.md) |
| `pipeline/__main__.py` | Commande locale : `python -m pipeline <id_profil> "<demande>"` (vrais appels Bedrock) | [012](docs/journal/012-orchestrateur.md) |
| `pipeline/univers.py` | `charger_univers` : vue de `donnees.charger_univers` en liste de dictionnaires (pour les prompts) ; respecte `SOURCE_DONNEES` | [008](docs/journal/008-agent-profil.md), [013](docs/journal/013-deploiement-aws.md) |
| `contrat/schema_sortie.json` | Schéma JSON de la sortie du pipeline | [002](docs/journal/002-contrat-json.md), [111](docs/journal/111-diversite-des-sources.md) |
| `contrat/valider.py` | Schéma + renvois entre champs : `valider_contrat`, ou `python -m contrat.valider` | [002](docs/journal/002-contrat-json.md), [065](docs/journal/065-valider-erreurs-outil.md), [111](docs/journal/111-diversite-des-sources.md) |
| `pipeline/pacte.py` | Chargement et validation d'un fichier profil : `charger_pacte`, `pacte_pour_contrat`, `piece_pacte` | [003](docs/journal/003-pacte-generique.md), [115](docs/journal/115-poches-horizons.md) |
| `pipeline/poches.py` | Plusieurs horizons dans un même portefeuille : `profil_de_la_poche` (le profil réduit à la poche jugée, même forme qu'un profil sans poches), `poche_la_plus_prudente`, `regles_de_la_poche` (règles propres, puis communes), `portefeuille_global` | [115](docs/journal/115-poches-horizons.md) |
| `pipeline/categories.py` | Catégories d'un titre : `categories_du_titre` (titre hors univers signalé, jamais deviné), selon la classe d'actifs, le secteur ou le marché de cotation, avec ajouts et retraits ; `nom_categories` (libellés) | [003](docs/journal/003-pacte-generique.md), [112](docs/journal/112-geographie-et-devise.md), [116](docs/journal/116-composition-fnb.md) |
| `pipeline/composition.py` | Plafonds par transparence : `part_des_categories` (un FNB compte pour sa part réelle de chaque catégorie, sinon classement direct signalé), `part_dans_le_fonds`, `piece_composition` (pièce versée d'office : parts avant / après et composition utilisée), `erreurs_compositions` | [116](docs/journal/116-composition-fnb.md) |
| `donnees_externes/composition_fnb.json` | Composition des 9 FNB de l'univers, relevée sur les pages des émetteurs : secteurs (GICS, ICB ou secteurs obligataires), poids d'Alphabet et d'Amazon, pays quand ils sont publiés ; source, date, conditions d'utilisation | [116](docs/journal/116-composition-fnb.md) |
| `personas/*.json` | Profils de test et leur Pacte, au format générique ; un profil peut aussi être écrit par le questionnaire. `sofia.json` : profil à deux poches (mise de fonds dans 3 ans, retraite) | [003](docs/journal/003-pacte-generique.md), [084](docs/journal/084-questionnaire-investisseur.md), [115](docs/journal/115-poches-horizons.md) |
| `personas/schema_pacte.json` | Schéma JSON d'un fichier profil, un sous-schéma par type de règle | [003](docs/journal/003-pacte-generique.md) |
| `config/categories.json` | Catégories des règles `plafond`, communes à tous les profils : `tech`, `crypto`, `energie_fossile`, et géographiques `canada`, `etats_unis`, `hors_canada` ; bloc `transparence` (comment lire la composition d'un FNB) | [003](docs/journal/003-pacte-generique.md), [084](docs/journal/084-questionnaire-investisseur.md), [112](docs/journal/112-geographie-et-devise.md), [116](docs/journal/116-composition-fnb.md) |
| `validation/` | Scénarios de validation et de sensibilité : même décision pour plusieurs profils, seuils, hypothèses, période, robustesse du Greffier, garde-fous, profil inventé, pouvoir d'achat et taux ; graphique de sensibilité. `python -m validation` | [015](docs/journal/015-scenarios-validation.md), [059](docs/journal/059-scenarios-panier-graphique.md), [111](docs/journal/111-diversite-des-sources.md) |
| `tests/` | Un fichier de test par module (`test_donnees.py` ↔ `pipeline/donnees.py`). `pytest -m bedrock` pour les vrais appels | — |
| `docs/GUIDE_DU_PROJET.md` | Guide complet du projet pour tous les niveaux : l'idée sans jargon, le fonctionnement, la visite de chaque dossier, le chemin d'une demande dans le code, la façon de travailler, l'état et les limites | — |
| `docs/guide_jurisprudence.md` | Guide pas à pas de la jurisprudence (#56) et de la correction du validateur (#65) : la boucle complète sur un vrai procès, les choix, les limites, et des questions pour vérifier sa compréhension | [056](docs/journal/056-jurisprudence.md), [065](docs/journal/065-valider-erreurs-outil.md) |
| `docs/CHOIX_CONCEPTION.md` | Le *pourquoi* de chaque choix d'architecture | [000](docs/journal/000-fondations.md) |
| `docs/validation/resultats_scenarios.md` | Tableau des résultats des scénarios (généré par `python -m validation`) | [015](docs/journal/015-scenarios-validation.md) |
| `docs/validation/sensibilite_seuil.svg` | Graphique : taille maximale compatible selon le seuil de pire baisse (généré par `python -m validation`) | [059](docs/journal/059-scenarios-panier-graphique.md) |
| `docs/exemples/` | Faux contrats valides (cas 1 et 2), utilisés par l'équipe interface ; `contrat_sofia.json`, vrai procès d'un profil à poches ; `reponses_questionnaire.json`, exemple de réponses au questionnaire | [002](docs/journal/002-contrat-json.md), [084](docs/journal/084-questionnaire-investisseur.md), [115](docs/journal/115-poches-horizons.md) |
| `docs/maquette/` | Maquette Figma V2 « Astrée » et sa spec d'implémentation (`spec_interface_astree.md`) ; ancienne maquette et prototype des 4 écrans | [000](docs/journal/000-fondations.md), [014](docs/journal/014-interface-astree.md) |
| `docs/journal/` | Journal de construction : une fiche par issue, et son modèle ; `captures/<issue>/`, captures d'écran avant / après citées par une fiche | [018](docs/journal/018-livrables-documentation.md), [103](docs/journal/103-interface-paysage.md) |
| `.env.example` | Variables à copier dans `.env` | [007](docs/journal/007-client-llm-bedrock.md) |
| `requirements.txt` / `requirements-dev.txt` | Dépendances épinglées : zip de la Lambda (boto3, jsonschema) / poste local (dont pandas, numpy et pyarrow, aux versions de la couche Lambda) | [007](docs/journal/007-client-llm-bedrock.md), [022](docs/journal/022-pieges-aws.md) |
| `deploiement/` | Paramètres vérifiés du déploiement (runtime, couche pandas, délai, mémoire, Function URL en `NONE` avec CORS limité à l'interface, zip, coûts), politique IAM de la Lambda, et `tester_function_url.py` pour lancer un procès sur la Lambda déployée | [022](docs/journal/022-pieges-aws.md), [013](docs/journal/013-deploiement-aws.md), [014](docs/journal/014-interface-astree.md) |
| `deploiement/lambda_tribunal.py` | Point d'entrée de la Lambda : `POST /tribunal` (procès, archivé dans `traces/` ; avec `progression: true`, 202 et procès en arrière-plan par invocation asynchrone, #90), `POST /progression` (progression réelle ou contrat, relus dans S3), `POST /verdict` (archivé dans `verdicts/<profil>/`), `POST /question` (contre-interrogatoire), `POST /verifier` (« Trompez le Greffier »), `POST /proces-verbal` (page HTML du procès archivé), `POST /questionnaire` (questions), `POST /profil` (profil créé, rangé dans `profils/`) et `POST /table` (table de décision d'un titre) | [013](docs/journal/013-deploiement-aws.md), [056](docs/journal/056-jurisprudence.md), [057](docs/journal/057-proces-verbal.md), [055](docs/journal/055-contre-interrogatoire.md), [069](docs/journal/069-trompez-le-greffier.md), [087](docs/journal/087-route-profil.md), [090](docs/journal/090-progression-en-direct.md), [086](docs/journal/086-construire-mon-pacte.md) |
| `deploiement/construire_zip.py` / `deploiement/deployer.py` | Construire le zip de la Lambda / déployer ou mettre à jour toute l'infrastructure (S3, IAM, Lambda, Function URL), de façon idempotente | [013](docs/journal/013-deploiement-aws.md) |
| `deploiement/deployer_interface.py` | Héberger l'interface : bucket S3 privé `alphaforge-site-<compte>`, distribution CloudFront (HTTPS, OAC, pages profondes), construction avec l'adresse de la Lambda lue sur le compte, envoi des seuls fichiers modifiés et invalidation, de façon idempotente | [135](docs/journal/135-interface-hebergee.md) |
| `docs/architecture.md` | Schéma d'architecture AWS (pour la doc et la vidéo) et rôle de chaque service | [013](docs/journal/013-deploiement-aws.md) |
| `pipeline/profils.py` | Profils créés par les utilisateurs : `enregistrer_profil` (rangés dans `profils/` du bucket, ou `archives/profils/` en local, sans jamais écraser), `lire_profil_cree`, `nouvel_identifiant_profil`, `appliquer_modifications` (seuils choisis par l'utilisateur, « Choisi par vous ») ; `agent_profil.charger_profil` lit `personas/` puis ces profils | [087](docs/journal/087-route-profil.md), [086](docs/journal/086-construire-mon-pacte.md) |
| `pipeline/vues_interface.py` | Ce que l'interface affiche pour un profil (portefeuille, courbe, indicateurs, Pacte, tables de décision, « Revivez 4 jours »), calculé par les fonctions du pipeline, dont le rendement après inflation (`rendementReel`) ; utilisé par `scripts/build_ui_series.py` et par la Lambda pour un profil créé (`/profil`, `/table`) | [086](docs/journal/086-construire-mon-pacte.md), [113](docs/journal/113-inflation-rendement-reel.md) |
| `pipeline/proces_verbal.py` | Procès-verbal d'un procès : le contrat JSON en page HTML imprimable, produite par Python sans LLM ; `python -m pipeline.proces_verbal <contrat.json>` ou `--demo` | [057](docs/journal/057-proces-verbal.md) |
| `frontend/public/proces-verbaux/` | Procès-verbaux des procès enregistrés de l'interface (mode démonstration), générés par `python -m pipeline.proces_verbal --demo` | [057](docs/journal/057-proces-verbal.md), [107](docs/journal/107-lisibilite-plaidoiries.md) |
| `frontend/` | Interface « Astrée » (React + TypeScript + Vite) : les écrans de la maquette V2, la couche `src/api/` (procès enregistrés ou Lambda en direct, drapeau `VITE_USE_MOCKS`), `e2e/verifier.mjs` (démonstration), `e2e/direct.mjs` (vrais procès sur la Lambda) et `e2e/greffier.mjs` (« Trompez le Greffier »). Écran « Revivez 4 jours » du Pacte vécu (`src/ecrans/Calibrage.tsx`) ; écran « Construire mon Pacte » du questionnaire (`src/ecrans/ConstruireMonPacte.tsx`, `src/api/questionnaire.ts`). Écran « Le Tribunal instruit le dossier » avec la vraie progression du procès (`src/components/ChargementTribunal.tsx`, `src/domaine/progression.ts`). Mode d'emploi : [`frontend/README.md`](frontend/README.md) | [014](docs/journal/014-interface-astree.md), [068](docs/journal/068-pacte-vecu.md), [069](docs/journal/069-trompez-le-greffier.md), [090](docs/journal/090-progression-en-direct.md), [086](docs/journal/086-construire-mon-pacte.md) |
| `scripts/build_ui_series.py` | Précalcule les données chiffrées de l'interface (`frontend/src/data/generated/`) avec les fonctions du pipeline : profils, courbes, tailles de 0 à 50 %, compositions du panier, jours de marché du Pacte vécu, questions du questionnaire et exemple de démonstration ; les calculs eux-mêmes sont dans `pipeline/vues_interface.py` | [014](docs/journal/014-interface-astree.md), [068](docs/journal/068-pacte-vecu.md), [086](docs/journal/086-construire-mon-pacte.md) |
| `pyproject.toml` | Configuration de pytest | [007](docs/journal/007-client-llm-bedrock.md) |
| `.github/pull_request_template.md` | Modèle de PR : `Closes #N`, fiche du journal, carte du dépôt | [000](docs/journal/000-fondations.md) |

## Données

Jeu de départ `alphaforge_starter/`, période du 2021-11-12 au 2026-11-12, extrait le 2026-11-13 :
- prix quotidiens : Yahoo Finance, via la bibliothèque yfinance (`adj_close` pour les rendements) ;
- taux USD/CAD : Banque du Canada (API Valet) ;
- taux et indicateurs macroéconomiques : Banque du Canada et FRED.

Sources, traitements, limites et conditions d'utilisation : `alphaforge_starter/README.md` et `alphaforge_starter/sources_metadata.csv`. Les pièges connus de ces données sont dans `CLAUDE.md`, section 6.

**Données ajoutées par l'équipe : documents ESG** (cas 3, #17), dans `donnees_externes/documents_esg.json`. Le jeu de départ ne contient aucune donnée ESG. Trois documents publics ont été lus dans leur version originale le 2026-11-14 :
- la fiche « Commonwealth v. Exxon Mobil Corp. » du Sabin Center for Climate Change Law (Columbia Law School) ;
- le prospectus simplifié de Vanguard ESG U.S. Stock ETF (ESGV) du 2025-12-19, déposé à la SEC ;
- les règles de la série d'indices FTSE Global Choice (v5.0, août 2026).

Pour chaque document, le fichier donne la source, la date de consultation, des extraits copiés mot pour mot, un résumé et une qualification écrits par l'équipe, le traitement et les limites. Les conditions d'utilisation sont de courts extraits cités avec leur source, à des fins éducatives.

**Données ajoutées par l'équipe : frais des FNB** (#114), dans `donnees_externes/frais_fnb.json`. Le ratio des frais de chacun des 9 FNB de l'univers a été relevé le 2026-11-15 sur la page ou le document officiel de l'émetteur (fiches iShares et Vanguard, aperçu du FNB de BMO, pages State Street, Invesco et iShares États-Unis). Ces frais sont prélevés sur l'actif des fonds : ils sont déjà dans `adj_close`. La simulation affiche leur coût annuel, sans le déduire une seconde fois.

**Données ajoutées par l'équipe : composition des FNB** (#116), dans `donnees_externes/composition_fnb.json`. Les répartitions par secteur (et par pays quand elles sont publiées) des 9 FNB de l'univers ont été relevées le 2026-11-15 sur les pages publiques de leurs émetteurs (State Street, Invesco, Vanguard, BlackRock, BMO), avec la date affichée par chacun. Elles servent à calculer les plafonds par transparence. Conditions d'utilisation : quelques chiffres agrégés cités avec leur source, à des fins éducatives ; hors du datathon, il faudrait une source sous licence.
