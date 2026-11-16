/**
 * Captures de preuve de chaque écran (#191) : le jury ne pourra pas tester (le compte AWS
 * sera supprimé), donc chaque écran est capturé et versé au dépôt.
 *
 * Mode démonstration : l'interface rejoue des procès réellement tenus par les agents sur AWS,
 * sans appel réseau. Lancer l'interface sans VITE_API_URL, puis :
 *
 *   ASTREE_URL=http://localhost:5173 node e2e/preuves.mjs [dossier]
 *
 * Dossier par défaut : ../docs/preuves/ecrans. Un écran qui échoue est signalé, les autres
 * sont quand même capturés. Utilise playwright-core avec le navigateur installé (Chrome ou Edge).
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { chromium } from 'playwright-core';

const BASE = process.env.ASTREE_URL ?? 'http://localhost:5173';
const DOSSIER = process.argv[2] ?? '../docs/preuves/ecrans';
mkdirSync(DOSSIER, { recursive: true });

const faites = [];
const ratees = [];
const erreursPage = [];

let navigateur;
for (const canal of ['chrome', 'msedge']) {
  try { navigateur = await chromium.launch({ channel: canal }); break; } catch { /* canal suivant */ }
}
if (!navigateur) throw new Error('Ni Chrome ni Edge trouvés.');

async function nouvellePage() {
  const page = await navigateur.newPage({ viewport: { width: 1440, height: 900 } });
  page.on('pageerror', (e) => erreursPage.push(e.message));
  return page;
}

async function capture(page, nom, description, cible = null) {
  await page.waitForTimeout(300);
  const chemin = `${DOSSIER}/${nom}.png`;
  if (cible) await cible.screenshot({ path: chemin });
  else {
    // Fenêtre à la hauteur de la page : une barre fixée en bas reste en bas, au lieu de
    // couvrir le milieu de la page comme dans une capture « pleine page ».
    const taille = page.viewportSize();
    const hauteur = await page.evaluate(() => document.documentElement.scrollHeight);
    await page.setViewportSize({ width: taille.width, height: Math.max(hauteur, taille.height) });
    await page.waitForTimeout(200);
    await page.screenshot({ path: chemin });
    await page.setViewportSize(taille);
  }
  faites.push({ nom: `${nom}.png`, description });
}

async function etape(nom, action) {
  try {
    await action();
  } catch (e) {
    ratees.push(`${nom} : ${e.message.split('\n')[0]}`);
  }
}

async function soumettre(page) {
  await page.getByRole('button', { name: /Soumettre au Tribunal/ }).click();
}

// --- Accueil ------------------------------------------------------------------------
await etape('accueil', async () => {
  const page = await nouvellePage();
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await page.evaluate(() => sessionStorage.clear());
  await page.reload({ waitUntil: 'networkidle' });
  await capture(page, '01-accueil', 'Accueil : choisir un profil de test ou construire son propre Pacte');
  await page.close();
});

// --- Robert : 30 % en TSLA, cas général 1 ------------------------------------------------
await etape('robert', async () => {
  const page = await nouvellePage();
  await page.goto(`${BASE}/robert/portefeuille`, { waitUntil: 'networkidle' });
  await page.waitForSelector('text=Bonjour Robert.');
  await capture(page, '02-robert-portefeuille', 'Robert, profil prudent : portefeuille, Pacte et recherche d’un titre');
  await page.getByRole('combobox').fill('tes');
  await page.getByRole('combobox').press('Enter');
  await page.waitForSelector('text=Effet sur votre Pacte');
  const curseur = page.getByRole('slider');
  await curseur.focus();
  await page.keyboard.press('Home');
  for (let i = 0; i < 30; i += 1) await page.keyboard.press('ArrowRight');
  await capture(page, '03-robert-decision', 'Décision : 30 % en TSLA, zone compatible avec le Pacte et effet sur chaque règle, avant le procès');
  await soumettre(page);
  await page.waitForTimeout(1500);
  await capture(page, '04-robert-proces-en-cours', 'Procès en cours : chaque étape réelle des agents (orchestrateur, Procureur, Avocat, Greffier)');
  await page.waitForSelector('#titre-bilan', { timeout: 30000 });
  await capture(page, '05-robert-tribunal', 'Tribunal : bilan du Greffier, réquisitoire et plaidoirie, chacun relié à ses pièces');
  await etape('robert · contrôles du Greffier', async () => {
    await page.getByRole('button', { name: /Contrôles du Greffier sur les arguments/ }).click();
    const liste = page.locator('#liste-controles');
    await liste.scrollIntoViewIfNeeded();
    await capture(page, '06-robert-controles-greffier',
      'Contrôles du Greffier sur les arguments, avec le taux mesuré de chacun (bulletin du Greffier, #172)', liste);
  });
  await etape('robert · pièce de simulation', async () => {
    const pastilles = page.getByRole('button', { name: /^Ouvrir la pièce P/ });
    const n = await pastilles.count();
    for (let i = 0; i < n; i += 1) {
      await pastilles.nth(i).click();
      const tiroir = page.getByRole('dialog');
      await tiroir.waitFor();
      if (await tiroir.getByRole('heading', { name: 'Données vérifiées' }).count()) {
        await capture(page, '07-robert-piece-simulation',
          'Tiroir d’une pièce : ce qu’elle montre, d’où viennent les données, données vérifiées, limites, calcul', tiroir);
        await page.keyboard.press('Escape');
        return;
      }
      await page.keyboard.press('Escape');
    }
    throw new Error('aucune pièce de simulation trouvée');
  });
  await page.getByRole('button', { name: /Rendre mon verdict/ }).click();
  await page.waitForSelector('text=Quelle est votre décision');
  await capture(page, '08-robert-verdict', 'Verdict : maintenir, modifier ou ajuster le Pacte, avec les points de bascule ; l’utilisateur décide');
  await etape('robert · procès-verbal', async () => {
    const [onglet] = await Promise.all([
      page.waitForEvent('popup'),
      page.getByRole('button', { name: /Exporter le procès-verbal/ }).click(),
    ]);
    await onglet.waitForLoadState();
    await onglet.setViewportSize({ width: 1100, height: 900 });
    await capture(onglet, '09-robert-proces-verbal', 'Procès-verbal exporté : pièces, débat, contrôles et trace du procès');
    await onglet.close();
  });
  await page.close();
});

