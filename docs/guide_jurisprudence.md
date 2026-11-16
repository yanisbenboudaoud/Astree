# Guide : la jurisprudence, expliquée pas à pas

Ce guide explique ce qui a été construit dans les issues #56 (jurisprudence) et #65 (validateur), et **pourquoi**. Il part de zéro : pas besoin d'avoir suivi le travail pour le comprendre.

Les fiches du journal ([056](journal/056-jurisprudence.md), [065](journal/065-valider-erreurs-outil.md)) disent *ce qui existe*. Ce guide dit *comment les morceaux s'emboîtent*.

---

## 1. En une phrase

Le Tribunal a maintenant une **mémoire** : quand l'utilisateur a déjà pris une décision qui violait son Pacte, le procès suivant le lui rappelle, preuve à l'appui.

> « Le 2026-11-15, vous avez jugé une autre position en TSLA qui violait votre règle « Pire baisse tolérée : −12 % », et vous avez rendu le verdict « maintenu ». »
> (vrai argument du Procureur, Lambda, 15 novembre 2026)

---

## 2. Rappel : un procès, en 5 phases

Avant de voir ce qui a changé, voici le procès tel qu'il existait déjà (`pipeline/tribunal.py`, fonction `juger_decision`) :

```
 Demande : « 25 % en Tesla »
        │
        ▼
 1. Agent Profil ........ charge le Pacte (pièce P1), comprend la demande
        │
        ▼
 2. Orchestrateur ....... un LLM CHOISIT quels outils Python appeler
        │                 chaque résultat devient une pièce : P2, P3, P4…
        ▼
 3. Procureur ┐ ......... deux LLM, en parallèle, argumentent
    Avocat    ┘           contre / pour, en citant les pièces
        │
        ▼
 4. Greffier ............ Python, sans LLM : vérifie le Pacte,
        │                 et vérifie que chaque chiffre cité existe dans une pièce
        ▼
 5. Verdict ............. l'utilisateur choisit : maintenu, modifie, pacte_ajuste
```

**À retenir** : les LLM ne calculent rien. Les chiffres viennent toujours d'un **outil Python**, qui produit une **pièce**. Le Greffier rejette tout chiffre qui n'est pas dans une pièce.

---

## 3. Le problème qu'on a réglé

À l'étape 5, la Lambda **archivait** déjà le verdict dans S3 (issue #13). Mais **personne ne relisait ces archives**. Chaque procès repartait de zéro, comme si l'utilisateur n'était jamais venu.

On a donc ajouté un **7ᵉ outil** que l'orchestrateur peut appeler : `consulter_jurisprudence`. Il relit les verdicts passés du même profil et en fait une pièce.

---

## 4. La boucle complète

Voici le trajet de l'information, d'un procès au suivant :

```
 PROCÈS 1 : « 30 % en Tesla »
   │  le Greffier constate : violation de pire_baisse_max
   │  l'utilisateur choisit : « maintenu »
   ▼
 Lambda, route /verdict
   │  écrit le contrat complet + le verdict dans S3 :
   │  verdicts/robert/2026-11-15-d60e97d1cbf1.json
   ▼
 ─────────────────────── (plus tard) ───────────────────────
   ▼
 PROCÈS 2 : « 25 % en Tesla »
   │
   ├─ Orchestrateur : « une règle est probablement violée,
   │  voyons si ce conflit se répète » → appelle consulter_jurisprudence
   │
   ├─ Python lit S3 : verdicts/robert/*.json  (et SEULEMENT robert)
   │  compte : 1 procès archivé, 1 en violation, 1 maintenu
   │  → pièce P6
   │
   ├─ Procureur : cite P6 dans un argument
   │
   └─ Greffier : vérifie chaque chiffre de cet argument contre P6
```

---

## 5. Le vrai procès du 15 novembre, étape par étape

Voici la trace réelle du procès « 25 % en Tesla » (profil prudent), renvoyée par la Lambda :

| # | Phase | Outil | Résultat |
|---|---|---|---|
| 1 | Agent Profil | `charger_pacte` | **P1** : le Pacte, signé le 14 nov. 2026 |
| 2 | Agent Profil | `bedrock` + `valider_decision` | décision : 25 % en TSLA, financement proportionnel |
| 3 | Orchestrateur | `simuler_portefeuille` | **P2** : −24,9 % de pire baisse, +11,8 %/an |
| 4 | Orchestrateur | `simuler_portefeuille` | **P3** : rejeu de 2022, −2,6 % → −20,3 % |
| 5 | Orchestrateur | `taille_max_compatible` | **P4** : 9 % au maximum |
| 6 | Orchestrateur | `indicateurs_actif` | **P5** : TSLA, −70,9 % au pire |
| 7 | Orchestrateur | **`consulter_jurisprudence`** | **P6** : 1 procès archivé · 1 en violation : 1 maintenu |
| 8 | Orchestrateur | `rechercher_documents` | **Erreur** : aucun document ESG sur TSLA (voir section 8) |
| 9 | Procureur / Avocat | `bedrock` | 4 arguments contre, 3 pour |
| 10 | Greffier | `verifier_pacte` | 1 violation, 1 conforme, 2 à vérifier |
| 11 | Procureur | **`bedrock_correction`** | un argument renvoyé, puis réécrit (voir ci-dessous) |
| 12 | Greffier | `verifier_chiffres` | 34/34 chiffres vérifiés, 7 arguments |

