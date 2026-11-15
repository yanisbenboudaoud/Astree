# #57 — Dossier de convenance : export du procès-verbal et angle business

- **Issue** : #57 · **PR** : #PR_A_RENSEIGNER · **Statut** : terminée (la diapositive du pitch reste à faire dans #18)
- **Dernière mise à jour** : 2026-11-14

## Ce qui a été construit
- **`pipeline/proces_verbal.py`** : `proces_verbal_html(contrat, identifiant=None)` met un contrat de procès en page HTML autonome et imprimable. La page contient : en-tête et bandeau de simulation, décision, Pacte avec sa date de signature, comparaison avant et après, taille maximale compatible, contrôles du Greffier, réquisitoire, plaidoirie, arguments rejetés avec leur motif, contre-interrogatoire s'il existe, verdict, pièces (valeurs brutes, source, traitement, limites), trace, hypothèses, sources, limites et avertissement.
  - **Python seul, sans LLM.** Chaque texte vient du contrat ou d'un libellé fixe (`LIBELLES`, `VERDICTS`, `STATUTS`…). Le module ne dépend que de la bibliothèque standard.
  - **Tout texte du contrat est échappé** (`html.escape`).
  - **Même contrat, même page** : aucune date ni valeur ajoutée à l'export.
  - **Ligne de commande** : `python -m pipeline.proces_verbal <contrat.json> [-o page.html] [--id <id>]`, ou `--demo` pour les procès enregistrés de l'interface.
- **`deploiement/lambda_tribunal.py`** : nouvelle route `POST /proces-verbal` `{"id"}`. Elle relit l'archive du verdict (`verdicts/<profil>/<id>.json`) si l'utilisateur a déjà tranché, sinon la trace du procès (`traces/<date>/<id>.json`), et renvoie la page en `text/html`. Aucun appel à Bedrock.
- **Interface Astrée** :
  - lien « Exporter le procès-verbal » sur l'écran Verdict (`frontend/src/ecrans/Verdict.tsx`) ;
  - `ouvrirProcesVerbal` (`frontend/src/api/tribunal.ts`) : en mode direct, elle appelle `POST /proces-verbal` ; en démonstration, elle ouvre la page précalculée `frontend/public/proces-verbaux/<identifiant>.html` du procès affiché ;
  - la fenêtre est ouverte avant l'appel réseau, pour ne pas être bloquée comme fenêtre surgissante ;
  - une erreur d'export a son propre message, distinct de celui du verdict.
- **`frontend/public/proces-verbaux/`** : un procès-verbal par procès enregistré de l'interface (7 aujourd'hui), nommé d'après son identifiant d'audience, généré par `python -m pipeline.proces_verbal --demo`. Une page dont le procès a été retiré de l'index est supprimée.
- **`docs/CHOIX_CONCEPTION.md`, choix 15** : le procès-verbal, le cadre canadien avec ses sources, et l'angle business formulé avec prudence.

## Comment l'utiliser
```bash
python -m pipeline.proces_verbal docs/exemples/contrat_robert.json -o pv.html   # puis ouvrir pv.html, imprimer en PDF
python -m pipeline.proces_verbal --demo        # après un nouveau procès enregistré dans frontend/src/data/proces/
```
Dans l'interface : écran Verdict, lien « Exporter le procès-verbal ».

## Comment vérifier
- `pytest tests/test_proces_verbal.py tests/test_lambda_tribunal.py` :
  - tout le dossier est dans la page pour les 2 faux contrats et les 7 procès enregistrés (règles, contrôles, arguments, motifs de rejet, pièces, trace, hypothèses, limites) ;
  - le verdict est affiché qu'il soit rendu ou non ;
  - le texte du contrat est échappé, et le module n'utilise aucun LLM ;
  - la route renvoie la page avec ou sans verdict, 404 pour un procès inconnu, 400 pour un identifiant invalide ;
  - les pages de `frontend/public/proces-verbaux/` sont à jour.
- `cd frontend && npm run dev`, puis `npm run verifier` : le parcours de Robert ouvre le procès-verbal depuis l'écran Verdict et vérifie son contenu (23 écrans vérifiés par axe-core, aucun problème).

## Choix faits en cours de route
- **HTML imprimable plutôt que PDF** : aucune dépendance de mise en page côté Lambda. L'impression du navigateur (« Enregistrer en PDF ») suffit, et une feuille de style pour l'impression évite les coupures au milieu d'une pièce.
- **Pages précalculées en démonstration** : l'interface en mode démonstration ne peut pas exécuter Python. Les pages sont donc générées par le même code, et un test vérifie qu'elles sont à jour.
- **Le verdict vient de l'archive S3**, pas du navigateur : le procès-verbal ne contient que ce qui a été archivé. Exporté avant la signature, il indique « Verdict non encore rendu ».
- **La règle de l'OCRI n'est pas affirmée.** Les pages de l'OCRI ont refusé l'accès (erreur 403). Le choix 15 cite BLG comme source lue, et marque les pages de l'OCRI « à vérifier ».
- **Correction de l'angle business de l'issue.** L'issue disait « un courtier doit documenter la convenance ». Ce n'est vrai que pour les comptes avec conseils. En courtage en ligne (sans conseils), l'obligation de convenance ne s'applique pas et les recommandations sont interdites. L'angle est donc présenté en deux usages, et l'admissibilité d'Astrée comme aide à la décision reste une question ouverte.

## Limites et suite
- **Pitch (#18)** : il reste la diapositive. La phrase du one pager est dans le choix 15.
- **La justification écrite** de « Maintenir malgré la violation » n'est pas dans le procès-verbal : la Lambda n'archive que `id` et `verdict` (fiche 014).
- **Le texte officiel des règles de l'OCRI** (numéro de la règle de convenance, note d'orientation de 2026) est à vérifier dans un navigateur avant le pitch.
