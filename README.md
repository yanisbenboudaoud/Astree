# AlphaForge AI — le Tribunal des décisions d'investissement

Projet du Datathon PolyFinances 2026. L'utilisateur arrive avec **sa propre décision** (ex. : « 30 % de mon portefeuille en Tesla »). Des agents Amazon Bedrock en font le **procès** à partir de pièces calculées en Python : un Procureur argumente contre, un Avocat pour, un Greffier vérifie le Pacte de l'investisseur et chaque chiffre cité. L'utilisateur rend le verdict.

> Simulation éducative. Aucune transaction réelle. Ceci n'est pas un conseil financier personnalisé.

## Par où commencer

| Pour… | Lire |
|---|---|
| Comprendre le projet, ses règles et son architecture | [`CLAUDE.md`](CLAUDE.md) |
| Savoir **pourquoi** l'architecture est ainsi | [`docs/CHOIX_CONCEPTION.md`](docs/CHOIX_CONCEPTION.md) |
| Savoir **ce qui a été construit**, issue par issue | [`docs/journal/`](docs/journal/) |
| Voir l'interface visée, ou la lancer | [`docs/maquette/`](docs/maquette/), [`frontend/`](frontend/README.md) |
| Connaître le format de sortie du pipeline | `CLAUDE.md` section 5, et [`docs/exemples/`](docs/exemples/) |