### Le moment le plus intéressant : la ligne 11

Le premier jet du Procureur disait :

> « …le 2026-11-15, vous avez jugé **« 30 % en TSLA »**, en violation de la règle pire_baisse_max… »

Le Greffier l'a **refusé** avec ce motif exact : `« 30 % » introuvable dans P6`.

Pourquoi ? Dans P6, « 30 % en TSLA » est rangé comme **texte** (le libellé de l'ancienne décision), pas comme **nombre**. Le Greffier ne compte que les nombres et les dates des pièces. Le Procureur a donc réécrit son argument sans « 30 % » (« une autre position en TSLA »), et cette version est passée.

C'est exactement la promesse du projet : **aucun chiffre non prouvé ne passe**, même quand il est vrai.

---

## 6. Fichier par fichier : ce qui a changé

### `pipeline/jurisprudence.py` (nouveau) : l'outil

Trois fonctions principales, qu'on peut lire dans cet ordre :

| Fonction | Ce qu'elle fait | LLM ? |
|---|---|---|
| `charger_archives(persona)` | Va chercher les verdicts du profil : dans S3 (`verdicts/<profil>/`) sur la Lambda, ou dans `archives/verdicts/<profil>/` en local | Non |
| `resumer_archive(identifiant, archive)` | Réduit un contrat archivé à 4 infos : date, décision, règles violées, verdict | Non |
| `piece_jurisprudence(archives, regle)` | Compte et fabrique la pièce au format du contrat | Non |

Et deux utilitaires : `cle_verdict(persona, identifiant)`, qui donne l'adresse S3 d'un verdict, et `decrire_consulter_jurisprudence(...)`, qui décrit l'outil au LLM.

**Les valeurs de la pièce** (exemple réel, P6) :

```json
{
  "regle": "toutes",
  "proces_archives": 1,
  "proces_en_violation": 1,
  "maintenu": 1, "modifie": 0, "pacte_ajuste": 0,
  "dates_antecedents": ["2026-11-15"],
  "decisions_antecedents": ["30 % en TSLA"],
  "regles_violees_antecedents": ["pire_baisse_max"],
  "verdicts_antecedents": ["maintenu"]
}
```

Les 4 listes `..._antecedents` se lisent **par rang** : l'élément 0 de chaque liste décrit le même procès passé.

### `pipeline/orchestrateur.py` : brancher l'outil

- L'outil est ajouté à la **liste blanche** (`outils_du_profil`). L'orchestrateur ne peut appeler que les outils de cette liste.
- Son seul paramètre est `regle` : l'`id` d'une règle du Pacte, ou `toutes`.
- Une phrase a été ajoutée aux consignes : une règle probablement violée rend la jurisprudence utile.

### `deploiement/lambda_tribunal.py` : ranger les verdicts par profil

- Avant : `verdicts/<id>.json`, tous les profils mélangés.
- Maintenant : `verdicts/<profil>/<id>.json`.

### `pipeline/debat.py` : faire citer la pièce

Une phrase dans la consigne du **Procureur** : s'il existe un antécédent, il le rappelle (date, décision, verdict), **sans reproche**. Sans cette phrase, la pièce P6 arrivait bien au dossier, mais personne ne la citait (constaté lors du premier test sur la Lambda).

### `contrat/valider.py` : la correction de l'issue #65

Voir la section 8.

---

## 7. Les 4 choix importants, et pourquoi

1. **Le LLM choisit la règle, jamais le profil.**
   Le profil vient du Pacte (`profil["id"]`), en Python. L'orchestrateur ne peut donc pas lire les verdicts de quelqu'un d'autre, même s'il se trompe ou s'il est manipulé.

2. **Les verdicts sont rangés par profil dans S3.**
   Sans ça, pour trouver les verdicts de Robert, il faudrait télécharger tous les verdicts de tout le monde, puis les trier. Avec un dossier par profil, on lit seulement le bon dossier.
   *Conséquence* : les quelques verdicts de test archivés avant ce changement ne sont plus relus.

3. **Des listes parallèles plutôt qu'une liste d'objets.**
   Le schéma du contrat (`contrat/schema_sortie.json`) n'accepte dans une pièce que des valeurs simples ou des listes de valeurs simples. Plutôt que de changer le contrat (partagé avec l'équipe interface), on s'y est adapté. L'interface n'a donc rien à changer.

4. **Rien de plus dans IAM.**
   La Lambda avait déjà le droit de lister et de lire le bucket. On n'a ajouté aucune permission.

---

## 8. Ce qui a été corrigé en passant : le validateur (#65)

