/**
 * Vérification de « Trompez le Greffier » (#69) dans le navigateur :
 * les 4 exemples prêts (vrai chiffre accepté ; chiffre inventé, arrondi faux et mauvaise pièce
 * rejetés avec leur motif), un argument tapé au clavier, réponse en moins d'une seconde,
 * axe-core, et l'affichage d'une vraie correction du Greffier (procès de Robert à 25 %).
 *
 * Gratuit : POST /verifier n'appelle pas Bedrock. Demande l'interface en mode démonstration
 * avec VITE_API_URL vers une Lambda qui a la route /verifier.
 *
 *   ASTREE_URL=http://localhost:5173 node e2e/greffier.mjs [dossier_captures]
 */
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import { chromium } from 'playwright-core';

const require = createRequire(import.meta.url);
const BASE = process.env.ASTREE_URL ?? 'http://localhost:5173';
const DOSSIER = process.argv[2] ?? 'e2e/captures';
const DELAI_MAX_MS = 1000;
mkdirSync(DOSSIER, { recursive: true });

const problemes = [];
const mesures = [];
let navigateur;
for (const canal of ['msedge', 'chrome']) {
  try { navigateur = await chromium.launch({ channel: canal }); break; } catch { /* canal suivant */ }
}
if (!navigateur) throw new Error('Ni Edge ni Chrome trouvés.');
const page = await navigateur.newPage({ viewport: { width: 1440, height: 900 } });
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) problemes.push(`console ${m.type()} : ${m.text()}`); });
page.on('pageerror', (e) => problemes.push(`erreur de page : ${e.message}`));

async function ouvrirTribunal(taille) {
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await page.evaluate(() => sessionStorage.clear());
  await page.goto(`${BASE}/robert/portefeuille`, { waitUntil: 'networkidle' });
  await page.getByRole('combobox').fill('tes');
  await page.getByRole('combobox').press('Enter');
  await page.waitForSelector('text=Effet sur votre Pacte');
  const curseur = page.getByRole('slider');
  await curseur.focus();
  await page.keyboard.press('Home');
  for (let i = 0; i < taille; i += 1) await page.keyboard.press('ArrowRight');
  await page.getByRole('button', { name: /Soumettre au Tribunal/ }).click();
  await page.waitForSelector('text=Bilan du Greffier', { timeout: 20_000 });
}

async function resultat() {
  const zone = page.locator('#titre-pieges').locator('xpath=ancestor::section[1]');
  await zone.getByText(/Argument (accepté|rejeté)/).waitFor({ timeout: 5000 });
  return (await zone.textContent()) ?? '';
}

try {
  await ouvrirTribunal(30);
  if (await page.getByText(/Le Greffier en direct a besoin/).count()) throw new Error('VITE_API_URL absent : le Greffier en direct est indisponible');
  if (!(await page.getByText(/Règle que vous avez signée le/).count())) problemes.push('date de signature du Pacte absente du bilan');

  const attendus = [
    ['Un vrai chiffre', /Argument accepté/, null],
    ['Un chiffre inventé', /Argument rejeté\s*0\/1/, /introuvable dans P2/],
    ['Un arrondi faux', /Argument rejeté\s*0\/1/, /introuvable dans P2/],
    ['La mauvaise pièce', /Argument rejeté\s*0\/1/, /présent dans P3, pièce non citée/],
  ];
  for (const [libelle, verdict, motif] of attendus) {
    await page.getByRole('button', { name: libelle }).click();
    await page.waitForTimeout(50);
    const texte = await resultat();
    const duree = Number((texte.match(/vérifié en ([\d\s ]+)\s*ms/) ?? [])[1]?.replace(/\D/g, ''));
    mesures.push(`${libelle} : ${duree} ms`);
    if (!verdict.test(texte)) problemes.push(`${libelle} : verdict inattendu (${texte.slice(0, 120)})`);
    if (motif && !motif.test(texte)) problemes.push(`${libelle} : motif attendu ${motif}`);
    if (!(duree < DELAI_MAX_MS)) problemes.push(`${libelle} : ${duree} ms, au-delà de ${DELAI_MAX_MS} ms`);
  }
  await page.screenshot({ path: `${DOSSIER}/greffier-piege.png`, fullPage: true });

  // Un argument tapé au clavier, pièce cochée au clavier.
  const champ = page.getByLabel('Votre argument');
  await champ.fill('');
  await champ.type('TSLA a mis 2,9 ans à revenir à son sommet, et le portefeuille perdrait 35 %.');
  await page.getByRole('checkbox', { name: /P2/ }).uncheck();
  await page.getByRole('checkbox', { name: /P5/ }).check();
  await page.getByRole('button', { name: /Faire vérifier par le Greffier/ }).click();
  try {
    await page.getByText(/« 35\s%\s» introuvable dans P5/).first().waitFor({ timeout: 5000 });
    const texte = await resultat();
    if (!/Trouvé\s*2,9/.test(texte)) problemes.push('argument tapé : « 2,9 » (présent dans P5) devrait être trouvé');
  } catch {
    problemes.push('argument tapé : « 35 % » devrait être introuvable dans P5');
  }

  await page.addScriptTag({ path: require.resolve('axe-core/axe.min.js') });
  // eslint-disable-next-line no-undef
  const violations = await page.evaluate(async () => (await axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] })).violations.map((v) => `${v.id} : ${v.nodes.map((n) => n.target.join(' ')).slice(0, 2).join(' | ')}`));
  for (const v of violations) problemes.push(`axe : ${v}`);

  // Vraie correction du Greffier : procès de Robert à 25 %.
  await ouvrirTribunal(25);
  if (!(await page.getByText(/Motif du Greffier : « 30 % » introuvable dans P6/).count())) problemes.push('correction réelle du procès à 25 % non affichée');
  await page.screenshot({ path: `${DOSSIER}/greffier-correction.png`, fullPage: true });
} catch (e) {
  problemes.push(`parcours interrompu : ${e.message}`);
} finally {
  await navigateur.close();
}

console.log(mesures.join('\n'));
console.log(problemes.length ? `\n${problemes.length} problème(s) :\n- ${problemes.join('\n- ')}` : '« Trompez le Greffier » vérifié : 4 exemples, argument tapé, moins d’une seconde, axe-core, correction réelle.');
process.exit(problemes.length ? 1 : 0);
