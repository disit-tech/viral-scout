"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { DocSection } from "@/lib/docs";

type Hit = DocSection & { score: number };

const tok = (s: string) => s.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [];
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** BM25 over sections, heading words count triple; the last query word matches as a prefix (search as you type). */
function rank(q: string, corpus: DocSection[], toks: string[][]): Hit[] {
  const qs = tok(q);
  if (!qs.length) return [];
  const last = qs.length - 1;
  const hit = (w: string, i: number) => (x: string) => (i === last ? x.startsWith(w) : x === w);
  const avg = toks.reduce((a, d) => a + d.length, 0) / (toks.length || 1);
  const df = qs.map((w, i) => toks.filter((d) => d.some(hit(w, i))).length);
  const scored = corpus.map((s, k) => {
    const d = toks[k];
    let score = 0, matched = 0;
    qs.forEach((w, i) => {
      const f = d.filter(hit(w, i)).length;
      if (!f) return;
      matched++;
      score += Math.log(1 + (corpus.length - df[i] + 0.5) / (df[i] + 0.5)) * (f * 2.2) / (f + 1.2 * (0.25 + 0.75 * d.length / avg));
    });
    if (tok(s.heading).join(" ").includes(qs.join(" "))) score *= 1.5; // phrase in the heading
    return { ...s, score: matched === qs.length ? score : matched ? score * 0.2 : 0 };
  });
  return scored.filter((h) => h.score > 0).sort((a, b) => b.score - a.score).slice(0, 25);
}

function snippet(text: string, qs: string[]): string {
  const m = qs.length ? text.match(new RegExp(`(^|[^\\p{L}\\p{N}])(${qs.map(esc).join("|")})`, "iu")) : null;
  const at = m?.index ?? 0;
  const start = Math.max(0, at - 60);
  const s = text.slice(start, start + 200);
  return (start ? "…" : "") + s + (start + 200 < text.length ? "…" : "");
}

function Marked({ text, qs }: { text: string; qs: string[] }) {
  if (!qs.length) return <>{text}</>;
  const re = new RegExp(`(${qs.map(esc).join("|")})`, "giu");
  return <>{text.split(re).map((p, i) => (i % 2 ? <mark key={i} className="rounded bg-accent/30 px-0.5 text-text">{p}</mark> : p))}</>;
}

export default function DocsSearch() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [corpus, setCorpus] = useState<DocSection[] | null>(null);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const [open, setOpen] = useState(false);

  function load() {
    if (corpus) return;
    setCorpus([]);
    fetch("/api/docs-index").then((r) => r.json()).then(setCorpus).catch(() => setCorpus(null));
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if ((e.key === "/" || (e.key === "k" && (e.ctrlKey || e.metaKey))) && !/INPUT|TEXTAREA|SELECT/.test(t.tagName) && !t.isContentEditable) {
        e.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const toks = useMemo(() => (corpus ?? []).map((s) => [...tok(s.heading), ...tok(s.heading), ...tok(s.heading), ...tok(s.doc), ...tok(s.text)]), [corpus]);
  const hits = useMemo(() => rank(q, corpus ?? [], toks), [q, corpus, toks]);
  const qs = tok(q);
  useEffect(() => setSel(0), [q]);

  const href = (h: Hit) => `/docs/${h.slug}${h.anchor ? `#${h.anchor}` : ""}`;
  function go(h: Hit) {
    setOpen(false);
    input.current?.blur();
    router.push(href(h));
  }

  return (
    <div className="relative mb-3">
      <input ref={input} value={q} type="search" placeholder="Search docs  ( / )"
        onFocus={() => { load(); setOpen(true); }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, hits.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
          else if (e.key === "Enter" && hits[sel]) { e.preventDefault(); go(hits[sel]); }
          else if (e.key === "Escape") { setQ(""); input.current?.blur(); }
        }}
        className="w-full rounded-lg border border-line bg-panel px-3 py-1.5 text-sm outline-none focus:border-accent" />
      {open && q.trim() && (
        <div className="absolute left-0 z-30 mt-1 max-h-[70vh] w-[min(36rem,calc(100vw-2rem))] overflow-y-auto rounded-xl border border-line bg-panel p-1.5 shadow-2xl">
          {corpus && !corpus.length ? <p className="p-3 text-sm text-muted">Loading…</p>
            : !hits.length ? <p className="p-3 text-sm text-muted">No matches for “{q}”.</p>
            : hits.map((h, i) => (
              <a key={`${h.slug}#${h.anchor}`} href={href(h)}
                onMouseDown={(e) => { e.preventDefault(); go(h); }} onMouseEnter={() => setSel(i)}
                className={`block rounded-lg px-3 py-2 ${i === sel ? "bg-panel-2" : ""}`}>
                <div className="text-sm">
                  <span className="text-muted">{h.doc}{h.heading !== h.doc ? " › " : ""}</span>
                  {h.heading !== h.doc && <span className="font-medium"><Marked text={h.heading} qs={qs} /></span>}
                </div>
                {h.text && <p className="mt-0.5 line-clamp-2 text-xs text-muted"><Marked text={snippet(h.text, qs)} qs={qs} /></p>}
              </a>
            ))}
        </div>
      )}
    </div>
  );
}
