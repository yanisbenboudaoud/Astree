/**
 * Vérification du mode direct (#14) : de vrais procès sur la Lambda, depuis le navigateur.
 * Robert (« 30 % en TSLA ») et Amira (panier crypto et tech, le procès le plus long),
 * jusqu'au verdict signé et archivé dans S3 (POST /verdict). Pendant l'attente, la vraie
 * progression (#90) : POST /tribunal en 202, relectures de /progression, phase qui avance.
 *
 * Coûte des appels Bedrock (quelques cents par procès) et ajoute deux verdicts à la
 * jurisprudence des profils (verdicts/<profil>/ du bucket).
 *
 *   frontend\.env.local : VITE_USE_MOCKS=false et VITE_API_URL=<Function URL>
 *   npm run dev            (sur http://localhost:5173, l'origine autorisée par le CORS)
 *   node e2e/direct.mjs [dossier_captures]
 *
 * Sur le site hébergé (#135), construit en mode direct (#136) :
 *   ASTREE_URL=https://<distribution>.cloudfront.net node e2e/direct.mjs
 */
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import { chromium } from 'playwright-core';

const require = createRequire(import.meta.url);
const BASE = (process.env.ASTREE_URL ?? 'http://localhost:5173').replace(/\/$/, '');
const DOSSIER = process.argv[2] ?? 'e2e/captures';
const DELAI_PROCES_MS = 180_000; // Lambda : 300 s au plus ; procès mesurés de 26 à 44 s
mkdirSync(DOSSIER, { recursive: true });

const problemes = [];
const bilan = [];
let navigateur;
for (const canal of ['msedge', 'chrome']) {
  try { navigateur = await chromium.launch({ channel: canal }); break; } catch { /* canal suivant */ }
}
if (!navigateur) throw new Error('Ni Edge ni Chrome trouvés.');

async function nouvellePage() {
  const page = await navigateur.newPage({ viewport: { width: 1440, height: 900 } });
  const appels = [];
  page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) problemes.push(`console ${m.type()} : ${m.text()}`); });
  page.on('pageerror', (e) => problemes.push(`erreur de page : ${e.message}`));
  page.on('response', (r) => {
    if (r.url().includes('.lambda-url.')) appels.push({ route: new URL(r.url()).pathname, statut: r.status(), id: r.headers()['x-proces-id'] });
  });
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await page.evaluate(() => sessionStorage.clear());
  return { page, appels };
}

async function axe(page, ecran) {
  await page.addScriptTag({ path: require.resolve('axe-core/axe.min.js') });
  // eslint-disable-next-line no-undef
  const violations = await page.evaluate(async () => (await axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] })).violations.map((v) => v.id));
  for (const v of violations) problemes.push(`axe, ${ecran} : ${v}`);
}

async function attendreProces(page, profil, appels) {
  const debut = Date.now();
  if (await page.getByText(/procès enregistré/).count()) problemes.push(`${profil} : l'interface est en mode démonstration (VITE_USE_MOCKS)`);
  // Progression en direct (#90) : la phase en cours doit changer pendant l'attente.
  const phasesVues = new Set();
  while (!(await page.locator('#titre-bilan').count())) {
    if (Date.now() - debut > DELAI_PROCES_MS) throw new Error(`${profil} : pas de résultat après ${DELAI_PROCES_MS / 1000} s`);
    const phase = await page.locator('li[aria-current="step"] .t-petit-fort').first().textContent({ timeout: 200 }).catch(() => null);
    if (phase) phasesVues.add(phase);
    await page.waitForTimeout(300);
  }
  const duree = Math.round((Date.now() - debut) / 1000);
  const tribunal = appels.find((a) => a.route === '/tribunal');
  const relectures = appels.filter((a) => a.route === '/progression');
  const audience = await page.locator('p.t-etiquette').first().textContent();
  const constat = await page.locator('section[aria-labelledby="titre-bilan"] p.t-corps').textContent();
  if (!tribunal || tribunal.statut !== 202) problemes.push(`${profil} : POST /tribunal a répondu ${tribunal?.statut} (202 attendu : procès en arrière-plan)`);
  if (!relectures.length || relectures.some((a) => a.statut !== 200)) problemes.push(`${profil} : relectures de /progression ${relectures.map((a) => a.statut).join(',') || 'absentes'}`);
  if (phasesVues.size < 2) problemes.push(`${profil} : phase en cours figée pendant l'attente (${[...phasesVues].join(', ') || 'aucune'})`);
  if (/n° —/.test(audience ?? '')) problemes.push(`${profil} : identifiant du procès illisible (CORS ExposeHeaders x-proces-id ?)`);
  if (/procès enregistré/.test(audience ?? '')) problemes.push(`${profil} : procès rejoué au lieu d'un vrai procès`);
  return { duree, id: tribunal?.id, audience: audience?.trim(), constat: constat?.trim(), phases: [...phasesVues].join(' → ') };
}

