# AlphaForge AI — le Tribunal des décisions d'investissement

Projet du Datathon PolyFinances 2026. L'utilisateur arrive avec **sa propre décision** (ex. : « 30 % de mon portefeuille en Tesla »). Des agents Amazon Bedrock en font le **procès** à partir de pièces calculées en Python : un Procureur argumente contre, un Avocat pour, un Greffier vérifie le Pacte de l'investisseur et chaque chiffre cité. L'utilisateur rend le verdict.

> Simulation éducative. Aucune transaction réelle. Ceci n'est pas un conseil financier personnalisé.

## Par où commencer

| Pour… | Lire |
|---|---|
| Comprendre le projet, ses règles et son architecture | [`CLAUDE.md`](CLAUDE.md) |
| Savoir **pourquoi** l'architecture est ainsi | [`docs/CHOIX_CONCEPTION.md`](docs/CHOIX_CONCEPTION.md) |
| Savoir **ce qui a été construit**, issue par issue | [`docs/journal/`](docs/journal/) |
| Voir l'interface visée | [`docs/maquette/`](docs/maquette/) |
| Connaître le format de sortie du pipeline | `CLAUDE.md` section 5, et [`docs/exemples/`](docs/exemples/) |

## Démarrage

Prérequis : Python 3.11 ou plus récent (le développement se fait en 3.14 ; la version finale sera alignée sur celle de Lambda, voir #22). Commandes pour PowerShell, sous Windows.

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
| `SOURCE_DONNEES` | Où lire les CSV | `local` (par défaut) ; `s3` pas encore branché (#13) |

Aucune clé AWS dans le code ni dans `.env` : les identifiants viennent de `aws login`.

## Carte du dépôt

État actuel du dépôt. La colonne « Fiche » renvoie à la fiche du journal qui raconte comment le fichier a été construit.

| Chemin | Rôle | Fiche |
|---|---|---|
| `CLAUDE.md` | Règles du projet, architecture du Tribunal, contrat JSON. Lu automatiquement par Claude Code | [000](docs/journal/000-fondations.md) |
| `alphaforge_starter/` | Données de départ fournies (prix, USD/CAD, macro, univers d'actifs). Ne pas modifier | — |
| `pipeline/donnees.py` | Socle de données : `charger_donnees` (prix `adj_close` en CAD sur le calendrier américain), `charger_prix` (devise d'origine), `convertir_en_cad`, `charger_univers` | [004](docs/journal/004-charger-donnees.md), [005](docs/journal/005-conversion-cad.md) |
| `pipeline/indicateurs.py` | Outil 1 `indicateurs_actif` (pièce d'un titre) et fonctions de calcul pures : rendement annualisé, volatilité, pire baisse, rendement 2022, temps de récupération | [006](docs/journal/006-indicateurs-actif.md) |
| `pipeline/correlations.py` | Outil 3 `calculer_correlations` (pièce : corrélation de chaque paire de titres) et `calculer_matrice_correlations` (calcul pur) | [016](docs/journal/016-diversification.md) |
| `pipeline/llm.py` | Client Bedrock commun : `appeler_llm` (texte ou JSON validé), `converser_avec_outils` (*tool use*) | [007](docs/journal/007-client-llm-bedrock.md) |
| `pipeline/debat.py` | Procureur et Avocat : `debattre` (les deux en parallèle), `corriger_argument` (mode correction) | [011](docs/journal/011-procureur-avocat.md) |
| `pipeline/greffier.py` | Greffier, outil 5 `verifier_pacte` : un contrôle par règle du Pacte (une fonction par type de règle), contrôles `biais_survivant` et `performance_passee` | [010](docs/journal/010-greffier.md) |
| `pipeline/chiffres.py` | Greffier, outil 6 `verifier_chiffres` : chaque nombre cité doit exister dans une pièce citée (`CLAUDE.md` §4 ter) ; `trier_arguments` (une relance, puis rejet), `controle_verifier_chiffres` | [010](docs/journal/010-greffier.md) |
| `pipeline/agent_profil.py` | Agent Profil (phase 1) : `lancer_agent_profil` charge et valide le Pacte, puis transforme la demande en `decision` du contrat (`position` ou `reallocation` vers un panier explicite). Demande ambiguë → contrôle `a_verifier` | [008](docs/journal/008-agent-profil.md), [016](docs/journal/016-diversification.md) |
| `pipeline/univers.py` | `charger_univers` : les titres connus du système (liste de dictionnaires, pour les prompts) | [008](docs/journal/008-agent-profil.md) |
| `contrat/schema_sortie.json` | Schéma JSON de la sortie du pipeline | [002](docs/journal/002-contrat-json.md) |
| `contrat/valider.py` | Schéma + renvois entre champs : `valider_contrat`, ou `python -m contrat.valider` | [002](docs/journal/002-contrat-json.md) |
| `pipeline/pacte.py` | Chargement et validation d'un fichier profil : `charger_pacte`, `pacte_pour_contrat`, `piece_pacte` | [003](docs/journal/003-pacte-generique.md) |
| `pipeline/categories.py` | Catégories d'un titre : `categories_du_titre` (titre hors univers signalé, jamais deviné) | [003](docs/journal/003-pacte-generique.md) |
| `personas/*.json` | Profils de test et leur Pacte, au format générique | [003](docs/journal/003-pacte-generique.md) |
| `personas/schema_pacte.json` | Schéma JSON d'un fichier profil, un sous-schéma par type de règle | [003](docs/journal/003-pacte-generique.md) |
| `config/categories.json` | Catégories (`tech`, `crypto`) des règles `plafond`, communes à tous les profils | [003](docs/journal/003-pacte-generique.md) |
| `tests/` | Un fichier de test par module (`test_donnees.py` ↔ `pipeline/donnees.py`). `pytest -m bedrock` pour les vrais appels | — |
| `docs/CHOIX_CONCEPTION.md` | Le *pourquoi* de chaque choix d'architecture | [000](docs/journal/000-fondations.md) |
| `docs/exemples/` | Faux contrats valides (cas 1 et 2), utilisés par l'équipe interface | [002](docs/journal/002-contrat-json.md) |
| `docs/maquette/` | Lien Figma et prototype interactif des 4 écrans | [000](docs/journal/000-fondations.md) |
| `docs/journal/` | Journal de construction : une fiche par issue, et son modèle | [018](docs/journal/018-livrables-documentation.md) |
| `.env.example` | Variables à copier dans `.env` | [007](docs/journal/007-client-llm-bedrock.md) |
| `requirements.txt` / `requirements-dev.txt` | Dépendances épinglées : pipeline déployé dans Lambda / poste local | [007](docs/journal/007-client-llm-bedrock.md) |
| `pyproject.toml` | Configuration de pytest | [007](docs/journal/007-client-llm-bedrock.md) |
| `.github/pull_request_template.md` | Modèle de PR : `Closes #N`, fiche du journal, carte du dépôt | [000](docs/journal/000-fondations.md) |

## Données

Jeu de départ `alphaforge_starter/`, période du 2021-11-12 au 2026-11-12, extrait le 2026-11-13 :
- prix quotidiens : Yahoo Finance, via la bibliothèque yfinance (`adj_close` pour les rendements) ;
- taux USD/CAD : Banque du Canada (API Valet) ;
- taux et indicateurs macroéconomiques : Banque du Canada et FRED.

Sources, traitements, limites et conditions d'utilisation : `alphaforge_starter/README.md` et `alphaforge_starter/sources_metadata.csv`. Les pièges connus de ces données sont dans `CLAUDE.md`, section 6.
