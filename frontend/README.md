# Astrée — interface du Tribunal

Interface web du projet (issue #14). React 18 + TypeScript + Vite, CSS Modules sur les jetons de design de la maquette (`src/styles/tokens.css`). Aucune bibliothèque de composants : chaque composant colle à la maquette Figma « V2 · Prototype simplifié ». La spec complète est dans [`docs/maquette/spec_interface_astree.md`](../docs/maquette/spec_interface_astree.md).

> Simulation éducative. Aucune transaction réelle. Ceci n'est pas un conseil financier personnalisé.

## Démarrer

Prérequis : Node 20 ou plus (testé avec Node 24), et le `.venv` Python du dépôt pour régénérer les séries.

```powershell
cd frontend
npm install
npm run dev          # http://localhost:5173
```

| Commande | Rôle |
|---|---|
| `npm run dev` | Serveur de développement |
| `npm run build` | Vérification des types, puis compilation dans `dist/` |
| `npm test` | Tests vitest : chiffres de l'annexe E, formats, adaptateur du contrat, questions, Verdict |
| `npm run verifier` | Parcours de bout en bout des 3 profils (Robert au clavier seul), axe-core sur chaque écran, débordement à 1440 et 1280 px, erreurs de console. Demande `npm run dev` dans un autre terminal et Edge ou Chrome installé. Captures dans `e2e/captures/` |
| `npm run verifier:greffier` | « Trompez le Greffier » : 4 exemples, argument tapé, réponse en moins d'une seconde, axe-core (gratuit, sans Bedrock) |
| `npm run verifier:direct` | Mode direct : deux vrais procès sur la Lambda par l'interface, une question libre au Tribunal, un essai « Trompez le Greffier », verdicts signés et archivés (Bedrock, quelques cents) |
| `npm run series` | Régénère les séries et les tables (`scripts/build_ui_series.py`) |

## D'où viennent les chiffres

**Aucun chiffre n'est écrit dans les composants, et aucun n'est estimé dans le navigateur.**

| Donnée | Source | Produite par |
|---|---|---|
| Portefeuilles, capitaux, Pactes | `personas/*.json` (le backend fait foi) | `scripts/build_ui_series.py` → `src/data/generated/profils/` |
| Indicateurs, courbe de valeur, recul | `alphaforge_starter/` (prix `adj_close`, USD/CAD) | le même script, avec les fonctions du pipeline (`pipeline.simulation`, `pipeline.indicateurs`, `pipeline.greffier`) |
| Curseur de taille (0 à 50 %, pas de 1 point) | idem | `src/data/generated/decisions/<profil>/<ticker>.json` : une table par titre de l'univers |
| Panier (pas de 5 points) | idem | `src/data/generated/paniers/<profil>.json` : chaque composition du panier de démonstration |
| Pacte vécu (#68) : jours de baisse, questions, réponses de démonstration | idem, avec `pipeline.calibrage` | `src/data/generated/calibrage/<profil>.json` |
| Arguments, contrôles, pièces, trace | le Tribunal (Bedrock + Python) | procès enregistrés dans `src/data/proces/`, ou Lambda en direct |
| Libellés français, textes de démonstration | écrits à la main | `src/data/libelles.json`, `src/data/profils_ui.json` |

Le script réutilise le code du pipeline : l'interface affiche exactement les chiffres que le Tribunal citerait (ex. : Robert, 30 % en TSLA → −29,0 %, 278 séances sous la limite, maximum conforme 9 %).

### Régénérer les séries

```powershell
.venv\Scripts\python -X utf8 scripts\build_ui_series.py     # depuis la racine, environ 1 minute
```

À relancer après une modification de `personas/`, `config/categories.json`, `donnees_externes/` ou des données de départ. Le résultat est déterministe.

## Passer des données de démonstration au Tribunal en direct

La couche `src/api/` isole les écrans du backend : les composants ne lisent que les types de `src/api/types.ts` (annexe D.7).

- **Mode démonstration** (défaut, `VITE_USE_MOCKS=true`) : `src/api/tribunal.ts` rejoue un procès **réellement tenu par la Lambda** et archivé dans S3, copié tel quel dans `src/data/proces/<id>.json` et validé par `python -m contrat.valider` : Robert à 30 % et à 25 % de TSLA (ce dernier contient un argument corrigé par le Greffier), Amira (panier à 25 %), Mateo (10 % de XOM). Un procès est rejoué seulement s'il juge exactement la décision soumise ; sinon, l'écran le dit et propose la décision enregistrée. Aucun procès n'est inventé.
- **Mode direct** : copier `.env.example` en `.env.local` et définir :
  ```
  VITE_USE_MOCKS=false
  VITE_API_URL=https://<id>.lambda-url.us-east-1.on.aws
  ```
  L'interface envoie `POST /tribunal` `{profil, demande}` (la demande est rédigée par `demandeDecision`, ex. « Je veux mettre 30 % de mon portefeuille en Tesla (TSLA) »), lit l'identifiant du procès dans l'en-tête `x-proces-id`, puis envoie `POST /verdict` `{id, verdict}` à la signature.
  L'adresse s'obtient avec `aws lambda get-function-url-config --function-name alphaforge-tribunal --query FunctionUrl` (elle n'est pas dans le dépôt). Relancer `npm run dev` après avoir modifié `.env.local`.
  **Côté AWS, c'est fait (#14)** : Function URL en type `NONE`, CORS limité à `http://localhost:5173` et `ExposeHeaders: x-proces-id` (`deploiement/README.md`, « Point d'accès »). L'interface doit donc tourner sur ce port ; pour un autre domaine, `deploiement\deployer.py --url-seulement --origine <domaine>`.
  **Vérifier** : `npm run verifier:direct` (avec `npm run dev` en mode direct) joue deux vrais procès par l'interface, Robert puis Amira, et signe leurs verdicts. Cela coûte quelques cents de Bedrock et ajoute deux verdicts à la jurisprudence.

Le même adaptateur (`src/api/adaptateur.ts`) traduit le contrat dans les deux modes.

## Pacte vécu (#68)

Écran `/:profil/pacte-vecu` (« Revivez 4 jours », lien depuis la carte « Votre Pacte ») : de vrais jours de baisse, en dollars, la courbe arrêtée au jour J. L'utilisateur répond « je reste » ou « je vends » ; `src/domaine/calibrage.ts` rejoue la dichotomie de `pipeline/calibrage.py` (un test vérifie qu'il trouve le même seuil que Python). Une fois terminé, tous les écrans reçoivent le profil au seuil mesuré (`App.tsx`), et les tables de décision sont rejugées avec ce seuil (même comparaison que le Greffier ; les séances sous la limite, comptées avec l'ancien seuil, ne sont plus affichées).

- **Mode direct** : les réponses partent avec `POST /tribunal` (`calibrage.reponses`) ; la Lambda recalcule tout en Python.
- **Mode démonstration** : seul un procès enregistré avec exactement les mêmes réponses (`"calibrage": true` dans `index.json`) peut être rejoué ; sinon, l'écran le dit. Le bouton « Utiliser les réponses de démonstration » applique celles du profil (étiquette Fictif). Pour enregistrer un tel procès sur la Lambda : `deploiement/tester_function_url.py <profil> "<demande>" --calibrage-demo --sortie …`, puis copier le contrat sous son identifiant dans `src/data/proces/`.

## Organisation

```
src/
  api/          contrat.ts (contrat du pipeline), types.ts (annexe D.7), adaptateur.ts, tribunal.ts, donnees.ts
  domaine/      logique d'affichage pure et testée : pacte.ts, decision.ts, questions.ts, verdict.ts
  state/        store par profil (sessionStorage), chargement des tables
  components/   Gabarit (bandeau, en-tête, étapes), Etiquettes (Provenance, Statut, Pièce), Bouton,
                Elements (Monogramme, Jauge, Message), Recherche (combobox), TiroirPiece, graphiques/
  ecrans/       Entree, Portefeuille, Decision, Tribunal, Verdict
  data/         generated/ (script Python), proces/ (procès enregistrés), libelles.json, profils_ui.json
  lib/          format.ts (formats fr-CA), recherche.ts, series.ts
  test/         tests vitest
e2e/verifier.mjs  vérification de bout en bout (playwright-core + axe-core)
```

Ajouter un profil : un fichier `personas/<id>.json`, puis `npm run series`. Une entrée dans `src/data/profils_ui.json` est facultative (textes de l'écran d'entrée, journal fictif) : la logique ne teste jamais un nom de profil.

## Contre-interrogatoire (#55)

Sur l'écran Tribunal, en mode direct, une question libre (« Et si je mettais 15 % au lieu de 30 % ? ») part au vrai Tribunal (`POST /question`, environ 15 à 40 s). L'orchestrateur choisit ses outils, le Procureur et l'Avocat répondent avec les pièces, puis le Greffier vérifie chaque chiffre. L'échange s'affiche avec les pièces ajoutées (P7, P8…), consultables dans le tiroir. En démonstration, aucune question libre n'est envoyée (appels payants). Les questions suggérées sont calculées par le Greffier, sans IA, et leurs pièces s'appellent G1, G2…

## « Essayez de tromper le Greffier » (#69)

Sur l'écran Tribunal, n'importe qui peut écrire un argument chiffré, citer des pièces et le faire vérifier par le Greffier (`POST /verifier`, outil 6 `verifier_chiffres`, Python seul) : chaque nombre s'affiche trouvé, avec sa pièce, ou introuvable, avec le motif exact. Quatre exemples prêts, écrits à partir des pièces du procès affiché (`src/domaine/pieges.ts`) : un vrai chiffre, un chiffre inventé, un arrondi faux, la mauvaise pièce. Le même écran montre les vrais arguments que le Greffier a renvoyés pendant le procès, avec le motif et la version corrigée.

- Disponible dans les deux modes dès que `VITE_API_URL` est défini, car les procès enregistrés ont leur identifiant S3. Aucun appel Bedrock : gratuit.
- `npm run verifier:greffier` (avec `npm run dev`) vérifie les 4 exemples, un argument tapé au clavier, la réponse en moins d'une seconde, axe-core et l'affichage d'une correction réelle.

## Accessibilité

WCAG 2.2 AA visé : contrastes de la palette, focus visible (anneau bleu de 2 px), navigation complète au clavier (combobox ARIA, curseur `input type=range` avec `aria-valuetext`, accordéons `aria-expanded`, tiroir `role="dialog"` avec focus piégé), statuts et provenances toujours doublés d'un mot et d'une icône, `prefers-reduced-motion` respecté. `npm run verifier` passe axe-core (WCAG 2.2 AA et bonnes pratiques) sur chaque écran sans violation.
