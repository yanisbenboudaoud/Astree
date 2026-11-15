# #172 — Le bulletin du Greffier : chaque contrôle affiche son taux de réussite mesuré

- **Issue** : #172 · **PR** : #181 · **Statut** : terminée (la mesure de l'orchestrateur, #167, entrera au bulletin à la prochaine lecture S3)
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
« Notre Greffier ne vous demande pas de le croire : il affiche son taux de réussite, mesuré, à côté de chacun de ses contrôles. » Les mesures de #165 à #168 étaient dans `docs/validation/` ; elles sont maintenant dans l'interface, à l'endroit où l'utilisateur doit faire confiance au contrôle.

- **`validation/bulletin.py`** (nouveau) : écrit `frontend/src/data/bulletin.json`.
  - `mesure_taux(k, n)` : k, n, `taux` (k/n), `rates` (n − k) et `ic95` (Wilson), arrondis par Python pour que l'interface n'ait rien à calculer.
  - `mesure_chiffres`, `mesure_cadre`, `mesure_externe`, `mesure_orchestrateur` : l'entrée de chaque évaluation, avec le chemin de son rapport.
  - `ranger_mesure` : range l'entrée sans toucher aux autres ; la `date` de la mesure ne change que si les chiffres changent, donc relancer une commande sans rien modifier laisse le fichier identique.
- **Branchements** : `python -m validation.evaluation chiffres|cadre` (#165, #166), `python -m validation.externe` (#168) et `python -m validation.evaluation orchestrateur` (#167, seulement sur la lecture S3 : une lecture `--local` de quelques procès n'écrase pas la mesure faite sur tous les procès tenus).
- **`frontend/src/data/bulletin.json`** (généré) : `verifier_chiffres`, `cadre_simulation`, `validation_externe`, et l'adresse du dépôt pour les liens.
- **`frontend/src/domaine/bulletin.ts`** (nouveau) : lit le bulletin par `import.meta.glob` (sans fichier : objet vide, le build passe) et le met en phrase.
  - `epreuveDuControle(regle)` : « Mis à l'épreuve : 47 conseils et promesses bloqués sur 78 (60 %) ; 31 sont passés sans être vus. 71 arguments légitimes admis sur 71. Mesure du 15 nov. 2026. »
  - `epreuveDesDonnees()` : « Les prix de départ ont été confrontés aux rendements publiés par les émetteurs de 7 FNB : 27 années sur 27 à moins de 0,25 point d'écart, dont 2022 : 7 sur 7. »
  - Un taux sous 100 % est dit tel quel, avec le nombre de cas passés (ou refusés à tort, ou hors seuil).
- **`frontend/src/domaine/bilan.ts`** : `ControleExplique.epreuve`, rempli pour `verifier_chiffres` et `cadre_simulation`.
- **`frontend/src/ecrans/Tribunal.tsx`** : la ligne et le lien « Voir la mesure » sous ces deux contrôles (« Contrôles du Greffier sur les arguments »).
- **`frontend/src/components/TiroirPiece.tsx`** : section « Données vérifiées » dans le tiroir d'une pièce de `simuler_portefeuille`.
- **Tests** : `tests/test_bulletin.py` (taux, date conservée, autres mesures gardées, orchestrateur, **bulletin du dépôt identique aux mesures recalculées**, **chaque k/n du bulletin présent dans son rapport**) ; `frontend/src/test/bulletin.test.tsx` (taux sous 100 %, refus à tort, bulletin absent, validation externe, phrase reprenant exactement les chiffres du fichier, bilan, tiroir).

## Comment l'utiliser
Relancer une évaluation met le bulletin à jour :
```bash
python -m validation.evaluation chiffres
python -m validation.evaluation cadre
python -m validation.externe
python -m validation.evaluation orchestrateur   # lecture S3 (aws login)
```

## Comment vérifier
```bash
pytest tests/test_bulletin.py
cd frontend && npm test -- bulletin
```
Captures en mode démonstration (Robert, 30 % en TSLA) : [contrôles du Greffier](captures/172/controles-greffier.png), [tiroir de la pièce de simulation](captures/172/tiroir-simulation.png).

Vérifié aussi sans `bulletin.json` : le build passe, aucun test n'échoue (3 sautés), rien ne s'affiche.

## Choix faits en cours de route
- **Python met en forme les nombres, l'interface les met en phrase** : k/n, n − k et l'intervalle sont dans le fichier ; le navigateur ne fait aucune division.
- **« Le chiffre affiché est exactement celui du rapport »** est garanti par deux tests : côté Python, le bulletin est recalculé à partir des mêmes résultats que le rapport, et chaque « k/n » du bulletin est cherché dans le texte du rapport ; côté interface, la phrase reprend les k et n du fichier.
- **Ligne sous le contrôle, pas dans le titre** : le titre dit ce que le Greffier a vérifié dans *ce* procès ; la ligne dit à quel point on peut s'y fier en général.
- **Liens vers GitHub** (`depot` du bulletin) : les rapports sont des fichiers Markdown du dépôt.

## Limites et suite
- **Orchestrateur (#167)** : le branchement existe, mais aucun identifiant AWS n'était disponible pour relire les procès dans S3 ; l'entrée apparaîtra au bulletin à la prochaine lecture (`aws login`, puis la commande). Elle n'est pas affichée dans l'interface : l'issue ne la demande pas, elle pourrait aller dans la trace de l'orchestrateur.
- **Dépôt privé** : les liens « Voir la mesure » ne s'ouvrent que pour qui a accès au dépôt GitHub (l'équipe, et le jury quand le dépôt lui est ouvert).
- La ligne des contrôles est dans le volet repliable « Contrôles du Greffier sur les arguments » : il faut l'ouvrir pour la voir.
- #171 reprend les mêmes chiffres dans le README.
