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
              <Link href={`/p/${p.name}`} className="flex flex-col">
                <div className="grid h-28 grid-cols-4 gap-px bg-line">
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
                <div className="flex flex-col gap-2 px-4 pt-4">
                  <div className="flex items-baseline justify-between gap-2">
                    <h2 className="text-lg font-semibold">{p.display_name || p.name}</h2>
                    <span suppressHydrationWarning className="text-xs text-muted" title="last videos run">{p.date ? when(p.date) : "not run yet"}</span>
                  </div>
                  <p className="line-clamp-2 text-sm text-muted">{p.business || "No business description in the profile."}</p>
                </div>
              </Link>
              <FeatureRows p={p} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const usd = (v: number) => `$${Math.round(v).toLocaleString("en-US")}`;
const short = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });

/** The business at a glance: one row per feature it uses, each linking to its page. Features not set up stay off. */
function FeatureRows({ p }: { p: IndexEntry }) {
  const f = p.features ?? {};
  const base = `/p/${encodeURIComponent(p.name)}`;
  const rows: { href: string; icon: string; label: string; body: React.ReactNode }[] = [
    {
      href: `${base}/videos`, icon: "🎬", label: "Videos",
      body: p.posts ? <><b>{num(p.posts)}</b> posts · <b className="text-viral">{num(p.outliers)}</b> outliers · <b className="text-mega">{num(p.mega)}</b> 🔥</> : <span className="text-muted">not run yet</span>,
    },
  ];
  if (f.ads) rows.push({ href: `${base}/ads`, icon: "📢", label: "Competitor ads",
    body: <><b>{num(f.ads.ads)}</b> ads · <b>{num(f.ads.long)}</b> running 30d+ · {num(f.ads.advertisers)} advertisers</> });
  if (f.demand) rows.push({ href: `${base}/demand`, icon: "🔎", label: "Search demand",
    body: f.demand.in_season.length ? <>in season: <b>{f.demand.in_season.join(", ")}</b></>
      : f.demand.next ? <>next: <b>{f.demand.next.term}</b>, start by {short(f.demand.next.start_by)}</> : <>{f.demand.terms} terms, nothing in season</> });
  if (f.paid) rows.push({ href: `${base}/paid`, icon: "💳", label: "Paid ads",
    body: f.paid.cap > 0 ? <><b>{usd(f.paid.spent)}</b> of {usd(f.paid.cap)} this month · {f.paid.running} running</> : <span className="text-viral">no monthly cap yet</span> });
  if (f.perf) rows.push({ href: `${base}/performance`, icon: "📊", label: "Your performance", body: <><b>{num(f.perf.records)}</b> of your posts and ads measured</> });
  if (p.saved || p.ideas) rows.push({ href: `${base}/swipe`, icon: "💡", label: "Ideas & swipe file", body: <><b>{num(p.saved)}</b> saved · {num(p.ideas)} idea notes</> });
  return (
    <ul className="mt-3 flex-1 divide-y divide-line border-t border-line text-sm">
      {rows.map((r) => (
        <li key={r.label}>
          <Link href={r.href} className="flex items-center gap-2 px-4 py-1.5 hover:bg-panel-2">
            <span aria-hidden>{r.icon}</span>
            <span className="w-32 shrink-0 text-xs text-muted">{r.label}</span>
            <span className="min-w-0 truncate text-xs">{r.body}</span>
            <span className="ml-auto text-muted">→</span>
          </Link>
        </li>
      ))}
      {p.top[0] && (
        <li className="truncate px-4 py-1.5 text-[11px] text-muted">
          Top video: <span className="text-text">{p.top[0].title}</span> · {times(p.top[0].outlier)} usual
        </li>
      )}
    </ul>
  );
}

