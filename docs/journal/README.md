# Journal de construction

Une **fiche par issue** : ce qui a été construit, où, comment s'en servir et comment le vérifier. Lues dans l'ordre, les fiches racontent comment le projet s'est construit. Pour la personne qui arrive, c'est le moyen de retrouver d'où vient un fichier et pourquoi il est comme il est.

Ce que le journal **n'est pas** :
- les règles du projet → `REFERENCE_DU_PROJET.md` ;
- le *pourquoi* de l'architecture d'ensemble → `docs/CHOIX_CONCEPTION.md` ;
- la vue à jour du dépôt → la **carte du dépôt** dans le `README.md` de la racine.

## Règles

1. **Une fiche par issue**, nommée `NNN-titre-court.md`, avec le numéro de l'issue sur 3 chiffres pour que les fiches se trient dans l'ordre (ex. : `007-client-llm-bedrock.md`).
2. **La fiche est écrite dans la PR elle-même**, pas après la fusion : elle est relue en même temps que le code.
3. **Plusieurs PR pour une même issue** (`Avance #N`) : elles complètent la même fiche, ajoutent leur numéro à la ligne « PR » et mettent le statut à jour.
4. **Décrire ce qui existe**, pas ce qui était prévu. Nommer les fichiers et les fonctions exactement, pour qu'on puisse les chercher dans le code.
5. **Courte** : une page au plus. Renvoyer à `REFERENCE_DU_PROJET.md` (« section 4 ter ») au lieu de le recopier.
6. **Une fiche décrit son issue, à sa date.** Si une issue suivante modifie ce code, c'est la fiche de cette nouvelle issue qui le dit, avec un renvoi (« remplace `charger_prix` de la fiche 004 »). On ne réécrit pas l'histoire : c'est la carte du `README.md` qui donne l'état actuel.
7. **Pas d'issue, pas de fiche** : une PR sans issue qui ne touche que la configuration ou la documentation n'a pas de fiche. Si elle construit du code, on crée d'abord l'issue. Seule exception : la fiche `000`, qui décrit les fondations posées avant les issues de code.
8. **Carte du dépôt** : une PR qui ajoute, déplace ou supprime un fichier ou un dossier important met aussi à jour la carte dans le `README.md` de la racine.

## Modèle de fiche

Copier ce bloc dans `docs/journal/NNN-titre-court.md` et remplacer les indications en italique.

```markdown
# #N — Titre de l'issue

- **Issue** : #N · **PR** : #M (et suivantes) · **Statut** : terminée | en cours
- **Dernière mise à jour** : AAAA-MM-JJ

## Ce qui a été construit
_Fichiers ajoutés ou modifiés, et le rôle de chacun. Fonctions publiques principales._

## Comment l'utiliser
_Exemple d'appel minimal ou commande._

## Comment vérifier
_Commande de test, et ce qu'elle prouve._

## Choix faits en cours de route
_Décisions prises pendant le travail, alternatives écartées, écarts au `REFERENCE_DU_PROJET.md` (et si `REFERENCE_DU_PROJET.md` a été mis à jour)._

## Limites et suite
_Ce qui manque, ce qui dépend d'une autre issue, pièges à connaître pour la personne suivante._
```
