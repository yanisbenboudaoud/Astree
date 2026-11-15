# #138 — Mêmes fonctions de l'écran Décision pour tous les profils

- **Issue** : #138 · **PR** : #139 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Le code de l'écran Décision était déjà le même pour tous les profils, mais les données et les textes ne l'étaient pas : un panier n'avait d'aperçu que pour Amira, et la recherche changeait de textes et de suggestions d'un profil à l'autre. Désormais, un même panier donne le même écran pour tous ; seules les lignes des règles propres à chaque Pacte changent.

- **`frontend/src/data/profils_ui.json`** : `panierDemo` (BTC-USD, ETH-USD, NVDA, QQQ) passe au premier niveau, commun à tous les profils. Les textes `recherche` propres à chaque profil sont retirés ; il reste, par profil, les textes de l'écran d'entrée et le journal fictif.
- **`scripts/build_ui_series.py`** : `paniers/<id>.json` est généré pour chaque profil de `personas/` et pour l'exemple du questionnaire (`investisseur_exemple`), avec le panier commun. Nouveaux fichiers : `paniers/robert.json`, `paniers/mateo.json`, `paniers/investisseur_exemple.json` (1 771 compositions chacun, par pas de 5 points).
- **`frontend/src/api/donnees.ts`** :
  - `rechercheUi(mode)` : les mêmes textes pour tous, selon le mode (titre ou panier) ;
  - `modeDeDepart(profil)` : panier si la décision de démonstration est une réallocation, sinon titre (lu dans le profil, jamais dans son nom) ;
  - `PANIER_DEMO` : le panier commun.
- **`frontend/src/ecrans/Portefeuille.tsx`** : en mode panier, les titres proposés sont ceux du panier commun, pour tous ; en mode titre, la règle ne change pas (titres de la décision de démonstration, puis exemples variés).
- **`frontend/src/api/types.ts`** : `ConfigProfilUI` perd `recherche` et `panierDemo`.

## Comment l'utiliser
Ajouter un profil ne demande toujours qu'un fichier `personas/<id>.json` : `python -X utf8 scripts/build_ui_series.py` lui génère ses tables de titres et de panier. Changer le panier de démonstration : modifier `panierDemo` dans `profils_ui.json`, puis relancer le script.

## Comment vérifier
- Depuis la racine : `python -X utf8 scripts/build_ui_series.py` (environ 80 s) écrit les 4 paniers ; les autres fichiers générés ne changent pas.
- Depuis `frontend/` : `npx tsc --noEmit` passe ; `npm test` donne 135 tests sur 137. Les 2 échecs de `domaine.test.ts` (« Tribunal occupé ») existaient avant.
- `ASTREE_URL=http://localhost:5175 node e2e/verifier.mjs` (mode démonstration) : 23 écrans, aucun problème axe-core ni de parcours ; il ne reste que les erreurs CORS du port 5175 (la Lambda n'accepte que `localhost:5173`).
- Mode démonstration, le panier BTC, ETH, NVDA, QQQ à 25 % : Robert, Amira et Mateo ont les mêmes sections (composition, effet sur le Pacte, graphique, verdict). Seules changent les lignes des règles de chaque Pacte (plafond tech + crypto d'Amira, valeurs de Mateo).

## Choix faits en cours de route
- **Un panier commun plutôt qu'un panier par profil** : l'écran doit se comporter pareil pour tous ; le panier d'Amira (crypto et tech) sert aussi à montrer ce que les Pactes de Robert et de Mateo en disent.
- **Toujours précalculé en Python** : le navigateur ne calcule rien. Un panier quelconque ne peut pas être précalculé (trop de combinaisons) ; la route `/table` de la Lambda ne traite qu'un titre à la fois, et une route pour un panier demanderait un redéploiement.

## Limites et suite
- En mode démonstration, l'écran Tribunal rejoue seulement les procès enregistrés (`frontend/src/data/proces/`) : un panier pour Robert ou Mateo y affiche « Aucun procès enregistré ». Il faudrait enregistrer ces procès sur Bedrock (appels payants). En mode direct, tout profil est jugé.
- Un profil créé par le questionnaire pendant la session n'a pas de table de panier : l'aperçu y reste « non calculé ».
- Les 4 tables de panier pèsent environ 2 Mo chacune ; elles ne sont chargées qu'à l'ouverture d'un panier.
