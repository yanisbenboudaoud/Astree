# Installer, utiliser et déployer

Le guide complet, repris du [`README.md`](../README.md) qui n'en garde que l'essentiel.

> Simulation éducative. Aucune transaction réelle. Ceci n'est pas un conseil financier personnalisé.

## Installation

Prérequis : **Python 3.14** (la version du runtime Lambda), **Node 20 ou plus** et Git. Aucun compte AWS n'est nécessaire pour les tests ni pour l'interface en mode démonstration.

**1. Récupérer le code et installer Python**

macOS ou Linux :

```bash
git clone https://github.com/yanisbenboudaoud/Astree.git
cd Astree
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Windows (PowerShell) :

```powershell
git clone https://github.com/yanisbenboudaoud/Astree.git
cd Astree
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

**2. Lancer les tests** (sans réseau ni AWS)

```bash
python -m pytest
```

**3. Lancer l'interface** en mode démonstration (procès enregistrés, sans AWS)

```bash
cd frontend
npm install
npm run dev
```

Puis ouvrir <http://localhost:5173>. Le mode direct (branché sur la Lambda) et les autres commandes (`npm test`, `npm run verifier`…) sont dans [`frontend/README.md`](../frontend/README.md).

**4. Facultatif : appeler Bedrock** depuis votre poste (une fois par poste)

```bash
aws login                    # région us-east-1 ; ne crée aucune clé
python -m pytest -m bedrock  # vrais appels Bedrock, payants (quelques cents)
```

Il faut l'AWS CLI (sous Windows : `winget install Amazon.AWSCLI`, puis ouvrir un nouveau terminal). Aucune clé AWS dans le code ni dans `.env` : les identifiants viennent de `aws login`.

Réglages du fichier `.env` :

| Variable | Rôle | Valeur |
|---|---|---|
| `AWS_REGION` | Région Bedrock | `us-east-1` |
| `BEDROCK_MODEL_ID` | Modèle des agents (profil d'inférence) | `global.anthropic.claude-sonnet-5-5` ; `global.anthropic.claude-haiku-5-5` pour les tests |
| `SOURCE_DONNEES` | Où lire les CSV | `local` (par défaut) ; `s3` dans la Lambda, avec `BUCKET_PROJET` = nom du bucket |

Après une mise à jour de `requirements-dev.txt`, relancer `pip install -r requirements-dev.txt`. Sous Windows, ajouter `-X utf8` aux commandes `python` ci-dessous pour afficher ✓ et ✗.

## Utiliser le projet

Les commandes suivantes se lancent depuis la racine du dépôt, l'environnement `.venv` activé.

**Juger une décision** (vrais appels Bedrock ; le contrat JSON sort sur la sortie standard) :

```bash
python -m pipeline robert "Je veux mettre 30 % de mon portefeuille en Tesla"
```

**Valider un contrat JSON** (format de sortie : [`REFERENCE_DU_PROJET.md`](../REFERENCE_DU_PROJET.md), section 5 ; exemples dans [`exemples/`](exemples/)) :

```bash
python -m contrat.valider docs/exemples/contrat_robert.json docs/exemples/contrat_amira.json docs/exemples/contrat_sofia.json
```

### Ajouter un profil

Un fichier JSON, sans une ligne de code ([`REFERENCE_DU_PROJET.md`](../REFERENCE_DU_PROJET.md), section 3).

1. Copier `personas/robert.json` dans `personas/<id>.json` (`<id>` en minuscules, chiffres et `_`, le même que le champ `id`) et changer `id`, `nom`, `profil_risque`, `horizon_ans`, `capital_fictif_cad` et `portefeuille` (titres de `alphaforge_starter/assets_universe.csv`, poids totalisant 1).
2. Écrire les règles du `pacte` avec les types `pire_baisse_max`, `plafond` (catégories de `config/categories.json`), `critere_documentaire` ou `qualitative`, chacune avec `libelle` et `justification`.
3. Vérifier le fichier : `python -c "from pipeline.pacte import charger_pacte; charger_pacte('personas/<id>.json')"` (format : `personas/schema_pacte.json`).
4. Le juger : `python -m pipeline <id> "<demande>"`.

On peut aussi le construire par le questionnaire investisseur : `python -m pipeline.questionnaire <reponses.json>` (exemple : `docs/exemples/reponses_questionnaire.json`), ou par l'écran « Construire mon Pacte » de l'interface.

### Reproduire les résultats

Sans AWS ni Bedrock ; chaque commande régénère son rapport dans `docs/validation/` ([`validation/README.md`](validation/README.md)) :

```bash
python -m validation                        # scénarios de validation et de sensibilité (#15)
python -m validation.evaluation chiffres    # « Trompez le Greffier, 100 fois » (#165)
python -m validation.evaluation cadre       # « Trompez le Greffier », côté cadre (#166)
python -m validation.externe                # nos rendements face à ceux des émetteurs (#168)
python -m contrat.valider frontend/src/data/proces/2026-11-15-032ec3367b19.json
```

Un procès enregistré se relit pièce par pièce, et chaque chiffre se recalcule avec le même code : exemple complet dans [`DOCUMENTATION_TECHNIQUE.md`](DOCUMENTATION_TECHNIQUE.md), section 6.

### Déployer sur AWS

`deploiement/deployer.py` crée ou met à jour toute l'infrastructure (S3, IAM, Lambda, Function URL, Guardrail), de façon idempotente ; `deploiement/tester_function_url.py` lance un procès sur la Lambda déployée ; `deploiement/deployer_interface.py` héberge l'interface (S3 + CloudFront). Paramètres vérifiés (runtime, couche pandas, délai, mémoire, CORS, coûts, IAM) : [`deploiement/README.md`](../deploiement/README.md). Schéma : [`architecture.md`](architecture.md).

## Les deux sites

| | **Version AWS (complète)** | **Version démonstration (durable)** |
|---|---|---|
| Adresse | <https://d15khh2djw55mh.cloudfront.net> | <https://yanisbenboudaoud.github.io/Astree/> |
| Hébergement | S3 + CloudFront ; agents sur Lambda + Bedrock | GitHub Pages, aucun appel à AWS |
| Procès | Vrais procès en direct (20 à 50 s), progression affichée étape par étape | Procès réellement tenus sur Bedrock, enregistrés dans le dépôt, rejoués instantanément |
| Juger **n'importe quelle décision** | Oui | Non : seulement les décisions enregistrées (sinon, l'écran propose la décision enregistrée) |
| Poser une question libre (contre-interrogatoire) | Oui | Non : les questions enregistrées sont affichées telles quelles |
| Construire un Pacte avec vos propres réponses | Oui | Non |
| Disponible | Pendant l'évaluation ; coupée après le jury pour éviter des coûts | Toujours, même après la fermeture du compte AWS |

