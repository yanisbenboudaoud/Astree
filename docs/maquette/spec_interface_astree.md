# Prompt pour Claude Code — Implémenter l'interface Astrée (V2 · Prototype simplifié)

> **Comment l'utiliser :** dépose ce fichier dans le dépôt (par exemple `docs/ui-spec.md`), puis dis à Claude Code :
> « Lis `docs/ui-spec.md` en entier et implémente l'interface en suivant la section *Mission*. »

---

## Mission

Tu implémentes l'interface web d'**Astrée**, notre prototype pour le Datathon PolyFinances 2026 (cas AlphaForge AI). Astrée soumet une décision d'investissement à un **Tribunal** d'agents : un **Procureur** plaide contre, un **Avocat** plaide pour, un **Greffier** vérifie chaque chiffre et le **Pacte** de l'investisseur. L'investisseur rend ensuite son **verdict**. Tout est en simulation : aucune transaction réelle, aucun conseil personnalisé.

**Nom du produit : Astrée.** Écris-le toujours avec l’accent aigu dans l’interface (logo, `<title>`, textes). Pour les identifiants techniques (nom de paquet, dossiers, URL, clés de stockage), utilise `astree` sans accent. « AlphaForge AI » est seulement l’entreprise fictive de l’énoncé : ce nom n’apparaît pas dans l’interface. Le logo est une balance (Astrée est la déesse de la justice), ce qui va avec le thème du Tribunal. Titre des onglets : « Astrée · {nom de l’écran} ».

La maquette de référence est dans Figma (page « V2 · Prototype simplifié »). Ce document contient tout ce qu'il faut pour la reproduire fidèlement, même sans accès à Figma.

### Étapes de travail

1. **Explore d'abord le dépôt.** Repère la stack existante (frontend, backend, agents, AWS), les scripts de données et le format de sortie des agents. Résume ce que tu as trouvé en 10 lignes maximum avant d'écrire du code.
2. **Choisis l'emplacement du frontend.**
   - S'il existe déjà un frontend, intègre-toi dedans en respectant ses conventions.
   - Sinon, crée `frontend/` en **React + TypeScript + Vite**, avec les jetons de design en variables CSS (CSS Modules, ou Tailwind configuré sur ces variables). Pas de bibliothèque de composants UI : les composants sont simples et doivent coller à la maquette.
   - Ne modifie pas le backend ni les agents sans me le demander.
3. **Propose un plan court** : arborescence, routes, composants, source des données. Puis implémente par étapes :
   1. jetons et composants de base ;
   2. écran d'entrée et Portefeuille ;
   3. recherche et Décision ;
   4. Tribunal et tiroir de pièce ;
   5. Verdict et confirmation ;
   6. accessibilité et tests.
4. **Données.** Commence avec les données de démonstration de l'annexe C (fichiers JSON dans `frontend/src/data/`). Prévois une couche `api/` dont les types correspondent à l'annexe D, pour brancher plus tard les vraies sorties des agents sans toucher aux composants. Si le backend expose déjà un endpoint de Tribunal, branche-le derrière un drapeau `VITE_USE_MOCKS=true|false`.
5. **Courbes.** Ne dessine pas de courbes inventées. Génère les séries avec un script Python reproductible (`scripts/build_ui_series.py`) à partir de `prices_daily.csv` et `fx_usdcad_daily.csv`, selon la méthode de l'annexe B. Le script produit du JSON consommé par le frontend.
6. **Vérifie ton travail.**
   - Lance l'application et parcours les 3 parcours de bout en bout.
   - Compare chaque écran à la maquette (Figma MCP ou les captures que je te fournirai).
   - Exécute les tests de l'annexe E. Corrige avant de dire que c'est terminé.

### Si tu as accès au serveur MCP Figma

- **Fichier :** `31U3H5m2gPdbqzfg4qgulC`, page « V2 · Prototype simplifié ».
- **Appels :** utilise `get_design_context` ou `get_screenshot` **une fois par écran**. Le compte est limité en nombre d'appels, alors pas de lectures répétées.
- **Identifiants des écrans** (format `node-id`) :

| Écran | Amira | Mateo | Robert |
|---|---|---|---|
| 1 Portefeuille | 32:1152 | 32:1699 | 32:2177 |
| 1b Recherche ouverte | 32:1412 | 32:1925 | 32:2403 |
| 2 Décision | 35:1426 | 35:1704 | 35:1902 |
| 3 Tribunal | 36:1631 | 36:2073 | 36:2520 |
| 3b Tiroir de pièce | 36:1855 | 36:2304 | 36:2765 |
| 4 Verdict | 37:2364 | 37:2779 | 37:3151 |
| 5 Verdict archivé | 37:2503 | 37:2908 | 37:3298 |

- **Autres nœuds :**
  - Entrée (choisir un profil) : `30:1181`.
  - En-tête V2 : `30:1180`.
  - Composants de la page 1 : Provenance `1:59`, Statut `1:79`, Bouton `1:112`, Pièce `1:115`, Étape `1:138`.

### Règles non négociables

- **Bandeau de simulation** visible sur tous les écrans : « Simulation · aucune transaction réelle · aucun conseil personnalisé ». Aucun bouton n'exécute de transaction ; « Signer le verdict » ne fait qu'archiver.
- **Pas de recommandation de l'outil.** Astrée expose les deux côtés ; c'est l'utilisateur qui tranche. N'écris jamais « recommandé ».
- **Provenance.** Chaque chiffre affiché vient des données ou d'un calcul déterministe. Les agents citent des pièces, ils ne calculent pas.
- **Formats français canadiens.**
  - Nombres : `Intl.NumberFormat('fr-CA')`, soit `650 000 $`, `−7,8 %`, `+12,0 %`.
  - Espace insécable fine avant `%` et `$`, vrai signe moins `−` (U+2212), guillemets « … ».
  - Dates : `12 nov. 2026`.
- **Accessibilité WCAG 2.2 AA.** Contrastes ≥ 4,5:1 (la palette fournie les respecte), focus visible partout, navigation complète au clavier. La couleur n'est jamais le seul signal (toujours une icône ou un mot en plus). Respecte `prefers-reduced-motion`.
- **Pas d'ombres décoratives, pas de dégradés, pas d'émojis.** La hiérarchie passe par la typographie, les filets et l'espace. Seules exceptions (#103) : l'ombre de survol des éléments cliquables et celle de la liste flottante de recherche (annexe A.3), qui signalent un état ; les hachures de la zone hors limite (D.4) sont un motif, pas un dégradé.

---

## Annexe A — Système de design

### A.1 Couleurs (variables CSS)

