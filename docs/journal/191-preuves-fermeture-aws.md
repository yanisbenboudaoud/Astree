# #191 — Preuves avant la fermeture du compte AWS

- **Issue** : #191 · **PR** : #192 (captures d'écran), #197 (captures refaites après #193 et #195) · **Statut** : en cours (procès sauvegardés et preuves AWS dans une seconde PR)
- **Dernière mise à jour** : 2026-11-16

Message du jury : « On ne pourra pas tester : tout sera supprimé. Assurez-vous donc de prendre vidéos, captures d'écran, toutes preuves et tout ce qui est nécessaire pour démontrer votre solution. » Ce qui ne vit que sur AWS ou dans le navigateur est donc capturé et versé au dépôt.

## Ce qui a été construit

### Captures de chaque écran
- **`frontend/e2e/preuves.mjs`** (nouveau) : parcourt l'interface en mode démonstration (procès réellement tenus par les agents sur AWS, rejoués sans réseau) et capture chaque écran. Un écran qui échoue est signalé, les autres sont capturés quand même. La fenêtre est agrandie à la hauteur de la page avant chaque capture, pour que la barre fixée en bas ne couvre pas le milieu de la page.
- **`docs/preuves/ecrans/`** : 18 captures et leur index (`README.md`, une phrase par capture) :
  - accueil ;
  - Robert, 30 % en TSLA (cas 1) : portefeuille, décision, procès en cours, Tribunal (bilan, débats, répliques, instruction par l'orchestrateur, argument renvoyé par le Greffier, contre-interrogatoire), contrôles du Greffier avec leurs taux mesurés, tiroir d'une pièce de simulation, verdict, procès-verbal ;
  - Amira, panier crypto-tech (cas 2) : décision, Tribunal, verdict avec un point de bascule par règle ;
  - Mateo, XOM (cas 3) : décision et Tribunal ;
  - Construire mon Pacte : une question, puis le Pacte tiré des réponses ;
  - Pacte vécu : une question, puis la limite mesurée.
- **`docs/DOCUMENTATION_TECHNIQUE.md`** : nouvelle section 11, « Le prototype en captures » (le parcours écran par écran, quatre écrans clés affichés), et une ligne « À l'écran » dans les sections 2, 3, 5, 6, 7 et 8, qui renvoie à la capture qui illustre chacune.
- **`.gitignore`** : le dossier local `Datathonprep2026/` (case, présentation et transcription de l'événement) n'est jamais versionné.

## Comment l'utiliser
```bash
cd frontend
npm run dev                                   # sans VITE_API_URL : mode démonstration
ASTREE_URL=http://localhost:5173 node e2e/preuves.mjs   # → ../docs/preuves/ecrans
```

## Comment vérifier
Ouvrir [`docs/preuves/ecrans/README.md`](../preuves/ecrans/README.md) : chaque capture et ce qu'elle montre.

## Choix faits en cours de route
- **Mode démonstration** : les captures ne dépendent pas d'AWS et se refont à l'identique ; ce sont des procès réellement tenus par Bedrock, rejoués.
- **Captures refaites sur le `main` le plus récent** (après #188 et #190), pour montrer l'interface telle qu'elle sera remise.
- **Refaites de nouveau le 2026-11-16 (PR #197)**, sur `main` après #193 (mode choisi à l'utilisation, #137) et #195 : les 18 écrans passent, aucun en échec. Le script tourne sans `VITE_API_URL`, donc sans interrupteur de mode : les captures montrent l'interface comme la démonstration durable (GitHub Pages). Depuis #137, `preuves.mjs` fixe aussi le mode « procès enregistrés » dans le navigateur : lancé contre le site hébergé, en direct par défaut depuis #141, il ne déclenche aucun procès payant.

## Limites et suite
- Seconde PR : sauvegarde des procès tenus dans S3 (`validation/proces_tenus.tar.gz`) et preuves AWS exportées par l'API (`docs/preuves/aws/`), puis README et documentation technique.
- La vidéo (#18) reste à tourner.
