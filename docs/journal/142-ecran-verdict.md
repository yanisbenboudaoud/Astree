# #142 — Écran Verdict : quatre options au même niveau, jauge du seuil, ce que la signature archive

- **Issue** : #142 · **PR** : #143 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
L'écran Verdict présente maintenant les trois verdicts du contrat (`maintenu`, `modifie`, `pacte_ajuste`) comme des options de même rang, chacune avec ses chiffres et une jauge qui la place face au seuil du Pacte.

- **`frontend/src/domaine/verdict.ts`** :
  - `optionsVerdict` renvoie aussi l'option `pacte` (remplace la constante `OPTION_PACTE`). Sa fonction interne `optionPacte` lit `points_de_bascule` (#61) : une ligne par règle à changer (« §1 · Pire baisse tolérée : −29,0 % au lieu de −12 % »), avec ses pièces. Statut `Conforme` si chaque violation a un point de bascule, sinon `Violation` (ex. : critère ESG, aucun seuil ne le rend conforme).
  - `OptionVerdict` gagne `pireBaisse`, `seuil`, `ancienSeuil` et `ajustements`.
  - « Renoncer » affiche le portefeuille actuel (`comparaison.actuel`) et un statut : `Conforme` si `taille_max_compatible` existe (à 0 %, les règles chiffrées sont respectées), `Violation` s'il vaut `null`.
  - Une phrase neutre par option ; « Pire baisse » au lieu de « Chute max. », jusque dans la phrase d'engagement.
- **`frontend/src/ecrans/Verdict.tsx`** et **`Verdict.module.css`** :
  - `JaugeBaisse` : barre de la pire baisse (rouge au-delà du seuil, verte sinon), repère du seuil, légende ; même échelle pour toutes les options (`echelleJauges`). Décorative (`aria-hidden`) : les nombres sont écrits dans la carte.
  - Encadré « Ce que la signature archive » (choix, date, nombre de pièces et de contrôles, justification si l'option en demande une, « Rien n'est exécuté ») avec le bouton d'export. Il remplace l'encadré « Ce qui changerait la réponse » de la fiche 061 et le bloc « Procès-verbal » de la fiche 103.
  - Retirés : le lien « Ou ajuster votre Pacte avant de décider », le second « Retour au Tribunal », la phrase en double à côté du bouton.
  - Sur téléphone, l'encadré passe entre les options et le bouton de signature.
- **`frontend/src/components/Limites.tsx`** : `ouvertParDefaut={false}` replie aussi un panneau sur grand écran ; le Verdict l'utilise, le Tribunal garde ses limites ouvertes.
- **`frontend/e2e/verifier.mjs`** : les points de bascule se comptent dans la carte « Ajuster mon Pacte » (`[data-ajustement]`).

## Comment l'utiliser
Rien à configurer : l'écran lit le contrat. Un profil sans violation garde quatre options ; « Ajuster mon Pacte » n'y propose alors aucun seuil.

## Comment vérifier
- Depuis `frontend/` : `npx tsc --noEmit` passe ; `npm test` donne 135 tests sur 137. Les 2 échecs de `domaine.test.ts` (« Tribunal occupé ») existaient avant. Les tests « options du Verdict » couvrent la 4ᵉ option (Robert : conforme avec −29,0 % ; Mateo : aucune bascule, reste en violation ; Amira : 3 ajustements) et les chiffres de « Renoncer » (−7,8 %).
- `ASTREE_URL=http://localhost:<port> node e2e/verifier.mjs` (mode démonstration) : 23 écrans, aucun problème axe-core ni de parcours ; seules restent les erreurs CORS d'un port autre que 5173.

## Choix faits en cours de route
- **Pas de repère de l'ancien seuil sur la jauge** de « Ajuster mon Pacte » : en pointillé sur la barre verte, il ne se voyait pas. La légende l'écrit (« Seuil ajusté −29,0 % (au lieu de −12 %) »).
- **Limites repliées** sur cet écran : elles concurrençaient les options. Le compteur (4) reste visible.
- **Disposition en paysage (#103) conservée** : les options à gauche, l'archive et les limites à droite.

## Limites et suite
- Le reste de l'interface (Portefeuille, Décision) dit encore « Chute maximale » : à harmoniser avec « Pire baisse » du Pacte.
- La jauge ne montre que la règle `pire_baisse_max` ; les plafonds n'ont que leurs chiffres et leur badge.
- Choisir « Ajuster mon Pacte » archive une intention ; la modification du Pacte et le nouveau procès restent à faire par l'utilisateur.
