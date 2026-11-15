# #56 — Jurisprudence : l'orchestrateur consulte les verdicts passés archivés dans S3

- **Issue** : #56 · **PR** : #63 · **Statut** : en cours (code et tests faits ; reste la vérification sur la Lambda déployée)
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- `pipeline/jurisprudence.py` : outil 7 `consulter_jurisprudence`, sans LLM.
  - `charger_archives(persona)` : verdicts archivés du profil jugé, les plus récents d'abord (au plus `LIMITE_ARCHIVES` = 200). Source selon `SOURCE_DONNEES` : `archives/verdicts/<profil>/` en local (ignoré par Git), préfixe `verdicts/<profil>/` du bucket en `s3`. Une archive S3 illisible lève `ErreurDonnees` : l'orchestrateur la renvoie au modèle comme erreur d'outil, le procès continue.
  - `piece_jurisprudence(archives, regle)` : pièce `calculee`, étiquette `fait`. Valeurs : `proces_archives`, `proces_en_violation` (de la règle, ou de toute règle du Pacte avec `regle = "toutes"`), le nombre de verdicts `maintenu` / `modifie` / `pacte_ajuste` parmi ces procès, et les 5 derniers antécédents en listes parallèles (`dates_antecedents`, `decisions_antecedents`, `regles_violees_antecedents`, `verdicts_antecedents`).
  - `cle_verdict(persona, identifiant)` : clé d'archive, partagée avec la Lambda.
- `pipeline/orchestrateur.py` : l'outil est ajouté à la liste blanche de `outils_du_profil`. Son seul paramètre est `regle`, avec pour valeurs possibles les `id` des règles du Pacte jugé et `toutes`. Une ligne d'exemple a été ajoutée aux consignes. Le budget de 8 appels ne change pas.
- `deploiement/lambda_tribunal.py` : `/verdict` archive désormais dans `verdicts/<profil>/<id>.json` (au lieu de `verdicts/<id>.json`, fiche 013), pour que la jurisprudence lise un seul préfixe.
- `CLAUDE.md` (tableau 4 bis, outil 7), carte du `README.md`, `deploiement/README.md`, `docs/architecture.md`.

## Comment l'utiliser
```python
from pipeline.jurisprudence import charger_archives, piece_jurisprudence
piece = piece_jurisprudence(charger_archives("robert"), "pire_baisse_max")
piece["valeur_affichee"]  # « 3 procès archivés · 2 en violation : 1 maintenu, 1 modifié, 0 Pacte ajusté »
```
Dans un procès, c'est l'orchestrateur qui décide d'appeler l'outil. Pour l'essayer en local, déposer des contrats avec un `verdict` dans `archives/verdicts/<profil>/<id>.json`.

## Comment vérifier
`pytest tests/test_jurisprudence.py`. Les tests prouvent :
- sans archive, la pièce le dit ; le compte par règle et par verdict ; « toutes » ;
- les procès sans verdict et les contrôles du système (`verifier_chiffres`) sont ignorés ; les antécédents détaillés sont bornés ;
- la pièce respecte le schéma du contrat ;
- **le Greffier vérifie ses chiffres** : « Sur 3 procès archivés, 2 violaient déjà… le 14 novembre » passe, « violée 4 fois » est rejeté ;
- seules les archives du profil jugé sont lues, en local comme dans S3 ; une erreur S3 devient `ErreurDonnees` ;
- un premier procès maintenu malgré une violation devient une pièce du procès suivant.

## Choix faits en cours de route
- **Archives rangées par profil** (`verdicts/<profil>/`) : sinon il faudrait lire toutes les archives de tous les profils pour en filtrer un. Les verdicts déjà archivés à l'ancienne clé ne sont pas relus (seulement des procès de test).
- **Le profil vient du Pacte, pas du modèle** : le modèle choisit seulement la règle. Il ne peut pas lire les verdicts d'un autre profil.
- **Listes parallèles** plutôt qu'une liste d'objets : le schéma du contrat n'admet que des listes de valeurs simples dans une pièce. Le format du contrat n'a donc pas changé.
- **IAM inchangée** : la politique donne déjà `s3:GetObject` sur le bucket et `s3:ListBucket`, ce qui suffit pour lister et lire `verdicts/`.

## Limites et suite
- Pas encore vérifié sur la Lambda déployée : il faut redéployer, rendre un verdict, puis relancer un procès du même profil.
- Les règles sont comparées par identifiant : si le Pacte a été ajusté depuis, une ancienne violation peut porter sur un ancien seuil. La pièce le dit dans ses `limites`.
- L'interface (#14) n'a rien de spécial à faire : c'est une pièce comme les autres.