Sur la version AWS, l'interrupteur en haut à droite, ou `?mode=demo` dans l'adresse, passe aussi en mode démonstration. Dans les deux versions, chaque procès garde la preuve de son passage sur Bedrock (champ `bedrock` : appels par agent, jetons, durée, coût estimé).

## Données

**Jeu de départ** `alphaforge_starter/`, période du 2021-11-12 au 2026-11-12, extrait le 2026-11-13 :
- prix quotidiens : Yahoo Finance, via la bibliothèque yfinance (`adj_close` pour les rendements) ;
- taux USD/CAD : Banque du Canada (API Valet) ;
- taux et indicateurs macroéconomiques : Banque du Canada et FRED.

Sources, traitements, limites et conditions d'utilisation : `alphaforge_starter/README.md` et `alphaforge_starter/sources_metadata.csv`. Pièges connus de ces données : [`REFERENCE_DU_PROJET.md`](../REFERENCE_DU_PROJET.md), section 6.

**Données ajoutées par l'équipe**, dans `donnees_externes/`. Chaque fichier donne, pour chaque valeur, sa source, sa date de relevé, son traitement et ses limites.

| Fichier | Contenu | Relevé le | Sert à |
|---|---|---|---|
| `documents_esg.json` (#17) | Trois documents publics lus dans leur version originale : la fiche « Commonwealth v. Exxon Mobil Corp. » du Sabin Center for Climate Change Law (Columbia Law School), le prospectus simplifié de Vanguard ESG U.S. Stock ETF (ESGV) du 2025-12-19 déposé à la SEC, et les règles de la série d'indices FTSE Global Choice (v5.0, août 2026). Extraits copiés mot pour mot ; résumé et qualification écrits par l'équipe. | 2026-11-14 | Cas 3 (préférences non financières) : le jeu de départ ne contient aucune donnée ESG |
| `frais_fnb.json` (#114) | Ratio des frais des 9 FNB de l'univers, sur la page ou le document officiel de l'émetteur (iShares, Vanguard, BMO, State Street, Invesco) | 2026-11-15 | Afficher le coût annuel des frais. Ils sont déjà prélevés dans `adj_close`, donc jamais déduits une seconde fois |
| `composition_fnb.json` (#116) | Répartitions par secteur (et par pays quand elles sont publiées) des 9 FNB, avec la date affichée par chaque émetteur | 2026-11-15 | Calculer les plafonds par transparence |
| `rendements_emetteurs.json` (#168) | Rendements totaux par année civile, 2022 à 2025, de 7 FNB (XIU, XBB, ZST, AGG, TLT, SPY, ESGV), avec la ligne citée mot pour mot. QQQ et GLD n'en publient pas dans les documents lus | 2026-11-15 | Valider nos rendements calculés : **27/27** dans le seuil de 0,25 point, fixé avant le calcul |

Conditions d'utilisation : de courts extraits et quelques chiffres agrégés, cités avec leur source, à des fins éducatives ; hors du datathon, il faudrait une source sous licence.

## Organisation du dépôt

| Dossier | Contenu |
|---|---|
| `pipeline/` | Le Tribunal en Python : données, outils de calcul (pièces), agents Bedrock (Profil, Orchestrateur, Procureur, Avocat), Greffier, contrat final |
| `contrat/` | Schéma JSON de la sortie et validateur (`python -m contrat.valider`) |
| `personas/`, `config/` | Profils de test et leur Pacte (un fichier JSON par profil), catégories, questionnaire, Pacte vécu |
| `alphaforge_starter/`, `donnees_externes/` | Données de départ fournies ; données ajoutées par l'équipe (ESG, frais, composition et rendements publiés des FNB), sourcées et datées |
| `deploiement/` | Lambda, déploiement AWS idempotent (S3, IAM, Lambda, Function URL, CloudFront), politique IAM |
| `frontend/` | Interface « Astrée » (React + TypeScript + Vite) et ses tests de bout en bout |
| `validation/`, `tests/` | Scénarios de validation et évaluations mesurées des garde-fous ; tests unitaires (un fichier par module) |
| `scripts/` | Précalcul des données de l'interface |
| `docs/` | Guide, documentation technique, one pager, choix de conception, architecture AWS, résultats de validation, maquette, journal |

Le rôle de chaque fichier : [`CARTE_DU_DEPOT.md`](CARTE_DU_DEPOT.md).
