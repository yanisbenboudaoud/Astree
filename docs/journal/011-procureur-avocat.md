# #11 — Procureur et Avocat : arguments contre et pour, avec pièces

- **Issue** : #11 · **PR** : #36, #44 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`pipeline/debat.py`** : les deux agents du débat, qui ne calculent rien et n'appellent aucun outil.
  - `debattre(dossier)` : appelle le Procureur et l'Avocat **en parallèle** et renvoie un `ResultatDebat` (`requisitoire`, `plaidoirie`, `trace`).
  - `plaider(role, dossier)` : les arguments d'un seul rôle (`"procureur"` ou `"avocat"`), au format `argument` du contrat (`etiquette`, `texte`, `pieces`), avec leur étape de trace.
  - `corriger_argument(role, dossier, argument, motif)` : mode correction, qui renvoie un argument refusé à son agent avec le motif exact du Greffier, pour une réécriture unique. Il se branche sur `pipeline.chiffres.trier_arguments` (fiche du Greffier, #10).
  - `CONSIGNES` et `REGLES_COMMUNES` : les prompts, qui reprennent les règles de `verifier_chiffres` (`REFERENCE_DU_PROJET.md`, section 4 ter).
  - `schema_arguments` et `schema_argument` : la sortie JSON imposée. Les pièces citées sont limitées à celles du dossier.
- **`tests/test_debat.py`** : 6 tests unitaires sans LLM (dont un qui prouve que les deux appels se chevauchent) et 5 tests réels. Ceux-ci couvrent les deux faux contrats de `docs/exemples/`, deux **vrais procès** (vraies pièces de l'Agent Profil et de l'orchestrateur), chacun passé au Greffier, et une correction.

## Comment l'utiliser
```python
from pipeline.chiffres import trier_arguments
from pipeline.debat import debattre, corriger_argument

dossier = {"decision": ..., "pacte": ..., "pieces": [...],   # champs du contrat (section 5)
           "periode": ["2021-11-12", "2026-11-12"]}
resultat = debattre(dossier)          # resultat.requisitoire, resultat.plaidoirie, resultat.trace
tri = trier_arguments(resultat.requisitoire, "requisitoire", dossier,
                      lambda argument, motif: corriger_argument("procureur", dossier, argument, motif)[0])
```

## Comment vérifier
```bash
pytest tests/test_debat.py                 # tests unitaires, sans réseau
pytest tests/test_debat.py -m bedrock -s   # vrais débats passés au Greffier (affiche les arguments)
```
**Critère de fin atteint** : sur le cas de démo (profil prudent, 30 % en TSLA), avec les vraies pièces de l'orchestrateur, tous les arguments passent `verifier_chiffres`. Avec les consignes finales, **65 arguments sur 65 ont été acceptés dès le premier jet**, sur 9 débats réels : 5 sur des procès réels (profil prudent et profil ESG, XOM 10 %) et 4 dans les tests. La relance n'a pas servi.

## Choix faits en cours de route
- **Dossier** : les champs `decision`, `pacte` et `pieces` du contrat, plus `periode`, une source toujours admise par `verifier_chiffres`. Des pièces, seuls `id`, `titre`, `etiquette`, `valeurs`, `valeur_affichee` et `limites` sont transmis ; la source et le traitement ne servent pas à argumenter.
- **Étiquettes** limitées à `fait` et `hypothese` : un argument ne décrit pas un scénario fictif, il cite des pièces.
- **Vouvoiement** des deux côtés ; l'Avocat défend **honnêtement**, sans nier les risques. Il peut mettre en avant une taille plus modeste compatible avec le Pacte.
- **Règles ajoutées aux consignes après des essais**, chacune pour corriger une erreur observée :
  - aucun chiffre tiré des textes `titre` ou `limites`, et rappeler une limite sans chiffre (l'agent écrivait « une seule période de 5 ans », absent des valeurs) ;
  - ne comparer un chiffre qu'au seuil du même indicateur (un rendement 2022 était comparé au seuil de pire baisse) ;
  - pour écrire une année, citer la pièce dont les **valeurs** contiennent une date de cette année ; le nom d'une clé (`rendement_2022`) ne compte pas. Le Greffier refusait à juste titre « +100,2 % en 2022 » cité avec la seule pièce des indicateurs.
- **Trace** : `entree` = identifiants des pièces fournies ; la correction a l'outil `bedrock_correction`.

## Limites et suite
- **Branchement dans le procès complet** : `pipeline/tribunal.py` (#12) doit encore appeler `debattre`, puis `trier_arguments` avec `corriger_argument`, et remplir `requisitoire`, `plaidoirie`, `arguments_rejetes`, le contrôle `verifier_chiffres` et la trace. Le test `test_proces_reel_tous_les_chiffres_passent_le_greffier` montre l'enchaînement.
- **Durée** : environ 14 à 19 s par débat (deux appels Sonnet 5.5 en parallèle) et 7 s par correction.
- Le contre-interrogatoire (question libre de l'utilisateur) passe par l'orchestrateur (#12) et n'est pas traité ici.