## Démarrage

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
.venv\Scripts\python -X utf8 -m contrat.valider docs\exemples\contrat_robert.json docs\exemples\contrat_amira.json
```

### Configuration (`.env`)

| Variable | Rôle | Valeur |
|---|---|---|
| `AWS_REGION` | Région Bedrock | `us-east-1` |
| `BEDROCK_MODEL_ID` | Modèle des agents (profil d'inférence) | `us.anthropic.claude-sonnet-5-5` ; `us.anthropic.claude-haiku-5-5` pour les tests |
| `SOURCE_DONNEES` | Où lire les CSV | `local` (par défaut) ; `s3` dans la Lambda (#13), avec `BUCKET_PROJET` = nom du bucket |

Aucune clé AWS dans le code ni dans `.env` : les identifiants viennent de `aws login`.

## Carte du dépôt

État actuel du dépôt. La colonne « Fiche » renvoie à la fiche du journal qui raconte comment le fichier a été construit.

| Chemin | Rôle | Fiche |
|---|---|---|
| `CLAUDE.md` | Règles du projet, architecture du Tribunal, contrat JSON. Lu automatiquement par Claude Code | [000](docs/journal/000-fondations.md) |
| `alphaforge_starter/` | Données de départ fournies (prix, USD/CAD, macro, univers d'actifs). Ne pas modifier | — |
| `pipeline/donnees.py` | Socle de données : `charger_donnees` (prix `adj_close` en CAD sur le calendrier américain), `charger_prix` (devise d'origine), `convertir_en_cad`, `charger_univers` ; lecture des CSV en local ou dans S3 (`SOURCE_DONNEES`) | [004](docs/journal/004-charger-donnees.md), [005](docs/journal/005-conversion-cad.md), [013](docs/journal/013-deploiement-aws.md) |
| `pipeline/indicateurs.py` | Outil 1 `indicateurs_actif` (pièce d'un titre) et fonctions de calcul pures : rendement annualisé, volatilité, pire baisse, rendement 2022, temps de récupération | [006](docs/journal/006-indicateurs-actif.md) |
| `pipeline/documents.py` | Recherche documentaire `rechercher_documents` : pièce `documentaire` sur un titre et un critère extra-financier, tirée du corpus ESG ; sans document, « source manquante » | [017](docs/journal/017-preferences-non-financieres.md) |
| `donnees_externes/documents_esg.json` | Corpus ESG constitué par l'équipe : documents publics sourcés et datés, extraits mot pour mot, limites | [017](docs/journal/017-preferences-non-financieres.md) |
| `pipeline/jurisprudence.py` | Outil 7 `consulter_jurisprudence` : relit les verdicts archivés du profil jugé (`verdicts/<profil>/`, local ou S3) et compte, par règle du Pacte, les violations passées et le verdict choisi ; sans archive, « aucun procès archivé » | [056](docs/journal/056-jurisprudence.md) |
| `pipeline/correlations.py` | Outil 3 `calculer_correlations` (pièce : corrélation de chaque paire de titres) et `calculer_matrice_correlations` (calcul pur) | [016](docs/journal/016-diversification.md) |
| `pipeline/llm.py` | Client Bedrock commun : `appeler_llm` (texte ou JSON validé), `converser_avec_outils` (*tool use*) | [007](docs/journal/007-client-llm-bedrock.md) |
| `pipeline/debat.py` | Procureur et Avocat : `debattre` (les deux en parallèle), `corriger_argument` (mode correction) | [011](docs/journal/011-procureur-avocat.md) |
| `pipeline/greffier.py` | Greffier, outil 5 `verifier_pacte` : un contrôle par règle du Pacte (une fonction par type de règle), contrôles `biais_survivant` et `performance_passee` | [010](docs/journal/010-greffier.md) |
| `pipeline/chiffres.py` | Greffier, outil 6 `verifier_chiffres` : chaque nombre cité doit exister dans une pièce citée (`CLAUDE.md` §4 ter) ; `trier_arguments` (une relance, puis rejet), `controle_verifier_chiffres` | [010](docs/journal/010-greffier.md) |
| `pipeline/agent_profil.py` | Agent Profil (phase 1) : `lancer_agent_profil` charge et valide le Pacte, puis transforme la demande en `decision` du contrat (`position` ou `reallocation` vers un panier explicite). Demande ambiguë → contrôle `a_verifier` | [008](docs/journal/008-agent-profil.md), [016](docs/journal/016-diversification.md) |
| `pipeline/simulation.py` | Outil 2 `simuler_portefeuille` : portefeuille avant et après la décision (`position` ou `reallocation` vers un panier), pièce de la période complète ou du rejeu de 2022 | [009](docs/journal/009-simuler-portefeuille.md), [016](docs/journal/016-diversification.md) |
| `pipeline/orchestrateur.py` | Orchestrateur (phase 2) : `instruire_dossier`, le modèle choisit parmi les outils 1 à 4 (décrits pour une position ou pour le panier d'une réallocation) ; garde-fous (liste blanche, budget, raison sans chiffre, simulation obligatoire), pièces numérotées et trace | [012](docs/journal/012-orchestrateur.md), [016](docs/journal/016-diversification.md) |
| `pipeline/tribunal.py` | `juger_decision` : enchaîne les phases du procès et assemble le contrat : Profil, Orchestrateur, débat Procureur / Avocat, puis Greffier (`verifier_pacte`, `verifier_chiffres` avec une relance), et `taille_max_compatible` calculé par Python. Contrat complet pour une position comme pour une réallocation | [012](docs/journal/012-orchestrateur.md), [021](docs/journal/021-taille-max-compatible.md), [016](docs/journal/016-diversification.md) |
| `pipeline/taille_max.py` | Outil 4 `taille_max_compatible` : plus grande taille qui respecte les règles calculables du Pacte, recherche par pas de 1 point jugée par `verifier_pacte` | [021](docs/journal/021-taille-max-compatible.md) |
| `pipeline/__main__.py` | Commande locale : `python -m pipeline <id_profil> "<demande>"` (vrais appels Bedrock) | [012](docs/journal/012-orchestrateur.md) |
| `pipeline/univers.py` | `charger_univers` : vue de `donnees.charger_univers` en liste de dictionnaires (pour les prompts) ; respecte `SOURCE_DONNEES` | [008](docs/journal/008-agent-profil.md), [013](docs/journal/013-deploiement-aws.md) |
| `contrat/schema_sortie.json` | Schéma JSON de la sortie du pipeline | [002](docs/journal/002-contrat-json.md) |
| `contrat/valider.py` | Schéma + renvois entre champs : `valider_contrat`, ou `python -m contrat.valider` | [002](docs/journal/002-contrat-json.md), [065](docs/journal/065-valider-erreurs-outil.md) |
| `pipeline/pacte.py` | Chargement et validation d'un fichier profil : `charger_pacte`, `pacte_pour_contrat`, `piece_pacte` | [003](docs/journal/003-pacte-generique.md) |
| `pipeline/categories.py` | Catégories d'un titre : `categories_du_titre` (titre hors univers signalé, jamais deviné) | [003](docs/journal/003-pacte-generique.md) |
| `personas/*.json` | Profils de test et leur Pacte, au format générique | [003](docs/journal/003-pacte-generique.md) |
| `personas/schema_pacte.json` | Schéma JSON d'un fichier profil, un sous-schéma par type de règle | [003](docs/journal/003-pacte-generique.md) |
| `config/categories.json` | Catégories (`tech`, `crypto`) des règles `plafond`, communes à tous les profils | [003](docs/journal/003-pacte-generique.md) |
| `validation/` | Scénarios de validation et de sensibilité : même décision pour plusieurs profils, seuils, hypothèses, période, robustesse du Greffier, garde-fous, profil inventé. `python -m validation` | [015](docs/journal/015-scenarios-validation.md) |
| `tests/` | Un fichier de test par module (`test_donnees.py` ↔ `pipeline/donnees.py`). `pytest -m bedrock` pour les vrais appels | — |
| `docs/guide_jurisprudence.md` | Guide pas à pas de la jurisprudence (#56) et de la correction du validateur (#65) : la boucle complète sur un vrai procès, les choix, les limites, et des questions pour vérifier sa compréhension | [056](docs/journal/056-jurisprudence.md), [065](docs/journal/065-valider-erreurs-outil.md) |
| `docs/CHOIX_CONCEPTION.md` | Le *pourquoi* de chaque choix d'architecture | [000](docs/journal/000-fondations.md) |
| `docs/validation/resultats_scenarios.md` | Tableau des résultats des scénarios (généré par `python -m validation`) | [015](docs/journal/015-scenarios-validation.md) |
| `docs/exemples/` | Faux contrats valides (cas 1 et 2), utilisés par l'équipe interface | [002](docs/journal/002-contrat-json.md) |
| `docs/maquette/` | Maquette Figma V2 « Astrée » et sa spec d'implémentation (`spec_interface_astree.md`) ; ancienne maquette et prototype des 4 écrans | [000](docs/journal/000-fondations.md), [014](docs/journal/014-interface-astree.md) |
| `docs/journal/` | Journal de construction : une fiche par issue, et son modèle | [018](docs/journal/018-livrables-documentation.md) |
| `.env.example` | Variables à copier dans `.env` | [007](docs/journal/007-client-llm-bedrock.md) |
| `requirements.txt` / `requirements-dev.txt` | Dépendances épinglées : zip de la Lambda (boto3, jsonschema) / poste local (dont pandas, numpy et pyarrow, aux versions de la couche Lambda) | [007](docs/journal/007-client-llm-bedrock.md), [022](docs/journal/022-pieges-aws.md) |
| `deploiement/` | Paramètres vérifiés du déploiement (runtime, couche pandas, délai, mémoire, Function URL, zip, coûts), politique IAM de la Lambda, et `tester_function_url.py` pour lancer un procès sur la Lambda déployée | [022](docs/journal/022-pieges-aws.md), [013](docs/journal/013-deploiement-aws.md) |
| `deploiement/lambda_tribunal.py` | Point d'entrée de la Lambda : `POST /tribunal` (procès, archivé dans `traces/`) et `POST /verdict` (archivé dans `verdicts/<profil>/`) | [013](docs/journal/013-deploiement-aws.md), [056](docs/journal/056-jurisprudence.md) |
| `deploiement/construire_zip.py` / `deploiement/deployer.py` | Construire le zip de la Lambda / déployer ou mettre à jour toute l'infrastructure (S3, IAM, Lambda, Function URL), de façon idempotente | [013](docs/journal/013-deploiement-aws.md) |
| `docs/architecture.md` | Schéma d'architecture AWS (pour la doc et la vidéo) et rôle de chaque service | [013](docs/journal/013-deploiement-aws.md) |
| `frontend/` | Interface « Astrée » (React + TypeScript + Vite) : les écrans de la maquette V2, la couche `src/api/` (procès enregistrés ou Lambda en direct, drapeau `VITE_USE_MOCKS`) et `e2e/verifier.mjs`. Mode d'emploi : [`frontend/README.md`](frontend/README.md) | [014](docs/journal/014-interface-astree.md) |
| `scripts/build_ui_series.py` | Précalcule les données chiffrées de l'interface (`frontend/src/data/generated/`) avec les fonctions du pipeline : profils, courbes, tailles de 0 à 50 %, compositions du panier | [014](docs/journal/014-interface-astree.md) |
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
