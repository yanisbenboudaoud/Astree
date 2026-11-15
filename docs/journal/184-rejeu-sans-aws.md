# #184 — Mode démonstration sans AWS : contre-interrogatoires réels rejoués

- **Issue** : #184 · **PR** : à venir · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Les comptes AWS du Datathon sont supprimés le 16 novembre 2026 à 11 h 30. Après, l'interface ne peut plus que rejouer des procès enregistrés (mode démonstration, fiche [014](014-interface-astree.md)).

- `frontend/src/data/proces/2026-11-15-e79cef530bc9.json` : Robert, 30 % en TSLA, avec le contre-interrogatoire « Et si je mettais 15 % au lieu de 30 % ? » (pièces P9 et P10, 26/26 chiffres). Il est placé **avant** `fcb6ce39f184` dans `index.json` : c'est lui qui est rejoué pour Robert à 30 %.
- `frontend/src/data/proces/2026-11-15-537f2b8e2d49.json` : Amira, 100 % réalloué vers QQQ et NVDA à 50 %, avec deux règles en violation et le contre-interrogatoire « si j'enlève 50% » (27/27 chiffres).
- Les deux contrats sont copiés tels quels depuis `traces/2026-11-15/` du bucket, sauvegardé avant la suppression du compte.
- `frontend/public/proces-verbaux/` : leurs deux procès-verbaux.
- `frontend/src/domaine/debat.ts` : la règle du thème `taille` reconnaît aussi « réallocation limitée à 71 % ». Sans cela, un argument de l'Avocat d'Amira tombait dans « Autres points ».
- `frontend/README.md` : la liste des procès enregistrés et une ligne « Sans AWS ».

Aucun changement de code d'accès : `jugerDecision` rejouait déjà le champ `contre_interrogatoire` d'un contrat enregistré (`adapterContrat`).

## Comment l'utiliser
```bash
VITE_USE_MOCKS=true VITE_API_URL= npm --prefix frontend run dev
```
Robert → 30 % en TSLA → Soumettre au Tribunal : la question enregistrée et ses réponses s'affichent sous le débat.

## Comment vérifier
- `python -m contrat.valider frontend/src/data/proces/2026-11-15-e79cef530bc9.json` (et `537f2b8e2d49`) : contrats valides.
- `VITE_USE_MOCKS=true VITE_API_URL= npm --prefix frontend test` : 154 tests. `domaine.test.ts` vérifie que le procès rejoué pour Robert à 30 % a son échange ; `debat.test.ts` vérifie que chaque argument des procès enregistrés a un thème.
- Dans le navigateur, sans `VITE_API_URL` : aucune requête vers `amazonaws.com`, aucune erreur dans la console.

## Choix faits en cours de route
- Ces procès ont été tenus sur la Lambda **avant** la suppression du compte. Aucun procès n'est fabriqué ni retouché.
- Procès-verbaux générés en local par `python -m pipeline.proces_verbal --demo`, pas par la route `/proces-verbal` : la commande redonne à l'identique les 7 pages déjà présentes, et elle marchera encore sans AWS.
- Mateo n'a pas de contre-interrogatoire rejoué : les seuls enregistrés pour ce profil (« allo ») ne montrent rien d'utile.

## Limites et suite
- Sans AWS : pas de nouvelle décision, de question libre, de « Trompez le Greffier » ni de « Construire mon Pacte » avec vos propres réponses. L'écran le dit à chaque fois.
- Sofia (poches, #115) n'a aucun procès enregistré, et l'interface ne gère pas les poches.
- Le site CloudFront (#135) disparaît avec le compte : un autre hébergement serait nécessaire pour donner un lien au jury.
