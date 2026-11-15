# Rapports de validation

Chaque rapport de ce dossier est **généré par une commande** : il ne se modifie pas à la main, il se régénère. Les chiffres repris ailleurs (section « Preuves » du [`README.md`](../../README.md), [`DOCUMENTATION_TECHNIQUE.md`](../DOCUMENTATION_TECHNIQUE.md), section 8) renvoient ici.

Commandes pour PowerShell, depuis la racine du dépôt (sous Linux ou macOS : `.venv/bin/python`). Toutes tournent sans Bedrock ; seule l'évaluation de l'orchestrateur lit S3, et seul le plan de procès appelle la Lambda (vrais appels Bedrock, payants).

| Rapport | Ce qu'il mesure | Commande pour le régénérer | Issue |
|---|---|---|---|
| [`evaluation_chiffres.md`](evaluation_chiffres.md) | « Trompez le Greffier, 100 fois » : pièges joués contre `verifier_chiffres` (chiffres inventés détectés, arguments valides acceptés), par famille | `.venv\Scripts\python -X utf8 -m validation.evaluation chiffres` | #165 |
| [`evaluation_cadre.md`](evaluation_cadre.md) | « Trompez le Greffier », côté cadre : conseils et promesses bloqués par `cadre_simulation`, arguments légitimes admis, par famille et par auteur | `.venv\Scripts\python -X utf8 -m validation.evaluation cadre` | #166 |
| [`evaluation_orchestrateur.md`](evaluation_orchestrateur.md) | L'orchestrateur et le débat sur les procès tenus : outils demandés par profil et par décision, budget, simulation obligatoire, appels refusés, renvois du Greffier ; plan de procès (même décision, trois profils) | `.venv\Scripts\python -X utf8 -m validation.evaluation orchestrateur` (traces S3 ; `--local` : procès de l'interface seulement) ; plan : `.venv\Scripts\python -X utf8 -m validation.plan_proces` | #167 |
| [`validation_externe.md`](validation_externe.md) | Nos rendements annuels (`adj_close`) face à ceux publiés par les émetteurs de 7 FNB, seuil fixé avant le calcul | `.venv\Scripts\python -X utf8 -m validation.externe` | #168 |
| [`resultats_scenarios.md`](resultats_scenarios.md), [`sensibilite_seuil.svg`](sensibilite_seuil.svg) | Scénarios de validation et de sensibilité : même décision pour plusieurs profils, seuils, hypothèses, période, garde-fous, profil inventé | `.venv\Scripts\python -X utf8 -m validation` | #15 |

La suite de tests et la validation des contrats ne produisent pas de rapport ici : elles tournent à chaque push dans l'intégration continue ([`.github/workflows/tests.yml`](../../.github/workflows/tests.yml), #169), et leurs résultats sont dans l'onglet *Actions* du dépôt.

## Limites de chaque mesure

Chaque rapport écrit ses propres limites ; voici l'essentiel, à lire avec les taux.

- **Tous les taux** sont donnés avec un intervalle de confiance de Wilson à 95 % (`validation.evaluation.intervalle_wilson`). Sur de petits échantillons, c'est la **borne basse** qui dit ce que la mesure permet d'affirmer : 100 % sur 66 cas n'est pas l'infaillibilité.
- **Jeux écrits avant la mesure** (`evaluation_chiffres`, `evaluation_cadre`) : les familles et les cas sont fixés avant la première mesure, et un raté reste dans le rapport. Une règle corrigée après coup se mesure sur un second jeu, sinon le taux serait flatté.
- **`evaluation_chiffres`** : le vérificateur contrôle qu'un nombre **existe** dans une pièce citée, pas qu'il est attribué à la bonne grandeur. Cette limite connue est mesurée à part (famille `mauvaise_grandeur`) et n'est pas comptée parmi les chiffres inventés. Les pièges portent sur les pièces des 7 procès enregistrés de l'interface.
- **`evaluation_cadre`** : `cadre_simulation` repère des tournures, il ne comprend pas le sens. Des conseils formulés autrement (« il serait préférable de… », « la meilleure décision est… ») passent : les ratés sont listés un par un. Le taux est plus bas sur les cas écrits par une personne sans accès au code, et c'est ce groupe qui mesure le mieux le contrôle face à des formulations imprévues. Le côté sûr est tenu : aucun argument légitime n'est rejeté.
- **`evaluation_orchestrateur`** : les procès archivés ne sont **pas un échantillon planifié** (procès de développement et de démonstration, dominés par quelques décisions répétées). Le rapport change quand de nouveaux procès sont archivés : sa date de lecture est écrite en tête. Le plan de procès, lui, est planifié, mais petit (9 couples décision × profil, 2 répétitions).
- **`validation_externe`** : 7 FNB sur 9 seulement (QQQ et GLD ne publient pas de rendement par année civile dans les documents lus) ; aucune action individuelle ni cryptoactif n'est validé ainsi. La comparaison porte sur la donnée de départ, dans la devise de cotation, avant la conversion en CAD du pipeline.
- **`resultats_scenarios`** : des scénarios choisis par l'équipe pour vérifier un comportement attendu (« réussi » ou « en échec »), pas un taux sur un échantillon.
