# Astrée : le Tribunal des décisions d'investissement

[![Tests](https://github.com/yanisbenboudaoud/Astree/actions/workflows/tests.yml/badge.svg)](https://github.com/yanisbenboudaoud/Astree/actions/workflows/tests.yml)

**Avant d'investir, faites le procès de votre décision.** Vous arrivez avec votre propre idée (« 30 % de mon portefeuille en Tesla »). Un Procureur argumente contre, un Avocat pour, un Greffier vérifie chaque chiffre et les règles que vous vous êtes fixées. Vous rendez le verdict.

Projet AlphaForge AI, Datathon PolyFinances 2026.

> Simulation éducative. Aucune transaction réelle. Ceci n'est pas un conseil financier personnalisé.

## Essayer

| Site | Ce qu'il fait | Disponible |
|---|---|---|
| **Démonstration** : <https://yanisbenboudaoud.github.io/Astree/> | Rejoue des procès réellement tenus sur Amazon Bedrock, sans appeler AWS. Seulement les décisions enregistrées | Toujours |
| **Version AWS** : <https://d15khh2djw55mh.cloudfront.net> | Vrais procès en direct sur Bedrock : n'importe quelle décision, questions libres, Pacte construit avec vos réponses | Jusqu'au 16 novembre 2026 (fermeture des comptes AWS du Datathon) |

## Comment ça marche

1. **Le Pacte** : vos règles, déclarées à l'avance (pire baisse tolérée, plafonds, exclusions comme la crypto ou les controverses ESG).
2. **L'Orchestrateur** (un LLM sur Bedrock) choisit les calculs à faire. Chaque résultat, calculé en Python, devient une **pièce** numérotée.
3. **Le Procureur et l'Avocat** (LLM) plaident contre et pour la décision, en citant seulement des pièces.
4. **Le Greffier** (Python, sans LLM) vérifie le Pacte, rejette tout chiffre introuvable dans les pièces et tout conseil déguisé.
5. **Vous** : maintenir la décision, la modifier ou ajuster votre Pacte. Le système ne bloque jamais.

Règle d'or : **Python calcule, le LLM explique.** Aucun chiffre n'est produit par un modèle de langage.

## Preuves

| Promesse | Mesure |
|---|---|
| Aucun chiffre inventé ne passe | **66/66** chiffres inventés détectés, **80/80** arguments valides acceptés |
| Aucun conseil ni promesse | **71/71** arguments légitimes admis ; **47/78** conseils piégés bloqués (limite connue, détaillée) |
| L'orchestrateur s'adapte au profil | Corrélations demandées dans **33/33** procès du profil audacieux, contre **53/138** du profil prudent |
| Nos données concordent avec les émetteurs | **27/27** rendements annuels de FNB à moins de 0,25 point des chiffres publiés |
| AWS a réellement servi | **1 725** appels Bedrock, **1 573** appels Lambda, 0 erreur, **17,29 $** au total |

Intervalles de confiance, ratés et limites de chaque mesure : [`docs/validation/README.md`](docs/validation/README.md#résultats-en-détail).

## Lancer en local

Python 3.14 et Node 20 ou plus. Aucun compte AWS n'est nécessaire.

```bash
git clone https://github.com/yanisbenboudaoud/Astree.git
cd Astree
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
```

```bash
cd frontend && npm install && npm run dev
```

Puis ouvrir <http://localhost:5173>. Windows, appels Bedrock, ajout d'un profil, reproduction des résultats et déploiement : [`docs/INSTALLATION.md`](docs/INSTALLATION.md).

## Pour aller plus loin

| Pour… | Lire |
|---|---|
| **Tout comprendre, quel que soit votre niveau** | [`docs/GUIDE_DU_PROJET.md`](docs/GUIDE_DU_PROJET.md) |
| Le projet **en une page** | [`docs/ONE_PAGER.md`](docs/ONE_PAGER.md) |
| La **documentation technique** (agents, garde-fous, méthode, explicabilité, validations, AWS) | [`docs/DOCUMENTATION_TECHNIQUE.md`](docs/DOCUMENTATION_TECHNIQUE.md) |
| Chaque écran du prototype, en captures | [`docs/preuves/ecrans/`](docs/preuves/ecrans/README.md) |
| Installer, utiliser, déployer ; les données et leurs sources | [`docs/INSTALLATION.md`](docs/INSTALLATION.md) |
| Les règles du projet, son architecture et le contrat JSON (la référence) | [`REFERENCE_DU_PROJET.md`](REFERENCE_DU_PROJET.md) |
| Savoir **pourquoi** l'architecture est ainsi | [`docs/CHOIX_CONCEPTION.md`](docs/CHOIX_CONCEPTION.md) |
| Savoir **ce qui a été construit**, issue par issue | [`docs/journal/`](docs/journal/) |
| Trouver le rôle de **chaque fichier** | [`docs/CARTE_DU_DEPOT.md`](docs/CARTE_DU_DEPOT.md) |
