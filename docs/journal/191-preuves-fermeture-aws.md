# #191 — Preuves avant la fermeture du compte AWS

- **Issue** : #191 · **PR** : #192 (captures d'écran), #196 (procès sauvegardés et preuves AWS) · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

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

### Procès sauvegardés
- **`validation/archive_proces.py`** (nouveau) : copie en lecture seule les préfixes `traces/`, `verdicts/` et `profils/` du bucket du projet dans **`validation/proces_tenus.tar.gz`** (811 Ko). L'archive contient `MANIFESTE.json` : bucket, date de lecture, et pour chaque fichier sa date S3, sa taille et son empreinte SHA-256, vérifiée à chaque relecture. Elle est reproductible : fichiers triés, dates des objets S3, en-tête gzip sans date.
- Copie du 2026-11-16 : **218 procès**, 15 verdicts, 5 profils, tenus du 2026-11-14 au 2026-11-16. Aucune clé ni adresse courriel dedans (vérifié).
- **`validation/evaluation_orchestrateur.py`** : option `--archive`. La mesure de #167 relit l'archive au lieu de S3 ; la date de lecture est celle de la copie, donc le rapport se régénère à l'identique. Le bulletin du Greffier (#172) reçoit enfin l'entrée de l'orchestrateur : budget respecté 218/218, simulation demandée 218/218, arguments corrigés après renvoi 146/152.
- **`docs/validation/evaluation_orchestrateur.md`** régénéré depuis l'archive (218 procès au lieu de 201).

### Preuves AWS
- **`deploiement/preuves_aws.py`** (nouveau) : lit le compte en lecture seule (aucune création, aucun appel à Bedrock) et écrit dans **`docs/preuves/aws/`** un fichier JSON par preuve, tel que l'API le renvoie, et un résumé (`README.md`). Un appel refusé ou une preuve introuvable est notée « à capturer dans la console » sans arrêter les autres ; les variables d'environnement au nom de secret sont masquées.
- Export du 2026-11-16 (aucun refus du rôle de l'atelier) :
  - **Bedrock** : Claude Sonnet 5.5 appelé 1 725 fois (10 282 625 jetons lus, 0 erreur client) ;
  - **Lambda** `alphaforge-tribunal` : python3.14, 1024 Mo, 300 s, concurrence réservée 2, 0 relance asynchrone ; 1 573 appels, 0 erreur, 419 refus de débit (la concurrence réservée fait son travail) ;
  - **S3** : 218 traces, 15 verdicts, 5 profils, 121 progressions, 6 fichiers de données ; site : 162 objets ;
  - **IAM** (rôle et politiques), **CloudFront** (`Deployed`), **budget** : 17,29 $ dépensés sur 100 $.
- README et documentation technique (sections 3 et 8, section 10 « Preuves que AWS a réellement servi ») : chiffres mis à jour, adresses AWS annoncées comme fermées, renvoi vers les captures et les preuves.

## Comment l'utiliser
```bash
cd frontend
npm run dev                                   # sans VITE_API_URL : mode démonstration
ASTREE_URL=http://localhost:5173 node e2e/preuves.mjs   # → ../docs/preuves/ecrans
```
Tant que le compte AWS existe (identifiants dans le terminal) :
```bash
python -m validation.archive_proces                       # procès de S3 → validation/proces_tenus.tar.gz
python -m deploiement.preuves_aws                         # preuves → docs/preuves/aws/
```
Ensuite, sans AWS :
```bash
python -m validation.evaluation orchestrateur --archive   # même rapport, même bulletin
```

## Comment vérifier
Ouvrir [`docs/preuves/ecrans/README.md`](../preuves/ecrans/README.md) et [`docs/preuves/aws/README.md`](../preuves/aws/README.md). `pytest tests/test_archive_proces.py tests/test_preuves_aws.py` : archive reproductible, empreintes vérifiées, **rapport de l'orchestrateur régénéré à l'identique depuis l'archive du dépôt**, secrets masqués, refus notés sans arrêter la collecte.

## Choix faits en cours de route
- **Mode démonstration** : les captures ne dépendent pas d'AWS et se refont à l'identique ; ce sont des procès réellement tenus par Bedrock, rejoués.
- **Captures refaites sur le `main` le plus récent** (après #188 et #190), pour montrer l'interface telle qu'elle sera remise.
- **Refaites de nouveau le 2026-11-16 (PR #197)**, sur `main` après #193 (mode choisi à l'utilisation, #137) et #195 : les 18 écrans passent, aucun en échec. Le script tourne sans `VITE_API_URL`, donc sans interrupteur de mode : les captures montrent l'interface comme la démonstration durable (GitHub Pages). Depuis #137, `preuves.mjs` fixe aussi le mode « procès enregistrés » dans le navigateur : lancé contre le site hébergé, en direct par défaut depuis #141, il ne déclenche aucun procès payant.

- **Les clés AWS ne passent jamais par l'outil d'IA** : les deux commandes ont été lancées par un membre de l'équipe dans son propre terminal.
- **Journaux CloudWatch** : la première exportation cherchait les lignes qui citent l'identifiant du dernier procès et n'en a trouvé aucune ; le fichier vide a été retiré et le script se rabat désormais sur les dernières lignes du flux le plus récent.

## Limites et suite
- Les journaux CloudWatch ne sont pas dans les preuves exportées (voir ci-dessus) : à capturer dans la console si la vidéo en a besoin.
- La vidéo (#18) reste à tourner.
