# #169 — Intégration continue : tests Python, tests de l'interface et contrats à chaque push

- **Issue** : #169 · **PR** : #M · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
- `.github/workflows/tests.yml` : workflow GitHub Actions « Tests », lancé à chaque push et à chaque PR, avec trois tâches indépendantes :
  - **Python (pytest)** : Python 3.14, `pip install -r requirements-dev.txt` (versions épinglées, les mêmes que la couche Lambda), puis `pytest -q` ;
  - **Interface (vitest et build)** : Node 22, dans `frontend/` : `npm ci`, `npm test`, puis `npm run build` (qui lance aussi `tsc --noEmit`) ;
  - **Contrats JSON** : `python -m contrat.valider` sur `docs/exemples/contrat_*.json` et sur chaque procès enregistré de `frontend/src/data/proces/`, sauf `index.json` (la liste des procès, pas un contrat).
- `README.md` : badge du workflow sous le titre, et ligne `.github/workflows/tests.yml` dans la carte du dépôt.

## Comment l'utiliser
Rien à lancer : chaque push et chaque PR déclenchent le workflow. Les résultats sont dans l'onglet *Actions* du dépôt, ou :

```bash
gh run list --workflow tests.yml
gh run view <id> --log-failed
```

## Comment vérifier
Les mêmes commandes en local :
- `pytest -q` → 985 réussis, 24 désélectionnés (les tests `bedrock`) ;
- `cd frontend && npm ci && npm test && npm run build` → 144 tests réussis, construction sans erreur ;
- `python -m contrat.valider docs/exemples/contrat_*.json frontend/src/data/proces/2026-*.json` → un ✓ par fichier.

## Choix faits en cours de route
- **Aucun secret AWS** dans le workflow, et aucun n'est nécessaire :
  - les **24 tests qui appellent vraiment Bedrock** (marqueur `bedrock`, dans `test_agent_profil.py`, `test_correlations.py`, `test_contre_interrogatoire.py`, `test_debat.py`, `test_llm.py`, `test_orchestrateur.py`) sont **exclus** par défaut par `pyproject.toml` (`-m 'not bedrock'`) ;
  - les tests qui passent par S3 ou Lambda sont **simulés** : `botocore.stub.Stubber` avec de fausses clés (`test_lambda_tribunal.py`, `test_llm.py`) ou `boto3.client` remplacé (`test_jurisprudence.py`, `test_profils.py`, `test_lambda_tribunal.py`) ;
  - `tests/conftest.py` charge `.env` s'il existe ; ce fichier est ignoré par Git, donc absent en CI. Le pipeline lit alors les CSV du dépôt (`SOURCE_DONNEES` absent = `local`).
  - Vérifié en local : la suite complète passe **sans réseau** (`unshare -rn`), avec un environnement vide (`env -i`, sans `.env`, sans `~/.aws`) : 985 réussis.
- **Trois tâches séparées** plutôt qu'une seule : elles tournent en parallèle, et un échec dit tout de suite quelle partie casse.
- **Node 22** : la version de l'équipe ; `package.json` n'impose pas de version.
- Caches `pip` et `npm` de `setup-python` et `setup-node`, indexés sur les fichiers de dépendances.
- `permissions: contents: read` : le workflow ne peut rien écrire dans le dépôt.

## Limites et suite
- Les tests `bedrock` (vrais appels payants) ne tournent jamais en CI ; ils restent à lancer à la main avec `pytest -m bedrock` et un accès AWS.
- Les vérifications de bout en bout de `frontend/e2e/` (navigateur, Lambda en direct) ne sont pas dans le workflow : elles demandent un navigateur et, pour `direct.mjs`, la Function URL.
- Le workflow ne déploie rien (`deploiement/deployer.py` et `deployer_interface.py` restent manuels).
