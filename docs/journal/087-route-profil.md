# #87 — Route /profil : construire et stocker dans S3 le Pacte d'un nouvel utilisateur

- **Issue** : #87 · **PR** : #94 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
La Lambda ne connaissait que les profils embarqués dans le zip (`personas/`). Un Pacte construit par le questionnaire (#84) est maintenant **calculé et rangé par AWS** : le procès, le contre-interrogatoire, la jurisprudence et le procès-verbal le retrouvent par son identifiant.

- **`pipeline/profils.py`** (nouveau) :
  - `nouvel_identifiant_profil()` : `investisseur_<12 hex>`, même format que l'`id` d'un profil, jamais tiré d'un nom saisi ;
  - `enregistrer_profil(profil)` : valide le profil (`erreurs_profil`) et le range dans `profils/<id>.json` du bucket (`SOURCE_DONNEES=s3`) ou dans `archives/profils/` (local, ignoré par Git). N'écrase jamais rien : refus si l'`id` est un profil de `personas/`, écriture conditionnelle `IfNoneMatch="*"` dans S3, ouverture en mode `x` en local (`ProfilDejaExistant`) ;
  - `lire_profil_cree(identifiant)` : le profil rangé, ou `None` ;
  - `appliquer_modifications(profil, modifications, date)` : l'utilisateur choisit lui-même un seuil avant de signer (`pire_baisse_max.seuil`, `plafond.max`). La règle garde son type ; son libellé est réécrit et sa justification commence par « Choisi par vous le … : −15,0 % au lieu de −20,0 % proposé par le barème », suivie de la justification du barème. Les autres types de règles n'ont pas de seuil à choisir.
- **`pipeline/agent_profil.py`** : `charger_profil(identifiant)` lit `personas/<id>.json`, sinon le profil créé, et le valide (`PacteInvalide` s'il est abîmé, `ProfilInconnu` s'il n'existe nulle part). Elle remplace `charger_pacte(chemin_profil(...))` dans `lancer_agent_profil`, `tribunal.juger_decision` (Pacte vécu) et `contre_interrogatoire.interroger`. `chemin_profil` reste pour les profils de démonstration.
- **`deploiement/lambda_tribunal.py`** : deux routes, **sans Bedrock** :
  - `POST /questionnaire` `{}` → `{"questions": questions()}` ;
  - `POST /profil` `{"reponses", "capital", "portefeuille", "nom", "modifications"}` → 201 `{"id", "profil", "bareme", "contradictions", "archive"}`. Réponse refusée : 400 avec `details` (motifs de `ReponsesInvalides`), rien n'est rangé. S3 indisponible : 500.
  - `trop_d_appels` généralise la limite de débit de `/verifier` ; `/profil` est limité à 10 profils par minute et par adresse IP.
- **`deploiement/tester_function_url.py`** : `--creer-profil REPONSES` crée le profil par `/profil`, puis fait le procès de ce profil.
- **`deploiement/deployer.py`** : la liste des routes affichée à la fin du déploiement.

## Comment l'utiliser
```bash
curl -X POST "$URL/profil" -H 'content-type: application/json' \
  -d '{"reponses": {...}, "capital": 120000, "portefeuille": [{"ticker": "XIU.TO", "poids": 1}], "nom": "Sam"}'
# → {"id": "investisseur_3f9a0c1b2d4e", ...}
curl -X POST "$URL/tribunal" -d '{"profil": "investisseur_3f9a0c1b2d4e", "demande": "30 % en TSLA"}'
```
Sur la Lambda déployée, avec un vrai procès : `python deploiement/tester_function_url.py --creer-profil docs/exemples/reponses_questionnaire.json "Je veux mettre 30 % en Tesla"`.

## Comment vérifier
```bash
.venv/bin/python -m pytest tests/test_profils.py tests/test_route_profil.py
```
- `test_profils.py` (21 tests) : rangement et relecture en local et dans un faux S3, refus d'écraser (profil de démonstration, même identifiant), profil abîmé refusé à la lecture, identifiant hors format jamais cherché, seuils choisis par l'utilisateur (et valeurs refusées).
- `test_route_profil.py` (17 tests) : `/questionnaire` renvoie les cartes calculées ; `/profil` range un profil que `charger_profil` relit tel quel ; seuil modifié ; réponses, titres, modifications et champs invalides → 400 sans rien ranger ; le nom « robert » ne touche pas au profil de démonstration ; limite de débit par adresse ; S3 indisponible → 500.

## Choix faits en cours de route
- **Identifiant généré par la Lambda** : le nom saisi n'est qu'un libellé. C'est ce qui garantit qu'un profil créé n'écrase jamais un profil de démonstration, sans liste d'exceptions.
- **`charger_profil` dans `agent_profil.py`**, la lecture et l'écriture dans `profils.py` : `profils.py` n'importe pas l'Agent Profil, ce qui évite une importation circulaire.
- **Les seuils modifiés restent dans le format du Pacte** : le schéma des règles n'admet pas de champ de plus, donc « Choisi par vous » va dans la justification et le libellé.
- **IAM inchangé** : la politique donne déjà `GetObject` et `PutObject` sur tout le bucket. L'issue proposait de la restreindre à `profils/*` ; ce serait une restriction de l'existant, pas un besoin de cette route.

## Limites et suite
- **Aucune authentification** : n'importe qui peut créer un profil, et lire un profil dont il connaît l'identifiant en lançant un procès. Acceptable en simulation (capital fictif, profil `fictif`) ; à dire dans la documentation.
- La limite de débit est en mémoire de chaque instance : un garde-fou, pas une protection complète.
- La pièce `declaree` du questionnaire (#85) garde le seuil proposé par le barème ; si l'utilisateur l'a changé, la règle du Pacte et la pièce diffèrent, et la justification de la règle le dit.
- L'écran qui appelle ces routes est #86. Les nouvelles routes ne sont actives qu'après un redéploiement (`python deploiement/deployer.py`).
