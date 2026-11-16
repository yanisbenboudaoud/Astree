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
| `npm run verifier:mode` | Mode choisi à l'utilisation (#137) : `?mode=demo` rejoue le procès de Robert jusqu'au verdict signé sans aucune requête vers la Lambda, mode mémorisé, interrupteur du bandeau (axe-core), aller-retour vers le direct sans lancer de procès (gratuit). Demande un site qui connaît `VITE_API_URL` |
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
| Questionnaire (#84, #86) : questions, cartes de portefeuilles, exemple de démonstration | `config/questionnaire.json`, avec `pipeline.questionnaire` | `src/data/generated/questionnaire.json` (et `decisions/investisseur_exemple/`) |
| Profil créé par le questionnaire, en direct | la Lambda, avec `pipeline.vues_interface` (mêmes fonctions que le script) | `POST /profil` (vues renvoyées à la signature), `POST /table` (une table de décision par titre) |
| Arguments, contrôles, pièces, trace | le Tribunal (Bedrock + Python) | procès enregistrés dans `src/data/proces/`, ou Lambda en direct |
| Sources du dossier (#111) : chaque source, ses pièces et la raison de l'orchestrateur | champ `sources` du contrat, écrit par `pipeline/sources.py` | bloc « D'où viennent les données » de l'écran Tribunal (`domaine/sources.ts`) |
| Libellés français, textes de démonstration | écrits à la main | `src/data/libelles.json`, `src/data/profils_ui.json` |

Le script réutilise le code du pipeline : l'interface affiche exactement les chiffres que le Tribunal citerait (ex. : Robert, 30 % en TSLA → −29,0 %, 278 séances sous la limite, maximum conforme 9 %).

### Régénérer les séries

```powershell
.venv\Scripts\python -X utf8 scripts\build_ui_series.py     # depuis la racine, environ 1 minute
```

À relancer après une modification de `personas/`, `config/categories.json`, `donnees_externes/` ou des données de départ. Le résultat est déterministe.

## Passer des données de démonstration au Tribunal en direct

La couche `src/api/` isole les écrans du backend : les composants ne lisent que les types de `src/api/types.ts` (annexe D.7).

**Le mode se choisit à l'utilisation (#137)**, dans `src/api/config.ts`, au chargement de la page et dans cet ordre :
1. `?mode=demo` ou `?mode=direct` dans l'adresse (ex. : `https://d15khh2djw55mh.cloudfront.net/?mode=demo`), mémorisé pour les visites suivantes ;
2. le mode mémorisé dans `localStorage` (clé `astree.mode`), par l'interrupteur ou un `?mode=` précédent. Sans `localStorage` (navigation privée, stockage bloqué), le site marche : `?mode=` vaut pour la page, et le mode de la construction revient ensuite ;
3. le mode de la construction, `VITE_USE_MOCKS` (ci-dessous).

**Interrupteur** discret à droite du bandeau « Simulation » : « En direct (Bedrock sur AWS) » ou « Procès enregistrés », avec une phrase qui dit ce que fait chaque mode. Changer de mode recharge l'interface sur l'accueil (`changerMode`) : le mode reste fixe pendant la vie de la page, donc `MODE_DIRECT` est toujours le mode courant. L'état de session (`astree.etat.v1`, `astree.profils.v1`) a une clé à part en direct (`.direct`) : un procès, un verdict ou un profil créé dans un mode ne réapparaît pas dans l'autre. **Sans `VITE_API_URL`, il n'y a pas d'interrupteur** et `?mode=direct` est ignoré : seule la démonstration existe (GitHub Pages).

- **Mode démonstration** (défaut, `VITE_USE_MOCKS=true`) : `src/api/tribunal.ts` rejoue un procès **réellement tenu par la Lambda** et archivé dans S3, copié tel quel dans `src/data/proces/<id>.json` et validé par `python -m contrat.valider` : Robert à 30 % et à 25 % de TSLA (ce dernier contient un argument corrigé par le Greffier), Amira (panier à 25 %, et QQQ et NVDA à 50 %), Mateo (10 % de XOM). Deux d'entre eux gardent leur contre-interrogatoire réel (#55), affiché tel quel : Robert à 30 % de TSLA (« Et si je mettais 15 % au lieu de 30 % ? ») et Amira à QQQ et NVDA. Depuis #189, Robert à 30 % de TSLA, le panier d'Amira à 25 % et Mateo à 10 % de XOM sont rejoués par des procès tenus après le redéploiement : ils montrent les répliques, l'heure de chaque étape et la mesure Bedrock, et Robert garde sa question « Et si je mettais 15 % au lieu de 30 % ? » ; les trois procès avec Pacte vécu aussi (procès placés en tête de `index.json`). Un procès est rejoué seulement s'il juge exactement la décision soumise ; sinon, l'écran le dit et propose la décision enregistrée. Aucun procès n'est inventé.
- **Sans AWS** (comptes du Datathon supprimés le 16 novembre 2026) : seul le mode démonstration fonctionne, avec `VITE_API_URL` vide. Toutes les données viennent du dépôt ; la question libre et « Trompez le Greffier » le disent au lieu d'appeler la Lambda. Ce mode est publié sur GitHub Pages à chaque fusion dans `main` : <https://yanisbenboudaoud.github.io/Astree/> (#186).
- **Mode direct** : copier `.env.example` en `.env.local` et définir :
  ```
  VITE_USE_MOCKS=false
  VITE_API_URL=https://<id>.lambda-url.us-east-1.on.aws
  ```
  L'interface envoie `POST /tribunal` `{profil, demande, progression: true}` (la demande est rédigée par `demandeDecision`, ex. « Je veux mettre 30 % de mon portefeuille en Tesla (TSLA) ») ; la Lambda répond tout de suite 202 `{id}` et fait le procès en arrière-plan. Pendant le procès, `suivreProces` relit `POST /progression` `{id}` toutes les 1,5 s (S3, jamais Bedrock) jusqu'au contrat, puis l'interface envoie `POST /verdict` `{id, verdict}` à la signature.
  **Écran « Le Tribunal instruit le dossier »** (`src/components/ChargementTribunal.tsx`, #90) : les 4 phases fixes, la phase en cours pulsée, les phases finies cochées, et sous chaque phase ses étapes réelles au fur et à mesure (outils de l'orchestrateur avec leur pièce et leur raison, retour du Procureur et de l'Avocat, renvois du Greffier), plus ce que fait le Tribunal en ce moment. Rien n'avance selon le temps écoulé. La relecture s'arrête au contrat, sur une erreur du procès (motif affiché), après 120 s, ou quand on quitte l'écran ; en revenant (ou après un rechargement), elle reprend sur le même procès, sans en relancer un. Un 429 (deux procès déjà en cours) affiche « Tribunal occupé » et la relecture continue. Une Lambda d'avant #90 renvoie encore le contrat en 200 : l'interface l'accepte, sans progression.
  En démonstration, le même écran relit la trace du procès enregistré, une étape toutes les 0,5 s, et le dit (« Relecture d'un procès enregistré »).
  L'adresse s'obtient avec `aws lambda get-function-url-config --function-name alphaforge-tribunal --query FunctionUrl` (elle n'est pas dans le dépôt). Relancer `npm run dev` après avoir modifié `.env.local`.
  **Côté AWS, c'est fait (#14)** : Function URL en type `NONE`, CORS limité à `http://localhost:5173` et au site hébergé (lu sur le compte, #136), `ExposeHeaders: x-proces-id` (`deploiement/README.md`, « Point d'accès »). En local, l'interface doit donc tourner sur ce port ; pour un autre port, `deploiement\deployer.py --url-seulement --origine <origine>` (jusqu'au déploiement suivant). La Lambda limite `/tribunal` à 3 procès et `/question` à 10 questions par minute et par adresse IP (#136) : son message (429) s'affiche tel quel ; un 429 d'AWS (deux procès en cours) donne un message générique qui le rappelle aussi (`lireErreur`, `src/api/config.ts`).
  **Site hébergé (#135)** : https://d15khh2djw55mh.cloudfront.net (S3 + CloudFront), construit et envoyé par `deploiement\deployer_interface.py`, qui lit l'adresse de la Lambda sur le compte. Mode direct par défaut, `--mode demo` pour les procès enregistrés (`deploiement/README.md`, « Interface hébergée ») ; dans les deux cas, `?mode=` et l'interrupteur changent de mode (#137). `ASTREE_URL=https://d15khh2djw55mh.cloudfront.net npm run verifier` joue le parcours sur le site ; `npm run verifier:direct` lit aussi `ASTREE_URL` (#136), pour un site construit en mode direct.
  **Vérifier** : `npm run verifier:direct` (avec `npm run dev` en mode direct) joue deux vrais procès par l'interface, Robert puis Amira, et signe leurs verdicts. Il vérifie aussi la progression (202, relectures de `/progression`, phase qui avance). Cela coûte quelques cents de Bedrock et ajoute deux verdicts à la jurisprudence.

Le même adaptateur (`src/api/adaptateur.ts`) traduit le contrat dans les deux modes.

## Pacte vécu (#68)

Écran `/:profil/pacte-vecu` (« Revivez 4 jours », lien depuis la carte « Votre Pacte ») : de vrais jours de baisse, en dollars, la courbe arrêtée au jour J. L'utilisateur répond « je reste » ou « je vends » ; `src/domaine/calibrage.ts` rejoue la dichotomie de `pipeline/calibrage.py` (un test vérifie qu'il trouve le même seuil que Python). Une fois terminé, tous les écrans reçoivent le profil au seuil mesuré (`App.tsx`), et les tables de décision sont rejugées avec ce seuil (même comparaison que le Greffier ; les séances sous la limite, comptées avec l'ancien seuil, ne sont plus affichées).

- **Mode direct** : les réponses partent avec `POST /tribunal` (`calibrage.reponses`) ; la Lambda recalcule tout en Python.
- **Mode démonstration** : seul un procès enregistré avec exactement les mêmes réponses (`"calibrage": true` dans `index.json`) peut être rejoué ; sinon, l'écran le dit. Le bouton « Utiliser les réponses de démonstration » applique celles du profil (étiquette Fictif). Pour enregistrer un tel procès sur la Lambda : `deploiement/tester_function_url.py <profil> "<demande>" --calibrage-demo --sortie …`, puis copier le contrat sous son identifiant dans `src/data/proces/`.

## Construire mon Pacte (#86)

Écran `/construire` (carte « Construire mon Pacte » de l'entrée) : 15 questions, une par écran et par sections (horizon, capacité, tolérance, expérience, préférences), puis le portefeuille (titres de l'univers, poids totalisant 100 %, capital fictif), puis l'aperçu du Pacte : chaque règle dit quelle réponse l'a produite, les contradictions et réponses manquantes sont « à vérifier ». Après la signature, le profil créé s'ouvre sur « Revivez 4 jours », puis Portefeuille, Décision et Tribunal comme un profil de démonstration. Le brouillon est gardé dans sessionStorage.

- **Mode direct** : `POST /profil` avec `apercu: true` pour l'aperçu (rien n'est rangé ; on peut y choisir un autre seuil, « Choisi par vous »), puis sans pour signer : la Lambda range le profil dans S3 et renvoie ses vues (écrans Portefeuille et « Revivez 4 jours ») ; l'écran Décision demande ses tables à `POST /table`. La Lambda doit être redéployée avec ces routes, et l'interface servie sur `http://localhost:5173` (CORS).
- **Mode démonstration** : le barème ne tourne pas dans le navigateur. Seul l'exemple préenregistré (`docs/exemples/reponses_questionnaire.json`, bouton « Remplir comme un profil de test », étiquette Fictif) devient un Pacte, calculé d'avance par `scripts/build_ui_series.py` ; toute autre saisie affiche « Pacte non disponible en démonstration ». Aucun procès n'est enregistré pour ce profil : le Tribunal le dit.

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

- Disponible dans les deux modes dès que `VITE_API_URL` est défini, car les procès enregistrés ont leur identifiant S3. Aucun appel Bedrock : gratuit. En direct, l'écran réveille la Lambda dès son ouverture ; en démonstration, seulement à l'ouverture de « Mettre le Greffier à l'épreuve », car rejouer un procès enregistré n'appelle jamais la Lambda (#137).
- `npm run verifier:greffier` (avec `npm run dev`) vérifie les 4 exemples, un argument tapé au clavier, la réponse en moins d'une seconde, axe-core et l'affichage d'une correction réelle.

## Accessibilité

WCAG 2.2 AA visé : contrastes de la palette, focus visible (anneau bleu de 2 px), navigation complète au clavier (combobox ARIA, curseur `input type=range` avec `aria-valuetext`, accordéons `aria-expanded`, tiroir `role="dialog"` avec focus piégé), statuts et provenances toujours doublés d'un mot et d'une icône, `prefers-reduced-motion` respecté. `npm run verifier` passe axe-core (WCAG 2.2 AA et bonnes pratiques) sur chaque écran sans violation.
