# #11 — Procureur et Avocat : arguments contre et pour, avec pièces

- **Issue** : #11 · **PR** : à compléter · **Statut** : en cours
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`pipeline/debat.py`** : les deux agents du débat, qui ne calculent rien et n'appellent aucun outil.
  - `debattre(dossier)` : appelle le Procureur et l'Avocat **en parallèle** et renvoie un `ResultatDebat` (`requisitoire`, `plaidoirie`, `trace`).
  - `plaider(role, dossier)` : les arguments d'un seul rôle (`"procureur"` ou `"avocat"`), au format `argument` du contrat (`etiquette`, `texte`, `pieces`), avec leur étape de trace.
  - `corriger_argument(role, dossier, argument, motif)` : mode correction, qui renvoie un argument refusé à son agent avec le motif exact du Greffier, pour une réécriture unique.
  - `CONSIGNES` et `REGLES_COMMUNES` : les prompts, qui reprennent les règles de `verifier_chiffres` (`CLAUDE.md`, section 4 ter).
  - `schema_arguments` et `schema_argument` : la sortie JSON imposée. Les pièces citées sont limitées à celles du dossier.
- **`tests/test_debat.py`** : 6 tests unitaires sans LLM (dont un qui prouve que les deux appels se chevauchent) et 3 tests réels sur les faux contrats de `docs/exemples/`.

## Comment l'utiliser
```python
from pipeline.debat import debattre, corriger_argument

dossier = {"decision": ..., "pacte": ..., "pieces": [...],   # champs du contrat (section 5)
           "periode": ["2021-11-12", "2026-11-12"]}
resultat = debattre(dossier)          # resultat.requisitoire, resultat.plaidoirie, resultat.trace
nouveau, etape = corriger_argument("avocat", dossier, argument_refuse, motif_du_greffier)
```

## Comment vérifier
```bash
pytest tests/test_debat.py                 # tests unitaires, sans réseau
pytest tests/test_debat.py -m bedrock -s   # vrais débats sur les deux faux contrats (affiche les arguments)
```

## Choix faits en cours de route
- **Dossier** : les champs `decision`, `pacte` et `pieces` du contrat, plus `periode`, une source toujours admise par `verifier_chiffres`. Des pièces, seuls `id`, `titre`, `etiquette`, `valeurs`, `valeur_affichee` et `limites` sont transmis ; la source et le traitement ne servent pas à argumenter.
- **Étiquettes** limitées à `fait` et `hypothese` : un argument ne décrit pas un scénario fictif, il cite des pièces.
- **Vouvoiement** des deux côtés ; l'Avocat défend **honnêtement**, sans nier les risques. Il peut mettre en avant une taille plus modeste compatible avec le Pacte.
- **Deux règles ajoutées après un premier essai** : aucun chiffre tiré des textes `titre` ou `limites` (l'agent écrivait « une seule période de 5 ans », introuvable dans les valeurs) ; ne comparer un chiffre qu'au seuil du même indicateur (un rendement 2022 était comparé au seuil de pire baisse).
- **Trace** : `entree` = identifiants des pièces fournies ; la correction a l'outil `bedrock_correction`.

## Limites et suite
- **`verifier_chiffres` (#10) n'existe pas encore** : le critère de fin de l'issue n'est pas vérifiable. Les arguments des tests réels ont été relus à la main contre les pièces : après les deux règles ajoutées, tous leurs chiffres correspondaient à une valeur de pièce citée, de la décision ou du Pacte.
- **Branchement** : les vraies pièces viendront des outils #6 et #9 via l'orchestrateur (#12), qui gérera aussi la boucle « vérifier, corriger une fois, puis rejeter ».
- **Durée** : environ 14 s par débat (deux appels Sonnet 5.5 en parallèle) et 7 s par correction.
- Le contre-interrogatoire (question libre de l'utilisateur) passe par l'orchestrateur (#12) et n'est pas traité ici.