async function signer(page, profil, appels, choix) {
  await page.getByRole('button', { name: /Rendre mon verdict/ }).click();
  await page.waitForSelector('text=Quelle est votre décision');
  for (const motif of choix) {
    const option = page.getByRole('radio', { name: motif });
    if (await option.count()) { await option.check(); break; }
  }
  await page.getByRole('button', { name: /Signer le verdict/ }).click();
  await page.waitForURL(`**/${profil}/portefeuille?archive=1`, { timeout: 30_000 });
  const verdict = appels.find((a) => a.route === '/verdict');
  if (!verdict || verdict.statut !== 200) problemes.push(`${profil} : POST /verdict a répondu ${verdict?.statut}`);
  return verdict?.statut;
}

try {
  // Robert : 30 % en TSLA
  {
    const { page, appels } = await nouvellePage();
    await page.goto(`${BASE}/robert/portefeuille`, { waitUntil: 'networkidle' });
    await page.getByRole('combobox').fill('tes');
    await page.getByRole('combobox').press('Enter');
    await page.waitForSelector('text=Effet sur votre Pacte');
    await page.getByRole('button', { name: /Soumettre au Tribunal/ }).click();
    const proces = await attendreProces(page, 'robert', appels);
    await axe(page, 'Robert · tribunal en direct');
    await page.screenshot({ path: `${DOSSIER}/direct-robert-tribunal.png`, fullPage: true });

    // « Trompez le Greffier » sur ce vrai procès (POST /verifier, sans Bedrock).
    await page.getByRole('button', { name: 'Un chiffre inventé' }).click();
    try {
      await page.getByText(/Argument rejeté/).waitFor({ timeout: 10_000 });
    } catch {
      problemes.push('robert : « Trompez le Greffier » sans verdict sur le procès en direct');
    }

    // Contre-interrogatoire (#55) : la question de l'issue, posée au vrai Tribunal.
    const debutQuestion = Date.now();
    await page.getByLabel('Votre question aux agents').fill('Et si je mettais 15 % au lieu de 30 % ?');
    await page.getByRole('button', { name: /^Envoyer$/ }).click();
    try {
      await page.getByText(/Question 1 : « Et si je mettais 15/).waitFor({ timeout: DELAI_PROCES_MS });
      const question = appels.find((a) => a.route === '/question');
      if (!question || question.statut !== 200) problemes.push(`robert : POST /question a répondu ${question?.statut}`);
      const echange = await page.locator('li', { hasText: /Question 1 :/ }).first().textContent();
      bilan.push({ profil: 'robert (question)', duree: Math.round((Date.now() - debutQuestion) / 1000), id: proces.id, audience: '', constat: echange?.match(/Greffier : [^·]*/)?.[0] ?? '', verdict: '' });
      if (!/pièces ajoutées/.test(echange ?? '')) problemes.push('robert : la question n\'a ajouté aucune pièce');
      await axe(page, 'Robert · contre-interrogatoire');
      await page.screenshot({ path: `${DOSSIER}/direct-robert-question.png`, fullPage: true });
    } catch (e) {
      problemes.push(`robert : pas de réponse à la question (${e.message})`);
    }
    const verdict = await signer(page, 'robert', appels, [/Ramener la position/, /Renoncer/]);
    bilan.push({ profil: 'robert', ...proces, verdict });
    await page.close();
  }
  // Amira : panier BTC, ETH, NVDA, QQQ à 25 % (le procès le plus long)
  {
    const { page, appels } = await nouvellePage();
    await page.goto(`${BASE}/amira/portefeuille`, { waitUntil: 'networkidle' });
    const champ = page.getByRole('combobox');
    for (const q of ['bit', 'eth', 'nvd', 'qqq']) { await champ.fill(q); await page.waitForTimeout(100); await champ.press('Enter'); }
    await page.getByRole('button', { name: /Instruire le panier/ }).click();
    await page.waitForSelector('text=Effet sur votre Pacte');
    await page.getByRole('button', { name: /Soumettre au Tribunal/ }).click();
    const proces = await attendreProces(page, 'amira', appels);
    await axe(page, 'Amira · tribunal en direct');
    await page.screenshot({ path: `${DOSSIER}/direct-amira-tribunal.png`, fullPage: true });
    const verdict = await signer(page, 'amira', appels, [/Réallouer seulement/, /Garder mon portefeuille/]);
    bilan.push({ profil: 'amira', ...proces, verdict });
    await page.close();
  }
} catch (e) {
  problemes.push(`parcours interrompu : ${e.message}`);
} finally {
  await navigateur.close();
}

for (const b of bilan) {
  console.log(`${b.profil} : procès ${b.id} en ${b.duree} s${b.phases ? ` (phases vues : ${b.phases})` : ''} · ${b.audience} · ${b.constat} · POST /verdict ${b.verdict}`);
}
console.log(problemes.length ? `\n${problemes.length} problème(s) :\n- ${problemes.join('\n- ')}` : 'Mode direct vérifié : vrais procès, verdicts archivés, CORS, axe-core et console.');
process.exit(problemes.length ? 1 : 0);
