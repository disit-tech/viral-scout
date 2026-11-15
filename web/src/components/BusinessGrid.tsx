"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { IndexEntry } from "@/lib/types";
import { num, times, when } from "@/lib/format";
import { Seg, readUrl, writeUrl } from "./FilterControls";

type Sort = "name" | "date" | "posts" | "outliers" | "mega" | "new" | "saved" | "ads";
type F = { sort: Sort; dir: "desc" | "asc"; q: string };
const DEFAULT: F = { sort: "date", dir: "desc", q: "" };

const SORTS: [Sort, string][] = [
  ["date", "last run"], ["name", "name A–Z"], ["posts", "posts"], ["outliers", "outliers"], ["mega", "🔥 mega"],
  ["new", "new since last run"], ["saved", "saved"], ["ads", "ads in the niche"],
];
const key = (p: IndexEntry, s: Sort): number | string =>
  s === "name" ? (p.display_name || p.name).toLowerCase() : s === "date" ? new Date(p.date).getTime() || 0 : (p[s] as number | null | undefined) ?? -1;

/** The business cards on the home page, with sorting and a name filter (kept in the URL). */
export default function BusinessGrid({ profiles }: { profiles: IndexEntry[] }) {
  const [f, setF] = useState<F>(DEFAULT);
  const [ready, setReady] = useState(false);
  useEffect(() => { setF({ ...DEFAULT, ...readUrl(DEFAULT) }); setReady(true); }, []);
  useEffect(() => { if (ready) writeUrl(f, DEFAULT); }, [f, ready]);
  const set = <K extends keyof F>(k: K, v: F[K]) => setF((x) => ({ ...x, [k]: v }));

  const list = useMemo(() => {
    const needle = f.q.trim().toLowerCase();
    const m = f.dir === "desc" ? -1 : 1;
    return profiles
      .filter((p) => !needle || `${p.display_name ?? ""} ${p.name} ${p.business}`.toLowerCase().includes(needle))
      .sort((a, b) => {
        const x = key(a, f.sort), y = key(b, f.sort);
        // names read A–Z when "descending" (the default direction), like the other boards
        if (typeof x === "string" || typeof y === "string") return String(x).localeCompare(String(y)) * -m;
        return ((x as number) - (y as number)) * m || a.name.localeCompare(b.name);
      });
  }, [profiles, f]);

  return (
    <div className="space-y-4">
      {profiles.length > 1 && (
        <div className="flex flex-wrap items-center gap-2">
          {profiles.length > 3 && (
            <input value={f.q} onChange={(e) => set("q", e.target.value)} placeholder="Find a business…"
              className="w-56 rounded-lg border border-line bg-panel px-3 py-1.5 text-sm outline-none focus:border-accent" />
          )}
          <label className="flex items-center gap-1.5 text-sm text-muted">Sort
            <select value={f.sort} onChange={(e) => set("sort", e.target.value as Sort)}
              className="rounded-lg border border-line bg-panel px-2 py-1.5 text-sm text-text">
              {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <button onClick={() => set("dir", f.dir === "desc" ? "asc" : "desc")} className="rounded-lg border border-line px-2 py-1.5 text-text" title="Reverse">
              {f.dir === "desc" ? "↓" : "↑"}
            </button>
          </label>
          <Seg value={SORTS.slice(0, 4).some(([v]) => v === f.sort) ? f.sort : ("" as Sort)} onChange={(v) => setF((x) => ({ ...x, sort: v, dir: "desc" }))}
            options={[["date", "Recent"], ["outliers", "Most outliers"], ["posts", "Most posts"], ["name", "A–Z"]]} />
          {f.q && <span className="text-xs text-muted">{list.length} of {profiles.length}</span>}
        </div>
      )}

      {list.length === 0 ? (
        <div className="rounded-xl border border-dashed border-line p-8 text-center text-muted">No business matches “{f.q}”.</div>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {list.map((p) => (
            <div key={p.name}
              className="group flex flex-col overflow-hidden rounded-2xl border border-line bg-panel transition hover:-translate-y-0.5 hover:border-accent/60">
              <Link href={`/p/${p.name}`} className="flex flex-1 flex-col">
                <div className="grid h-32 grid-cols-4 gap-px bg-line">
                  {[0, 1, 2, 3].map((i) => {
                    const t = p.top[i];
                    return t?.thumbnail ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img key={i} src={t.thumbnail} alt="" className="h-full w-full object-cover opacity-90 group-hover:opacity-100" />
                    ) : (
                      <div key={i} className="bg-panel-2" />
                    );
                  })}
                </div>
                <div className="flex flex-1 flex-col gap-3 p-4">
                  <div className="flex items-baseline justify-between gap-2">
                    <h2 className="text-lg font-semibold">{p.display_name || p.name}</h2>
                    <span suppressHydrationWarning className="text-xs text-muted">{when(p.date)}</span>
                  </div>
                  <p className="line-clamp-2 text-sm text-muted">{p.business || "No business description in the profile."}</p>
                  <div className="mt-auto grid grid-cols-4 gap-2 text-center">
                    <Stat label="posts" value={num(p.posts)} />
                    <Stat label="outliers" value={num(p.outliers)} tone="text-viral" />
                    <Stat label="🔥 mega" value={num(p.mega)} tone="text-mega" />
                    <Stat label="saved" value={num(p.saved)} />
                  </div>
                  {p.top[0] && (
                    <p className="truncate text-xs text-muted">
                      Top: <span className="text-text">{p.top[0].title}</span> · {times(p.top[0].outlier)} usual
                    </p>
                  )}
                </div>
              </Link>
              <Link href={`/p/${p.name}/ads`}
                className="flex items-center justify-between border-t border-line px-4 py-2 text-sm text-muted hover:bg-panel-2 hover:text-text">
                <span>{p.ads ? <>Ads · <span className="text-text">{num(p.ads)}</span> running in the niche</> : "Ads · no ads run yet"}</span>
                <span>→</span>
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, tone = "text-text" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg bg-panel-2 px-2 py-1.5">
      <div className={`text-base font-semibold ${tone}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
    </div>
  );
}
