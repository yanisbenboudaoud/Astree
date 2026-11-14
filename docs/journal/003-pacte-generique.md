# #3 — Pacte générique : schéma, validation et chargement

- **Issue** : #3 · **PR** : #20, #23, #PR_A_RENSEIGNER · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`personas/robert.json`, `personas/amira.json`, `personas/mateo.json`** (#20, #23) : les trois profils de test (étiquette `fictif`). Chacun contient le profil, le portefeuille de départ, la `decision_demo` et le **Pacte** : une liste de règles typées (`pire_baisse_max`, `plafond`, `critere_documentaire`, `qualitative`), chacune avec un `id`, ses paramètres, un `libelle` et une `justification`. Format décrit dans `CLAUDE.md`, section 3.
- **`config/categories.json`** (#23) : les catégories `tech` et `crypto` utilisées par les règles `plafond`, définies **une seule fois** pour tous les profils, à partir des champs `asset_class` et `sector` de `assets_universe.csv`, plus des ajouts justifiés (`GOOGL`, `AMZN`, `QQQ` dans `tech`).
- **`personas/schema_pacte.json`** : schéma JSON d'un fichier profil, avec un sous-schéma par type de règle (paramètres obligatoires, aucun paramètre d'un autre type, `justification` obligatoire).
- **`pipeline/pacte.py`** :
  - `charger_pacte(chemin)` : lit un fichier profil, le valide et renvoie le profil complet. Lève `PacteInvalide` (attribut `erreurs` : toutes les erreurs, en français) ;
  - validation en deux niveaux : le schéma, puis la cohérence (`erreurs_coherence`) : id de règles uniques et non réservés, catégories connues, poids qui totalisent 1, tickers sans doublon, horizon minimum ≤ maximum, date réelle, `depuis_<ticker>` présent dans le portefeuille, `id` égal au nom du fichier ;
  - `pacte_pour_contrat(profil)` : champ `pacte` du contrat (règles sans justification) ;
  - `piece_pacte(profil, id_piece)` : pièce « Pacte » (paramètres chiffrés des règles, date, horizon).
- **`pipeline/categories.py`** :
  - `categories_du_titre(ticker)` : catégories d'un titre de l'univers. Lève `TitreHorsUnivers` (sous-classe de `ErreurDonnees`) si le titre est absent de `assets_universe.csv` ;
  - `noms_categories()`, `charger_categories()` ;
  - `erreurs_config_categories()` : vérifie que `config/categories.json` ne cite que des classes, secteurs et tickers de l'univers.

## Comment l'utiliser
```python
from pipeline.pacte import charger_pacte, pacte_pour_contrat, piece_pacte
from pipeline.categories import categories_du_titre

profil = charger_pacte("personas/robert.json")   # PacteInvalide si le fichier est faux
contrat["pacte"] = pacte_pour_contrat(profil)
pieces.append(piece_pacte(profil, "P3"))         # le pipeline choisit le numéro
categories_du_titre("NVDA")                       # frozenset({"tech"})
```
Ajouter un profil = ajouter un fichier `personas/<id>.json` au même format. Aucun code ne doit tester un nom de profil.

## Comment vérifier
`pytest tests/test_schema_pacte.py tests/test_pacte.py tests/test_categories.py` :
- les 3 profils de test et un 4e profil inventé se chargent sans changer le code ;
- un type de règle ou une catégorie inconnus, un paramètre ou une justification manquants, des poids faux, etc. sont refusés avec un message clair ;
- `pacte_pour_contrat` et `piece_pacte` redonnent exactement le `pacte` et la pièce P3 de `docs/exemples/contrat_robert.json` et `contrat_amira.json`.

## Choix faits en cours de route
- Les champs sur mesure (`interdit_exclusivement_tech`, catégories propres à un profil, exclusion `speculatif` jamais définie) ont disparu au profit des règles typées (#23).
- « Pas exclusivement tech » devient **tech + crypto ≤ 75 %** : hypothèse de l'équipe, à valider.
- `QQQ` est compté en entier dans `tech`, par simplicité.
- **`charger_pacte` renvoie le profil complet**, pas directement la pièce comme le prévoyait l'issue : le pipeline a besoin du portefeuille et des règles typées, et c'est lui qui numérote les pièces. La pièce est construite à part par `piece_pacte`.
- **Un titre hors univers lève une erreur** au lieu de renvoyer un ensemble vide : sinon, il passerait un plafond sans bruit, comme un titre « sans catégorie ».
- Tout champ inconnu est refusé (attrape les fautes de frappe) ; un nouveau champ doit d'abord être ajouté au schéma. `age` et `metier` sont facultatifs ; `decision_demo` est obligatoire, comme dans `CLAUDE.md`.

## Limites et suite
- **TSLA n'est pas classé `tech`** : son secteur est Consumer Discretionary et il n'est pas dans les ajouts. Sans effet pour le profil prudent (plafond sur la crypto seulement), mais avec le profil audacieux, TSLA ne compterait pas dans « tech + crypto ≤ 75 % ».
- Un ticker du portefeuille absent de l'univers n'est pas refusé au chargement : c'est le contrôle du Greffier (#10) qui rendra `a_verifier`.
- Les profils sont lus en local ; la lecture depuis S3 viendra avec #13 si nécessaire.