Regarde la ligne 8 du tableau de la section 5 : `rechercher_documents` a échoué (aucun document ESG sur TSLA). C'est **normal et voulu** : l'outil dit « source manquante » au lieu d'inventer, et le procès continue. Dans la trace, la sortie de cet appel est `Erreur : <motif>` au lieu d'un numéro de pièce.

Le problème : `contrat/valider.py` avait été écrit **avant** que l'orchestrateur sache gérer les erreurs. Il exigeait que chaque appel de l'orchestrateur produise une pièce. Il déclarait donc invalide un procès parfaitement correct.

La correction :
- une sortie `Erreur : <motif>` est maintenant acceptée (le motif ne doit pas être vide) ;
- toute autre sortie qui n'est pas une pièce reste refusée ;
- **plus strict** : la simulation obligatoire doit avoir **réussi**. Avant, une simulation demandée mais en erreur suffisait.

---

## 9. Limites à connaître

- **Rien n'est garanti à chaque procès.** C'est l'orchestrateur qui décide d'appeler l'outil, et le Procureur qui décide de citer la pièce. Le plus souvent ils le font, mais pas toujours.
- **Le pourcentage d'une ancienne décision ne peut pas être cité** (« 30 % en TSLA » est du texte dans la pièce, section 5). Si on en a besoin, il faudra ajouter une liste de tailles en **nombres** à la pièce.
- **Le Pacte a pu changer** depuis l'ancien procès : les règles sont comparées par identifiant. La pièce le dit dans ses `limites`.
- **Seuls les procès avec un verdict** sont archivés dans `verdicts/` : un procès abandonné sans verdict ne compte pas.

---

## 10. Le vérifier soi-même

**Les tests** (sans AWS, sans Bedrock, quelques secondes) :

```bash
.venv/bin/python -m pytest tests/test_jurisprudence.py -v
```

Chaque nom de test dit ce qu'il prouve. Le plus parlant : `test_le_greffier_verifie_les_chiffres_de_la_jurisprudence`.

**En local, sans AWS** : déposer un contrat avec un `verdict` dans `archives/verdicts/robert/2026-11-15-aaaaaaaaaaaa.json` (dossier ignoré par Git), puis :

```bash
.venv/bin/python -c "from pipeline.jurisprudence import *; print(piece_jurisprudence(charger_archives('robert'))['valeur_affichee'])"
```

**Sur la Lambda** (vrais appels Bedrock, payants) :

```bash
.venv/bin/python -X utf8 deploiement/tester_function_url.py robert "Je veux mettre 30 % de mon portefeuille en Tesla" --verdict maintenu
```
```bash
.venv/bin/python -X utf8 deploiement/tester_function_url.py robert "Je veux mettre 25 % de mon portefeuille en Tesla" --sortie contrat.json
```

Puis chercher `consulter_jurisprudence` dans `contrat.json`.

---

## 11. Pour vérifier que tu as compris

Essaie de répondre avant d'ouvrir la réponse.

<details>
<summary>1. Qui produit les chiffres de la pièce P6 : le LLM ou Python ?</summary>

Python (`piece_jurisprudence`). Le LLM de l'orchestrateur décide seulement **d'appeler** l'outil, et pour quelle règle.
</details>

<details>
<summary>2. Pourquoi l'orchestrateur ne peut-il pas lire les verdicts d'Amira pendant le procès de Robert ?</summary>

Parce que le profil n'est pas un paramètre de l'outil : Python le prend dans le Pacte du procès en cours. Le LLM ne choisit que la règle.
</details>

<details>
<summary>3. Pourquoi le premier argument du Procureur a-t-il été refusé ?</summary>

Il citait « 30 % », qui n'existe dans P6 que comme texte (« 30 % en TSLA »), pas comme nombre. Le Greffier ne trouve donc pas ce nombre dans la pièce citée.
</details>

<details>
<summary>4. Que se passe-t-il au tout premier procès d'un profil, quand il n'y a encore aucun verdict ?</summary>

La pièce dit « Aucun procès archivé pour ce profil », avec tous les comptes à 0. Rien n'est inventé.
</details>

<details>
<summary>5. Pourquoi le validateur refusait-il un procès correct ?</summary>

Il avait été écrit avant la gestion des erreurs d'outil : il exigeait une pièce pour chaque appel de l'orchestrateur, alors qu'un appel en erreur n'en produit pas, volontairement.
</details>

---

## 12. Où trouver quoi

| Quoi | Où |
|---|---|
| Issue jurisprudence | #56, PR #63 (outil) et #64 (consigne du Procureur, vérification sur la Lambda) |
| Issue validateur | #65, PR #66 |
| Ce qui existe, en détail | fiches [056](journal/056-jurisprudence.md) et [065](journal/065-valider-erreurs-outil.md) |
| L'outil | `pipeline/jurisprudence.py` |
| Ses tests | `tests/test_jurisprudence.py` |
| Liste des 7 outils | `REFERENCE_DU_PROJET.md`, section 4 bis |
