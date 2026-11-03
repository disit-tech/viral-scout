import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { marked } from "marked";

const DIR = path.join(/*turbopackIgnore: true*/ process.cwd(), "content", "docs");

export type Doc = { slug: string; title: string; html: string };

export async function docSlugs(): Promise<string[]> {
  try {
    return (await readdir(DIR)).filter((f) => f.endsWith(".md")).map((f) => f.replace(/\.md$/, "").toLowerCase());
  } catch {
    return [];
  }
}

export async function loadDoc(slug: string): Promise<Doc | null> {
  if (!/^[\w.-]+$/.test(slug)) return null;
  const files = await readdir(DIR).catch(() => [] as string[]);
  const file = files.find((f) => f.replace(/\.md$/, "").toLowerCase() === slug);
  if (!file) return null;
  const md = await readFile(path.join(DIR, file), "utf-8");
  const title = md.match(/^#\s+(.+)$/m)?.[1] ?? slug;
  // Links between docs (foo.md, foo.md#x) → /docs/foo; repo files → GitHub.
  const linked = md
    .replace(/\]\((?!https?:|#)([\w./-]+?)\.md(#[\w-]+)?\)/g, (_, p: string, h = "") => `](/docs/${p.split("/").pop()!.toLowerCase()}${h})`)
    .replace(/\]\(\.\.\/([^)]+)\)/g, "](https://github.com/disit-tech/viral-scout/blob/main/$1)");
  return { slug, title, html: marked.parse(linked, { async: false }) as string };
}
