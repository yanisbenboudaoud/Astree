# #99 — Portefeuille : composer un panier depuis n'importe quel profil

- **Issue** : #99 · **PR** : #101 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Le mode de la recherche (`position` ou `panier`) était lu profil par profil dans `profils_ui.json`. Un profil créé avec « Construire mon Pacte » n'y figure pas : il recevait le mode par défaut, `position`, et ne pouvait jamais composer de panier. Robert et Mateo non plus. Le Tribunal, lui, juge un panier (`reallocation`) pour n'importe quel Pacte.

- **`frontend/src/components/Recherche.tsx`** : nouvelle propriété facultative `onMode`. Si elle est fournie, la carte affiche deux boutons « Un titre » / « Un panier » (`aria-pressed`) sous son titre. Styles `.modes`, `.mode`, `.modeActif` dans `Recherche.module.css`.
- **`frontend/src/ecrans/Portefeuille.tsx`** : état local `modeRecherche`. Il part du mode du profil, ou de `panier` si un panier est déjà commencé (retour depuis « + Ajouter un titre » de l'écran Décision).
- **`frontend/src/api/donnees.ts`** : `rechercheUi(id, mode)` renvoie les textes de la recherche pour un mode : ceux du profil s'il a choisi ce mode, sinon des textes génériques (`RECHERCHE_PANIER_PAR_DEFAUT` pour le panier).
- **`frontend/src/api/types.ts`** : le type `ConfigRecherche` est extrait de `ConfigProfilUI`.
- **`frontend/src/ecrans/Decision.tsx`** : quand le profil n'a aucune table de panier précalculée (`chargerTablePanier` renvoie `null`), le message « À vérifier · Aperçu non calculé pour ce panier » remplace l'écran vide. Le panier peut quand même être soumis au Tribunal.
- **`docs/maquette/spec_interface_astree.md`** (annexe D.3) : le choix du mode est décrit.

## Comment l'utiliser
`npm run dev`, n'importe quel profil → Portefeuille → « Un panier » → ajouter au moins 2 titres → « Instruire le panier ».

## Comment vérifier
- `npx tsc --noEmit` passe.
- `npm test` : 79 tests passent. Les 2 échecs de `domaine.test.ts` (« procès enregistrés ») existent aussi sur `main` : ces tests appellent la Lambda quand le mode direct est configuré, et elle a répondu « Tribunal occupé ».
- Dans le navigateur (mode démonstration) : Robert → « Un panier » → AAPL + XIU → écran Décision avec le message, bouton « Soumettre au Tribunal » actif.

## Choix faits en cours de route
- **Le mode du profil reste le point de départ.** Amira s'ouvre toujours sur le panier, Robert et Mateo sur un titre : la démo ne change pas.
- **Aucun aperçu calculé pour un panier quelconque.** Il faudrait étendre la route `/table` (#86) aux paniers ; le procès, lui, simule le panier avec les mêmes outils Python.

## Limites et suite
- L'écran Décision d'un panier sans table n'a ni comparaison avant / après, ni graphique, ni zone compatible. Suite possible : une route Lambda qui calcule la table d'un panier à la demande, sans Bedrock.
