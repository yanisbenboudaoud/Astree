# #165 — Trompez le Greffier, 100 fois : taux de détection de verifier_chiffres

- **Issue** : #165 · **PR** : #173 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
La promesse « aucun chiffre inventé ne passe » est maintenant **mesurée** : un jeu de 152 cas écrits à l'avance est joué contre le vérificateur du Greffier, et un rapport donne un taux par famille avec son intervalle de confiance.

- **`validation/evaluation.py`** (nouveau), module commun aux évaluations (servira à #166 et #167) :
  - `intervalle_wilson(k, n)` : intervalle de Wilson à 95 % ;
  - `charger_jeu(nom)` : lit `validation/jeux/<nom>.json`, refuse une famille non déclarée ou un identifiant en double ;
  - `ResultatCas`, `taux`, `tableau_familles` : briques du rapport Markdown ;
  - `evaluer_jeu(nom)` et `main` : `python -m validation.evaluation <jeu>` écrit `docs/validation/evaluation_<jeu>.md`. Le jeu déclare son `evaluation` (aujourd'hui seulement `chiffres`), donc un second jeu `chiffres_2.json` passerait par la même commande.
- **`validation/evaluation_chiffres.py`** (nouveau) : `jouer_cas` vérifie chaque texte avec `verifier_argument` (`pipeline/chiffres.py`, le code du Greffier et de « Trompez le Greffier »), sur la décision et les pièces du procès enregistré et la période 2021-11-12 → 2026-11-12. Un piège compte comme détecté seulement si l'argument est rejeté **et** que le nombre piège est parmi les introuvables : un rejet pour un autre nombre est un raté. Pour un piège accepté, `ou_est_trouve` nomme la pièce et le champ qui le contiennent. `rapport` écrit le rapport.
- **`validation/jeux/chiffres.json`** (nouveau) : 152 cas sur les pièces des 7 procès de `frontend/src/data/proces/`.
  - 66 pièges, 11 par famille de l'issue : `chiffre_altere`, `arrondi_faux`, `signe_faux`, `nombre_derive`, `piece_non_citee`, `date_absente`.
  - 6 pièges `mauvaise_grandeur` (`hors_promesse`), mesurés à part (voir plus bas).
  - 80 arguments valides : les 56 arguments acceptés des 7 procès, tels quels, et 24 variantes (`arrondi_legitime`, `mot_de_baisse`, `plage`, `ecart_de_piece`, `date_legitime`).
- **`docs/validation/evaluation_chiffres.md`** (généré) : le rapport.
- **`tests/test_evaluation.py`** (nouveau) : Wilson (valeur de référence 5/10, 0/n, n/n, entrées impossibles), contenu du jeu (au moins 60 pièges et 40 valides, familles de l'issue, chaque piège extrait tel qu'écrit), règle de détection, et **le rapport se régénère à l'identique et correspond au fichier du dépôt**.

## Comment l'utiliser
```bash
python -m validation.evaluation chiffres
```

## Comment vérifier
```bash
pytest tests/test_evaluation.py
```
Résultat de la première mesure : **66/66 chiffres inventés détectés** (IC 95 % : 94,5 % à 100 %), **80/80 arguments valides acceptés** (aucun faux rejet), **0/6** pièges `mauvaise_grandeur` détectés.

## Choix faits en cours de route
- **Jeu contrôlé avant la mesure, puis figé.** Un script à part (non versé) a vérifié, sans passer par le vérificateur, que chaque nombre piège est absent des sources admises (et, pour `piece_non_citee`, présent dans une autre pièce), et que chaque nombre d'une variante valide existe. Il a trouvé des pièges mal écrits : la pièce de simulation calcule déjà des écarts (`ecart_pire_baisse_points`, `ecart_rendement_annuel_points`, `rapport_volatilite`), donc « 21,2 points de plus » est **juste** pour 30 % en TSLA (règle 6). Ces cas sont devenus la famille valide `ecart_de_piece`, et les pièges `nombre_derive` utilisent des écarts que Python ne calcule pas. Les familles ont été fixées avant la première mesure.
- **Limite connue mesurée, pas cachée** : `mauvaise_grandeur`. Le vérificateur contrôle qu'un nombre existe dans une pièce citée, pas qu'il désigne la bonne grandeur : « la volatilité était de 9,3 % » passe, parce que 9,3 % est le rendement d'avant (`rendement_annuel_actuel`). Ce n'est pas un chiffre inventé, donc ces cas ne comptent pas dans le taux de la promesse, mais le rapport les affiche, avec le champ trouvé. Une parade possible (rattacher chaque nombre au champ voulu) demanderait aux agents de citer le champ, pas seulement la pièce.
- **Rapport sans date** pour qu'il se régénère à l'identique ; la date de rédaction du jeu est dans le jeu.
- Un raté n'est pas corrigé en silence : si une règle est corrigée, la mesure suivante se fait sur un second jeu écrit après la correction.

## Limites
- 11 cas par famille : l'intervalle de Wilson par famille reste large (74 % à 100 %). Le taux global sur 66 pièges est plus serré.
- Les pièges sont écrits par l'équipe, qui connaît les règles ; ils ne remplacent pas des tentatives d'utilisateurs (#69).
- Les procès enregistrés viennent de 3 profils de test ; un procès rejoué change de pièces, donc le jeu reste lié à ces fichiers.
