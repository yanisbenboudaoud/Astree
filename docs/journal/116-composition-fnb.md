# #116 — Composition des FNB : plafonds calculés par transparence

- **Issue** : #116 · **PR** : #140, puis la PR de la Lambda redéployée et des procès de démo d'Amira refaits · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Atelier Banque Nationale : pour un fonds, il faut regarder sa composition. Avant cette issue, un FNB était classé en entier : QQQ comptait pour 100 % `tech`, SPY et XIU.TO pour 0 % `energie_fossile`.

- **`donnees_externes/composition_fnb.json`** (nouveau) : la composition des 9 FNB de l'univers, relevée le 2026-11-15 sur les pages publiques des émetteurs. Pour chaque fonds :
  - l'URL et le nom de l'émetteur ;
  - la répartition par secteur, avec sa classification et sa date : GICS (SPY, XIU.TO), ICB (QQQ, ESGV), secteurs obligataires (XBB.TO, ZST.TO, AGG), obligations d'État (TLT), or physique (GLD) ;
  - le poids d'Alphabet et d'Amazon (SPY, QQQ, ESGV) ;
  - la répartition par pays quand elle est publiée (ZST.TO, TLT, GLD), sinon `null` ;
  - des notes ; les pourcentages sont copiés tels qu'affichés.
- **`config/categories.json`** : un bloc `transparence` par catégorie, qui dit comment lire une composition :
  - `tech` : Information Technology plus Alphabet et Amazon en GICS ; Technology plus Amazon en ICB ;
  - `energie_fossile` : Energy en GICS, en ICB et dans les secteurs obligataires canadiens ;
  - `canada`, `etats_unis`, `hors_canada` : la répartition par pays ;
  - `crypto` n'en a pas : elle se lit toujours en classement direct.
- **`pipeline/composition.py`** (nouveau) :
  - `part_dans_le_fonds(ticker, categories)` : part de l'union des catégories dans un FNB ; `None` si la composition ne permet pas le calcul ;
  - `part_des_categories(poids, categories)` → `PartCategories` (`part`, `hors_univers`, `par_transparence`, `classement_direct`) ; `part_sans_transparence` donne l'ancien calcul ;
  - `piece_composition` : la pièce `composition_fnb`, avec `part_<catégorie>`, `_actuelle` et `_sans_transparence`, pour chaque catégorie et chaque union d'un plafond du Pacte, plus `fonds_lus` et, à plat, `<ticker>_part_<catégorie>`, `<ticker>_date_secteurs`, `<ticker>_classification_secteurs` ;
  - `erreurs_compositions` : vérifie que chaque fonds est dans l'univers, que chaque répartition totalise 100 %, que les classifications sont connues et que les secteurs cités par les catégories existent.
- **Même calcul partout** : `pipeline/greffier.py` (`controler_plafond`), `pipeline/taille_max.py`, donc les points de bascule, et `pipeline/vues_interface.py`, donc l'interface. Le message du Greffier dit comment chaque FNB a été compté, par exemple « (par transparence : GLD, QQQ, SPY, XIU.TO ; classement direct : XBB.TO) ». Le contrôle cite la pièce de composition. `nom_categories` passe dans `pipeline/categories.py`, pour éviter une importation circulaire ; `greffier.nom_categories` reste disponible.
- **`pipeline/tribunal.py`** : `verser_composition` verse la pièce d'office avant les points de bascule. La raison est `RAISON_COMPOSITION`, et l'hypothèse `HYPOTHESE_COMPOSITION` est ajoutée au contrat. **`pipeline/sources.py`** : nouvelle source « Composition des FNB », reliée à la pièce et aux plafonds qui la citent. **`pipeline/debat.py`** : une consigne pour lire la pièce.
- **`validation/scenarios.py`** : la part tech + crypto attendue est calculée, au lieu d'être fixée à 65 %. Le scénario « QQQ retiré des ajouts tech » vérifie maintenant que c'est sans effet par transparence. `docs/validation/resultats_scenarios.md` est régénéré (52 réussis).
- **`frontend/src/data/generated/`** régénéré : seules les tables d'Amira et de l'exemple du questionnaire changent. Les Pactes de Robert et de Mateo ne plafonnent que la crypto.

## Comment l'utiliser
```python
from pipeline.composition import part_dans_le_fonds, part_des_categories
part_dans_le_fonds("QQQ", ["tech"])            # 0.691 (ICB Technology 64,4 % + Amazon 4,70 %)
part_dans_le_fonds("SPY", ["energie_fossile"])  # 0.0358
r = part_des_categories({"AGG": 0.4, "XOM": 0.1, "SPY": 0.5}, ["energie_fossile"])
r.part, r.par_transparence, r.classement_direct  # 0.1179, ["SPY"], ["AGG"]
```

## Comment vérifier
```bash
pytest tests/test_composition.py tests/test_greffier.py tests/test_taille_max.py tests/test_points_de_bascule.py tests/test_orchestrateur.py
python -m validation
```
Les tests demandés par l'issue (`tests/test_composition.py`) :
- QQQ compte pour 69,1 % de technologie, pas 100 % ;
- un portefeuille avec SPY a une part `energie_fossile` > 0 ;
- un plafond `etats_unis` de 40 % est calculé par transparence pour un FNB mondial : 62 % américain, composition injectée, car aucun FNB mondial n'est dans l'univers. Il est conforme (31,0 %) là où le classement direct donnerait 50 %.

