/**
 * Vérification de bout en bout (annexe E) : parcours des 3 profils, Robert au clavier seul,
 * axe-core sur chaque écran, débordement horizontal à 1440 et 1280 px, erreurs de console,
 * captures des écrans de Robert.
 *
 *   npm run dev            (dans un autre terminal)
 *   npm run verifier       (ou : node e2e/verifier.mjs [dossier_captures])
 *
 * Utilise playwright-core avec le navigateur installé (Edge, sinon Chrome) : aucun téléchargement.
 */
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import { chromium } from 'playwright-core';

const require = createRequire(import.meta.url);
const CHEMIN_AXE = require.resolve('axe-core/axe.min.js');
const BASE = process.env.ASTREE_URL ?? 'http://localhost:5173';
const DOSSIER = process.argv[2] ?? 'e2e/captures';
mkdirSync(DOSSIER, { recursive: true });

const problemes = [];
const bilanAxe = [];

async function lancer() {
  for (const canal of ['msedge', 'chrome']) {
    try {
      return await chromium.launch({ channel: canal });
    } catch {
      /* canal absent : on essaie le suivant */
    }
  }
  throw new Error('Ni Edge ni Chrome trouvés : installez l’un des deux.');
}

const navigateur = await lancer();

async function nouvellePage(largeur = 1440) {
  const page = await navigateur.newPage({ viewport: { width: largeur, height: 900 } });
  page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) problemes.push(`console ${m.type()} : ${m.text()}`); });
  page.on('pageerror', (e) => problemes.push(`erreur de page : ${e.message}`));
  return page;
}

async function axe(page, ecran) {
  await page.addScriptTag({ path: CHEMIN_AXE });
  const resultat = await page.evaluate(async () => {
    // eslint-disable-next-line no-undef
    const r = await axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] });
    return r.violations.map((v) => `${v.id} (${v.impact}) : ${v.nodes.length} élément(s) — ${v.nodes.slice(0, 2).map((n) => n.target.join(' ')).join(' | ')}`);
  });
  bilanAxe.push({ ecran, violations: resultat.length });
  for (const v of resultat) problemes.push(`axe, ${ecran} : ${v}`);
}

async function debordement(page, ecran) {
  const largeurs = await page.evaluate(() => ({ document: document.documentElement.scrollWidth, fenetre: window.innerWidth }));
  if (largeurs.document > largeurs.fenetre) problemes.push(`débordement horizontal, ${ecran} : ${largeurs.document} px pour ${largeurs.fenetre} px`);
}

