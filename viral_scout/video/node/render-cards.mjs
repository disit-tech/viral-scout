// Renders video cards (a filled card.html + one JSON spec per card) to 1080×1920 PNGs.
// Usage: node render-cards.mjs <card.html> <cards.json> <outDir>
//   cards.json: [{ "id": "v01", "kind": "stat", "big": "2 million", "small": "...", "source": "..." }, ...]
// Playwright is loaded from VIRAL_SCOUT_VIDEO_NODE_MODULES if set, else from ./node_modules (npm install here).
import { createRequire } from "node:module";
import { readFileSync, mkdirSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { join, resolve } from "node:path";

const [template, specFile, outDir] = process.argv.slice(2);
if (!template || !specFile || !outDir) {
  console.error("Usage: node render-cards.mjs <card.html> <cards.json> <outDir>");
  process.exit(1);
}
const base = process.env.VIRAL_SCOUT_VIDEO_NODE_MODULES
  ? join(process.env.VIRAL_SCOUT_VIDEO_NODE_MODULES, "..", "index.js")
  : import.meta.url;
const { chromium } = createRequire(base)("playwright");
const cards = JSON.parse(readFileSync(specFile, "utf8"));
const url = pathToFileURL(resolve(template)).href;
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
try {
  for (const card of cards) {
    const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
    await page.addInitScript((c) => (window.CARD = c), card);
    await page.goto(url, { waitUntil: "load" });
    await page.evaluate(() => document.fonts.ready);
    const out = join(outDir, `${card.id}.png`);
    await page.screenshot({ path: out });
    await page.close();
    console.log("card", out);
  }
} finally {
  await browser.close();
}
