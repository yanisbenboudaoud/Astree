# Évaluation : Trompez le Greffier, 100 fois : taux de détection de verifier_chiffres

> Généré par `python -m validation.evaluation chiffres` à partir de `validation/jeux/chiffres.json` (issue #165, jeu rédigé le 2026-11-15). Ne pas modifier à la main : relancer la commande.

Jeu écrit avant la première mesure, sur les pièces des 7 procès enregistrés (frontend/src/data/proces/). Un piège contient un seul nombre fautif, `piege`, écrit tel que le vérificateur l'extrait ; tous ses autres nombres existent dans les pièces citées. Il est détecté si l'argument est rejeté et que ce nombre est parmi les introuvables. Un argument valide doit être accepté. Les familles sont fixées avant la mesure ; un raté reste dans le rapport, et une règle corrigée se mesure sur un second jeu écrit après la correction.

## Résultat

- **Chiffres inventés détectés** : 66/66 (100,0 % ; IC 95 % : 94,5 % à 100,0 %).
- **Arguments valides acceptés** : 80/80 (100,0 % ; IC 95 % : 95,4 % à 100,0 %) ; faux rejets : 0.
- **Limite connue, mesurée à part** (chiffre exact, mauvaise grandeur) : 0/6 (0,0 % ; IC 95 % : 0,0 % à 39,0 %) détectés.

152 cas sur les pièces de 7 procès enregistrés. Un taux de 100 % sur 66 pièges ne prouve pas l'infaillibilité : la borne basse de l'intervalle de Wilson dit ce que l'échantillon permet d'affirmer.

## Par famille

| Famille | Attendu | Réussis | Taux | IC 95 % (Wilson) |
|---|---|---|---|---|
| Chiffre altéré (`chiffre_altere`) | rejeté | 11/11 | 100,0 % | 74,1 % à 100,0 % |
| Arrondi au-delà de la pièce (`arrondi_faux`) | rejeté | 11/11 | 100,0 % | 74,1 % à 100,0 % |
| Signe faux (`signe_faux`) | rejeté | 11/11 | 100,0 % | 74,1 % à 100,0 % |
| Nombre dérivé (`nombre_derive`) | rejeté | 11/11 | 100,0 % | 74,1 % à 100,0 % |
| Chiffre d'une pièce non citée (`piece_non_citee`) | rejeté | 11/11 | 100,0 % | 74,1 % à 100,0 % |
| Date absente (`date_absente`) | rejeté | 11/11 | 100,0 % | 74,1 % à 100,0 % |
| Chiffre exact, mauvaise grandeur (`mauvaise_grandeur`) | rejeté | 0/6 | 0,0 % | 0,0 % à 39,0 % |
| Argument accepté d'un procès (`argument_proces`) | accepté | 56/56 | 100,0 % | 93,6 % à 100,0 % |
| Arrondi légitime (`arrondi_legitime`) | accepté | 5/5 | 100,0 % | 56,6 % à 100,0 % |
| Valeur absolue après un mot de baisse (`mot_de_baisse`) | accepté | 5/5 | 100,0 % | 56,6 % à 100,0 % |
| Plage (`plage`) | accepté | 5/5 | 100,0 % | 56,6 % à 100,0 % |
| Écart calculé par Python (`ecart_de_piece`) | accepté | 4/4 | 100,0 % | 51,0 % à 100,0 % |
| Date d'une pièce (`date_legitime`) | accepté | 5/5 | 100,0 % | 56,6 % à 100,0 % |

## Ratés

| Cas | Famille | Texte | Pièces | Résultat |
|---|---|---|---|---|
| `piege-056` | `mauvaise_grandeur` | Sans cette position, la volatilité du portefeuille était de 9,3 %. | P2 | accepté : « 9,3 % » trouvé dans P2 (rendement_annuel_actuel) |
| `piege-057` | `mauvaise_grandeur` | Avec la décision, la pire baisse est 3 fois plus profonde qu'avant. | P2 | accepté : « 3 » trouvé dans P2 (rapport_volatilite) |
| `piege-058` | `mauvaise_grandeur` | Avec 30 % en TSLA, la pire baisse atteint −7,8 %. | P2 | accepté : « −7,8 % » trouvé dans P2 (pire_baisse_actuelle) |
| `piege-059` | `mauvaise_grandeur` | La réallocation a affiché un rendement de +19,0 % par an. | P2 | accepté : « +19,0 % » trouvé dans P2 (rendement_annuel_actuel) |
| `piege-060` | `mauvaise_grandeur` | Avec XOM, le portefeuille a rendu +11,5 % par an. | P2 | accepté : « +11,5 % » trouvé dans P2 (rendement_annuel_actuel) |
| `piege-061` | `mauvaise_grandeur` | Avec XOM, la part du portefeuille en dollars américains est de 45 %. | P3 | accepté : « 45 % » trouvé dans P3 (part_usd_actuelle) |

## Familles

- **Chiffre altéré** (`chiffre_altere`, rejet attendu) : Un chiffre d'une pièce citée, modifié (« −26,9 % » au lieu de « −24,9 % »).
- **Arrondi au-delà de la pièce** (`arrondi_faux`, rejet attendu) : Plus de décimales que la pièce n'en justifie, ou une troncature au lieu d'un arrondi (« −29,03 % », « −28,9 % » pour −0,289679).
- **Signe faux** (`signe_faux`, rejet attendu) : Signe inversé, ou valeur négative écrite sans signe hors d'un mot de baisse (« le portefeuille ferait 2,6 % »).
- **Nombre dérivé** (`nombre_derive`, rejet attendu) : Écart, ratio ou variation calculé par l'auteur et absent des pièces (« 2,5 points de plus », « 3 fois plus »).
- **Chiffre d'une pièce non citée** (`piece_non_citee`, rejet attendu) : Chiffre exact, mais qui n'existe que dans une pièce que l'argument ne cite pas.
- **Date absente** (`date_absente`, rejet attendu) : Date, mois ou année qui ne correspond à aucune date des pièces citées, de la décision ou de la période.
- **Chiffre exact, mauvaise grandeur** (`mauvaise_grandeur`, rejet attendu) : Limite connue, mesurée à part : un chiffre qui existe dans une pièce citée, mais attribué à une autre grandeur (le rendement d'avant présenté comme celui d'après). Le vérificateur contrôle l'existence d'un nombre, pas son sens : ce piège n'est pas un chiffre inventé.
- **Argument accepté d'un procès** (`argument_proces`, acceptation attendue) : Réquisitoire et plaidoirie affichés par les 7 procès enregistrés, tels quels.
- **Arrondi légitime** (`arrondi_legitime`, acceptation attendue) : Chiffre d'une pièce arrondi correctement, avec moins ou plus de décimales (« −29 % », « −28,97 % »).
- **Valeur absolue après un mot de baisse** (`mot_de_baisse`, acceptation attendue) : Valeur négative écrite sans signe juste après « chute de », « baisse de », « perte de », « recul de ».
- **Plage** (`plage`, acceptation attendue) : Deux nombres d'une plage ou d'un « de … à … », vérifiés chacun (« 3 à 5 ans »).
- **Écart calculé par Python** (`ecart_de_piece`, acceptation attendue) : Écart ou rapport que l'outil de simulation a calculé et versé dans la pièce (règle 6 : un nombre dérivé passe s'il existe tel quel dans une pièce).
- **Date d'une pièce** (`date_legitime`, acceptation attendue) : Date ISO, jour et mois, mois et année d'une pièce citée ou de la période.

## Méthode

- Vérificateur : `pipeline.chiffres.verifier_argument`, le même que le Greffier et l'écran « Trompez le Greffier » (`REFERENCE_DU_PROJET.md`, section 4 ter).
- Dossier de chaque cas : décision et pièces du procès enregistré (`frontend/src/data/proces/<id>.json`), période 2021-11-12 → 2026-11-12.
- Piège détecté : argument rejeté **et** nombre piège parmi les introuvables. Argument valide : accepté.
- Intervalle de confiance : Wilson à 95 % (`validation.evaluation.intervalle_wilson`).
- Un raté reste dans ce rapport. Une règle corrigée se mesure sur un second jeu, écrit après la correction.
