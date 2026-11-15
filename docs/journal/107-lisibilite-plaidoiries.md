# #107 — Lisibilité : typographie, écrans du Tribunal et plaidoiries en clair

- **Issue** : #107 · **PR** : #108 · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Deux volets : l'interface en dit moins à la fois, et les plaidoiries parlent en dollars.

**Interface** (`frontend/`)
- **Typographie** (`index.html`, `styles/tokens.css`, `styles/base.css`) : remplace Inter et JetBrains Mono de la fiche 105. Police du système sur Apple (`-apple-system`, SF Pro), **Geist** ailleurs, `ui-monospace` / Geist Mono pour la trace. Le trait d'union et le signe moins (−) d'Inter, très larges, se lisaient comme des tirets longs. Échelle agrandie sur celle d'iOS : corps 17 px, petit 15, étiquette 13, h1 40. Les tailles écrites en dur des `*.module.css` montent d'un cran, sauf dans les graphiques SVG.
- **`Message`** (`components/Elements.tsx`) : carte blanche avec liseré de couleur, pastille d'icône, étiquette « Hors Pacte » ou « À vérifier » avec le § du Pacte (tiré du titre par `separerParagraphe`), pied grisé pour le bouton de correction et l'aide. `messagesDecision` (`domaine/decision.ts`) met « Vous pouvez soumettre quand même… » dans `aide`, plus dans le corps.
- **Pacte vécu** (`ecrans/Calibrage.tsx`) : deux colonnes en paysage, comme l'écran Décision. À gauche, le titre, le fil des jours (`Etapes` : date, baisse et réponse des jours passés) et la règle en une phrase ; à droite, la question. En une colonne, la question suit le titre. `GraphiqueValeur` accepte `hauteurTrace` (300 px ici, 200 par défaut). Textes raccourcis.
- **Attente du Tribunal** (`components/ChargementTribunal.tsx`) : chaque étape est une phrase claire (« Simuler votre portefeuille avec 10 % en XOM », « Rejouer l'année 2022… ») avec sa pièce en pastille et la raison de l'orchestrateur en gris. Les appels bruts sont dans un bloc repliable « Trace technique ». La phrase vient du nouveau champ `EtapeTrace.titre`, écrit par `titreEtape` (`api/adaptateur.ts`) à partir de l'outil et de ses paramètres, sans LLM ; `appel` garde l'appel technique. Le contrat ne change pas.
- **Débat en salle d'audience** (`ecrans/Tribunal.tsx`, `Debat`) : au lieu de deux listes séparées, les arguments sont rangés par question (« Combien pourriez-vous perdre au pire moment ? »…) et le débat montre **un point à la fois**, sans défilement (chaque point des procès de démo tient à 1440×900 sous le bilan). Un sommaire en onglets (`role="tablist"`, ← → Début Fin) donne le nom court de chaque point (`LIBELLES_COURTS`) et deux pastilles qui disent quel camp a parlé ; la scène met le Procureur (`Tribune`) et l'Avocat face à face de part et d'autre d'une balance (nouvelle icône `balance` de `components/Icone.tsx`), avec des flèches précédent / suivant. Un camp muet « garde le silence sur ce point ». Une pièce ouverte amène sur le point qui la cite. Sur téléphone, les tribunes passent l'une sous l'autre. `domaine/debat.ts` range chaque argument : `themeArgument` lit sa première phrase (`accroche`, sa conclusion d'après les consignes) avec des règles fixes ; `regrouperDebat` ordonne les points comme le Procureur et garde le rang de chaque argument dans son camp. Le texte des agents et le contrat ne changent pas.
- **Arguments** (`Plaidoyer`) : la conclusion en gras et les pièces ; « Voir la preuve » déplie la suite. `sansCoupure` lie « 188 291 $ » et « −29,0 % » par des espaces insécables. Le bilan du Greffier n'affiche plus les compteurs à zéro, et le rappel « Règle que vous avez signée… » passe dans la liste des contrôles.

**Pipeline**
- **`pipeline/simulation.py`** : `piece_simulation(…, capital=None)`. Avec le capital fictif du profil (passé par `pipeline/orchestrateur.py`), la pièce ajoute :
  - `comparaisons_periode_complete` : `capital`, `perte_au_pire_moment_cad` (avec la décision) et `_actuelle`, `ecart_perte_au_pire_moment_cad`, `ecart_pire_baisse_points`, `ecart_rendement_annuel_points`, `rapport_volatilite` ;
  - `comparaisons_2022` : `resultat_2022_cad_apres` et `_actuel` (signés), `ecart_2022_cad`, `ecart_2022_points`.
  - Montants arrondis au dollar ; pertes et écarts positifs, le texte dit le sens.
- **`pipeline/debat.py`** : la règle 4 des consignes autorise ces comparaisons déjà calculées (CLAUDE.md, section 4 ter, règle 6 : un nombre dérivé passe s'il existe tel quel dans une pièce). Nouvelles « Règles d'écriture » : première phrase = conclusion en 25 mots au plus, deux phrases au plus, dollars d'abord, trois chiffres au plus, mots courants, aucun nom technique ni identifiant de pièce dans le texte.
- **Procès de démonstration refaits** sur la Lambda redéployée et copiés tels quels depuis S3 dans `frontend/src/data/proces/` (7 contrats, `index.json`), avec leurs procès-verbaux (`frontend/public/proces-verbaux/`, `python -m pipeline.proces_verbal --demo`). Ils remplacent ceux des fiches 061 et 068. Tous : 100 % des chiffres vérifiés, aucun argument rejeté ; `2026-11-15-c1600201b123` (Robert, 25 % en TSLA) garde deux corrections du Greffier.

## Comment l'utiliser
Rien à changer dans l'interface. Pour refaire un procès de démonstration : `deploiement/deployer.py --sans-donnees`, puis `deploiement/tester_function_url.py <profil> "<demande>" [--calibrage-demo]`, et copier `traces/<date>/<id>.json` du bucket.

## Comment vérifier
- `python -m pytest` : 766 tests. `tests/test_simulation.py` vérifie les comparaisons, l'arrondi au dollar, et qu'une phrase en dollars qui les cite **passe** `verifier_argument` alors qu'un montant faux est rejeté.
- Depuis `frontend/` : `npx tsc --noEmit` passe ; `npm test` donne 108 tests sur 110. Les 2 échecs de `domaine.test.ts` (« Tribunal occupé ») existaient avant. `src/test/accroche.test.ts` couvre `accroche` et `sansCoupure` ; `src/test/debat.test.ts` vérifie le sujet de phrases types et que chaque argument des 7 procès de démo trouve un sujet, sans en perdre aucun ; `progression.test.tsx` vérifie les phrases claires et la trace technique.
- `python -m contrat.valider frontend/src/data/proces/<id>.json` passe pour les 7 procès.

## Choix faits en cours de route
- **Python calcule, le LLM cite** : plutôt que d'assouplir `verifier_chiffres`, les comparaisons parlantes sont ajoutées aux pièces. La promesse « aucun chiffre inventé ne passe » reste entière.
- **Dollars à l'unité** : un premier passage a donné « 23 407,08 $ ». Les montants des pièces sont arrondis, ce qui empêche le modèle d'écrire des centimes.
- **Phrases claires écrites par l'interface**, pas par le pipeline : le contrat et la trace stockée dans S3 ne changent pas, et la trace technique reste visible pour le jury.
- **Geist plutôt qu'Inter** hors Apple : trait d'union et signe moins plus étroits, même sobriété.

## Limites et suite
- La première phrase est trouvée par une règle simple (ponctuation suivie d'une majuscule) : une abréviation suivie d'une majuscule couperait trop tôt.
- Le sujet d'un argument est lu par mots-clés : une phrase d'un procès en direct qui sort de ces formulations va dans « Autres points », en fin de débat, sans être perdue.
- La Lambda a été déployée depuis la branche : la redéployer depuis `main` après la fusion.
- Les 7 procès du premier passage (avec centimes) restent archivés dans S3 sans être utilisés.