async function capture(page, nom) {
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${DOSSIER}/${nom}.png`, fullPage: true });
}

async function verifierEcran(page, ecran, nomCapture) {
  await axe(page, ecran);
  await debordement(page, ecran);
  if (nomCapture) await capture(page, nomCapture);
}

async function tabulerJusqua(page, motif, maximum = 60) {
  for (let i = 0; i < maximum; i += 1) {
    await page.keyboard.press('Tab');
    const texte = await page.evaluate(() => {
      const el = document.activeElement;
      const etiquette = el && 'labels' in el && el.labels?.length ? el.labels[0].textContent : '';
      return `${el?.getAttribute('aria-label') ?? ''} ${el?.textContent ?? ''} ${etiquette} ${el?.getAttribute('role') ?? ''} ${el?.getAttribute('type') ?? ''} ${el?.tagName ?? ''}`;
    });
    if (motif.test(texte)) {
      if (process.env.DEBUG) console.log(`clavier : ${motif} → ${texte.slice(0, 80)}`);
      return;
    }
  }
  throw new Error(`Élément introuvable au clavier : ${motif}`);
}

// --- Robert, au clavier seul, avec captures à 1440 px --------------------------------
async function robertAuClavier(largeur, suffixe) {
  const page = await nouvellePage(largeur);
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await page.evaluate(() => sessionStorage.clear());
  await page.reload({ waitUntil: 'networkidle' });
  await verifierEcran(page, `Entrée ${suffixe}`, `robert-0-entree${suffixe}`);
  await tabulerJusqua(page, /Entrer comme Robert/);
  await page.keyboard.press('Enter');
  await page.waitForURL('**/robert/portefeuille');
  await page.waitForSelector('text=Bonjour Robert.');
  await verifierEcran(page, `Portefeuille ${suffixe}`, `robert-1-portefeuille${suffixe}`);
  await tabulerJusqua(page, /combobox/);
  await page.keyboard.type('tes');
  await verifierEcran(page, `Recherche ouverte ${suffixe}`, `robert-1b-recherche${suffixe}`);
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter');
  await page.waitForURL('**/robert/decision');
  await page.waitForSelector('text=Effet sur votre Pacte');
  await tabulerJusqua(page, /range|INPUT/);
  await page.keyboard.press('End');
  await page.keyboard.press('Home');
  for (let i = 0; i < 30; i += 1) await page.keyboard.press('ArrowRight');
  await verifierEcran(page, `Décision ${suffixe}`, `robert-2-decision${suffixe}`);
  await tabulerJusqua(page, /Soumettre au Tribunal/);
  await page.keyboard.press('Enter');
  await page.waitForSelector('#titre-bilan', { timeout: 20000 });
  await verifierEcran(page, `Tribunal ${suffixe}`, `robert-3-tribunal${suffixe}`);
  await tabulerJusqua(page, /Ouvrir la pièce P5/);
  await page.keyboard.press('Enter');
  await page.waitForSelector('[role="dialog"]');
  await page.waitForTimeout(250);
  await verifierEcran(page, `Tiroir de pièce ${suffixe}`, `robert-3b-tiroir${suffixe}`);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(100);
  const focus = await page.evaluate(() => document.activeElement?.getAttribute('aria-label'));
  if (focus !== 'Ouvrir la pièce P5') problemes.push(`tiroir : le focus ne revient pas au déclencheur (${focus})`);
  await tabulerJusqua(page, /Rendre mon verdict/);
  await page.keyboard.press('Enter');
  await page.waitForURL('**/robert/verdict');
  // La navigation est une transition React : on attend que l'écran soit vraiment affiché.
  await page.waitForSelector('text=Quelle est votre décision');
  if (!(await page.getByText('Ce qui changerait la réponse').count())) problemes.push('verdict : points de bascule absents (#61)');
  await tabulerJusqua(page, /radio|Maintenir/);
  await page.keyboard.press('Space');
  try {
    await page.waitForSelector('textarea', { timeout: 3000 });
  } catch {
    problemes.push('verdict : Espace sur « Maintenir » n’affiche pas la justification');
  }
  const desactive = await page.getByRole('button', { name: /Signer le verdict/ }).getAttribute('aria-disabled');
  if (desactive !== 'true') problemes.push('verdict : « Signer » devrait rester désactivé sans justification');
  await tabulerJusqua(page, /TEXTAREA/);
  await page.keyboard.type("Je veux une exposition à Tesla et j'accepte ce risque. Je réévaluerai la position dans 6 mois.");
  await tabulerJusqua(page, /checkbox|INPUT/);
  await page.keyboard.press('Space');
  await verifierEcran(page, `Verdict ${suffixe}`, `robert-4-verdict${suffixe}`);
  // Procès-verbal (#57) : s'ouvre dans un nouvel onglet, avec le contenu du procès.
  const [onglet] = await Promise.all([
    page.waitForEvent('popup'),
    page.getByRole('button', { name: /Exporter le procès-verbal/ }).click(),
  ]);
  await onglet.waitForLoadState();
  const titreOnglet = await onglet.title();
  const texteOnglet = await onglet.locator('body').innerText();
  if (!titreOnglet.includes('Procès-verbal') || !texteOnglet.includes('Contrôles du Greffier')) {
    problemes.push(`verdict : le procès-verbal ne s’ouvre pas correctement (${titreOnglet})`);
  }
  await onglet.close();
  await tabulerJusqua(page, /Signer le verdict/);
  await page.keyboard.press('Enter');
  await page.waitForURL('**/robert/portefeuille?archive=1');
  await page.waitForSelector('text=Verdict signé et archivé');
  await verifierEcran(page, `Confirmation ${suffixe}`, `robert-5-archive${suffixe}`);
  // « Changer de profil » ramène à l'entrée, au clavier.
  await tabulerJusqua(page, /menu du profil/);
  await page.keyboard.press('Enter');
  await page.keyboard.press('Enter');
  await page.waitForURL(`${BASE}/`);
  await page.close();
}

// --- Amira (panier) et Mateo (ESG), à la souris ----------------------------------------
async function amira() {
  const page = await nouvellePage();
  await page.goto(`${BASE}/amira/portefeuille`, { waitUntil: 'networkidle' });
  const champ = page.getByRole('combobox');
  for (const q of ['bit', 'eth', 'nvd', 'qqq']) {
    await champ.fill(q);
    await page.waitForTimeout(100);
    await champ.press('Enter');
  }
  await verifierEcran(page, 'Amira · portefeuille (panier)');
  await page.getByRole('button', { name: /Instruire le panier \(4 titres\)/ }).click();
  await page.waitForSelector('text=Effet sur votre Pacte');
  await verifierEcran(page, 'Amira · décision');
  await page.getByRole('button', { name: /Augmenter Bitcoin/ }).click();
  const erreur = await page.getByText(/Le total fait 105/).count();
  if (!erreur) problemes.push('panier : le total différent de 100 % devrait être signalé');
  await page.getByRole('button', { name: /Diminuer Bitcoin/ }).click();
  await page.getByRole('button', { name: /Soumettre au Tribunal/ }).click();
  await page.waitForSelector('#titre-bilan', { timeout: 20000 });
  await verifierEcran(page, 'Amira · tribunal');
  await page.getByRole('button', { name: /Rendre mon verdict/ }).click();
  await page.waitForSelector('text=Quelle est votre décision');
  const bascules = await page.locator('section', { hasText: 'Ce qui changerait la réponse' }).locator('li').count();
  if (bascules !== 3) problemes.push(`verdict du panier : ${bascules} points de bascule au lieu de 3 (#61)`);
  await page.getByRole('radio', { name: /Réallouer seulement/ }).check();
  await verifierEcran(page, 'Amira · verdict');
  await page.getByRole('button', { name: /Signer le verdict/ }).click();
  await page.waitForURL('**/amira/portefeuille?archive=1');
  await page.close();
}

async function mateo() {
  const page = await nouvellePage();
  await page.goto(`${BASE}/mateo/portefeuille`, { waitUntil: 'networkidle' });
  await page.getByRole('combobox').fill('xom');
  await verifierEcran(page, 'Mateo · recherche');
  await page.getByRole('combobox').press('Enter');
  await page.waitForSelector('text=Effet sur votre Pacte');
  await verifierEcran(page, 'Mateo · décision');
  await page.getByRole('button', { name: /Soumettre au Tribunal/ }).click();
  await page.waitForSelector('#titre-bilan', { timeout: 20000 });
  await page.getByRole('button', { name: /Pourquoi le Greffier/ }).click();
  await verifierEcran(page, 'Mateo · tribunal');
  await page.getByRole('button', { name: /Rendre mon verdict/ }).click();
  await page.getByRole('radio', { name: /Renoncer/ }).check();
  await page.getByRole('button', { name: /Signer le verdict/ }).click();
  await page.waitForURL('**/mateo/portefeuille?archive=1');
  await page.close();
}

try {
  await robertAuClavier(1440, '');
  await robertAuClavier(1280, '-1280');
  await amira();
  await mateo();
} catch (e) {
  problemes.push(`parcours interrompu : ${e.message}`);
} finally {
  await navigateur.close();
}

console.log(`Écrans vérifiés par axe-core : ${bilanAxe.length}`);
console.log(problemes.length ? `\n${problemes.length} problème(s) :\n- ${problemes.join('\n- ')}` : 'Aucun problème : parcours, axe-core, débordement et console.');
process.exit(problemes.length ? 1 : 0);
