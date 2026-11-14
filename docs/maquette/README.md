# Maquette de référence — Le Tribunal

## Où la trouver

- **Figma (référence visuelle, modifiable)** : https://www.figma.com/design/eBlJ3Ze7ALeY2QdFXZMdI4
  - Parcours de Robert : Portefeuille → Décision → Tribunal → Verdict, relié en prototype cliquable (▶ Présenter).
  - Tribunal d'Amira et Tribunal de Mateo.
  - Couleurs en variables (« AlphaForge · Couleurs ») et composants réutilisables (étiquettes, boutons, chiffres clés, contrôles du Greffier).
- **`prototype.html` (comportement)** : ouvrir dans un navigateur. Tout est interactif : choix du persona, curseur de taille, financement, trace animée, pièces, contre-interrogatoire, verdict. Le style est plus ancien que celui de Figma : Figma fait foi pour le visuel, le prototype pour le comportement.

## Les 4 écrans

1. **Portefeuille** : chiffres clés, allocation, positions, Pacte du persona, décision à tester.
2. **Décision** : fiche du titre, curseur de taille avec zone compatible / en conflit, taille maximale compatible, mode de financement, comparaison avant / après, alerte de conflit, bouton « Soumettre au Tribunal ».
3. **Tribunal** : trace d'exécution des agents, Procureur et Avocat (arguments étiquetés, chacun avec ses pièces), contrôles du Greffier, pièces à conviction dépliables (source, traitement, limites), contre-interrogatoire.
4. **Verdict** : synthèse, avertissement, trois choix (maintenir, modifier, ajuster le Pacte), archivage dans le journal.

## Données

Les chiffres de la maquette ont été calculés sur `alphaforge_starter/` avec la méthode décrite dans `CLAUDE.md` (section 6 bis). Dans le prototype, les tailles de position sont **précalculées** ; dans l'application, elles seront calculées à la demande par les outils Python dans Lambda.

Le faux JSON correspondant à l'écran Tribunal de Robert est dans `docs/exemples/contrat_robert.json`.
