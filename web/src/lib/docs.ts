import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { Marked } from "marked";

const DIR = path.join(/*turbopackIgnore: true*/ process.cwd(), "content", "docs");

export type Doc = { slug: string; title: string; html: string };
/** One searchable chunk: a doc's intro or one of its headings with the text under it. */
export type DocSection = { slug: string; doc: string; heading: string; anchor: string; text: string };

export async function docSlugs(): Promise<string[]> {
  try {
    return (await readdir(DIR)).filter((f) => f.endsWith(".md")).map((f) => f.replace(/\.md$/, "").toLowerCase());
  } catch {
    return [];
  }
}

/** Markdown inline syntax → plain text (links keep their label, code keeps its content). */
function plain(md: string): string {
  return md
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/<[^>]+>/g, " ")
    .replace(/[*_`~]+/g, "")
    .replace(/&nbsp;/g, " ");
}

/** GitHub-style heading anchor, so links like foo.md#some-heading land on the heading. */
export function headingAnchor(text: string): string {
  return plain(text).trim().toLowerCase().replace(/[^\p{L}\p{N}\s-]/gu, "").replace(/\s/g, "-");
}

function uniq(seen: Map<string, number>, a: string): string {
  const n = seen.get(a) ?? 0;
  seen.set(a, n + 1);
  return n ? `${a}-${n}` : a;
}

async function readDoc(slug: string): Promise<string | null> {
  if (!/^[\w.-]+$/.test(slug)) return null;
  const files = await readdir(DIR).catch(() => [] as string[]);
  const file = files.find((f) => f.replace(/\.md$/, "").toLowerCase() === slug);
  return file ? readFile(path.join(DIR, file), "utf-8") : null;
}

export async function loadDoc(slug: string): Promise<Doc | null> {
  const md = await readDoc(slug);
  if (md == null) return null;
  const title = md.match(/^#\s+(.+)$/m)?.[1] ?? slug;
  // Links between docs (foo.md, foo.md#x) → /docs/foo; repo files → GitHub.
  const linked = md
    .replace(/\]\((?!https?:|#)([\w./-]+?)\.md(#[\w-]+)?\)/g, (_, p: string, h = "") => `](/docs/${p.split("/").pop()!.toLowerCase()}${h})`)
    .replace(/\]\(\.\.\/([^)]+)\)/g, "](https://github.com/disit-tech/viral-scout/blob/main/$1)");
  const seen = new Map<string, number>();
  const marked = new Marked({
    renderer: {
      heading({ tokens, depth, text }) {
        const id = uniq(seen, headingAnchor(text));
        return `<h${depth} id="${id}" class="scroll-mt-20">${this.parser.parseInline(tokens)}</h${depth}>\n`;
      },
    },
  });
  return { slug, title, html: marked.parse(linked, { async: false }) as string };
}

/** Every doc split at its headings (h1–h4), as plain text for the docs search. */
export async function docSections(): Promise<DocSection[]> {
  const out: DocSection[] = [];
  for (const slug of await docSlugs()) {
    const md = await readDoc(slug);
    if (md == null) continue;
    const doc = plain(md.match(/^#\s+(.+)$/m)?.[1] ?? slug).trim();
    const seen = new Map<string, number>();
    let cur: DocSection = { slug, doc, heading: doc, anchor: "", text: "" };
    let fence = false;
    const flush = () => { cur.text = cur.text.replace(/\s+/g, " ").trim(); if (cur.text || cur.anchor) out.push(cur); };
    for (const line of md.split(/\r?\n/)) {
      if (/^\s*(```|~~~)/.test(line)) { fence = !fence; continue; }
      const h = !fence && line.match(/^(#{1,4})\s+(.+?)\s*#*\s*$/);
      if (h) {
        const anchor = uniq(seen, headingAnchor(h[2]));
        if (h[1].length === 1 && !cur.text) continue; // the title itself: keep collecting the intro
        flush();
        cur = { slug, doc, heading: plain(h[2]).trim(), anchor, text: "" };
        continue;
      }
      if (/^\s*\|?\s*:?-{3,}/.test(line)) continue; // table separator rows
      cur.text += " " + plain(line.replace(/^\s*(>|[-*+]|\d+\.)\s+/, "").replace(/\|/g, " "));
    }
    flush();
  }
  return out;
}
