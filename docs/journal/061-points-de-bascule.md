# #61 — « Qu'est-ce qui changerait la réponse ? » : points de bascule par règle

- **Issue** : #61 · **PR** : #75 · **Statut** : terminée côté code ; procès de démo à refaire par la Lambda après la fusion
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`pipeline/points_de_bascule.py`** : outil Python sans LLM. Pour chaque règle **calculable** du Pacte en violation (`pire_baisse_max`, `plafond`), il donne deux façons de la rendre conforme.
  - `points_de_bascule(recherche)` : relit la recherche de `taille_max_compatible` (fiche 021), sans nouvelle simulation. La dernière taille testée est la taille demandée, et son statut dit quelles règles sont en violation. Pour chacune, il renvoie `taille_max`, la plus grande taille (ou part réallouée) où **cette** règle est conforme (`None` si même 0 % la viole), et `seuil_suffisant`, la valeur simulée après la décision : la pire baisse, ou la part des catégories du plafond.
  - `seuil_suffisant(type, valeur)` : arrondit la valeur à 6 décimales **du côté permissif**, avec les comparaisons du Greffier.
  - `piece_points_de_bascule(id, recherche, decision)` : pièce `calculee`, étiquette `fictif`, valeurs brutes en listes parallèles (`regles_en_violation`, `seuils_du_pacte`, `seuils_suffisants`, `tailles_max_par_regle`), plus `taille_demandee`, `taille_max_toutes_regles` et `pas_de_recherche`. Elle vaut `None` sans violation.
  - `pour_contrat(recherche, decision, id_piece)` : le champ `points_de_bascule` du contrat, avec un `message` écrit par Python.
- **`pipeline/taille_max.py`** : `EtapeRecherche.statuts` garde le statut que le Greffier rend pour chaque règle calculable, à chaque taille.
- **`pipeline/tribunal.py`** : `verser_points_de_bascule` ajoute la pièce **d'office**, après l'orchestrateur et avant le débat. L'étape de trace porte `etape: "orchestrateur"` et la raison `RAISON_POINTS_DE_BASCULE` (« Pièce obligatoire ajoutée d'office : une règle calculable du Pacte est en violation »). La recherche de taille maximale est faite une seule fois, pour les deux champs. `prochain_numero` numérote la pièce à la suite du dossier ; il vient de `pipeline/contre_interrogatoire.py` (fiche 055), qui l'importe désormais de `tribunal.py`.
- **`pipeline/debat.py`** : une phrase de consigne de plus pour le Procureur (rappeler ce qui changerait la réponse) et pour l'Avocat (version plus modeste), **comme un constat, jamais comme un conseil** (« jamais « vous devriez » ni « il faudrait » »). Sans cette précision, un argument de l'Avocat disait « il faudrait envisager d'ajuster le seuil du Pacte ».
- **`pipeline/greffier.py`** : `_nom_categories` devient public (`nom_categories`), pour le résumé de la pièce.
- **Contrat** : champ `points_de_bascule` dans `contrat/schema_sortie.json` (`$defs/point_de_bascule`). `contrat/valider.py` (`erreurs_points_de_bascule`) exige un point par règle calculable en violation, et seulement pour elles. Il vérifie aussi le type, les doublons et les pièces citées. `docs/exemples/` : pièce P6, étape de trace et champ dans les deux exemples. `CLAUDE.md` : sections 4, 4 bis (outil 8) et 5.
- **Interface** : `points_de_bascule?` dans `src/api/contrat.ts` ; `pointsDeBascule()` dans `src/domaine/verdict.ts`. L'écran Verdict affiche un encadré « Ce qui changerait la réponse » : paragraphe et libellé de la règle, message, lien vers la pièce (qui ouvre son tiroir). Sans le champ, rien n'est affiché.

## Comment l'utiliser
```python
from pipeline.taille_max import rechercher_taille_max
from pipeline.points_de_bascule import points_de_bascule, pour_contrat

recherche = rechercher_taille_max(profil["portefeuille"], decision, profil["pacte"]["regles"])
pour_contrat(recherche, decision, "P7")[0]["message"]
# « Conforme jusqu'à 9 % en TSLA, ou avec un seuil de −29,0 % au lieu de −12,0 % »
```
Dans un procès (`juger_decision`), rien à faire : la pièce est versée d'office dès qu'une règle calculable est en violation.

## Comment vérifier
`pytest tests/test_points_de_bascule.py tests/test_orchestrateur.py tests/test_contrat.py`, puis `npm test` dans `frontend/`. Les tests prouvent :
- **les trois tests de l'issue** : profil prudent + 30 % de TSLA, conforme jusqu'à 9 % ou avec un seuil de −29,0 % ; profil audacieux + panier crypto-tech, 3 points (pire baisse 36 %, plafond crypto 28 %, tech et crypto 50 %) ; aucune violation, ni pièce ni erreur ;
- **les points disent vrai** : mêmes règles que les violations du Greffier. Avec le seuil suffisant à la place du sien, le Greffier rend `conforme`. À `taille_max`, la règle est conforme ; un point plus haut, elle est en violation ;
- les cas limites : exclusion (« conforme seulement sans la décision »), portefeuille déjà hors Pacte (`taille_max` à `None`), règle `a_verifier` sans point ;
- `verifier_chiffres` accepte un argument qui cite la pièce, et rejette un chiffre absent ou une pièce non citée ;
- le validateur rejette un point manquant, en trop, d'un autre type, en double, ou qui cite une pièce inexistante ; un contrat sans le champ reste valide.

