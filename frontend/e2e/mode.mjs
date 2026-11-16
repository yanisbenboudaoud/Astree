/**
 * Mode choisi à l'utilisation (#137), dans le navigateur. Gratuit : aucun procès n'est lancé en direct.
 * 1. `?mode=demo` : le procès enregistré de Robert (30 % en TSLA) est rejoué jusqu'au verdict signé,
 *    sans aucune requête vers la Lambda (adresse `*.lambda-url.*`) ;
 * 2. le mode est mémorisé : les pages chargées ensuite sans paramètre restent en procès enregistrés ;
 * 3. l'interrupteur du bandeau : les deux modes, axe-core sur son panneau ouvert ; « Passer en direct »
 *    ramène à l'accueil en mode direct (sans appel à la Lambda), puis retour aux procès enregistrés.
 *
 * Demande un site qui connaît l'adresse de la Lambda (VITE_API_URL) : le site hébergé, ou
 * `npm run dev` avec .env.local. Sans elle, l'interrupteur n'existe pas et le script le signale.
 *
 *   ASTREE_URL=https://d15khh2djw55mh.cloudfront.net node e2e/mode.mjs [dossier_captures]
 */
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import { chromium } from 'playwright-core';

const require = createRequire(import.meta.url);
const CHEMIN_AXE = require.resolve('axe-core/axe.min.js');
const BASE = (process.env.ASTREE_URL ?? 'http://localhost:5173').replace(/\/$/, '');
const DOSSIER = process.argv[2] ?? 'e2e/captures';
mkdirSync(DOSSIER, { recursive: true });

const problemes = [];
const appelsLambda = [];
let navigateur;
for (const canal of ['msedge', 'chrome']) {
  try { navigateur = await chromium.launch({ channel: canal }); break; } catch { /* canal suivant */ }
}
if (!navigateur) throw new Error('Ni Edge ni Chrome trouvés.');
const page = await navigateur.newPage({ viewport: { width: 1440, height: 900 } });
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) problemes.push(`console ${m.type()} : ${m.text()}`); });
page.on('pageerror', (e) => problemes.push(`erreur de page : ${e.message}`));
page.on('request', (r) => { if (/\.lambda-url\./.test(r.url())) appelsLambda.push(`${r.method()} ${new URL(r.url()).pathname}`); });

const modeMemorise = () => page.evaluate(() => localStorage.getItem('astree.mode'));
const interrupteur = (libelle) => page.getByRole('button', { name: `Mode : ${libelle}` });

async function axe(ecran) {
  await page.addScriptTag({ path: CHEMIN_AXE });
  const violations = await page.evaluate(async () => {
    // eslint-disable-next-line no-undef
    const r = await axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] });
    return r.violations.map((v) => `${v.id} (${v.impact}) : ${v.nodes.slice(0, 2).map((n) => n.target.join(' ')).join(' | ')}`);
  });
  for (const v of violations) problemes.push(`axe, ${ecran} : ${v}`);
}

try {
  // 1. ?mode=demo, puis le parcours de Robert jusqu'au verdict signé.
  await page.goto(`${BASE}/?mode=demo`, { waitUntil: 'networkidle' });
  if (!(await interrupteur('Procès enregistrés').count())) {
    throw new Error('interrupteur absent : le site ne connaît pas l’adresse de la Lambda (VITE_API_URL), ou ?mode=demo est ignoré');
  }
  if ((await modeMemorise()) !== 'demo') problemes.push('?mode=demo n’est pas mémorisé dans localStorage');

  // 2. Page chargée sans paramètre : le mode mémorisé s'applique.
  await page.goto(`${BASE}/robert/portefeuille`, { waitUntil: 'networkidle' });
  if (!(await interrupteur('Procès enregistrés').count())) problemes.push('mode mémorisé non appliqué : la page sans ?mode= n’est plus en procès enregistrés');
  await page.getByRole('combobox').fill('tes');
  await page.getByRole('combobox').press('Enter');
  await page.waitForSelector('text=Effet sur votre Pacte');
  const curseur = page.getByRole('slider');
  await curseur.focus();
  await page.keyboard.press('Home');
  for (let i = 0; i < 30; i += 1) await page.keyboard.press('ArrowRight');
  await page.getByRole('button', { name: /Soumettre au Tribunal/ }).click();
  await page.waitForSelector('#titre-bilan', { timeout: 30_000 });
  if (!(await page.getByText(/procès enregistré/).count())) problemes.push('écran Tribunal : « procès enregistré » absent');
  await page.screenshot({ path: `${DOSSIER}/mode-demo-tribunal.png`, fullPage: true });
  await page.getByRole('button', { name: /Rendre mon verdict/ }).click();
  await page.waitForSelector('text=Quelle est votre décision');
  await page.getByRole('radio', { name: /Maintenir/ }).check();
  await page.locator('textarea').fill('J’accepte ce risque et je réévaluerai la position dans six mois.');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: /Signer le verdict/ }).click();
  await page.waitForURL('**/robert/portefeuille?archive=1');
  if (appelsLambda.length) problemes.push(`?mode=demo : ${appelsLambda.length} appel(s) à la Lambda pendant le rejeu (${appelsLambda.join(', ')})`);
  const appelsRejeu = appelsLambda.length;

  // 3. L'interrupteur : panneau, axe-core, passage en direct puis retour.
  await interrupteur('Procès enregistrés').click();
  await page.getByRole('dialog', { name: 'Mode de l’interface' }).waitFor();
  await axe('panneau du mode');
  await page.screenshot({ path: `${DOSSIER}/mode-interrupteur.png` });
  await page.getByRole('button', { name: 'Passer en direct' }).click();
  await page.waitForURL(/\/\?mode=direct$/);
  await page.waitForLoadState('networkidle');
  if (!(await interrupteur('En direct (Bedrock sur AWS)').count())) problemes.push('« Passer en direct » : l’interrupteur n’affiche pas le mode direct');
  if ((await modeMemorise()) !== 'direct') problemes.push('« Passer en direct » : mode direct non mémorisé');
  if (!(await page.getByText(/Choisissez|Entrer comme/).count())) problemes.push('« Passer en direct » : l’accueil n’est pas affiché');
  await interrupteur('En direct (Bedrock sur AWS)').click();
  await page.getByRole('button', { name: 'Passer aux procès enregistrés' }).click();
  await page.waitForURL(/\/\?mode=demo$/);
  await page.waitForLoadState('networkidle');
  if (!(await interrupteur('Procès enregistrés').count())) problemes.push('retour aux procès enregistrés : interrupteur incorrect');
  if (appelsLambda.length > appelsRejeu) problemes.push(`changement de mode : appel(s) inattendu(s) à la Lambda (${appelsLambda.slice(appelsRejeu).join(', ')})`);
} catch (erreur) {
  problemes.push(`arrêt : ${erreur.message}`);
  await page.screenshot({ path: `${DOSSIER}/mode-erreur.png`, fullPage: true }).catch(() => {});
} finally {
  await navigateur.close();
}

console.log(`Appels à la Lambda : ${appelsLambda.length}`);
console.log(problemes.length ? `\n${problemes.length} problème(s) :\n- ${problemes.join('\n- ')}` : 'Mode vérifié : ?mode=demo sans appel à la Lambda jusqu’au verdict, mode mémorisé, interrupteur (axe-core), aller-retour vers le direct.');
process.exitCode = problemes.length ? 1 : 0;