// --- Amira : panier crypto-tech, cas général 2 --------------------------------------------
await etape('amira', async () => {
  const page = await nouvellePage();
  await page.goto(`${BASE}/amira/portefeuille`, { waitUntil: 'networkidle' });
  const champ = page.getByRole('combobox');
  for (const q of ['bit', 'eth', 'nvd', 'qqq']) {
    await champ.fill(q);
    await page.waitForTimeout(100);
    await champ.press('Enter');
  }
  await page.getByRole('button', { name: /Instruire le panier \(4 titres\)/ }).click();
  await page.waitForSelector('text=Effet sur votre Pacte');
  await capture(page, '10-amira-decision-panier', 'Amira, profil audacieux : réallocation vers un panier crypto-tech, plafonds de diversification');
  await soumettre(page);
  await page.waitForSelector('#titre-bilan', { timeout: 30000 });
  await capture(page, '11-amira-tribunal', 'Tribunal d’Amira : risque accepté, mais plafonds crypto et tech + crypto en violation');
  await page.getByRole('button', { name: /Rendre mon verdict/ }).click();
  await page.waitForSelector('text=Quelle est votre décision');
  await capture(page, '12-amira-verdict', 'Verdict d’Amira : un point de bascule par règle en violation');
  await page.close();
});

// --- Mateo : XOM, cas général 3 ---------------------------------------------------------
await etape('mateo', async () => {
  const page = await nouvellePage();
  await page.goto(`${BASE}/mateo/portefeuille`, { waitUntil: 'networkidle' });
  await page.getByRole('combobox').fill('xom');
  await page.getByRole('combobox').press('Enter');
  await page.waitForSelector('text=Effet sur votre Pacte');
  await capture(page, '13-mateo-decision', 'Mateo, profil équilibré ESG : 10 % en XOM');
  await soumettre(page);
  await page.waitForSelector('#titre-bilan', { timeout: 30000 });
  await capture(page, '14-mateo-tribunal', 'Tribunal de Mateo : la controverse ESG documentée, pièce documentaire avec sa source');
  await page.close();
});

// --- Construire mon Pacte (questionnaire) -------------------------------------------------
await etape('construire', async () => {
  const page = await nouvellePage();
  await page.goto(`${BASE}/construire`, { waitUntil: 'networkidle' });
  await capture(page, '15-construire-pacte-question', 'Construire mon Pacte : une question, à quoi sert la réponse, progression');
  await page.getByRole('button', { name: /Remplir comme un profil de test/ }).click();
  await page.waitForTimeout(1500);
  await capture(page, '16-construire-pacte-apercu', 'Pacte tiré du questionnaire : chaque règle avec la réponse qui l’a produite, seuils modifiables');
  await page.close();
});

// --- Pacte vécu -------------------------------------------------------------------------
await etape('pacte vécu', async () => {
  const page = await nouvellePage();
  await page.goto(`${BASE}/robert/pacte-vecu`, { waitUntil: 'networkidle' });
  await capture(page, '17-pacte-vecu-question', 'Pacte vécu : un vrai jour de baisse revécu, sans la suite ; « je reste » ou « je vends »');
  await etape('pacte vécu · résultat', async () => {
    await page.getByRole('button', { name: /Utiliser les réponses de démonstration/ }).click();
    await page.waitForTimeout(800);
    await capture(page, '18-pacte-vecu-resultat', 'Pacte vécu : seuil de pire baisse mesuré sur les réponses, au lieu d’être déclaré');
  });
  await page.close();
});

await navigateur.close();

const index = [
  '# Captures de chaque écran',
  '',
  `Mode démonstration (procès réellement tenus par les agents sur AWS, rejoués sans réseau), ${new Date().toISOString().slice(0, 10)}. Généré par \`frontend/e2e/preuves.mjs\` (#191).`,
  '',
  '| Capture | Ce qu’elle montre |',
  '|---|---|',
  ...faites.map((c) => `| [\`${c.nom}\`](${c.nom}) | ${c.description} |`),
  '',
];
writeFileSync(`${DOSSIER}/README.md`, index.join('\n'));
console.log(`${faites.length} captures → ${DOSSIER}`);
for (const r of ratees) console.log(`RATÉ  ${r}`);
for (const e of erreursPage) console.log(`ERREUR DE PAGE  ${e}`);
process.exit(ratees.length ? 1 : 0);
