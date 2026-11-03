// Copies ../docs/*.md (the repo docs) into web/content/docs so the dashboard can render them.
// On Vercel the repo root isn't uploaded, so a missing source is fine: the copy made locally is deployed.
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import path from "node:path";

const src = path.resolve(process.cwd(), "..", "docs");
const dst = path.resolve(process.cwd(), "content", "docs");
if (!existsSync(src)) {
  console.log(`copy-docs: ${src} not found, keeping ${existsSync(dst) ? "existing copy" : "no docs"}`);
  process.exit(0);
}
rmSync(dst, { recursive: true, force: true });
mkdirSync(dst, { recursive: true });
for (const f of readdirSync(src)) if (f.endsWith(".md")) cpSync(path.join(src, f), path.join(dst, f));
console.log(`copy-docs: ${readdirSync(dst).length} docs`);
