"use client";

import { useMemo, useState } from "react";
import { num } from "@/lib/format";

export type Hit = {
  profile: string; platform: string; id: string; url: string; title: string; channel: string;
  views: number | null; likes: number | null; hook: string; cta: string; saved: boolean | number; snippet: string; score: number;
};

const tok = (s: string) => (s.toLowerCase().match(/[\p{L}\p{N}']+/gu) ?? []).filter((w) => w.length > 1);

/** Small BM25 for the published (read-only) site; the local site asks the Python CLI instead. */
function rank(q: string, corpus: Hit[]): Hit[] {
  const qs = tok(q);
  if (!qs.length) return [];
  const docs = corpus.map((d) => tok(`${d.title} ${d.title} ${d.hook} ${d.hook} ${d.cta} ${d.snippet} ${d.channel}`));
  const avg = docs.reduce((a, d) => a + d.length, 0) / (docs.length || 1);
  const df = new Map(qs.map((w) => [w, docs.filter((d) => d.includes(w)).length]));
  return corpus
    .map((h, i) => {
      const d = docs[i];
      let s = 0;
      for (const w of qs) {
        const f = d.filter((x) => x === w).length;
        if (!f) continue;
        const n = df.get(w) ?? 0;
        s += Math.log(1 + (corpus.length - n + 0.5) / (n + 0.5)) * (f * 2.5) / (f + 1.5 * (0.25 + 0.75 * d.length / avg));
      }
      return { ...h, score: s };
    })
    .filter((h) => h.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 40);
}

export default function SearchBox({ local, corpus }: { local: boolean; corpus: Hit[] }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [busy, setBusy] = useState(false);
  const profiles = useMemo(() => Array.from(new Set((hits ?? []).map((h) => h.profile))), [hits]);

  async function go(e: React.FormEvent) {
    e.preventDefault();
    if (!local) return setHits(rank(q, corpus));
    setBusy(true);
    const r = await fetch(`/api/search?q=${encodeURIComponent(q)}`).then((x) => x.json()).catch(() => ({ hits: [] }));
    setBusy(false);
    setHits(r.hits ?? []);
  }

  return (
    <div className="mt-5">
      <form onSubmit={go} className="flex gap-2">
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder='e.g. "power outage", "polite rude", "before and after"'
          className="w-full max-w-xl rounded-lg border border-line bg-panel px-3 py-2 outline-none focus:border-accent" />
        <button className="rounded-lg bg-accent px-4 font-semibold text-ink hover:brightness-110">{busy ? "…" : "Search"}</button>
      </form>
      {hits && (
        <p className="mt-3 text-xs text-muted">{hits.length} results{profiles.length ? ` in ${profiles.join(", ")}` : ""}</p>
      )}
      <div className="mt-3 space-y-2.5">
        {hits?.map((h) => (
          <a key={`${h.profile}:${h.platform}:${h.id}`} href={h.url} target="_blank" rel="noreferrer"
            className="block rounded-xl border border-line bg-panel p-3 hover:border-accent/60">
            <div className="flex flex-wrap items-baseline gap-x-2 text-sm">
              <span className="font-medium">{h.title || h.id}</span>
              <span className="text-muted">· {h.channel} · {h.platform} · {num(h.views ?? h.likes)}{h.views == null ? " ♥" : ""}</span>
              <span className="ml-auto rounded-full bg-panel-2 px-2 text-[11px] text-muted">{h.profile}</span>
              {h.saved ? <span className="rounded-full bg-above px-2 text-[11px] text-ink">saved</span> : null}
            </div>
            {h.hook && <p className="mt-1 text-sm italic text-text/85">“{h.hook}”</p>}
            {h.snippet && <p className="mt-1 line-clamp-2 text-xs text-muted">{h.snippet}</p>}
          </a>
        ))}
      </div>
    </div>
  );
}
