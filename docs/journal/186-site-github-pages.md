# #186 — Site de démonstration sur GitHub Pages (sans AWS)

- **Issue** : #186 · **PR** : à venir · **Statut** : terminée
- **Dernière mise à jour** : 2026-11-15

## Ce qui a été construit
Les comptes AWS du Datathon sont supprimés le 16 novembre 2026 à 11 h 30, et le site CloudFront (#135) avec eux. L'interface en mode démonstration (#184) est donc aussi publiée sur GitHub Pages : <https://yanisbenboudaoud.github.io/Datathon2026/>.

- `.github/workflows/pages.yml` : à chaque push sur `main` (ou à la main, `workflow_dispatch`), construit `frontend/` avec `VITE_USE_MOCKS=true` et `VITE_API_URL` vide, puis publie `frontend/dist` sur Pages. Aucun secret.
- Le site est servi sous `/Datathon2026/` : `vite build --base "/<dépôt>/"`.
  - `frontend/src/main.tsx` : `BrowserRouter` reçoit `basename={import.meta.env.BASE_URL}`.
  - `frontend/src/components/Gabarit.tsx` : le logo lit `marque.svg` sous `BASE_URL`. Les procès-verbaux le faisaient déjà (`ouvrirProcesVerbal`).
  - En local et dans le site CloudFront, `BASE_URL` vaut `/` : rien ne change.
- `404.html` est une copie de `index.html` : Pages ne réécrit pas les URL, donc une page profonde rechargée (`/Datathon2026/tribunal`) charge quand même l'application.

## Comment l'utiliser
Le site se met à jour seul à chaque fusion dans `main`. Pour le relancer : onglet **Actions** → **Pages** → **Run workflow**.

## Comment vérifier
```bash
cd frontend && VITE_USE_MOCKS=true VITE_API_URL= npx vite build --base /Datathon2026/ && npx vite preview --base /Datathon2026/
```
Ouvrir `http://localhost:4173/Datathon2026/` : logo affiché, Robert → 30 % en TSLA → Soumettre au Tribunal rejoue le procès, aucune requête vers `amazonaws.com`.

## Limites
- Mêmes limites que le mode démonstration (#184) : pas de nouvelle décision, de question libre ni de Pacte construit avec vos propres réponses.
- Pages doit être activé dans le dépôt (Settings → Pages → Source : GitHub Actions). Sur un dépôt privé, il faut un compte GitHub Pro (gratuit avec le Student Developer Pack) ; le site, lui, est public.
