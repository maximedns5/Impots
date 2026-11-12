// Rend les images de la vidéo : chaque scène est une page HTML dont les animations sont
// arrêtées puis placées à l'instant voulu (window.seek), image par image. Une image
// identique à la précédente (aucune animation en cours, même sous-titre) n'est pas
// refaite : elle est liée à la précédente.
//
//   node video/render.mjs out/rendu_paysage.json
import { createRequire } from 'node:module';
// Playwright est installé globalement : require le trouve, import non.
const { chromium } = createRequire(import.meta.url)('playwright');
import fs from 'node:fs';
import path from 'node:path';

const cfg = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const PARALLELE = Number(process.env.PARALLELE || 3);
const nom = (i) => path.join(cfg.dossier, String(i).padStart(6, '0') + '.png');

const browser = await chromium.launch();
let faites = 0, liees = 0;

async function scene(tr) {
  const page = await browser.newPage({
    viewport: { width: cfg.largeur, height: cfg.hauteur }, deviceScaleFactor: 1,
  });
  await page.goto('file://' + tr.page);
  await page.evaluate(() => document.fonts.ready);
  let cle = null;
  for (let i = 0; i < tr.n; i++) {
    const t = (i + 0.5) / cfg.fps;
    const k = await page.evaluate((t) => window.seek(t), t);
    const f = nom(tr.debut + i);
    if (fs.existsSync(f)) fs.unlinkSync(f);
    if (k !== null && k === cle && i > 0) {
      fs.linkSync(nom(tr.debut + i - 1), f);
      liees++;
    } else {
      await page.screenshot({ path: f });
      faites++;
    }
    cle = k;
  }
  await page.close();
  process.stdout.write(`  ${path.basename(tr.page)} : ${tr.n} images\n`);
}

const file = [...cfg.travaux];
await Promise.all(Array.from({ length: PARALLELE }, async () => {
  while (file.length) await scene(file.shift());
}));
await browser.close();
console.log(`${faites} images rendues, ${liees} reprises`);