Style épuré (refonte #105, inspirée des applications de placement grand public) : fond blanc, encre presque noire, surfaces gris très clair, une seule famille sans empattement. Contrastes mesurés sur `#FFFFFF`. Source : `frontend/src/styles/tokens.css`.

```css
:root{
  --fond-papier:#FFFFFF;   /* fond de page */
  --fond-carte:#FFFFFF;    /* cartes, champs, éléments interactifs */
  --fond-creux:#F4F4F2;    /* zones en retrait, monogrammes, pistes de jauge, bandeau de simulation */
  --fond-sourdine:#F7F7F5; /* grands panneaux posés sur la page : recherche, carte du Pacte, « Construire mon Pacte » */
  --encre-900:#111111;     /* texte principal (18,9:1) */
  --encre-700:#3A3A3A;     /* texte secondaire (11,3:1) */
  --encre-500:#626262;     /* texte tertiaire (6,1:1) */
  --encre-300:#B5B5B5;     /* décoratif uniquement (jamais pour du texte) */
  --encre-200:#DCDCDC;     /* décoratif uniquement */
  --trait-fin:#E8E8E5;     /* filets et bords de cartes, décoratifs */
  --trait-moyen:#8A8A8A;   /* bords qui montrent un état ou un contrôle : pastilles, champs, boutons (3,4:1, #103) */
  --accent-bleu:#2747C9;   /* liens, sélection, focus (7,3:1) */
  --accent-bleu-teinte:#EEF1FD;
  --statut-violation:#C2261D; --statut-violation-teinte:#FDEEED;   /* 5,6:1 */
  --statut-verifier:#9A5B00;  --statut-verifier-teinte:#FDF3E1;    /* 5,2:1 */
  --statut-conforme:#0B7A4B;  --statut-conforme-teinte:#E7F6EE;    /* 5,4:1 */
  --camp-procureur:#A3245C;   --camp-procureur-teinte:#FCEDF3;     /* 6,9:1 */
  --camp-avocat:#0B6E79;      --camp-avocat-teinte:#E5F4F5;        /* 5,7:1 */
  --inverse-texte:#FFFFFF;
  /* Données (#105) */
  --donnee-principale:#4C5FD5; /* courbe de valeur, courbe « avec la décision », remplissage de jauge (5,4:1) */
  --donnee-secondaire:#8A8A8A; /* courbe « Actuel » (3,4:1) */
  --categorie-1:#4C5FD5; --categorie-2:#17A2B8; --categorie-3:#F2A93B;
  --categorie-4:#A35BD6; --categorie-5:#5CB85C; --categorie-6:#EF7B6C; /* barre de répartition, toujours avec sa légende chiffrée */
}
```

**Règle d'usage : une couleur = un sens.**
- Rouge, ambre et vert sont réservés aux statuts du Greffier.
- Framboise et sarcelle sont réservés aux deux camps (Procureur, Avocat).
- Le bleu est réservé à la sélection, au focus et aux liens.
- L'indigo `--donnee-principale` porte les données (courbes, jauges) ; le gris `--donnee-secondaire` l'état actuel ; la limite du Pacte et la pire baisse sont tracées en rouge (#105). Les couleurs de catégorie servent seulement à la barre de répartition, dont la légende donne le libellé et le pourcentage.
- Les gains et pertes s'écrivent en encre, avec un signe et ▲/▼ (pas en vert ou rouge).
- Un trait qui porte une information (bord de contrôle, pastille d'étape à venir, courbe « Actuel ») atteint au moins 3:1 sur le papier et sur les cartes (WCAG 1.4.11) : `--trait-moyen` ou plus foncé, jamais `--trait-fin`, `--encre-200` ni `--encre-300` (#103).

### A.2 Typographie (Google Fonts)

Polices (#105) :
- **Inter** : titres, interface, texte courant et chiffres. Les chiffres sont en chasse fixe (`font-variant-numeric: tabular-nums` sur `body`) pour rester alignés dans les tableaux.
- **JetBrains Mono** : traces seulement (`--police-code`).

`--police-titre`, `--police-texte` et `--police-mono` pointent toutes vers Inter ; les classes `.t-*` de `base.css` gardent leurs noms.

| Style | Police | Graisse | Taille / interligne | Approche |
|---|---|---|---|---|
| Titre/Affiche | Inter | 600 | 52 / 58 | −3,5 % |
| Titre/H1 | Inter | 600 | 38 / 44 | −3 % |
| Titre/H2 | Inter | 600 | 24 / 30 | −2 % |
| Titre/Panneau | Inter | 600 | 19 / 26 | −1,5 % |
| Titre/Citation | Inter | 400 italique, `--encre-700` | 17 / 26 | 0 |
| Texte/Intertitre | Inter | 600 | 16 / 22 | −0,5 % |
| Texte/Corps | Inter | 400 | 15 / 22 | 0 |
| Texte/Corps fort | Inter | 600 | 15 / 22 | 0 |
| Texte/Petit | Inter | 400 | 13 / 18 | 0 |
| Texte/Petit fort | Inter | 600 | 13 / 18 | 0 |
| Texte/Étiquette | Inter | 600 | 12 / 16 | +1 % |
| Chiffre/Moyen | Inter | 600 | 28 / 32 | −3 % |
| Chiffre/Tableau | Inter (chasse fixe) | 400 | 14 / 20 | 0 |
| Chiffre/Tableau fort | Inter (chasse fixe) | 600 | 14 / 20 | 0 |
| Code/Trace | JetBrains Mono | 400 | 12 / 16 | 0 |

### A.3 Espacement, grille, formes

- **Espacements :** multiples de 4 (4, 8, 12, 16, 20, 24, 32, 40, 44, 48, 56).
- **Gabarit desktop (paysage, #103) :** 1440 px de large, conteneur large de **1344 px** centré (`--conteneur-large`), marges de **48 px** dès 1024 px (`--marge-page` ; 24 px en dessous, 16 px sous 600 px). Il sert à l'Entrée, au Portefeuille, à la Décision, au chargement du Tribunal, au Tribunal et au Verdict.
- **Colonne étroite :** **776 px** centrée pour les formulaires et les messages : Pacte vécu, Construire mon Pacte, messages d'erreur du Tribunal.
- **Portefeuille :** bandeau de recherche sur toute la largeur ; dessous, colonne principale fluide (928 px à 1440) + gouttière de 40 + colonne latérale de 376.
- **Décision :** deux colonnes 5 : 7 (réglage | effet sur le Pacte), gouttière de 48.
- **Chargement du Tribunal et Verdict :** deux colonnes 7 : 5, gouttière de 48 ; la colonne de droite reste fixe au défilement.
- **Tribunal :** deux colonnes égales (Procureur | Avocat) séparées de 32 px.
- En dessous de 1024 px, toutes ces grilles s'empilent sur une colonne.
- **Rayons (#105) :** `--rayon` 16 px (cartes et panneaux), `--rayon-moyen` 12 px (menus, liste de recherche, messages, monogrammes), `--rayon-petit` 8 px (pièces, petits éléments), `--rayon-pilule` pour les boutons, le champ de recherche, les étiquettes de statut et de provenance, le sélecteur titre / panier et le menu de profil. Pas d'ombre au repos : les cartes et boutons cliquables prennent `--ombre-survol` (`0 4px 20px` encre à 8 %) au survol ; menus et liste de recherche ont `--ombre-flottante`.
- **Retours visuels (#103) :** au survol, un élément cliquable se détache (bord plus foncé, ombre de survol ou fond `--fond-creux`) ; à l'appui, il s'enfonce de 1 px (`translateY(1px)`). Durée commune : `--transition` (140 ms, `ease-out`). Les transitions portent seulement sur `transform`, `box-shadow` et `border-color`, jamais sur `color` ni sur le `background-color` d'un élément qui contient du texte : axe-core mesure le contraste pendant le fondu et échoue sur l'état intermédiaire. Avec `prefers-reduced-motion`, transitions et animations deviennent instantanées (`base.css`).
- **Sections (#105) :** chaque section commence par un filet fin `1px solid var(--trait-fin)` en haut, avec 24 px d'espace au-dessus du titre (Titre/Panneau) : l'espace sépare plus que le trait.
- **Cartes :** réservées aux éléments interactifs ou sélectionnables : fond `--fond-carte`, bordure `1px --trait-fin`, rayon 16. Les grands panneaux d'information (recherche, Pacte) prennent `--fond-sourdine`.
- **Responsive :** au minimum un desktop entre 1280 et 1440 px. En dessous de 1024 px, empile les colonnes (sans régression du parcours).

### A.4 Composants

| Composant | Spécification |
|---|---|
| **Bandeau de simulation** | Hauteur 28, fond `--fond-creux`, texte Petit `--encre-700` centré, icône fiole 13 px. |
| **En-tête** | Barre de 72 px, fond blanc, filet bas `--trait-fin`, padding horizontal `--marge-page` (48 px dès 1024 px, #103). Gauche : logo (carré encre de 26 px avec une balance dessinée en traits papier) et « Astrée » en Titre/Panneau. Centre : étapes de la procédure **uniquement pendant une décision**. Droite : « Aide » (icône ?) et **menu de profil** (pastille ronde à bordure `--trait-moyen` : avatar encre de 28 px avec l'initiale, prénom, chevron). Le menu propose « Changer de profil », qui ramène à l'Entrée. **Pas de sélecteur de profil permanent.** |
| **Étapes de la procédure** | Décision → Tribunal → Verdict. Pastille de 26 px : *faite* = contour et ✓ `--statut-conforme` sur sa teinte ; *courante* = fond encre + numéro papier ; *à venir* = contour `--trait-moyen` + numéro `--encre-500`. Les étapes sont reliées par des traits de 24 px. Attribut `aria-current="step"` sur l'étape courante. |
| **Provenance** | Trois variantes, toujours avec le mot. **Fait** : fond `--fond-creux`, bordure pleine, glyphe ● plein. **Hypothèse** : bordure tirets `3/2`, glyphe ◐ demi-plein. **Fictif** : bordure pointillés, glyphe ○ vide. Texte en Étiquette, padding 2/8, en pilule. |
| **Statut** | Violation (icône 🚫 dessinée, rouge), À vérifier (triangle ⚠ dessiné, ocre), Conforme (✓, vert). Fond de la teinte correspondante, texte en Étiquette de la couleur pleine, en pilule. |
| **Bouton** | En pilule, hauteur 48 (grande) ou 36 (compacte). *Primaire* : fond encre, texte blanc, flèche →. *Secondaire* : fond carte, bordure 1 px `--trait-moyen` (encre au survol). *Tertiaire* : lien bleu souligné. **Un seul primaire par écran.** Le focus est un anneau bleu de 2 px décalé de 2 px. Survol (#103) : le primaire s'éclaircit légèrement avec l'ombre de survol et sa flèche avance de 3 px ; le tertiaire prend un fond `--accent-bleu-teinte` et se souligne. Appui : enfoncement de 1 px. Désactivé : ni ombre, ni mouvement. |
| **Pièce** | Pastille « 📄 P4 » : icône document de 12 px + code en Mono 12, bordure `--trait-moyen`, fond carte. C'est un bouton qui ouvre le tiroir de la pièce. Au survol : bord encre et fond `--fond-creux`. |
| **Monogramme** | Carré de 36 px, rayon 12, fond `--fond-creux`, ticker court en 12 gras (sans `.TO` ni `-USD`). **Pas de logos d'entreprises.** |
| **Jauge** | Piste de 6 px arrondie `--fond-creux`, remplissage `--donnee-principale`, repère de limite de 2×12 px en encre. |
| **Message** | Bordure 1 px de la couleur pleine, rayon 12, fond teinte, icône de 22 px, titre en Intertitre de la couleur pleine, corps encre, bouton de correction en secondaire compact. Variantes : Violation et À vérifier. |
| **Champ** | Hauteur 44 à 48 (56 et en pilule pour la recherche du Portefeuille, D.3), fond carte, bordure `--trait-moyen`. Au focus : bordure 2 px `--accent-bleu` et halo `--accent-bleu-teinte`. Libellé visible au-dessus quand il y a la place ; sinon `aria-label` et texte indicatif avec exemple. |

---

## Annexe B — Méthode de calcul (à reproduire exactement)

Ces règles reproduisent nos chiffres au dixième près. Les valeurs attendues sont dans l'annexe C : sers-t'en comme tests.

1. **Prix :** `adj_close` de `prices_daily.csv`.
2. **Calendrier :** jours de bourse américains (les dates de `SPY`). Reporte le dernier prix connu de chaque actif sur ce calendrier (forward-fill) : les mouvements crypto du week-end tombent le lundi et les jours fériés de la TSX sont reportés.
3. **Devise :** convertis les actifs cotés en USD (tout ce qui ne finit pas par `.TO`) en CAD avec `usdcad` de `fx_usdcad_daily.csv` (forward-fill, puis back-fill pour la première date).
4. **Portefeuille :** poids constants, rééquilibrage quotidien. `r_p(t) = Σ w_i · r_i(t)`, puis `V(t) = Π (1 + r_p)`.
5. **Indicateurs :**
   - rendement annualisé = `V_fin^(1/années) − 1`, avec `années = jours calendaires / 365,25` ;
   - volatilité = `écart-type(r_p) × √252` ;
   - recul depuis le sommet = `V / max_cumulé(V) − 1` ;
   - chute maximale = minimum du recul ;
   - « rejeu de 2022 » = `V(dernier jour 2022) / V(dernier jour 2021) − 1`.
6. **Financement d'une position (proportionnel) :** pour ajouter un actif à `s %`, multiplie chaque poids existant par `(1 − s/100)`, puis ajoute `s` à l'actif.
7. **Courbe de valeur :** `V` mise à l'échelle pour que la dernière valeur égale la valeur fictive du portefeuille. Pour l'affichage, échantillonne à la semaine (dernier jour de chaque semaine), en conservant le jour exact du point le plus bas.
8. **Tailles de décision :** précalcule tous les pas de 1 % entre 0 et 50 %. Le curseur ne fait que lire cette table ; rien n'est estimé à la volée.
9. **« Séances sous la limite » :** nombre de jours de bourse où le recul de la version « avec la décision » est inférieur à la limite du Pacte.

---

## Annexe C — Profils et données de démonstration

> Les portefeuilles d'Amira et de Mateo sont **fictifs** (composés pour la démo). Si le backend produit d'autres chiffres pour eux, ce sont ceux du backend qui priment ; garde la même structure.

### C.1 Écran d'entrée

- **Étiquette :** « Démonstration ».
- **Titre (H1) :** « Testez une décision d'investissement avant de la prendre. » (#103 : le titre dit ce que fait Astrée, au lieu de « Avec quel profil voulez-vous explorer Astrée ? »)
- **Sous-titre :** « Cherchez un titre et choisissez une taille : un Procureur et un Avocat en débattent face aux règles de votre Pacte, et c'est vous qui rendez le verdict. Choisissez un profil pour commencer ; vous pourrez en changer à tout moment depuis le menu en haut à droite. »
- **Trois cartes cliquables** (carte entière + bouton secondaire « Entrer comme … »), dans cet ordre. Au survol, la carte se soulève de 2 px (bord encre, ombre de survol) ; à l'appui, elle redescend.

| Profil | Âge · métier | Risque | Horizon | Décision à tester | Question en italique |
|---|---|---|---|---|---|
| Amira | 26 ans · ingénieure logicielle | Élevé | 15 ans et plus | Composer un panier crypto et tech | Jusqu'où le système accepte-t-il le risque ? |
| Mateo | 41 ans · gestionnaire des opérations | Modéré | 8 à 12 ans | Ajouter 10 % d'Exxon Mobil (XOM) | Le système tient-il compte de ses valeurs ? |
| Robert | 59 ans · professionnel de la santé | Faible à modéré | 3 à 5 ans | Ajouter 30 % de Tesla (TSLA) | Le système ose-t-il contredire une envie ? |

- **Pied de page :** étiquette Fictif + « Profils fictifs tirés de l'énoncé PolyFinances 2026. Portefeuilles simulés sur des prix réels du 12 nov. 2021 au 12 nov. 2026. »

### C.2 Robert

```json
{
  "id": "robert", "nom": "Robert", "initiale": "R",
  "valeur": 650000, "gainDepuisDebut": 233034, "gainPct": 55.9,
  "statut": "Votre portefeuille respecte votre Pacte.",
  "indicateurs": [
    {"libelle":"Rendement annualisé","valeur":"+9,3 %","legende":"par an sur 5 ans"},
    {"libelle":"Chute maximale","valeur":"−7,8 %","legende":"65 % de votre limite de −12 %","jauge":0.65},
    {"libelle":"Volatilité","valeur":"5,6 %","legende":"annualisée"}
  ],
  "pointBas": {"date":"2022-10-12","valeur":394058,"recul":-7.8,"libelle":"−7,8 % · oct. 2022"},
  "positions": [
    {"groupe":"Revenu fixe","ticker":"ZST.TO","nom":"BMO obligations ultra court terme","poids":30,"valeur":195000},
    {"groupe":"Revenu fixe","ticker":"XBB.TO","nom":"iShares obligations canadiennes","poids":20,"valeur":130000},
    {"groupe":"Actions canadiennes","ticker":"XIU.TO","nom":"iShares S&P/TSX 60","poids":20,"valeur":130000},
    {"groupe":"Actions canadiennes","ticker":"RY.TO","nom":"Banque Royale","poids":10,"valeur":65000},
    {"groupe":"Actions canadiennes","ticker":"FTS.TO","nom":"Fortis","poids":10,"valeur":65000},
    {"groupe":"Actions américaines","ticker":"JNJ","nom":"Johnson & Johnson","poids":10,"valeur":65000}
  ],
  "pacte": {"signeLe":"2026-11-14","regleCle":{"texte":"Chute maximale tolérée : −12 %","detail":"−7,8 % au pire","jauge":0.65},
    "regles":["§1 Chute maximale tolérée : −12 %","§2 Préserver le capital (horizon 3 à 5 ans)","§3 Entreprises établies, modèle d'affaires compris","§4 Cryptoactifs exclus"]},
  "journal": [{"date":"02 nov.","texte":"Hausse de XIU de 5 %","statut":"Conforme"},{"date":"18 oct.","texte":"Achat de RY à 2 %","statut":"Conforme"}],
  "recherche": {"titre":"Tester une décision","aide":"Simulez un achat, puis soumettez-le au Tribunal. Rien n'est acheté.","placeholder":"Nom ou symbole, ex. : Tesla ou TSLA"},
  "decision": {
    "actif":"TSLA","h1":"Quelle part de votre portefeuille en Tesla ?",
    "fiche":"TSLA · action · NASDAQ · USD — volatilité ≈ 59 %, pire chute −73 % en 2022 (USD)",
    "tailleDefaut":30,"maxConforme":9,"raccourcis":[5,9,15,30],
    "zones":["Compatible : 0 à 9 %","Au-delà, la chute observée dépasse −12 %"],
    "attendus": {
      "5":  {"chuteMax":-9.0,"rendement":10.0},
      "9":  {"chuteMax":-11.2,"rendement":10.4,"rejeu2022":-9.1},
      "10": {"chuteMax":-12.1,"rendement":10.5},
      "15": {"chuteMax":-16.4,"rendement":11.0,"rejeu2022":-13.4},
      "30": {"chuteMax":-29.0,"rendement":12.0,"volatilite":19.0,"rejeu2022":-23.7}
    },
    "seancesSousLimite": {"nombre":278,"du":"2022-02-23","au":"2025-05-07"},
    "message": {"type":"Violation","titre":"Cette taille enfreint votre Pacte (§1)","corps":"Au-delà de 9 %, la pire chute observée dépasse votre limite de −12 %. Vous pouvez soumettre quand même : le Tribunal en débattra.","correction":"Ramener à 9 %"}
  }
}
```

### C.3 Amira

```json
{
  "id":"amira","nom":"Amira","initiale":"A","valeur":85000,"gainDepuisDebut":47053,"gainPct":124.0,
  "statut":"Votre portefeuille respecte votre Pacte.",
  "indicateurs":[
    {"libelle":"Rendement annualisé","valeur":"+17,5 %","legende":"par an sur 5 ans"},
    {"libelle":"Part en cryptoactifs","valeur":"15 %","legende":"sur 25 % permis par votre Pacte","jauge":0.6},
    {"libelle":"Chute maximale","valeur":"−38,6 %","legende":"limite de votre Pacte : −45 %"}
  ],
  "pointBas":{"date":"2022-07-01","recul":-38.6,"libelle":"−38,6 % · juil. 2022"},
  "positions":[
    {"groupe":"Tech et IA","ticker":"QQQ","nom":"Invesco QQQ (Nasdaq-100)","poids":20,"valeur":17000},
    {"groupe":"Tech et IA","ticker":"NVDA","nom":"NVIDIA","poids":10,"valeur":8500},
    {"groupe":"Tech et IA","ticker":"SHOP.TO","nom":"Shopify","poids":10,"valeur":8500},
    {"groupe":"Marché large","ticker":"SPY","nom":"SPDR S&P 500","poids":15,"valeur":12750},
    {"groupe":"Hors tech","ticker":"CNR.TO","nom":"Canadien National","poids":10,"valeur":8500},
    {"groupe":"Hors tech","ticker":"ATD.TO","nom":"Alimentation Couche-Tard","poids":10,"valeur":8500},
    {"groupe":"Cryptoactifs","ticker":"BTC-USD","nom":"Bitcoin","poids":10,"valeur":8500},
    {"groupe":"Cryptoactifs","ticker":"ETH-USD","nom":"Ether","poids":5,"valeur":4250},
    {"groupe":"Or","ticker":"GLD","nom":"SPDR Gold Shares","poids":10,"valeur":8500}
  ],
  "pacte":{"signeLe":"2026-11-14","regleCle":{"texte":"Cryptoactifs : 25 % au maximum","detail":"15 % du portefeuille","jauge":0.6},
    "regles":["§1 Chute maximale tolérée : −45 %","§2 Cryptoactifs : 25 % au maximum","§3 Ne pas miser exclusivement sur la tech","§4 Horizon de 15 ans et plus"]},
  "journal":[{"date":"28 oct.","texte":"Achat de SHOP à 10 %","statut":"Conforme"},{"date":"03 oct.","texte":"Hausse de BTC à 10 %","statut":"Conforme"}],
  "recherche":{"mode":"panier","titre":"Composer un panier","aide":"Ajoutez plusieurs titres : le Tribunal juge le panier en entier. Rien n'est acheté.","placeholder":"Nom ou symbole, ex. : Bitcoin, NVDA"},
  "decision":{
    "h1":"Votre panier de 4 titres","fiche":"Remplace votre répartition actuelle · simulé sur 5 ans de prix réels",
    "panier":[{"ticker":"BTC-USD","poids":25},{"ticker":"ETH-USD","poids":25},{"ticker":"NVDA","poids":25},{"ticker":"QQQ","poids":25}],
    "attendus":{"chuteMax":-58.5,"rendement":16.9,"volatilite":38.9,"rejeu2022":-49.3,"partCrypto":50,"partCryptoTech":100,"partCryptoTechActuelle":55},
    "effets":[
      {"libelle":"Cryptoactifs","avant":"15 %","apres":"50 %","limite":"maximum 25 %","statut":"Violation"},
      {"libelle":"Crypto et tech","avant":"55 %","apres":"100 %","limite":"pas exclusivement","statut":"Violation"},
      {"libelle":"Chute maximale","avant":"−38,6 %","apres":"−58,5 %","limite":"limite −45 %","statut":"Violation"},
      {"libelle":"Rendement annualisé","avant":"+17,5 %","apres":"+16,9 %","limite":"par an sur 5 ans"}
    ],
    "seancesSousLimite":{"nombre":149,"du":"2022-05-18","au":"2023-01-20"},
    "correlations":{"BTC/ETH":0.84,"NVDA/QQQ":0.77,"BTC/QQQ":0.40},
    "versionConforme":{"poids":{"BTC-USD":15,"ETH-USD":10,"NVDA":15,"QQQ":20,"CNR.TO":15,"ATD.TO":10,"GLD":15},"chuteMax":-37.1,"rendement":18.1,"partCrypto":25},
    "message":{"type":"Violation","titre":"Ce panier enfreint 3 règles de votre Pacte","corps":"Cryptoactifs à 50 % pour 25 % permis, portefeuille entièrement crypto et tech, pire chute de −58,5 % pour une limite de −45 %. Vous pouvez soumettre quand même : le Tribunal en débattra.","correction":"Proposer une version conforme"}
  }
}
```

### C.4 Mateo

```json
{
  "id":"mateo","nom":"Mateo","initiale":"M","valeur":280000,"gainDepuisDebut":103190,"gainPct":58.4,
  "statut":"Votre portefeuille respecte votre Pacte et vos valeurs.",
  "indicateurs":[
    {"libelle":"Rendement annualisé","valeur":"+9,6 %","legende":"par an sur 5 ans"},
    {"libelle":"Chute maximale","valeur":"−14,1 %","legende":"limite de votre Pacte : −20 %","jauge":0.705},
    {"libelle":"Coût de vos valeurs","valeur":"−0,4 pt","legende":"par an : ESGV comparé à SPY"}
  ],
  "pointBas":{"date":"2022-06-16","recul":-14.1,"libelle":"−14,1 % · juin 2022"},
  "positions":[
    {"groupe":"Actions filtrées ESG","ticker":"ESGV","nom":"Vanguard ESG U.S. Stock","poids":30,"valeur":84000},
    {"groupe":"Actions canadiennes","ticker":"XIU.TO","nom":"iShares S&P/TSX 60","poids":15,"valeur":42000},
    {"groupe":"Actions canadiennes","ticker":"CNR.TO","nom":"Canadien National","poids":10,"valeur":28000},
    {"groupe":"Actions canadiennes","ticker":"FTS.TO","nom":"Fortis","poids":10,"valeur":28000},
    {"groupe":"Actions canadiennes","ticker":"ATD.TO","nom":"Alimentation Couche-Tard","poids":10,"valeur":28000},
    {"groupe":"Revenu fixe","ticker":"XBB.TO","nom":"iShares obligations canadiennes","poids":25,"valeur":70000}
  ],
  "pacte":{"signeLe":"2026-11-14","regleCle":{"texte":"Chute maximale tolérée : −20 %","detail":"−14,1 % au pire","jauge":0.705},
    "regles":["§1 Chute maximale tolérée : −20 %","§2 Éviter les entreprises liées à des controverses ESG importantes","§3 Pas de placements hautement spéculatifs (crypto exclue)","§4 Au moins 20 % en revenu fixe"]},
  "journal":[{"date":"20 oct.","texte":"Hausse d'ESGV à 30 %","statut":"Conforme"},{"date":"06 oct.","texte":"Achat de CNR à 10 %","statut":"Conforme"}],
  "recherche":{"titre":"Tester une décision","aide":"Simulez un achat : Astrée vérifie aussi vos valeurs. Rien n'est acheté.","placeholder":"Nom ou symbole, ex. : Exxon ou XOM","afficherStatutESG":true},
  "decision":{
    "actif":"XOM","h1":"Quelle part de votre portefeuille en Exxon Mobil ?",
    "fiche":"XOM · action · NYSE · USD · Énergie — volatilité ≈ 26 %, +87,4 % en 2022 (USD)",
    "tailleDefaut":10,"maxConforme":20,"raccourcis":[5,10,15,20],
    "zones":["Compatible : 0 à 20 %","Au-delà, le revenu fixe passe sous 20 % (Pacte §4)"],
    "attendus":{"10":{"chuteMax":-10.3,"dateChuteMax":"2025-04-08","rendement":11.8,"volatilite":9.7,"rejeu2022":-0.2,"revenuFixe":22.5}},
    "esg":{"coutFonds":{"ESGV":12.9,"SPY":14.5,"ecart":-1.6},"coutPortefeuille":{"avecESGV":9.6,"avecSPY":10.1,"ecart":-0.4}},
    "message":{"type":"À vérifier","titre":"Vos valeurs : à vérifier (Pacte §2)","corps":"Le jeu de données ne contient aucune donnée ESG sur Exxon Mobil. Sans source externe, le Greffier ne pourra pas conclure sur une éventuelle controverse.","correction":"Joindre une source ESG","aide":"Ou continuez : le Tribunal signalera la lacune."}
  }
}
```

### C.5 Tribunal (contenu par profil)

**Règles communes à toutes les audiences :**
- Chaque argument a une provenance (Fait, Hypothèse ou Fictif) et cite au moins une pièce.
- **Encadré « Limite que l'Avocat reconnaît »** (fond ocre) sous les arguments de l'Avocat, pour les 3 profils : « Biais du survivant : l'univers a été choisi en 2026 parmi des titres devenus gros. Les rendements passés cités ici sont donc flattés. »
- **Sous-titre de toutes les audiences :** « Le Tribunal présente les deux côtés. C'est vous qui rendez le verdict. »

#### Robert

- **En-tête d'audience :** « Robert c. « 30 % en TSLA » » · Audience n° 0142.
- **Bilan du Greffier :** 1 Violation, 2 À vérifier, 2 Conforme. Constat : « Pire chute de −29,0 % pour une limite de −12 % (Pacte §1). »

**Contrôles du Greffier** (repliés derrière « Voir les 5 contrôles ») :
1. Violation : « Chute maximale de −29,0 % au-delà du seuil de −12,0 % (Pacte §1) » [P1, P3].
2. À vérifier : « Performance passée invoquée : elle ne prédit pas l'avenir ».
3. À vérifier : « Biais du survivant : univers choisi en 2026 ».
4. Conforme : « Chiffres cités vérifiés contre leurs pièces : 7 sur 7 ».
5. Conforme : « Cryptoactifs exclus : respecté (Pacte §4) » [P3].

**Procureur :**
1. Fait, P1 : « Le 14 novembre, vous avez écrit : « préserver mon capital ». Avec 30 % en TSLA, la pire chute observée passe de −7,8 % à −29,0 %. »
2. Fait, P3 : « C'est au-delà du seuil de −12 % que vous avez fixé dans votre Pacte. »
3. Fait, P4 : « Après sa chute de 2022, TSLA a mis près de 3 ans à revenir à son sommet : presque tout votre horizon de 3 à 5 ans. »
4. Hypothèse, P2 : « Si une année comme 2022 se répétait au moment de votre retraite, le portefeuille ferait −23,7 % au lieu de −2,6 %. »

**Avocat :**
1. Fait, P1 : « Sur la période, le rendement annualisé aurait été de +12,0 % contre +9,3 %. »
2. Fait, P1 : « Jusqu'à 9 %, la chute maximale reste dans les limites du Pacte : Robert peut s'exposer au titre sans renier ses objectifs. »
3. Hypothèse, P3 : « Robert suit activement les marchés : il est en mesure de surveiller de près une position volatile. »

**Trace d'exécution (7 étapes) :**
1. Agent Profil · `charger_pacte(robert)`
2. Outil de calcul · `calculer_risque(tailles=51, séances=1 255)`
3. Outil de calcul · `rejouer_periode(2022)`
4. Source · `yahoo + banque_du_canada · 2026-11-13`
5. Procureur · `réquisitoire · 4 arguments`
6. Avocat · `plaidoirie · 3 arguments`
7. Greffier · `contrôle chiffres + Pacte · 5 règles`

**Pièces :**
- P1 · Fictif · Simulation du portefeuille avec la décision · « −29,0 % max · +12,0 %/an ».
- P2 · Fictif · Rejeu de l'année 2022 · « −2,6 % → −23,7 % ».
- P3 · Fictif · Pacte de Robert · « signé le 14 nov. 2026 ».
- P4 · Fait · Temps de récupération de TSLA · « ≈ 3 ans ».
  - Source : Yahoo Finance via yfinance (prix ajustés, dividendes inclus), extrait le 13 nov. 2026, en USD.
  - Traitement : sommet le 3 janv. 2022, creux le 3 janv. 2023, retour au niveau du sommet le 10 déc. 2024.
  - Limites : une seule chute observée ; la prochaine peut être plus courte ou plus longue.
  - Citée par : Procureur, argument 3.
- P5 · Fictif · Simulation à 15 % (créée par une question) · « −16,4 % max · 2022 : −13,4 % ».

**Questions suggérées :** « Et à 15 % ? », « Pourquoi pas 5 % ? », « Ces données sont-elles fiables ? ».
Réponse à « Et à 15 % ? » : Procureur · Fait · P5 · « À 15 %, la chute maximale observée serait de −16,4 % et 2022 aurait donné −13,4 %. C'est encore au-delà de votre seuil de −12 %. »

#### Amira

- **En-tête d'audience :** « Amira c. « Panier crypto et tech » » · Audience n° 0143.
- **Bilan du Greffier :** 3 Violation, 2 À vérifier, 1 Conforme. Constat : « 3 règles de votre Pacte enfreintes : chute maximale, part en cryptoactifs, diversification. »

**Contrôles du Greffier (6) :**
1. Violation : « Chute maximale de −58,5 % au-delà du seuil de −45 % » [P1, P3].
2. Violation : « Cryptoactifs à 50 % pour un maximum de 25 % » [P3].
3. Violation : « Portefeuille exclusivement crypto ou tech, exclu par le Pacte » [P3].
4. À vérifier : « Poids de NVDA dans QQQ cité sans source : à documenter » [P4].
5. À vérifier : « Biais du survivant : univers choisi en 2026 ».
6. Conforme : « Chiffres cités vérifiés contre leurs pièces ».

**Procureur** (5 arguments ; les 3 premiers sont visibles, puis « Voir 2 autres arguments ») :
1. Fait, P1 : « Avec ce panier, la pire chute observée atteint −58,5 %, au-delà du seuil de −45 % inscrit dans votre Pacte. »
2. Fait, P3 : « La crypto passerait de 15 % à 50 % du portefeuille ; votre Pacte en fixe le maximum à 25 %. »
3. Fait, P2 : « BTC et ETH sont corrélés à 0,84 : deux cryptos, c'est presque un seul pari. »
4. Hypothèse, P4 : « NVDA et QQQ sont corrélés à 0,77, car NVDA est l'une des principales positions de QQQ : vous prenez deux fois le même pari tech (poids exact à documenter). »
5. Fait, P3 : « 100 % crypto ou tech : votre Pacte exclut de miser exclusivement sur la tech. »

**Avocat :**
1. Hypothèse, P3 : « Horizon de 15 ans et plus : le temps de traverser plusieurs cycles et de récupérer d'une forte baisse. »
2. Hypothèse, P1 : « Une poche spéculative est cohérente avec un profil de risque élevé : la vraie question est sa taille, pas sa présence. »

**Trace :** comme pour Robert, avec `charger_pacte(amira)`, `calculer_risque(tailles=21, séances=1 255)`, `réquisitoire · 5 arguments`, `plaidoirie · 2 arguments`, `6 règles`.

**Pièces :**
- P1 · Fictif · Simulation avec le panier · « −58,5 % max · +16,9 %/an ».
- P2 · Fait · Corrélations quotidiennes sur 5 ans · « BTC/ETH 0,84 · NVDA/QQQ 0,77 ».
  - Source : Yahoo Finance, extrait le 13 nov. 2026 ; USD/CAD de la Banque du Canada.
  - Traitement : corrélation de Pearson des rendements quotidiens en CAD, calendrier américain, crypto du week-end reportée au lundi.
  - Limites : les corrélations changent en période de crise ; BTC/QQQ vaut 0,40 sur la même période.
  - Citée par : Procureur, argument 3.
- P3 · Fictif · Pacte d'Amira.
- P4 · Hypothèse · Poids de NVDA dans QQQ · « À documenter ».

**Questions suggérées :** « Et si je garde 25 % de crypto ? », « Pourquoi la corrélation compte-t-elle ? », « Ces données sont-elles fiables ? ».
Réponse à la corrélation : Procureur · Fait · P2 · « Deux actifs corrélés à 0,84 montent et baissent presque ensemble. Détenir BTC et ETH n'ajoute presque pas de diversification : en 2022, les deux ont perdu plus de 60 % (en USD). »

#### Mateo

- **En-tête d'audience :** « Mateo c. « 10 % en XOM » » · Audience n° 0144 · 1 donnée manquante.
- **Bilan du Greffier :** 0 Violation (compteur affiché atténué, opacité 0,45), 3 À vérifier, 3 Conforme. Constat : « Controverse ESG d'Exxon Mobil non établie : aucune source externe dans le dossier (Pacte §2). »

**Contrôles du Greffier (6) :**
1. À vérifier : « Exclusion ESG du Pacte : controverse de XOM non établie, source externe requise » [P3, P4].
2. À vérifier : « Performance passée invoquée (XOM en 2022) : elle ne prédit pas l'avenir » [P2].
3. À vérifier : « Biais du survivant ».
4. Conforme : « Chiffres cités vérifiés contre leurs pièces ».
5. Conforme : « Chute maximale de −10,3 % dans la limite de −20 % (Pacte §1) » [P1].
6. Conforme : « Revenu fixe à 22,5 %, au-dessus du minimum de 20 % (Pacte §4) » [P1, P3].

**Procureur :**
1. Fait, P3 : « Votre Pacte exclut les entreprises liées à des controverses environnementales ou sociales importantes. C'est une règle de valeurs, pas un calcul de risque. »
2. Hypothèse, P4 : « Le jeu de données ne contient aucune donnée ESG : la controverse doit être établie par une source externe documentée avant toute conclusion. »
3. Fait, P3 : « Votre Pacte ne vous demande pas de maximiser le rendement, mais d'équilibrer croissance et stabilité selon vos valeurs. »

**Avocat :**
1. Fait, P1 : « Les chiffres sont favorables : rendement de +11,8 %/an contre +9,6 %, pire chute de −10,3 % contre −14,1 %. »
2. Fait, P2 : « L'énergie a protégé les portefeuilles en 2022 : XOM a gagné +87,4 % (USD, dividendes inclus) quand actions et obligations reculaient. »
3. Fait, P5 : « Vos valeurs ont déjà un coût : ESGV a fait +12,9 %/an contre +14,5 % pour SPY (−1,6 pt) ; dans votre portefeuille, environ −0,4 pt/an. »

**Trace :** l'étape 4 est en état d'avertissement (pastille ocre ⚠) : Source · `données ESG : introuvables → signalé`.

**Pièces :**
- P1 · Fictif · Simulation avec la décision · « −10,3 % max · +11,8 %/an ».
- P2 · Fait · XOM en 2022 · « +87,4 % (USD) ».
- P3 · Fictif · Pacte de Mateo.
- P4 · Hypothèse · Source ESG externe · « À documenter ».
  - Source : « [À AJOUTER : vérifier si XOM figure dans les titres détenus d'ESGV et citer la méthodologie d'exclusion de l'indice suivi, avec leurs dates] », affiché en ocre.
  - Traitement : critère de controverse défini par l'équipe et appliqué de façon identique à tous les titres.
  - Limites : sans source, le Greffier ne peut pas conclure.
  - Bouton : « Joindre une source ESG ».
- P5 · Fait · Coût du filtre ESG · « fonds −1,6 pt · portefeuille −0,4 pt ».

**Questions suggérées :** « Combien me coûtent mes valeurs ? », « Y a-t-il une alternative dans l'énergie ? », « Pourquoi le Greffier ne conclut-il pas ? ».
Réponse au coût : Greffier · Fait · P5 · « Au niveau des fonds, ESGV a fait +12,9 %/an contre +14,5 % pour SPY en CAD (−1,6 pt). Dans votre portefeuille, où ESGV pèse 30 %, l'écart est d'environ 0,4 pt/an (9,6 % contre 10,1 %). »

### C.6 Verdict (options par profil)

#### Robert

Rappel en haut de l'écran : statut Violation + « Pire chute de −29,0 % pour une limite de −12 % (Pacte §1). »

**Options :**
1. **Maintenir 30 % en TSLA.** Sous-titre : « Vous passez outre la violation de votre Pacte (§1). » Statut Violation. Chute max. −29,0 % · Rendement +12,0 %/an.
2. **Ramener la position à 9 %.** Sous-titre : « La plus grande taille compatible avec votre Pacte. » Statut Conforme. Chute max. −11,2 % · Rendement +10,4 %/an.
3. **Renoncer.** Sous-titre : « Le portefeuille reste tel qu'il est. »

**Choisir l'option 1 ouvre une confirmation renforcée :**
- champ obligatoire « Pourquoi maintenir malgré la violation ? », limité à 280 caractères, avec compteur ;
- case à cocher obligatoire : « Je comprends que la pire chute observée (−29,0 %) dépasse ma limite de −12 %, et que cette justification sera archivée. »
- « Signer le verdict » reste **désactivé** tant que les deux ne sont pas remplis, avec un message `aria-describedby` qui explique pourquoi.

#### Amira

Rappel en haut de l'écran : statut Violation + « 3 règles de votre Pacte enfreintes par le panier. »

**Options :**
1. **Garder le panier tel quel.** Statut Violation. Chute max. −58,5 % · Crypto 50 %.
2. **Adopter la version conforme.** Sous-titre : « Crypto 25 % (BTC 15, ETH 10), tech 35 % (NVDA 15, QQQ 20), le reste diversifié : CNR 15, ATD 10, or 15. » Statut Conforme. Chute max. −37,1 % · Rendement +18,1 %/an · Crypto 25 %.
   Quand elle est choisie, elle affiche : « Cette version respecte vos 3 règles. BTC et ETH restent corrélés à 0,84 : la poche crypto se comporte presque comme un seul actif. »
3. **Garder mon portefeuille actuel.**

#### Mateo

Rappel en haut de l'écran : statut À vérifier + « Controverse ESG non établie ; chiffres conformes à votre Pacte. »

**Options :**
1. **Ajouter 10 % de XOM maintenant.** Statut À vérifier. Chute max. −10,3 % · Rendement +11,8 %/an.
2. **Mettre en attente jusqu'à la source ESG.** Sous-titre : « La décision est gardée au journal ; le Tribunal la rejugera dès qu'une source sera jointe. »
   Quand elle est choisie, elle affiche : « À fournir : la méthodologie d'exclusion d'ESGV ou un rapport de durabilité d'Exxon Mobil, avec sa date. » + bouton « Joindre une source maintenant ».
3. **Renoncer.**

**Éléments communs au Verdict** (mise en page : annexe D.6 bis) :
- Lien « Ou ajuster votre Pacte avant de décider ».
- Barre d'actions : « Retour au Tribunal » (tertiaire) à gauche ; à droite, « Rien n'est exécuté : le verdict est archivé. » + « Signer le verdict » (primaire).

**Confirmation après signature :**
- On revient au Portefeuille du profil avec, en tête de page, un bandeau encre intégré (pas une notification flottante et pas de minuterie) : ✓ « Verdict signé et archivé » + résumé + « Annuler la signature ».
- Une nouvelle entrée apparaît en tête du journal, surlignée en `--accent-bleu-teinte`.

| Profil | Résumé du bandeau | Entrée de journal | Icône |
|---|---|---|---|
| Robert | « « 30 % en TSLA » maintenu malgré 1 violation · aucune transaction exécutée » | « 14 nov. · Maintien de TSLA à 30 % » | 🚫 rouge |
| Amira | « Version conforme adoptée (simulation) · aucune transaction exécutée » | « 14 nov. · Version conforme du panier » | ✓ vert |
| Mateo | « « 10 % en XOM » mis en attente d'une source ESG · aucune transaction exécutée » | « 14 nov. · En attente : 10 % en XOM » | ⚠ ocre |

---

## Annexe D — Écrans, interactions et types

### D.1 Routes

| Route | Écran |
|---|---|
| `/` | Entrée (choisir un profil) |
| `/:profil/portefeuille` | Portefeuille ; état « recherche ouverte » quand le champ a le focus |
| `/:profil/decision` | Décision |
| `/:profil/tribunal` | Tribunal ; `?piece=P4` ouvre le tiroir |
| `/:profil/verdict` | Verdict |
| `/:profil/portefeuille?archive=1` | Confirmation |

L'état est conservé par profil dans un store : taille choisie, panier, réponses du Tribunal, verdict, journal. Changer de profil ne perd pas l'état des autres.

### D.2 Portefeuille

La recherche est la fonction principale de l'écran : elle passe en tête, sur toute la largeur (#103).

- **En-tête de page :** « Bonjour {prénom}. » en H1, suivi sur la même ligne (renvoi à la ligne si la place manque) de ✓ vert + phrase de statut.
- **Bandeau de recherche** (D.3), juste sous l'en-tête, sur toute la largeur du conteneur : à gauche la recherche, à droite les **3 étapes du parcours** (`EtapesParcours`), séparées par un filet vertical clair :
  1. **Décision** : « Choisissez un titre et une taille : l'effet sur votre Pacte s'affiche aussitôt. »
  2. **Tribunal** : « Un Procureur et un Avocat (IA) plaident à partir de pièces calculées ; le Greffier vérifie chaque chiffre. »
  3. **Verdict** : « Vous décidez. Rien n'est acheté : le verdict est archivé. »

  Pastilles numérotées de 26 px à contour papier ; la première est pleine. Sous 1024 px, les étapes passent sous la recherche.
- **Colonne principale :**
  - Valeur : « Valeur du portefeuille », montant en Inter 600 48 / 52 (36 / 40 sous 600 px) + Fictif, ligne « ▲ 233 034 $ (+55,9 %) depuis le 12 nov. 2021 », mention « Sur 5 ans ».
  - Graphique de valeur : courbe `--donnee-principale` de 2,25 px, aire en dégradé de la même couleur (22 % en haut, transparente en bas, #105), axe en k$ à droite, pastille `--donnee-principale` de la valeur actuelle au bout de la courbe, point le plus bas marqué avec son libellé, années en abscisse. **Pas de bascule ni de choix de période** (simplification voulue).
  - 3 indicateurs **compacts** séparés par des filets verticaux : libellé au-dessus, puis chiffre (Inter 600 24 / 28) et contexte sur la même ligne (« par an sur 5 ans », jauge de 72 px + « 65 % de votre limite de −12 % », « annualisée »).
  - Ligne de provenance : Fait + « Calculé sur les prix réels du 12 nov. 2021 au 12 nov. 2026, en CAD. »
  - « Vos positions » : barre de répartition par groupe, légende à pastilles, puis la liste. Chaque ligne affiche monogramme, nom, « ticker · groupe », valeur et poids. Pas de colonnes rendement ou volatilité par titre.
- **Colonne latérale** (la recherche n'y est plus) :
  - Carte « Votre Pacte » (#105) : titre et « Signé le … », état à droite (point vert « Respecté » ou point rouge « N règles enfreintes ») ; chiffre clé de la règle la plus proche de sa limite (« Pire baisse observée −15,1 % / −20 % », 36 px), jauge arrondie avec « 76 % de la limite utilisée » et « Limite −20 % » ; **toutes les règles visibles** (§n, libellé, provenance éventuelle, statut écrit en couleur : Respectée, Enfreinte, À juger) ; pied de carte cliquable vers le Pacte vécu (« Limite supposée · Mesurez-la sur 4 vrais jours de marché · Commencer → », ou « Limite mesurée · … · Revoir »).
  - « Journal des décisions » (#105) : frise verticale, un point coloré par statut, texte de la décision, statut en toutes lettres (« Conforme au Pacte », « En conflit avec le Pacte », « À vérifier »), date à droite ; 3 entrées puis « Tout voir ».
- **Sous 1024 px :** la colonne latérale passe sous la colonne principale ; le bandeau de recherche reste en tête.

### D.3 Recherche (combobox ARIA)

- **Bandeau (#103)** (`components/Recherche.tsx`) : panneau clair (`--fond-sourdine`, bordure `--trait-fin`, texte encre, #105) en haut du Portefeuille, padding 32 / 36, rayon 16 ; grille « recherche | complément de 360 px », gouttière de 48. De haut en bas :
  - surtitre en Étiquette majuscule « Étape 1 · Décision » ;
  - titre-question (un H2 au style Titre/H1) tiré de `profils_ui.json` : « Quelle décision voulez-vous tester ? » (mode titre) ou « Quel panier voulez-vous tester ? » (mode panier) ; mêmes textes par défaut pour un profil sans textes propres ;
  - le choix du mode, aligné à droite du titre ;
  - l'aide, puis, en mode panier, les pastilles du panier ;
  - le champ de **56 px** en pilule (texte 17 px, icône loupe de 20 px), bord encre et ombre de survol au survol, bord bleu de 2 px et halo `--accent-bleu-teinte` au focus ;
  - les **titres suggérés en un clic**, précédés de « Essayer : » (mode titre : un clic ouvre la Décision) ou « Ajouter : » (mode panier : un clic ajoute au panier ; un titre déjà ajouté est désactivé avec ✓). Pastilles de 32 px : nom + ticker court en Mono. La liste vient de `suggestionsDe` : les titres de la décision de démonstration du profil, puis TSLA, NVDA, XOM, BTC-USD, sans doublon, 5 au plus ;
  - en mode panier, « Instruire le panier (N titres) » (bouton primaire) à partir de 2 titres.
- **Filtrage :** sur les 31 actifs de `assets_universe.csv`, par début de mot dans le nom ou par début de ticker, insensible aux accents et à la casse.
- **Résultats :**
  - liste de suggestions sous le champ, en couche flottante (fond carte, texte encre, rayon 12) avec bordure `--trait-fin` et `--ombre-flottante`, au-dessus du reste de la page ;
  - en-tête « N résultat(s) pour « … » » ;
  - chaque ligne : monogramme, nom avec la partie tapée en gras, « TICKER · classe · bourse · devise · secteur », volatilité annualisée en CAD à droite ;
  - la ligne active a un fond `--fond-creux` et une barre bleue de 3 px à gauche.
- **Clavier :** ↑ ↓ pour parcourir, Entrée pour ouvrir l'instruction, Échap pour fermer. Rappelle ces touches dans le pied de la liste.
- **Choix du mode :** à droite du titre du bandeau (dessous si la place manque), deux boutons « Un titre » / « Un panier » (`aria-pressed`), pour tout profil. Le mode prévu pour le profil dans `profils_ui.json` (ou un panier déjà commencé) est le mode de départ ; un profil sans textes propres reçoit des textes génériques.
- **Particularités par profil :**
  - **Mateo :** chaque action affiche un statut À vérifier + « Aucune donnée ESG ». ESGV affiche « Fonds filtré ESG ».
  - **Amira (mode panier) :**
    - le bouton « + Ajouter » (ou une suggestion) ajoute le titre à une rangée de pastilles « Dans votre panier · N titres », chacune retirable avec ×, au-dessus du champ ;
    - à partir de 2 titres, « Instruire le panier (N titres) » ouvre la Décision ;
    - les crypto sont permises pour Amira mais signalées selon son Pacte.
  - **Robert :** les crypto sont signalées « Exclu par votre Pacte (§4) » ; on peut quand même instruire, et le Tribunal le relèvera.

### D.4 Décision

- **Mise en page (paysage, #103) :** conteneur large. Lien « ← Portefeuille », étiquette « Instruction d'une décision », H1, ligne de fiche avec étiquette Fait. Dessous, une grille à zones de deux colonnes 5 : 7 :
  - à gauche, de haut en bas : le réglage (taille ou panier), les messages, les actions ;
  - à droite : « Effet sur votre Pacte », fixe au défilement (`position: sticky`).

  Tant que l'aperçu n'est pas calculé (chargement, panier non précalculé), la grille garde une seule colonne de 776 px. Sous 1024 px, tout s'empile : réglage, effet, messages, actions.
- **Taille (Robert, Mateo) :**
  - grand pourcentage, en rouge s'il dépasse le maximum conforme ;
  - montant « ≈ X $ sur Y $ » + Fictif ;
  - raccourcis ; celui du maximum conforme porte un ✓ vert et le libellé « max. conforme » ;
  - curseur 0–50 % (`input type=range` accessible, `aria-valuetext="30 %, hors limite du Pacte"`), avec un repère « Limite du Pacte · X % » ;
  - la piste se remplit en encre jusqu'à la poignée, **en rouge** quand la taille dépasse le maximum conforme (#103) ; la poignée prend un halo au survol et grossit pendant le glissement ;
  - bande de zones sous la piste : vert jusqu'au maximum conforme, **hachures rouges** au-delà (rayures `--statut-violation` sur `--statut-violation-teinte`, bord rouge : la teinte seule était à 1,1:1 sur le papier) ;
  - légende des zones ;
  - ligne « Financement simulé : réduction proportionnelle de vos positions. » (sans bouton : la démonstration ne précalcule que ce financement, #96).
- **Panier (Amira) :**
  - une ligne par titre : monogramme, nom, classe, pas-à-pas « − 25 % + » (pas de 5 %), bouton retirer ;
  - « Ajouter un titre » ;
  - « Total 100 % », avec une erreur claire si le total ≠ 100 %.
- **« Effet sur votre Pacte » :**
  - un **tableau compact** (#103, à la place des grandes cartes « avant → après ») : colonnes Indicateur, Actuel, « Avec 30 % de TSLA » (ou « Avec le panier »), Limite du Pacte, Statut. Une ligne par indicateur (`effetsSurLePacte`, `domaine/decision.ts`), avec une précision sous le libellé :
    - chaque plafond du Pacte concerné (« part du portefeuille », limite « max. 25 % » ou « exclu ») ;
    - chute maximale (« pire baisse depuis un sommet », limite du Pacte) ;
    - rendement annualisé (« par an sur 5 ans »), volatilité (« annualisée »), rendement en 2022 (« rejeu de l'année de crise ») : sans limite, la cellule affiche « — » ;
    - une ligne en violation a un fond `--statut-violation-teinte`, une barre rouge de 3 px à gauche et son chiffre « avec la décision » en rouge ;
    - le chiffre « avec la décision » s'éclaire brièvement en `--accent-bleu-teinte` quand le curseur le change ;
  - puis le graphique de recul comparé : ligne actuelle `--trait-moyen` (3,3:1 ; `--encre-300` n'atteignait que 2,4:1), ligne avec la décision `--encre-900`, ligne pointillée de la limite du Pacte, zone sous la limite en `--statut-violation` à 22 % d'opacité, point le plus bas annoté, annotation « N séances sous votre limite » si applicable ;
  - légende, puis provenance « Rejeu sur les prix réels, en CAD. Le passé ne prédit pas l'avenir. »
- **Message :** violation ou avertissement ESG, avec bouton de correction. « Ramener à 9 % » règle le curseur.
- **Actions :** « Annuler » (tertiaire) et « Soumettre au Tribunal » (primaire).
- **Mise à jour en direct :** tout l'écran se recalcule quand la taille ou le panier change, à partir des tables précalculées.

### D.5 Soumission et chargement

- Après « Soumettre au Tribunal », affiche un état de chargement qui déroule la trace d'exécution étape par étape (pastilles ✓ qui apparaissent).
- Utilise les durées réelles si le backend les fournit ; sinon environ 300 ms par étape, sans animation si `prefers-reduced-motion`.
- En cas d'erreur : message clair + « Réessayer », sans perdre la décision.
- **Mise en page (paysage, #103) :** conteneur large, deux colonnes 7 : 5.
  - À gauche, « Le Tribunal instruit le dossier » et ses phases. Pastille *à venir* : contour 1,5 px `--encre-500`, nom en `--encre-700`, détail en `--encre-500` ; *en cours* : contour encre de 2 px, pulsé ; *faite* : pleine encre avec ✓ papier.
  - À droite, la carte **« Le dossier »** (`DossierInstruit`, `components/ChargementTribunal.tsx`), fixe au défilement : « Décision jugée » (libellé de la décision) ; « Règles de votre Pacte » (§1, §2… et libellés) ; « Pièces versées au dossier · N », où chaque pièce (code encadré + nom de l'outil) apparaît quand une étape réelle la produit, avec, avant la première, « Aucune pièce pour l'instant : chaque outil appelé en versera une. ».
  - Les messages d'erreur du Tribunal restent dans la colonne étroite.

### D.6 Tribunal

- **Mise en page :** conteneur large (1344 px, #103). Lien « ← Décision », étiquette d'audience, H1 « {Prénom} c. « … » », sous-titre en Titre/Citation.
- **Bilan du Greffier :** en premier, dans une carte : compteurs par statut, constat principal, lien « Voir les N contrôles », qui déplie la liste triée par gravité, avec les pièces citées.
- **Débat :**
  - deux colonnes avec un filet de 3 px de la couleur du camp, titre « Procureur » ou « Avocat » dans cette couleur, puis « contre la décision » ou « pour la décision » ;
  - chaque argument est une carte : texte, puis rangée provenance + pastilles de pièces ;
  - « Voir N autres arguments » s'il y en a plus de 3.
- **Détails repliés** (accordéons `button[aria-expanded]`) :
  - « Comment le Tribunal a travaillé » : chronologie verticale des 7 étapes, pastilles reliées ;
  - « Pièces à conviction » : liste des pièces.
- **Tiroir de pièce** (`role="dialog"`, `aria-modal`, focus piégé, Échap ferme, le focus revient au déclencheur) :
  - panneau de 520 px à droite, toute la hauteur, voile encre à 32 % ;
  - en-tête : code + provenance + bouton fermer de 36 px ;
  - titre, valeur ;
  - sections Source / Traitement / Limites ;
  - « Citée par » ;
  - l'argument qui cite la pièce reçoit une bordure bleue de 2 px pendant que le tiroir est ouvert.
- **« Une question pour les agents ? » :**
  - pastilles de questions suggérées et champ libre « Posez votre question : les agents répondent avec les pièces du dossier » + « Envoyer » ;
  - la réponse s'affiche sous la forme rôle + provenance + pièce + texte, avec une barre gauche de la couleur du rôle ;
  - les réponses ne citent que des pièces du dossier ; un nouveau calcul crée une nouvelle pièce, par exemple P5.
- **Actions :** « Retour à la décision » et « Rendre mon verdict ».

### D.6 bis Verdict

Contenus par profil : annexe C.6.

- **Mise en page (paysage, #103) :** conteneur large. Lien « ← Tribunal », étiquette « Verdict », H1 « Quelle est votre décision ? », rappel (statut + constat). Dessous, deux colonnes 7 : 5 :
  - à gauche : les options (cartes radio), le lien « Ou ajuster votre Pacte avant de décider », puis la barre d'actions (« Retour au Tribunal » ; « Rien n'est exécuté : le verdict est archivé. » + « Signer le verdict ») et, s'il y a lieu, la raison pour laquelle la signature est désactivée ;
  - à droite, fixe au défilement : « Ce qui changerait la réponse » (points de bascule, avec les liens vers leurs pièces) et la carte **« Procès-verbal »** : « Tout le dossier du procès (pièces, contrôles, arguments, trace), en page imprimable. » + bouton secondaire compact « Exporter le procès-verbal » ; en cas d'échec, un message Violation avec « Réessayer ».
- **Options :** au survol, la carte prend un bord `--encre-500` et l'ombre de survol ; l'option choisie garde son bord encre de 1,5 px.
- **Sous 1024 px :** la colonne de droite passe en premier, puis les options, puis les actions.

### D.7 Types (contrat avec le backend)

```ts
type Provenance = 'Fait' | 'Hypothèse' | 'Fictif';
type Statut = 'Violation' | 'À vérifier' | 'Conforme';
interface Piece { code: string; provenance: Provenance; titre: string; valeur: string;
  source?: string; traitement?: string; limites?: string; citeePar?: string[]; }
interface Argument { camp: 'Procureur' | 'Avocat'; texte: string; provenance: Provenance; pieces: string[]; }
interface Controle { statut: Statut; texte: string; pieces: string[]; }
interface EtapeTrace { role: string; appel: string; etat: 'ok' | 'signalement'; dureeMs?: number; }
interface ResultatTribunal { audience: string; titre: string; constat: string;
  controles: Controle[]; arguments: Argument[]; limiteAvocat?: string;
  pieces: Piece[]; trace: EtapeTrace[]; questionsSuggerees: string[]; }
interface SimulationDecision { taille?: number; panier?: {ticker: string; poids: number}[];
  chuteMax: number; rendement: number; volatilite: number; rejeu2022: number;
  serieReculActuel: [string, number][]; serieReculDecision: [string, number][];
  seancesSousLimite?: {nombre: number; du: string; au: string}; }
```

---

## Annexe E — Définition de « terminé »

1. **Parcours complets :** Entrée → Portefeuille → Recherche → Décision → Tribunal (avec tiroir de pièce) → Verdict → Confirmation, pour les 3 profils, à la souris **et** au clavier seul. « Changer de profil » ramène à l'Entrée depuis n'importe quel écran.
2. **Fidélité visuelle :** les couleurs, typographies, espacements et textes correspondent à la maquette ; aucun texte n'est coupé à 1440 px ni à 1280 px.
3. **Tests de calcul** (pytest ou vitest), à 0,1 près :
   - Robert actuel : rendement +9,3 %, volatilité 5,6 %, chute max −7,8 %, 2022 −2,6 %.
   - Robert avec 30 % de TSLA : +12,0 %, 19,0 %, −29,0 %, −23,7 %.
   - Robert à 9 % : chute max −11,2 %.
   - Amira panier : −58,5 %.
   - Mateo avec 10 % de XOM : −10,3 %, +11,8 %.
   - Corrélation BTC/ETH : 0,84.
4. **Accessibilité :**
   - aucune erreur axe-core sur les 5 écrans ;
   - score Lighthouse Accessibilité ≥ 95 ;
   - focus toujours visible ;
   - les statuts et provenances sont lisibles sans couleur.
5. **Qualité :**
   - aucune erreur dans la console ;
   - aucun chiffre écrit en dur dans les composants (tout vient des données ou de l'API) ;
   - un README `frontend/README.md` explique comment lancer l'application, régénérer les séries et passer des données de démo au backend.
6. **Fin de tâche :** termine par un court compte rendu (ce qui est fait, ce qui reste, écarts avec la maquette) et des captures des écrans de Robert.
