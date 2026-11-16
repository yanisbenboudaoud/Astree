# #137 — Site hébergé : mode direct par défaut, bascule vers les procès enregistrés à l'utilisation

- **Issue** : #137 · **PR** : à venir · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Le mode de l'interface n'est plus fixé à la construction. Le site hébergé peut faire de vrais procès Bedrock par défaut et garder les procès enregistrés à portée de clic, pour une démonstration complète quoi qu'il arrive.

- **`frontend/src/api/config.ts`** :
  - `choisirMode({recherche, memorise, construction, directDisponible})`, fonction pure : `?mode=demo|direct`, sinon le mode mémorisé, sinon `MODE_CONSTRUCTION` (`VITE_USE_MOCKS`). Sans adresse de Lambda (`DIRECT_DISPONIBLE` faux), toujours `demo` ;
  - `MODE` et `MODE_DIRECT` sont calculés **une fois, au chargement de la page**. Un `?mode=` valide est mémorisé (`memoriserMode`, clé `astree.mode` de `localStorage`). Toutes les lectures du stockage sont dans un try/catch : sans `localStorage`, le site marche ;
  - `changerMode(mode)` mémorise le mode, puis recharge l'interface sur l'accueil avec `?mode=<mode>` (qui porte le choix même sans `localStorage`) ;
  - `cleSession(base)` : clé de `sessionStorage` propre au mode (`.direct` en direct ; la démonstration garde la clé d'origine). Utilisée par `state/store.tsx` (`astree.etat.v1`) et `api/donnees.ts` (`astree.profils.v1`).
- **`frontend/src/components/Gabarit.tsx`** : `ChoixMode`, interrupteur à droite du bandeau « Simulation » (« En direct (Bedrock sur AWS) » ou « Procès enregistrés »), qui ouvre un panneau : les deux modes, une phrase chacun, le mode actuel, un bouton vers l'autre et « Changer de mode ramène à l'accueil ». Absent sans `VITE_API_URL`. Le panneau d'aide le signale.
- **`frontend/src/ecrans/Tribunal.tsx`** : en démonstration, la Lambda n'est plus réveillée à l'ouverture de l'écran. Elle l'est seulement quand on ouvre « Mettre le Greffier à l'épreuve » (`Repli` reçoit `onOuvrir`). Quand une décision n'a pas de procès enregistré et que le direct existe, le message renvoie à l'interrupteur.
- **Tests** : `frontend/src/test/mode.test.tsx` (17 tests). Logique pure, chargement de page (défaut, `?mode=`, mémorisation, `localStorage` bloqué, sans `VITE_API_URL`, clés de session), `?mode=demo` sur un site construit en direct (procès de Robert rejoué et verdict gardé, `fetch` jamais appelé), mode direct (le procès part à `/tribunal`), interrupteur (absent, présent, bascule).
- **`frontend/e2e/mode.mjs`** (`npm run verifier:mode`) : la même preuve dans un vrai navigateur, gratuite.

`deploiement/deployer_interface.py` construisait déjà le site en mode direct par défaut (#135) : rien à changer.

## Comment l'utiliser
- `https://d15khh2djw55mh.cloudfront.net/?mode=demo` : procès enregistrés, mémorisés pour les visites suivantes ; `?mode=direct` pour revenir.
- Ou l'interrupteur, en haut à droite de chaque écran.

## Comment vérifier
- `npm test` dans `frontend/` : 186 tests, dont les 17 de `mode.test.tsx`. Aussi `npm run build`.
- `npm run verifier:mode` contre un serveur construit **en direct par défaut** avec l'adresse de la Lambda (port 5186, hors du CORS : tout appel à la Lambda échouerait en console). Résultat : 0 appel à la Lambda du `?mode=demo` jusqu'au verdict signé, mode mémorisé, axe-core sans violation sur le panneau, aller-retour vers le direct.
- `npm run verifier` contre un serveur en démonstration **avec** l'adresse de la Lambda (interrupteur visible) : aucun problème, 23 écrans sous axe-core, aucun débordement à 1440 et 1280 px, aucune erreur de console.

## Choix faits en cours de route
- **Rechargement plutôt que mode réactif** : changer de mode recharge la page. Un suivi de procès en cours (`suivreProces`), les tables calculées par `/table` ou un état React de l'autre mode ne peuvent donc pas survivre. `MODE_DIRECT` reste une constante, juste pour toute la vie de la page, et ses usages (`api/tribunal.ts`, `api/questionnaire.ts`, `api/donnees.ts`, écrans) n'ont pas eu à changer.
- **État de session séparé par mode** : sans cela, un procès en direct en cours (`procesId` dans `sessionStorage`) aurait été repris en démonstration, ce qui fait un appel à la Lambda, et un procès enregistré aurait été affiché comme un procès en direct.
- **« Trompez le Greffier » reste disponible en démonstration** (#69, gratuit, Python seul) : c'est une action de l'utilisateur, pas le rejeu. Seul le réveil automatique a été déplacé à l'ouverture de sa section. Conséquence pour `npm run verifier:greffier` en démonstration : la Lambda est réveillée à l'ouverture de la section, et non plus pendant la relecture du procès.
- **Pas d'interrupteur sans `VITE_API_URL`** : GitHub Pages (#186) et `npm run dev` sans `.env.local` sont inchangés.

## Limites et suite
- Un `?mode=` tapé dans l'adresse d'une page profonde vaut pour cette page et est mémorisé. Les liens internes ne le gardent pas, puisque le mode mémorisé suffit.
- **Suite : #141**, le site hébergé redéployé en mode direct par défaut.