Autres tests :
- un FNB sans composition, ou une classification qui n'isole pas la catégorie (AGG), garde son classement direct, et c'est signalé ;
- l'or et les obligations d'État ont 0 % de technologie et d'énergie ;
- une union secteur et pays n'est pas calculable ;
- la pièce passe le schéma, et un argument qui la cite passe `verifier_chiffres` ;
- dans un procès simulé, la pièce est versée d'office et citée par le plafond, et la source apparaît.

**Procès réel** (Bedrock, 2026-11-15), profil audacieux, « réallouer 40 % vers 30 % bitcoin, 20 % ether, 20 % NVIDIA, 20 % QQQ et 10 % Shopify » :
- la pièce P7 `composition_fnb` est versée d'office ;
- `pas_exclusivement_tech` est conforme avec 68,4 % de technologie et de crypto (70,0 % en classement direct), et le contrôle cite P7 ;
- l'Avocat a cité ce 68,4 % depuis P7 ; `verifier_chiffres` : 19/19 ;
- **le contrat passe `contrat.valider`**.

## Choix faits en cours de route
- **Lecture des pages, pas des fichiers de positions** : les téléchargements CSV des émetteurs ont été refusés par les permissions de l'outil. Les pages de QQQ, ESGV, XIU, XBB et ZST sont rendues en JavaScript ; elles ont été lues dans un navigateur, et les chiffres copiés tels qu'affichés.
- **Une classification par émetteur, pas de conversion** : QQQ et ESGV publient en ICB, et le bloc `transparence` dit quoi compter dans chaque classification. En ICB, Alphabet est déjà dans Technology : seul Amazon est ajouté. Meta reste compté, alors que le GICS le classe ailleurs ; c'est une différence assumée et documentée.
- **Jamais deviné** : AGG met l'énergie dans Industrial, XBB et ZST n'ont pas de secteur technologie, et la plupart des émetteurs ne publient pas de pays. Ces FNB gardent leur classement direct, et le message du Greffier le dit. Les pays de TLT se déduisent de son secteur (Treasuries) ; XIU.TO a 0 % d'Alphabet et d'Amazon, puisque c'est un indice de sociétés canadiennes. Les deux déductions sont écrites dans les notes.
- **Valeurs à plat dans la pièce** (`QQQ_part_tech`) : le schéma du contrat n'admet pas d'objet dans `valeurs`, et le format reste inchangé.
- **Pièce seulement quand elle compte** : si aucun plafond du Pacte ne porte sur une catégorie lue par transparence (Robert, Mateo : crypto seulement), il n'y a pas de pièce. Leurs procès ne changent pas.
- **Les pourcentages des émetteurs ne sont pas renormalisés** : leurs sommes s'écartent au plus de 0,01 point de 100 %.

**Sur AWS (après la fusion de #140)**
- **Lambda redéployée** (`deploiement/deployer.py --sans-donnees`) depuis `main` : le zip contient `pipeline/composition.py`, `config/categories.json` et `donnees_externes/composition_fnb.json`. Aucun service, fichier S3 ni droit IAM de plus.
- **Les 2 procès de démo d'Amira refaits** sur cette Lambda, avec la même demande (panier BTC-USD, ETH-USD, NVDA, QQQ à 25 %, tout le portefeuille). Ils sont copiés tels quels depuis `traces/2026-11-15/` du bucket : le contenu est identique à la réponse reçue, et chaque contrat passe `contrat.valider`.
  - `index.json`, les procès-verbaux et les imports des tests de l'interface suivent.
  - Les procès de Robert et de Mateo ne changent pas, puisque leurs Pactes ne plafonnent que la crypto : ils ne sont pas refaits.

| Procès | Remplace | Taille max | Tech + crypto | Point de bascule tech + crypto | Chiffres vérifiés |
|---|---|---|---|---|---|
| `2026-11-15-5ba5343b2165` | `2026-11-15-f59548b2fdd9` | 28 % (inchangée) | 92,3 % (100 % avant) | 57 % ou plafond 92,3 % (50 % ou 100 % avant) | 22/22 |
| `2026-11-15-30993c3a1ebf` (Pacte vécu) | `2026-11-15-1b59a098a64c` | 26 % (inchangée) | 92,3 % | 57 % ou plafond 92,3 % | 25/25 |

Dans les deux procès :
- la pièce `composition_fnb` est versée d'office, et le contrôle `pas_exclusivement_tech` la cite ;
- le Procureur la cite lui-même : « Technologie et cryptoactifs pèsent 92,3 % du portefeuille, contre 51,5 % avant la décision » ;
- aucun argument n'est rejeté ;
- l'orchestrateur appelle aussi `mesurer_liquidite` (#117), fusionné depuis les procès précédents.

`npm run verifier` (parcours des 3 profils, axe-core sur 23 écrans, débordement, console) passe sans problème.

## Limites et suite
- L'exemple du questionnaire, qui exclut les énergies fossiles, est désormais en violation dès 0 %. C'est fidèle : son portefeuille contient XIU.TO, SPY, XBB.TO et ZST.TO, donc déjà de l'énergie.
- La composition date de novembre 2026 et s'applique à toute la période simulée. Les dates diffèrent selon l'émetteur (ESGV : septembre 2026).
- Les conditions d'utilisation de State Street interdisent la reproduction : hors du datathon, il faudrait une autorisation ou une source sous licence.
- Aucun FNB mondial dans l'univers : la transparence géographique ne change encore rien pour les fonds réels. Elle servira pour un fonds comme XSP ou ZEQT.
