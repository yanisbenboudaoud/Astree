# #182 — En-tête de l'interface : marque, devise et curseur de procédure

- **Issue** : #182 · **PR** : #183 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
- `frontend/src/components/Gabarit.tsx` :
  - la marque devient un logo dans un cadre (`styles.marque`) avec le nom « Astrée » (`motMarque`) et la devise « Tribunal des décisions » (`devise`) ;
  - `Procedure` affiche les étapes en contrôle segmenté : un curseur (`styles.progression`) glisse jusqu'à l'étape courante. Le rang affiché part de celui de l'écran précédent (`dernierRang`, au niveau du module, car chaque écran remonte le gabarit), puis passe au rang courant à l'image suivante (`requestAnimationFrame`) pour que la transition CSS joue. Les variables CSS `--rang` et `--nb-etapes` portent la position et le nombre d'étapes.
- `frontend/src/components/Gabarit.module.css` : bandeau de simulation sombre, dégradé léger de l'en-tête, styles de la marque et du contrôle segmenté. Le trait de liaison entre les étapes (`liaison`) est retiré.

## Comment l'utiliser
Rien à appeler : tous les écrans passent par `Gabarit`. `npm run dev` dans `frontend/`, puis passer d'un écran à l'autre pour voir le curseur glisser.

## Comment vérifier
`npm run typecheck` dans `frontend/` passe. `npm test` : seuls les deux tests du mode démonstration qui appellent la vraie Lambda peuvent échouer si elle répond 429 (« Tribunal occupé ») ; ils échouent aussi sans ce changement.

## Choix faits en cours de route
- Changement purement visuel : aucun texte de procédure, aucun lien ni aucune route ne change ; `aria-current` reste sur l'étape courante.
- Déployé sur CloudFront avant la fusion (depuis la copie locale), pour la vidéo de démonstration ; cette PR ramène le code dans `main` pour qu'un redéploiement ne le perde pas.

## Limites et suite
- `dernierRang` est partagé par tout le module : avec deux gabarits affichés en même temps, le curseur du second partirait du rang du premier (cas absent de l'interface).
