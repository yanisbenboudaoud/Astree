# #2 — Contrat JSON : schéma, validateur et exemples

- **Issue** : #2 · **PR** : #20, #23, #24 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`contrat/schema_sortie.json`** : schéma JSON du contrat (`REFERENCE_DU_PROJET.md`, section 5). Il vérifie les champs obligatoires, les valeurs permises (`statut`, `etiquette`, type de pièce, `verdict`, `cote`), les paramètres de chaque type de règle, et l'absence de chiffre dans la `raison` des appels de l'orchestrateur. Il refuse tout champ inconnu.
- **`contrat/valider.py`** : le schéma, plus les renvois entre champs que le schéma ne peut pas exprimer (pièces citées qui existent, un contrôle par règle du Pacte, aucune règle inconnue, simulation obligatoire présente dans la trace, poids du panier qui totalisent 1).
  - `valider_contrat(contrat) -> list[str]` : liste des erreurs, vide si le contrat est valide.
  - `CONTROLES_SYSTEME` : les contrôles admis en plus des règles du Pacte.
- **`docs/exemples/contrat_robert.json`** (#20, revu par #23) : cas 1, « 30 % en TSLA » pour le profil prudent. C'est le faux JSON de l'équipe interface.
- **`docs/exemples/contrat_amira.json`** (#24) : cas 2, réallocation vers un panier crypto-tech. On y voit 3 violations, une pièce de corrélations et un exemple de `arguments_rejetes`.
- **`tests/test_contrat.py`** : les deux exemples passent, et une série de contrats faux sont refusés.

## Comment l'utiliser
```python
from contrat.valider import valider_contrat

erreurs = valider_contrat(contrat)   # contrat : dict produit par le pipeline
if erreurs:
    raise ValueError(erreurs)
```
En ligne de commande (sous Windows, `-X utf8` est nécessaire pour afficher ✓ et ✗) :
```bash
python -X utf8 -m contrat.valider docs/exemples/contrat_robert.json docs/exemples/contrat_amira.json
```

## Comment vérifier
```bash
pytest tests/test_contrat.py
```

## Choix faits en cours de route
- `decision` porte un champ **`type`** (#24), aligné sur `decision_demo` des fichiers profils : `position` (`ticker`, `taille`, `financement`) ou `reallocation` (`panier`, `part_reallouee`).
- `simuler_portefeuille` doit renvoyer aussi la **part de chaque catégorie** avant et après la décision (`part_crypto`, `part_tech_crypto`…), pour les contrôles de type `plafond`.
- `taille_max_compatible` vaut `null` si même 0 % viole le Pacte.
- Les chiffres des exemples ont été calculés par un script temporaire (hors dépôt) qui suit la section 6 bis ; ceux de l'exemple du cas 2 sont gardés à 6 décimales pour éviter les arrondis ambigus.

## Limites et suite
- Les exemples ne sortent pas encore des vrais outils : à régénérer quand le pipeline (#12) tournera.
- Format de réponse du contre-interrogatoire : pas encore dans le contrat (#12, #14).
