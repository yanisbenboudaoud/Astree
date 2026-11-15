# #166 — Trompez le Greffier, côté cadre : conseils et promesses bloqués, arguments légitimes admis

- **Issue** : #166 · **PR** : #176 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
La règle « aucun conseil personnalisé ni promesse sur l'avenir » (`CLAUDE.md`, section 4 quater) est maintenant **mesurée**, dans les deux sens : ce que le contrôle bloque, et ce qu'il laisse passer à tort ou bloque à tort.

- **`validation/jeux/cadre.json`** (nouveau) : 149 cas écrits avant la mesure, chacun avec son `auteur` :
  - `equipe` (109 cas) : écrits à partir de la règle de `CLAUDE.md`, par une personne qui a vu les signatures du code ;
  - `externe` (40 cas : 20 à bloquer, 20 légitimes) : écrits par un agent sans aucun accès au dépôt, à partir de la seule règle (tâche de l'issue).

  Les familles :
  - 78 cas **à bloquer**, en 8 familles, chacune liée à une infraction (`conseil` ou `promesse`) : `conseil_direct`, `imperatif`, `conseil_nie`, `conseil_au_profil` (conseils) ; `promesse_hausse`, `promesse_baisse`, `repetition`, `garantie` (promesses).
  - 71 cas **légitimes et piégeux**, en 6 familles : `pacte_cite` (mots de l'investisseur entre guillemets, même à l'impératif), `prevision_niee`, `conditionnel_scenario`, `interrogation_indirecte`, `reponse_demande_conseil` (contre-interrogatoire), `constat_factuel` (verbes de hausse et de baisse au passé).
- **`validation/evaluation_cadre.py`** (nouveau) :
  - `jouer_cas` : joue un texte avec `verifier_cadre_simulation` (`pipeline/cadre_simulation.py`, la fonction du Greffier). Un cas à bloquer est détecté seulement si l'argument est rejeté **et** qu'une infraction de la famille attendue est relevée ; un rejet pour l'autre famille est un raté (`rejete_autre_motif`).
  - `evaluer`, `rapport` : rapport Markdown avec le taux global, le taux des conseils et celui des promesses, le taux d'arguments légitimes admis, le taux de chaque groupe d'auteurs, le tableau par famille (Wilson à 95 %) et chaque raté avec son texte.
- **`validation/evaluation.py`** : le jeu `cadre` est branché sur la commande commune de #165.
- **`docs/validation/evaluation_cadre.md`** (généré) : le rapport.
- **`tests/test_evaluation_cadre.py`** (nouveau) : contenu du jeu (au moins 50 + 50, familles de l'issue, infraction déclarée, textes distincts), part écrite sans accès au code, règle de détection (conseil, promesse, rejet pour l'autre famille, raté, faux rejet), **rapport régénéré à l'identique et identique au fichier du dépôt**, chaque raté présent avec son texte.

## Comment l'utiliser
```bash
python -m validation.evaluation cadre
```

## Comment vérifier
```bash
pytest tests/test_evaluation_cadre.py
```
Résultat de la mesure :
- **47/78 conseils et promesses bloqués** (60,3 % ; IC 95 % : 49,2 % à 70,4 %) : conseils 23/41, promesses 24/37 ;
- **71/71 arguments légitimes admis** (IC 95 % : 94,9 % à 100 %) : **aucun faux rejet** ;
- par auteur : cas de l'équipe 38/58 bloqués (65,5 %) ; **cas écrits sans accès au code 9/20 bloqués (45,0 %)**, 20/20 légitimes admis.

Le contrôle est donc **précis mais incomplet** : il ne bloque jamais à tort sur ce jeu, mais laisse passer environ deux tournures interdites sur cinq, et davantage quand l'auteur ne connaît pas le code. Les 31 ratés, tous dans le rapport, se regroupent ainsi :
- conseil indirect ou impersonnel : « il serait préférable de », « la meilleure décision est de », « mieux vaut », « il est recommandé à Mateo de » ;
- impératifs absents de la liste : « gardez », « pensez à », « ne touchez pas », « n'ajoutez pas » ;
- conseil nié : « il ne faut surtout pas », « je ne recommande pas » ;
- conseil au profil sans « devrait » : « aurait intérêt à », « ferait mieux de », « gagnerait à » ;
- futur simple sans verbe de marché listé : « continuera de », « finira par », « sera supérieur », « restera élevée », « retrouvera son sommet » ;
- certitude : « il est certain que », « sans aucun doute », « assure à Robert de retrouver », « sera immanquablement effacée » ;
- côté cas externes aussi : « le plus raisonnable serait de », « il ne faut pas toucher », « Mateo doit retirer », « subira une chute », « finira par décrocher ».

## Choix faits en cours de route
- **Jeu écrit à partir de la règle, pas du code.** Les cas de l'équipe viennent de `CLAUDE.md` (section 4 quater) et de tournures courantes en français ; seules les signatures publiques de `pipeline/cadre_simulation.py` ont été lues, pour savoir comment l'appeler. Chacun des 20 ratés a été relu après la mesure : tous sont bien des conseils ou des promesses selon la règle, aucun cas n'a été retiré ni réécrit.
- **Le jeu est figé.** Le contrôle n'a pas été corrigé dans cette issue : un raté reste dans le rapport, et une correction se mesurera sur un second jeu (`cadre_2.json`), écrit après la correction, comme pour #165.
- **Détection par famille d'infraction** : un conseil rejeté seulement comme promesse ne compte pas, sinon le taux mesurerait la chance plutôt que la règle.
- **Pas d'arguments réels des procès enregistrés comme cas légitimes** (contrairement à #165) : ils ont déjà passé ce même contrôle pour être affichés, donc ils mesureraient le filtre contre lui-même.

## Limites et suite
- **Cas externes** : écrits par un agent Claude lancé sans accès au dépôt, avec pour seule consigne la règle de la section 4 quater ; chaque cas a été relu avant d'entrer dans le jeu (familles correctes, aucun retiré). Un humain de l'équipe qui n'a pas lu le code peut encore en ajouter (`"auteur": "externe"`), puis relancer la commande.
- Suite proposée : une issue pour élargir `cadre_simulation` aux tournures ratées, mesurée sur un second jeu. Risque à surveiller : élargir les motifs fera monter les faux rejets (« le Tribunal ne recommande ni d'acheter ni de vendre » doit rester admis).
- 6 à 9 cas par famille : les intervalles de Wilson par famille restent larges ; les taux globaux sont plus serrés.
- Les cas sont écrits par l'équipe, en français soigné ; un LLM pourrait produire d'autres tournures. #172 affichera ces taux dans l'interface.
