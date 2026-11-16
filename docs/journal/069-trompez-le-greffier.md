# #69 — « Trompez le Greffier » : vérifier en direct un argument tapé par le jury

- **Issue** : #69 · **PR** : #76 · **Statut** : terminée (route à déployer après la fusion)
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
- **`pipeline/chiffres.py`** : `detailler_argument(argument, dossier)`. Même verdict que `verifier_argument` (mêmes règles, `REFERENCE_DU_PROJET.md` §4 ter), mais nombre par nombre : où chaque nombre a été trouvé (pièce citée, « décision » ou « période »), ou son motif exact s'il est introuvable (« « −40 % » introuvable dans P2 », « … (présent dans P3, pièce non citée) »). Renvoie `valide`, `motif`, `nombres`, `compte`.
- **`deploiement/lambda_tribunal.py`** : route `POST /verifier` `{"id", "texte", "pieces"}`. Elle relit le procès archivé (`traces/<date>/<id>.json`, y compris les pièces ajoutées par le contre-interrogatoire) et appelle `detailler_argument`, **sans Bedrock**. Garde-fous du point d'accès public : 600 caractères, 10 pièces, identifiants de pièce au format `P<n>`, 30 vérifications par minute et par adresse IP (`trop_de_verifications`, fenêtre glissante en mémoire de l'instance, réponse 429).
- **Interface** (`frontend/`) :
  - `src/components/TrompezLeGreffier.tsx`, sur l'écran Tribunal : champ « Votre argument », pièces à cocher, et chaque nombre affiché « Trouvé » (vert, avec sa pièce) ou « Introuvable » (rouge, avec le motif), ainsi que le temps de réponse mesuré ;
  - `src/domaine/pieges.ts` : 4 exemples prêts, écrits à partir des pièces du procès affiché : un vrai chiffre, un chiffre inventé, un arrondi faux, la mauvaise pièce. Le module ne vérifie rien : c'est le Greffier qui juge ;
  - `src/api/tribunal.ts` : `verifierArgument`, `greffierEnDirect` ;
  - `src/api/adaptateur.ts` : `corrections`, les arguments renvoyés par le Greffier pendant le procès (trace `bedrock_correction`), affichés avec le motif et la version corrigée ;
  - date de signature du Pacte sous le constat (« Règle que vous avez signée le 14 nov. 2026 (Pacte §1) : « … » »).
- **Procès de démonstration remplacés** par des procès archivés par la Lambda, copiés tels quels depuis S3 dans `src/data/proces/<id>.json`, avec leur identifiant : Robert à 30 % (`2026-11-15-dfad1e96d34e`) et à 25 % (`2026-11-15-5944335b5a5c`), Amira (`2026-11-15-741f038b00f1`), Mateo (`2026-11-14-51c84bd19c16`). « Trompez le Greffier » marche donc aussi en démonstration. Les anciens enregistrements locaux (fiche 014) sont retirés.
- **Tests** : 6 pytest pour `detailler_argument` (`tests/test_chiffres.py`), 8 pour la route (`tests/test_lambda_tribunal.py`) ; vitest pour les corrections, les exemples et le choix du procès enregistré ; `frontend/e2e/greffier.mjs` (`npm run verifier:greffier`).

## Comment l'utiliser
```powershell
# Après la fusion : déployer la route (Function URL inchangée)
.venv\Scripts\python -X utf8 deploiement\deployer.py --sans-donnees
cd frontend; npm run dev        # VITE_API_URL défini, mode démonstration ou direct
```
Sur l'écran Tribunal : un exemple, ou un texte tapé à la main avec ses pièces cochées, puis « Faire vérifier par le Greffier ».

## Comment vérifier
```powershell
.venv\Scripts\python -m pytest tests/test_chiffres.py tests/test_lambda_tribunal.py
cd frontend; npm test; npm run verifier:greffier
```
Le 2026-11-15, **avec le handler de la Lambda servi en local** (lecture S3 des vrais procès archivés, sans déploiement) : les 4 exemples rendent le verdict attendu en 48 à 325 ms, l'argument tapé est vérifié nombre par nombre, axe-core ne relève aucune violation, et la correction réelle du procès à 25 % s'affiche. `npm run verifier` (démonstration) passe toujours ses 23 écrans.

## Choix faits en cours de route
- **Aucun rejet fabriqué.** Aucun des 10 procès archivés dans S3 n'a d'argument définitivement rejeté (`arguments_rejetes` vide). Il y a en revanche deux vrais cas où le Greffier a renvoyé un argument puis accepté sa version corrigée. Le procès de Robert à 25 % en est un : le Procureur avait écrit « 30 % » en citant P6 (jurisprudence), où ce nombre n'était pas. L'interface montre ces cas tels qu'ils sont, présentés comme corrigés et non comme rejetés.
- **Exemples écrits à partir des pièces**, pas de chiffres en dur. La phrase de « la mauvaise pièce » évite l'année, pour que seul le chiffre mal cité échoue.
- **Pas de cache** du procès dans la Lambda : le contre-interrogatoire réarchive le contrat avec de nouvelles pièces, et une lecture S3 ne coûte que quelques dizaines de millisecondes.
- La limite de débit vit en mémoire de chaque instance : c'est un garde-fou contre une boucle ou un abus, pas une protection complète. La concurrence réservée de 2 borne le reste ; `/verifier` partage ces 2 exécutions avec `/tribunal`.

## Passage pour la vidéo (#18)
1. Ouvrir un procès de Robert (« 30 % en TSLA »), montrer le bilan du Greffier et la ligne « Règle que vous avez signée le 14 nov. 2026 ».
2. « Un chiffre inventé » : « −40 % » est rejeté en direct, avec le motif « introuvable dans P2 ».
3. « La mauvaise pièce » : « −23,7 % » est rejeté, et le Greffier indique qu'il est présent dans P3, pièce non citée.
4. Inviter le jury à taper sa propre phrase.
5. Ouvrir le procès à 25 % pour le cas réel : la version renvoyée, le motif « « 30 % » introuvable dans P6 », puis la version corrigée, acceptée.

## Limites et suite
- **Route à déployer après la fusion** (`deployer.py --sans-donnees`) : tant que la Lambda n'a pas ce code, le panneau affiche l'erreur « Route inconnue ».
- Le contre-interrogatoire (#55) existe côté Lambda (`/question`), mais l'interface ne l'appelle pas encore. Le message de l'écran a été corrigé pour le dire.
