# #145 — Police de l'interface : une typographie de finance, la même sur tous les systèmes

- **Issue** : #145 · **PR** : à venir · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
L'interface utilisait Geist (Linux, Windows) ou SF Pro (Mac), les polices de la plupart des interfaces générées. Elle passe à un duo de presse financière, identique sur toutes les machines.

- **`frontend/index.html`** : chargement Google Fonts de Source Serif 4 (400, 600, 700, italique 400), IBM Plex Sans (400 à 700, italique 400) et IBM Plex Mono (400, 500), à la place de Geist et Geist Mono.
- **`frontend/src/styles/tokens.css`** :
  - `--police-titre` : `'Source Serif 4'` (titres, nom de la marque, grands chiffres) ;
  - `--police-texte` : `'IBM Plex Sans'` (texte ; `--police-mono` le reprend, en chiffres à chasse fixe) ;
  - `--police-code` : `'IBM Plex Mono'` (trace).
  Les polices du système (`-apple-system`, SF Pro) ne passent plus en premier.
- **`frontend/src/styles/base.css`**, **`ecrans/Portefeuille.module.css`**, **`ecrans/Decision.module.css`** : interlettrage des titres et des grands chiffres desserré (de −0,03 à −0,045 em vers −0,02 à 0 em). Réglé serré pour Geist, il collait les lettres d'une serif.

## Comment l'utiliser
Rien à faire : tout passe par les trois variables de `tokens.css`. Changer de police = modifier ces variables et le lien de `index.html`.

## Comment vérifier
- Mode démonstration, n'importe quel écran ; dans la console : `[...document.fonts].filter(f => f.status === 'loaded').map(f => f.family)` donne IBM Plex Sans et Source Serif 4.
- Écrans Portefeuille, Tribunal et Verdict relus dans le navigateur : titres en serif, texte en Plex, chiffres alignés, signe moins correct.

## Choix faits en cours de route
- **Serif pour les titres** : ton éditorial (FT, The Economist) qui s'accorde avec le Tribunal (« Robert c. « 30 % en TSLA » »).
- **IBM Plex Sans plutôt qu'Inter** : Inter est aussi très associé aux interfaces générées ; Plex a des chiffres en chasse fixe et le signe moins (U+2212).
- **Polices web pour tous** : la même apparence sur Mac, Windows et Linux, au prix d'un chargement depuis Google Fonts (`display=swap` ; repli sur Georgia et Segoe UI).

## Limites et suite
- Hors connexion, les polices de repli s'affichent (Georgia, Segoe UI ou celle du système).
- Les captures d'écran de `docs/journal/captures/` et de la maquette montrent encore l'ancienne police.
