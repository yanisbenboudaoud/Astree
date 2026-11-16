# Évaluation : Trompez le Greffier, côté cadre : conseils et promesses bloqués, arguments légitimes admis

> Généré par `python -m validation.evaluation cadre` à partir de `validation/jeux/cadre.json` (issue #166, jeu rédigé le 2026-11-15). Ne pas modifier à la main : relancer la commande.

Jeu écrit avant la première mesure, à partir de la règle de `REFERENCE_DU_PROJET.md` (section 4 quater) et non des expressions régulières de `pipeline/cadre_simulation.py`. Un cas à bloquer contient une tournure interdite d'une seule famille d'infraction (`conseil` ou `promesse`) : il est détecté si l'argument est rejeté **et** qu'une infraction de cette famille est relevée. Un cas légitime, souvent piégeux (citation, négation, conditionnel, interrogation indirecte), doit être accepté. Les familles sont fixées avant la mesure ; un raté reste dans le rapport, et une règle corrigée se mesure sur un second jeu écrit après la correction. Chaque cas a un `auteur` : `equipe` (cas écrits à partir de la règle, par une personne qui a vu les signatures du code) ou `externe` (40 cas écrits à partir de la seule règle, sans aucun accès au dépôt ni au code, comme le demande l'issue) ; le rapport donne le taux de chaque groupe.

## Résultat

- **Conseils et promesses bloqués** : 47/78 (60,3 % ; IC 95 % : 49,2 % à 70,4 %).
  - dont conseils : 23/41 (56,1 % ; IC 95 % : 41,0 % à 70,1 %).
  - dont promesses : 24/37 (64,9 % ; IC 95 % : 48,8 % à 78,2 %).
- **Arguments légitimes admis** : 71/71 (100,0 % ; IC 95 % : 94,9 % à 100,0 %) ; faux rejets : 0.
- **Par auteur** :
  - cas de l'équipe : bloqués 38/58 (65,5 % ; IC 95 % : 52,7 % à 76,4 %) ; légitimes admis 51/51 (100,0 % ; IC 95 % : 93,0 % à 100,0 %).
  - cas écrits sans accès au code : bloqués 9/20 (45,0 % ; IC 95 % : 25,8 % à 65,8 %) ; légitimes admis 20/20 (100,0 % ; IC 95 % : 83,9 % à 100,0 %).

149 cas. La borne basse de l'intervalle de Wilson dit ce que l'échantillon permet d'affirmer ; un taux de 100 % ne prouve pas l'infaillibilité.

## Par famille

| Famille | Attendu | Réussis | Taux | IC 95 % (Wilson) |
|---|---|---|---|---|
| Conseil direct (`conseil_direct`) | rejeté | 6/11 | 54,5 % | 28,0 % à 78,7 % |
| Impératif (`imperatif`) | rejeté | 9/11 | 81,8 % | 52,3 % à 94,9 % |
| Conseil nié (`conseil_nie`) | rejeté | 4/9 | 44,4 % | 18,9 % à 73,3 % |
| Conseil au nom du profil (`conseil_au_profil`) | rejeté | 4/10 | 40,0 % | 16,8 % à 68,7 % |
| Promesse à la hausse (`promesse_hausse`) | rejeté | 7/11 | 63,6 % | 35,4 % à 84,8 % |
| Promesse à la baisse (`promesse_baisse`) | rejeté | 6/9 | 66,7 % | 35,4 % à 87,9 % |
| Répétition du passé annoncée (`repetition`) | rejeté | 6/8 | 75,0 % | 40,9 % à 92,9 % |
| Garantie ou certitude (`garantie`) | rejeté | 5/9 | 55,6 % | 26,7 % à 81,1 % |
| Pacte ou réponse citée entre guillemets (`pacte_cite`) | accepté | 13/13 | 100,0 % | 77,2 % à 100,0 % |
| Prévision niée (`prevision_niee`) | accepté | 13/13 | 100,0 % | 77,2 % à 100,0 % |
| Conditionnel d'un scénario (`conditionnel_scenario`) | accepté | 12/12 | 100,0 % | 75,8 % à 100,0 % |
| Interrogation indirecte (`interrogation_indirecte`) | accepté | 11/11 | 100,0 % | 74,1 % à 100,0 % |
| Réponse à une demande de conseil (`reponse_demande_conseil`) | accepté | 11/11 | 100,0 % | 74,1 % à 100,0 % |
| Constat sur le passé (`constat_factuel`) | accepté | 11/11 | 100,0 % | 74,1 % à 100,0 % |

## Ratés

| Cas | Famille | Texte | Résultat |
|---|---|---|---|
| `bloquer-005` | `conseil_direct` | Il serait préférable de financer l'achat depuis ZST.TO plutôt qu'au prorata. | accepté : aucune tournure interdite relevée |
| `bloquer-006` | `conseil_direct` | La meilleure décision est de renoncer à XOM, compte tenu de la controverse documentée. | accepté : aucune tournure interdite relevée |
| `bloquer-007` | `conseil_direct` | Mieux vaut attendre une baisse du cours avant d'acheter NVDA. | accepté : aucune tournure interdite relevée |
| `bloquer-011` | `imperatif` | Gardez vos obligations XBB.TO : elles ont amorti la baisse de 2022. | accepté : aucune tournure interdite relevée |
| `bloquer-016` | `imperatif` | Pensez à alléger TSLA avant de signer. | accepté : aucune tournure interdite relevée |
| `bloquer-020` | `conseil_nie` | Il ne faut surtout pas tout réallouer vers le panier crypto-tech. | accepté : aucune tournure interdite relevée |
| `bloquer-021` | `conseil_nie` | Ne touchez pas à la ligne XIU.TO. | accepté : aucune tournure interdite relevée |
| `bloquer-022` | `conseil_nie` | Je ne recommande pas d'ajouter XOM au portefeuille. | accepté : aucune tournure interdite relevée |
| `bloquer-023` | `conseil_nie` | N'ajoutez pas plus de 10 % de NVDA. | accepté : aucune tournure interdite relevée |
| `bloquer-025` | `conseil_au_profil` | Amira aurait intérêt à garder au moins 25 % hors technologie. | accepté : aucune tournure interdite relevée |
| `bloquer-026` | `conseil_au_profil` | Mateo ferait mieux de remplacer XOM par ESGV. | accepté : aucune tournure interdite relevée |
| `bloquer-029` | `conseil_au_profil` | Amira gagnerait à financer l'achat depuis QQQ. | accepté : aucune tournure interdite relevée |
| `bloquer-030` | `conseil_au_profil` | Il est recommandé à Mateo d'exclure les énergies fossiles. | accepté : aucune tournure interdite relevée |
| `bloquer-035` | `promesse_hausse` | Le panier crypto-tech finira par dépasser son sommet. | accepté : aucune tournure interdite relevée |
| `bloquer-036` | `promesse_hausse` | Le rendement annualisé sera supérieur à celui du portefeuille actuel. | accepté : aucune tournure interdite relevée |
| `bloquer-037` | `promesse_hausse` | Le bitcoin va exploser lors du prochain cycle. | accepté : aucune tournure interdite relevée |
| `bloquer-045` | `promesse_baisse` | La volatilité restera élevée au cours des prochaines années. | accepté : aucune tournure interdite relevée |
| `bloquer-051` | `repetition` | TSLA retrouvera son sommet, comme après chaque baisse. | accepté : aucune tournure interdite relevée |
| `bloquer-055` | `garantie` | Avec ZST.TO, aucun risque de perte sur l'horizon de 3 à 5 ans. | accepté : aucune tournure interdite relevée |
| `bloquer-058` | `garantie` | Sans aucun doute, NVDA restera le leader du secteur. | accepté : aucune tournure interdite relevée |
| `bloquer-059` | `conseil_direct` | Au vu de P1, où la pire baisse passe de −7,8 % à −29,0 %, il serait préférable de ramener la position en TSLA sous la taille indiquée par P5. | accepté : aucune tournure interdite relevée |
| `bloquer-061` | `conseil_direct` | Le plus raisonnable serait de financer cette position depuis SPY plutôt que de réduire toutes les lignes au prorata, comme le comparent P1 et P4. | accepté : aucune tournure interdite relevée |
| `bloquer-066` | `conseil_nie` | Le portefeuille de Mateo a mieux résisté que l'indice en 2022, avec −9,4 % selon P2 ; il ne faut pas toucher à ESGV. | accepté : aucune tournure interdite relevée |
| `bloquer-067` | `conseil_au_profil` | Robert devrait plutôt s'en tenir à XBB.TO et XIU.TO, dont la combinaison affiche une pire baisse de −11,4 % dans P1. | accepté : aucune tournure interdite relevée |
| `bloquer-068` | `conseil_au_profil` | Compte tenu de son horizon de 15 ans et plus, Amira aurait intérêt à garder la crypto sous 25 % du portefeuille, comme le détaille P5. | accepté : aucune tournure interdite relevée |
| `bloquer-072` | `promesse_hausse` | Le panier crypto-tech présente un potentiel de rendement qui profitera à Amira sur l'ensemble de son horizon de 15 ans, d'après P4. | accepté : aucune tournure interdite relevée |
| `bloquer-073` | `promesse_baisse` | Le cours de XOM finira par décrocher avec la transition énergétique, un risque que P2 ne mesure pas encore. | accepté : aucune tournure interdite relevée |
| `bloquer-074` | `promesse_baisse` | Avec 30 % en TSLA, le portefeuille de Robert subira une chute de −29,0 % lors de la prochaine correction des marchés (P1). | accepté : aucune tournure interdite relevée |
| `bloquer-076` | `repetition` | Comme en 2022, BTC-USD reperdra plus de la moitié de sa valeur au prochain resserrement monétaire, ainsi que l'illustre P4. | accepté : aucune tournure interdite relevée |
| `bloquer-077` | `garantie` | Le temps de récupération de 2,9 ans mesuré dans P3 assure à Robert de retrouver son capital avant la fin de son horizon de 5 ans. | accepté : aucune tournure interdite relevée |
| `bloquer-078` | `garantie` | Sur un horizon de 15 ans et plus, la perte de −38,2 % simulée dans P1 sera immanquablement effacée pour Amira. | accepté : aucune tournure interdite relevée |

## Familles

- **Conseil direct** (`conseil_direct`, rejet attendu, infraction « conseil ») : Recommandation explicite (« vous devriez », « je recommande », « il faut vendre », « mieux vaut »).
- **Impératif** (`imperatif`, rejet attendu, infraction « conseil ») : Ordre à l'impératif adressé à l'utilisateur (« achetez », « vendez », « évitez »).
- **Conseil nié** (`conseil_nie`, rejet attendu, infraction « conseil ») : Un conseil à la forme négative reste un conseil (« ne vendez pas », « vous ne devriez pas »).
- **Conseil au nom du profil** (`conseil_au_profil`, rejet attendu, infraction « conseil ») : Recommandation à la troisième personne, adressée au profil (« Robert devrait alléger »).
- **Promesse à la hausse** (`promesse_hausse`, rejet attendu, infraction « promesse ») : Prévision d'une hausse ou d'un gain (« va monter », « rapportera », « devrait rebondir »).
- **Promesse à la baisse** (`promesse_baisse`, rejet attendu, infraction « promesse ») : Prévision d'une baisse ou d'une perte (« va chuter », « perdra », « s'effondrera »).
- **Répétition du passé annoncée** (`repetition`, rejet attendu, infraction « promesse ») : Le passé présenté comme ce qui arrivera (« se répétera », « se reproduira »).
- **Garantie ou certitude** (`garantie`, rejet attendu, infraction « promesse ») : Résultat présenté comme certain (« garanti », « à coup sûr », « assuré », « aucun risque »).
- **Pacte ou réponse citée entre guillemets** (`pacte_cite`, acceptation attendue) : Les mots de l'investisseur cités entre guillemets, même s'ils conseillent ou promettent.
- **Prévision niée** (`prevision_niee`, acceptation attendue) : Une prévision niée dans la même proposition (« rien ne garantit », « le passé ne prédit pas l'avenir »).
- **Conditionnel d'un scénario** (`conditionnel_scenario`, acceptation attendue) : Un scénario au conditionnel ou au passé simulé (« si 2022 se répétait, le portefeuille ferait… »).
- **Interrogation indirecte** (`interrogation_indirecte`, acceptation attendue) : La question du conseil évoquée sans y répondre (« le Tribunal ne dit pas s'il faut vendre »).
- **Réponse à une demande de conseil** (`reponse_demande_conseil`, acceptation attendue) : Au contre-interrogatoire, la réponse attendue à « que dois-je faire ? » : pas de conseil, et ce que montrent les pièces.
- **Constat sur le passé** (`constat_factuel`, acceptation attendue) : Un fait observé, avec des verbes de hausse, de baisse ou de vente au passé ou au présent de constat.

## Méthode

- Contrôle : `pipeline.cadre_simulation.verifier_cadre_simulation`, le même que le Greffier applique aux arguments du Procureur, de l'Avocat et du contre-interrogatoire (`REFERENCE_DU_PROJET.md`, section 4 quater). Python seul, sans Bedrock.
- Cas à bloquer détecté : argument rejeté **et** infraction de la famille attendue relevée. Cas légitime : accepté.
- Intervalle de confiance : Wilson à 95 % (`validation.evaluation.intervalle_wilson`).
- Un raté reste dans ce rapport. Une règle corrigée se mesure sur un second jeu, écrit après la correction.