**Vrais procès** (Bedrock, `python -m pipeline`, 2026-11-14), les deux contrats passent `valider_contrat` :
1. Profil prudent, « 30 % en Tesla », 28 s : pièce P7 ; le Procureur la cite (« La règle de pire baisse serait respectée jusqu'à 9 % en TSLA, ou avec un seuil de −29,0 % inscrit au Pacte à la place de −12 % »), l'Avocat aussi. `verifier_chiffres` : 34/34 chiffres, 7 arguments, 0 rejeté.
2. Profil audacieux, panier crypto-tech à 100 %, 36 s : 3 points de bascule ; le Procureur cite P7 deux fois ; 33/33 chiffres, 7 arguments, 0 rejeté.

**Lambda déployée** (`deployer.py` depuis cette branche, puis `tester_function_url.py robert "Je veux mettre 30 % de mon portefeuille en Tesla"`) : HTTP 200 en 20,5 s, procès archivé `2026-11-15-1e35809282d3`. Le contrat passe `valider_contrat` ; la pièce P7 est versée d'office et citée par 3 arguments. Avant le déploiement, le code en ligne était celui de `main` avant #72 : aucun travail non fusionné n'a été écrasé. **Attention** : quelques minutes plus tard, la Lambda a été redéployée depuis la branche de #78 (fusionnée depuis), sans #61. Le code en ligne ne produit donc plus les points de bascule ; il faut redéployer `main` après la fusion.

**Interface** : `npm run verifier` passe sans problème (23 écrans, axe-core). L'encadré a été vérifié avec un vrai procès, le temps de la vérification, à 1440 et à 390 px : 1 point pour Robert, 3 pour le panier d'Amira. Le lien de la pièce ouvre son tiroir.

## Choix faits en cours de route
- **Pièce d'office, pas un outil de l'orchestrateur** : elle n'a aucun paramètre à choisir et doit être là à chaque violation. Un outil aurait été un faux choix qui consomme le budget d'appels. L'orchestrateur garde `taille_max_compatible` pour explorer. Le pourquoi est dans `docs/CHOIX_CONCEPTION.md`, choix 10 bis.
- **Une taille par règle** plutôt que la seule taille maximale globale : l'utilisateur voit quelle règle bloque. La taille globale reste dans `taille_max_compatible` et dans la pièce.
- **Arrondi du côté permissif** : au plus proche, la pire baisse du panier audacieux (−0,6185554) donnait −0,618555, qui laissait la règle en violation. Le test « le seuil suffisant rend la règle conforme » l'a montré.
- **Champ facultatif dans le schéma** : les procès enregistrés de l'interface (`frontend/src/data/proces/`) datent d'avant #61 et doivent continuer à passer `contrat.valider`. Le pipeline produit toujours le champ, et `valider.py` le contrôle dès qu'il est présent.
- **Listes parallèles dans la pièce**, comme la jurisprudence (fiche 056) : le schéma n'admet que des listes de valeurs simples.
- **Raison de trace d'office** : elle commence par « Pièce obligatoire ajoutée d'office », comme le demande `CLAUDE.md` section 5. L'interface l'affiche donc avec l'icône de signalement, comme la simulation ajoutée d'office.

## Limites et suite
- Seules les règles calculables ont un point de bascule. Pour le cas 3 (profil ESG + XOM, critère documentaire), le champ est vide.
- **Procès de démo** : pendant ce travail, `main` est passé à de vrais procès de la Lambda, archivés dans S3 et nommés d'après leur identifiant (#74, #76). Ils datent d'avant #61 : sans le champ, l'encadré du Verdict n'apparaît pas encore en démonstration. Un premier réenregistrement local, fait sur l'ancienne convention, a été remplacé par ces fichiers à la fusion. À faire après la fusion de #75 : déployer `main`, puis refaire par la Lambda les procès de Robert à 30 % et du panier d'Amira (`tester_function_url.py … --sortie`). Il faudra remplacer leurs fichiers et `index.json`, ajuster `src/test/domaine.test.ts`, et faire contrôler l'encadré par `e2e/verifier.mjs`. Les procès de Mateo (sans point de bascule) et de Robert à 25 % (argument corrigé par le Greffier) peuvent rester tels quels.
- Le champ reste facultatif dans le schéma. On pourra le rendre obligatoire quand les procès enregistrés l'auront tous et qu'aucune branche en cours ne fabriquera plus de contrat sans lui.
- Un seuil qui suffit sur la période passée ne protège pas d'une baisse future plus forte : la pièce le dit dans ses `limites`.
