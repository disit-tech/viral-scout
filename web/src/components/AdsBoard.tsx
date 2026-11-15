"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import type { AdItem, AdsData } from "@/lib/types";
import { ago, num, when } from "@/lib/format";
import { LIBRARY, OFFER, SOURCE, SOURCE_SHORT, STUDY_RULE, adHref, competitorSearch, queryLabel, studyPicks } from "@/lib/ads";
import Link from "next/link";
import { More, Seg, Select, Stat } from "./FilterControls";

// ---------- filter state (kept in the URL, so a link reopens the same view) ----------

type View = "cards" | "table" | "groups";
type Sort = "score" | "days" | "variants" | "newest" | "oldest" | "reach" | "likes" | "advertiser";
type GroupBy = "advertiser" | "source" | "placement" | "offer" | "format" | "cta" | "domain" | "query" | "running" | "month" | "label";
type F = {
  q: string; src: string[]; status: "all" | "running" | "stopped"; minDays: number; format: string; offer: string;
  advertiser: string; found: "all" | "competitor" | "keyword"; newOnly: boolean; worth: boolean; hide: string[];
  view: View; group: GroupBy; sort: Sort; dir: "desc" | "asc";
};
const DEFAULT: F = {
  q: "", src: [], status: "all", minDays: 0, format: "all", offer: "all", advertiser: "all", found: "all",
  newOnly: false, worth: false, hide: [], view: "cards", group: "advertiser", sort: "score", dir: "desc",
};

function readUrl(): Partial<F> {
  if (typeof window === "undefined") return {};
  const p = new URLSearchParams(window.location.search);
  const out: Partial<F> = {};
  for (const k of Object.keys(DEFAULT) as (keyof F)[]) {
    const v = p.get(k);
    if (v === null) continue;
    const d = DEFAULT[k];
    if (Array.isArray(d)) (out as Record<string, unknown>)[k] = v ? v.split("|") : [];
    else if (typeof d === "number") (out as Record<string, unknown>)[k] = Number(v) || 0;
    else if (typeof d === "boolean") (out as Record<string, unknown>)[k] = v === "1";
    else (out as Record<string, unknown>)[k] = v;
  }
  return out;
}

function writeUrl(f: F) {
  const p = new URLSearchParams();
  for (const k of Object.keys(DEFAULT) as (keyof F)[]) {
    const v = f[k], d = DEFAULT[k];
    if (JSON.stringify(v) === JSON.stringify(d)) continue;
    p.set(k, Array.isArray(v) ? v.join("|") : typeof v === "boolean" ? (v ? "1" : "0") : String(v));
  }
  const qs = p.toString();
  window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
}

// ---------- derived values ----------

const runningBucket = (d: number | null) =>
  d === null ? "unknown start" : d < 7 ? "under 7 days" : d < 30 ? "7–30 days" : d < 60 ? "30–60 days 🏆" : d < 90 ? "60–90 days 🏆" : "90+ days 🏆";
const BUCKET_ORDER = ["90+ days 🏆", "60–90 days 🏆", "30–60 days 🏆", "7–30 days", "under 7 days", "unknown start"];

function groupKeys(a: AdItem, g: GroupBy): string[] {
  switch (g) {
    case "advertiser": return [a.advertiser || "Unknown advertiser"];
    case "source": return [SOURCE[a.source] ?? a.source];
    case "placement": return a.platforms.length ? a.platforms : ["unknown"];
    case "offer": return a.offers.length ? a.offers.map((o) => OFFER[o] ?? o) : ["no offer detected"];
    case "format": return [a.format || "unknown"];
    case "cta": return [a.cta || a.cta_text || "no CTA"];
    case "domain": return [a.landing_domain || "no landing domain"];
    case "query": return a.found_by.length ? a.found_by.map(queryLabel) : ["unknown"];
    case "running": return [runningBucket(a.days_running)];
    case "month": return [a.start ? a.start.slice(0, 7) : "unknown start"];
    case "label": return a.labels.length ? a.labels : ["no label"];
  }
}
const GROUP_LABEL: Record<GroupBy, string> = {
  advertiser: "Advertiser", source: "Platform", placement: "Placement", offer: "Offer", format: "Format", cta: "CTA",
  domain: "Landing domain", query: "Found by (search)", running: "Running time", month: "Start month", label: "Label",
};

const SORTERS: Record<Sort, (a: AdItem) => number | string> = {
  score: (a) => a.ad_score,
  days: (a) => a.days_running ?? -1,
  variants: (a) => a.variants,
  newest: (a) => (a.start ? new Date(a.start).getTime() : 0),
  oldest: (a) => (a.start ? -new Date(a.start).getTime() : -Infinity),
  reach: (a) => a.reach ?? -1,
  likes: (a) => a.likes ?? -1,
  advertiser: (a) => (a.advertiser || "").toLowerCase(),
};
function sortAds(list: AdItem[], sort: Sort, dir: "asc" | "desc") {
  const fn = SORTERS[sort];
  const m = dir === "desc" ? -1 : 1;
  return [...list].sort((x, y) => {
    const a = fn(x), b = fn(y);
    if (typeof a === "string" || typeof b === "string") return String(a).localeCompare(String(b)) * (sort === "advertiser" ? -m : m);
    return (a - b) * m;
  });
}

const csvCell = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""').replace(/\s+/g, " ")}"`;
function downloadCsv(name: string, ads: AdItem[]) {
  const cols: [string, (a: AdItem) => unknown][] = [
    ["score", (a) => Math.round(a.ad_score)], ["advertiser", (a) => a.advertiser], ["platform", (a) => SOURCE[a.source] ?? a.source],
    ["placements", (a) => a.platforms.join(" ")], ["status", (a) => (a.active ? "running" : "stopped")],
    ["days_running", (a) => (a.days_running === null ? "" : Math.round(a.days_running))], ["start", (a) => a.start?.slice(0, 10)],
    ["variants", (a) => a.variants], ["reach", (a) => a.reach], ["likes", (a) => a.likes], ["format", (a) => a.format],
    ["offers", (a) => a.offers.map((o) => OFFER[o] ?? o).join("; ")], ["cta", (a) => a.cta || a.cta_text],
    ["landing_domain", (a) => a.landing_domain], ["hook", (a) => a.hook], ["copy", (a) => a.body],
    ["found_by", (a) => a.found_by.map(queryLabel).join("; ")], ["labels", (a) => a.labels.join(" ")], ["url", (a) => a.url],
  ];
  const text = [cols.map((c) => c[0]).join(","), ...ads.map((a) => cols.map(([, fn]) => csvCell(fn(a))).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob(["﻿" + text], { type: "text/csv;charset=utf-8" }));
  const el = Object.assign(document.createElement("a"), { href: url, download: name });
  el.click();
  URL.revokeObjectURL(url);
}

// ---------- the board ----------

export default function AdsBoard({ data, profile = "ads" }: { data: AdsData; profile?: string }) {
  const [f, setF] = useState<F>(DEFAULT);
  const [ready, setReady] = useState(false);
  const [limit, setLimit] = useState(60);
  useEffect(() => { setF({ ...DEFAULT, ...readUrl() }); setReady(true); }, []);
  useEffect(() => { if (ready) writeUrl(f); }, [f, ready]);
  useEffect(() => { setLimit(60); }, [f]);
  const set = <K extends keyof F>(k: K, v: F[K]) => setF((x) => ({ ...x, [k]: v }));

  const sources = useMemo(() => {
    const c = new Map<string, number>();
    data.ads.forEach((a) => c.set(a.source, (c.get(a.source) ?? 0) + 1));
    return [...c.entries()].sort((a, b) => b[1] - a[1]);
  }, [data.ads]);
  const formats = useMemo(() => Array.from(new Set(data.ads.map((a) => a.format || "unknown"))).sort(), [data.ads]);
  const offers = useMemo(() => Array.from(new Set(data.ads.flatMap((a) => a.offers))).sort(), [data.ads]);
  const advertiserNames = useMemo(() => Array.from(new Set(data.ads.map((a) => a.advertiser || "Unknown advertiser"))).sort(), [data.ads]);
  const picks = useMemo(() => studyPicks(data.ads), [data.ads]);
  const bursts = useMemo(() => new Set(data.advertisers.filter((r) => r.launch_burst).map((r) => r.advertiser)), [data.advertisers]);

  // Every filter except the advertiser one: the advertiser table shows the alternatives under the other filters.
  const base = useMemo(() => {
    const needle = f.q.trim().toLowerCase();
    const hidden = new Set(f.hide);
    return data.ads.filter((a) =>
      (!f.src.length || f.src.includes(a.source)) &&
      (f.status === "all" || (f.status === "running" ? a.active : !a.active)) &&
      (!f.minDays || (a.days_running ?? 0) >= f.minDays) &&
      (f.format === "all" || (a.format || "unknown") === f.format) &&
      (f.offer === "all" || a.offers.includes(f.offer)) &&
      (f.found === "all" || (f.found === "competitor" ? competitorSearch(a) : !competitorSearch(a))) &&
      (!f.newOnly || a.new) &&
      (!f.worth || picks.has(a.key)) &&
      !hidden.has(a.advertiser || "Unknown advertiser") &&
      (!needle || `${a.advertiser} ${a.hook} ${a.title ?? ""} ${a.body ?? ""} ${a.landing_domain ?? ""} ${a.cta} ${a.found_by.join(" ")}`
        .toLowerCase().includes(needle)));
  }, [data.ads, f]);
  const list = useMemo(() => sortAds(f.advertiser === "all" ? base : base.filter((a) => (a.advertiser || "Unknown advertiser") === f.advertiser), f.sort, f.dir),
    [base, f.advertiser, f.sort, f.dir]);

  const active = (Object.keys(DEFAULT) as (keyof F)[]).filter((k) => !["view", "group", "sort", "dir"].includes(k) && JSON.stringify(f[k]) !== JSON.stringify(DEFAULT[k])).length;
  const stat = {
    shown: list.length, running: list.filter((a) => a.active).length,
    long: list.filter((a) => (a.days_running ?? 0) >= 30).length,
    advertisers: new Set(list.map((a) => a.advertiser)).size, fresh: list.filter((a) => a.new).length,
  };

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-5">
        <Stat label={`ads${active ? " (filtered)" : ""}`} value={`${num(stat.shown)}${active ? ` / ${num(data.ads.length)}` : ""}`} />
        <Stat label="still running" value={num(stat.running)} tone="text-above" />
        <Stat label="🏆 30d+ long-runners" value={num(stat.long)} tone="text-viral" />
        <Stat label="advertisers" value={num(stat.advertisers)} />
        <Stat label="new since last run" value={num(stat.fresh)} tone="text-rise" />
      </div>

      {/* filters */}
      <section className="sticky top-[57px] z-10 space-y-2.5 rounded-2xl border border-line bg-ink/95 p-3 backdrop-blur">
        <div className="flex flex-wrap items-center gap-2">
          <input value={f.q} onChange={(e) => set("q", e.target.value)} placeholder="Search advertiser, hook, copy, CTA, domain, query…"
            className="w-72 rounded-lg border border-line bg-panel px-3 py-1.5 text-sm outline-none focus:border-accent" />
          {sources.map(([s, n]) => {
            const on = f.src.includes(s);
            return (
              <button key={s} onClick={() => set("src", on ? f.src.filter((x) => x !== s) : [...f.src, s])}
                className={`rounded-full border px-3 py-1 text-xs ${on ? "border-accent bg-accent/15 text-accent" : "border-line text-muted hover:text-text"}`}>
                {SOURCE[s] ?? s} <span className="opacity-70">{n}</span>
              </button>
            );
          })}
          <Seg value={f.status} onChange={(v) => set("status", v)} options={[["all", "All"], ["running", "Running"], ["stopped", "Stopped"]]} />
          <Seg value={String(f.minDays)} onChange={(v) => set("minDays", Number(v))}
            options={[["0", "Any age"], ["7", "7d+"], ["30", "30d+"], ["60", "60d+"], ["90", "90d+"]]} />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Seg value={f.found} onChange={(v) => set("found", v)}
            options={[["all", "All searches"], ["competitor", "Competitor searches"], ["keyword", "Keyword / category"]]} />
          <Select value={f.advertiser} onChange={(v) => set("advertiser", v)} all="All advertisers" options={advertiserNames} />
          <Select value={f.format} onChange={(v) => set("format", v)} all="All formats" options={formats} />
          <Select value={f.offer} onChange={(v) => set("offer", v)} all="All offers" options={offers} labels={OFFER} />
          <label className="flex items-center gap-1.5 text-sm text-muted">
            <input type="checkbox" checked={f.newOnly} onChange={(e) => set("newOnly", e.target.checked)} /> New since last run
          </label>
          <label className="flex items-center gap-1.5 text-sm text-muted" title={STUDY_RULE}>
            <input type="checkbox" checked={f.worth} onChange={(e) => set("worth", e.target.checked)} /> <span className="text-viral">★</span> Worth studying ({picks.size})
          </label>
          {active > 0 && (
            <button onClick={() => setF({ ...DEFAULT, view: f.view, group: f.group, sort: f.sort, dir: f.dir })}
              className="text-xs text-rise hover:underline">Clear {active} filter{active > 1 ? "s" : ""}</button>
          )}
        </div>
        {f.hide.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
            Hidden:
            {f.hide.map((h) => (
              <button key={h} onClick={() => set("hide", f.hide.filter((x) => x !== h))}
                className="rounded-full border border-line px-2 py-0.5 hover:text-text" title="Show again">{h} ✕</button>
            ))}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2 border-t border-line pt-2.5">
          <Seg value={f.view} onChange={(v) => set("view", v)} options={[["cards", "▦ Cards"], ["table", "☰ Table"], ["groups", "⊞ Groups"]]} />
          {f.view === "groups" && (
            <label className="flex items-center gap-1.5 text-sm text-muted">Group by
              <select value={f.group} onChange={(e) => set("group", e.target.value as GroupBy)} className="rounded-lg border border-line bg-panel px-2 py-1.5 text-sm text-text">
                {(Object.keys(GROUP_LABEL) as GroupBy[]).map((g) => <option key={g} value={g}>{GROUP_LABEL[g]}</option>)}
              </select>
            </label>
          )}
          <label className="flex items-center gap-1.5 text-sm text-muted">Sort
            <select value={f.sort} onChange={(e) => set("sort", e.target.value as Sort)} className="rounded-lg border border-line bg-panel px-2 py-1.5 text-sm text-text">
              <option value="score">ad score</option><option value="days">days running</option><option value="variants">variants</option>
              <option value="newest">newest start</option><option value="oldest">oldest start</option><option value="reach">reach</option>
              <option value="likes">likes</option><option value="advertiser">advertiser A–Z</option>
            </select>
            <button onClick={() => set("dir", f.dir === "desc" ? "asc" : "desc")} className="rounded-lg border border-line px-2 py-1.5 text-text" title="Reverse">
              {f.dir === "desc" ? "↓" : "↑"}
            </button>
          </label>
          <span className="text-xs text-muted">{num(list.length)} shown</span>
          <button onClick={() => downloadCsv(`${profile}-ads.csv`, list)} className="ml-auto rounded-lg border border-line px-3 py-1.5 text-xs text-muted hover:text-text">
            ⬇ CSV ({num(list.length)})
          </button>
        </div>
      </section>

      <AdvertiserTable ads={base} selected={f.advertiser} bursts={bursts}
        onSelect={(a) => set("advertiser", f.advertiser === a ? "all" : a)}
        onHide={(a) => setF((x) => ({ ...x, hide: [...x.hide, a], advertiser: x.advertiser === a ? "all" : x.advertiser }))} />

      {list.length === 0 ? (
        <div className="rounded-xl border border-dashed border-line p-8 text-center text-muted">
          {data.ads.length ? "Nothing matches the filters." : "No ads collected in the last run. See the sources below: each skipped source says which key unlocks it."}
        </div>
      ) : f.view === "cards" ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {list.slice(0, limit).map((a) => <AdCard key={a.key} ad={a} profile={profile} worth={picks.has(a.key)} />)}
          </div>
          <More shown={Math.min(limit, list.length)} total={list.length} onMore={() => setLimit(limit + 60)} />
        </>
      ) : f.view === "table" ? (
        <>
          <AdsTable ads={list.slice(0, limit * 2)} sort={f.sort} dir={f.dir} profile={profile} picks={picks}
            onSort={(s) => setF((x) => ({ ...x, sort: s, dir: x.sort === s && x.dir === "desc" ? "asc" : "desc" }))} />
          <More shown={Math.min(limit * 2, list.length)} total={list.length} onMore={() => setLimit(limit + 60)} />
        </>
      ) : (
        <Groups ads={list} by={f.group} sort={f.sort} dir={f.dir} profile={profile} picks={picks}
          onFilter={f.group === "advertiser" ? (k) => set("advertiser", k) : undefined} />
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {data.offers.length > 0 && (
          <Panel title="Offers that keep running">
            <ul className="space-y-1">
              {data.offers.map((o) => (
                <li key={o.offer} className="flex justify-between gap-2">
                  <button onClick={() => set("offer", f.offer === o.offer ? "all" : o.offer)} className="text-left hover:text-text">{OFFER[o.offer] ?? o.offer}</button>
                  <span><b className="text-text">{o.ads}</b> ads · <span className="text-viral">{o.long_runners}</span> in 30d+ ads</span>
                </li>
              ))}
            </ul>
          </Panel>
        )}
        <Panel title="This ads run">
          <p>
            {num(data.ads.length)} ads from {data.coverage.length} ad librar{data.coverage.length === 1 ? "y" : "ies"} ·{" "}
            {data.skipped.length ? `${data.skipped.length} skipped` : "nothing skipped"} ·{" "}
            <span className={data.errors.length ? "text-mega" : ""}>{data.errors.length} error{data.errors.length === 1 ? "" : "s"}</span>
          </p>
          {data.budget?.map((b) => <p key={b} className="mt-2 text-viral">⚠️ {b}</p>)}
          <p className="mt-2 text-xs">
            <Link href={`/p/${profile}/runs#run-ads`} className="text-rise hover:underline">What it read, what it skipped and why, and what it used →</Link>
          </p>
        </Panel>
        {data.lookup.length > 0 && (
          <Panel title="Look them up yourself">
            <ul className="max-h-72 space-y-1.5 overflow-auto">
              {data.lookup.map((r) => (
                <li key={`${r.kind}:${r.label}`}>
                  <span className="text-text">{r.label}</span> <span className="text-xs">({r.kind})</span>:{" "}
                  {Object.entries(r.links).map(([k, v], i) => (
                    <span key={k}>{i > 0 && " · "}<a href={v} target="_blank" rel="noreferrer" className="text-rise underline">{k}</a></span>
                  ))}
                </li>
              ))}
            </ul>
          </Panel>
        )}
      </div>
      <p className="text-xs text-muted">
        Borrow angles (the problem, the offer type, the format), never creatives, copy or trademarks. Every claim in your
        own ads must be true and provable.
      </p>
    </div>
  );
}

// ---------- advertiser table (follows the filters) ----------

type AdvRow = {
  name: string; ads: number; running: number; longest: number | null; long: number; maxVariants: number;
  avgScore: number; sources: string[]; offers: [string, number][]; fresh: number; burst: boolean;
};
type AdvSort = "ads" | "running" | "longest" | "long" | "maxVariants" | "avgScore" | "fresh" | "name";

function AdvertiserTable({ ads, selected, bursts, onSelect, onHide }: {
  ads: AdItem[]; selected: string; bursts: Set<string>; onSelect: (a: string) => void; onHide: (a: string) => void;
}) {
  const [sort, setSort] = useState<AdvSort>("ads");
  const [asc, setAsc] = useState(false);
  const [q, setQ] = useState("");
  const [all, setAll] = useState(false);
  const [open, setOpen] = useState(false);
  const rows = useMemo(() => {
    const m = new Map<string, AdItem[]>();
    ads.forEach((a) => { const k = a.advertiser || "Unknown advertiser"; m.set(k, [...(m.get(k) ?? []), a]); });
    const out: AdvRow[] = [...m.entries()].map(([name, xs]) => {
      const offers = new Map<string, number>();
      xs.forEach((a) => a.offers.forEach((o) => offers.set(o, (offers.get(o) ?? 0) + 1)));
      const days = xs.map((a) => a.days_running).filter((d): d is number => d !== null);
      return {
        name, ads: xs.length, running: xs.filter((a) => a.active).length, longest: days.length ? Math.max(...days) : null,
        long: xs.filter((a) => (a.days_running ?? 0) >= 30).length, maxVariants: Math.max(...xs.map((a) => a.variants)),
        avgScore: xs.reduce((s, a) => s + a.ad_score, 0) / xs.length, sources: Array.from(new Set(xs.map((a) => a.source))),
        offers: [...offers.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3), fresh: xs.filter((a) => a.new).length,
        burst: bursts.has(name),
      };
    });
    const key = (r: AdvRow) => (sort === "name" ? r.name.toLowerCase() : sort === "longest" ? r.longest ?? -1 : r[sort]);
    return out.sort((a, b) => {
      const x = key(a), y = key(b);
      const c = typeof x === "string" ? String(x).localeCompare(String(y)) : (x as number) - (y as number);
      return asc ? c : -c;
    });
  }, [ads, sort, asc, bursts]);
  const needle = q.trim().toLowerCase();
  const shown = rows.filter((r) => !needle || r.name.toLowerCase().includes(needle));
  if (!rows.length) return null;
  const head = (k: AdvSort, label: string, cls = "") => (
    <th className={`cursor-pointer select-none px-3 py-2 hover:text-text ${cls}`} onClick={() => { if (sort === k) setAsc(!asc); else { setSort(k); setAsc(k === "name"); } }}>
      {label}{sort === k ? (asc ? " ↑" : " ↓") : ""}
    </th>
  );
  return (
    <section className="rounded-2xl border border-line bg-panel">
      <div className="flex flex-wrap items-center gap-2 px-3 py-3">
        <button onClick={() => setOpen(!open)} className="font-semibold hover:text-accent">
          {open ? "▾" : "▸"} Advertisers <span className="font-normal text-muted">({rows.length}, following the filters)</span>
        </button>
        {selected !== "all" && <span className="rounded-full bg-accent/15 px-2 py-0.5 text-xs text-accent">{selected}</span>}
        {open && <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find advertiser…"
          className="ml-auto w-48 rounded-lg border border-line bg-panel-2 px-2.5 py-1 text-sm outline-none focus:border-accent" />}
      </div>
      {open && (<>
      <div className="max-h-[28rem] overflow-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="sticky top-0 bg-panel-2 text-left text-xs uppercase tracking-wide text-muted">
            <tr>
              {head("name", "Advertiser")}<th className="px-3 py-2">On</th>{head("ads", "Ads")}{head("running", "Running")}
              {head("longest", "Longest")}{head("long", "30d+")}{head("maxVariants", "Max var.")}{head("avgScore", "Avg score")}
              <th className="px-3 py-2">Top offers</th>{head("fresh", "New")}<th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {(all || needle ? shown : shown.slice(0, 15)).map((r) => (
              <tr key={r.name} className={`cursor-pointer border-t border-line hover:bg-panel-2 ${selected === r.name ? "bg-accent/10" : ""}`} onClick={() => onSelect(r.name)}>
                <td className={`px-3 py-1.5 font-medium ${selected === r.name ? "text-accent" : ""}`}>{r.name}{r.burst ? " 🚀" : ""}</td>
                <td className="px-3 py-1.5">
                  <span className="flex gap-1">{r.sources.map((s) => <span key={s} title={SOURCE[s] ?? s} className="rounded bg-panel-2 px-1.5 text-[11px] text-muted">{SOURCE_SHORT[s] ?? s}</span>)}</span>
                </td>
                <td className="px-3 py-1.5">{r.ads}</td>
                <td className="px-3 py-1.5 text-above">{r.running}</td>
                <td className="px-3 py-1.5">{r.longest !== null ? `${Math.round(r.longest)} d` : "—"}</td>
                <td className="px-3 py-1.5 text-viral">{r.long || "—"}</td>
                <td className="px-3 py-1.5">{r.maxVariants}</td>
                <td className="px-3 py-1.5">{Math.round(r.avgScore)}</td>
                <td className="px-3 py-1.5 text-xs text-muted">{r.offers.map(([o, n]) => `${OFFER[o] ?? o} (${n})`).join(", ") || "—"}</td>
                <td className="px-3 py-1.5 text-rise">{r.fresh || "—"}</td>
                <td className="px-3 py-1.5 text-right">
                  <button onClick={(e) => { e.stopPropagation(); onHide(r.name); }} className="text-xs text-muted hover:text-mega" title="Hide this advertiser's ads">hide</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!needle && shown.length > 15 && (
        <button onClick={() => setAll(!all)} className="w-full border-t border-line py-2 text-xs text-rise hover:bg-panel-2">
          {all ? "Show top 15" : `Show all ${shown.length} advertisers`}
        </button>
      )}
      </>)}
    </section>
  );
}

// ---------- table view ----------

function AdsTable({ ads, sort, dir, onSort, profile, picks }: { ads: AdItem[]; sort: Sort; dir: "asc" | "desc"; onSort: (s: Sort) => void; profile: string; picks: Set<string> }) {
  const [open, setOpen] = useState<string | null>(null);
  const head = (s: Sort | null, label: string, cls = "") => (
    <th className={`px-2 py-2 ${s ? "cursor-pointer select-none hover:text-text" : ""} ${cls}`} onClick={s ? () => onSort(s) : undefined}>
      {label}{s && sort === s ? (dir === "desc" ? " ↓" : " ↑") : ""}
    </th>
  );
  return (
    <div className="overflow-x-auto rounded-2xl border border-line bg-panel">
      <table className="w-full min-w-[1100px] text-sm">
        <thead className="bg-panel-2 text-left text-xs uppercase tracking-wide text-muted">
          <tr>
            <th className="w-16 px-2 py-2" />{head("score", "Score")}{head("advertiser", "Advertiser")}{head(null, "Platform")}
            {head(null, "Status")}{head("days", "Days")}{head("newest", "Since")}{head("variants", "Var.")}{head("reach", "Reach")}
            {head(null, "Offer")}{head(null, "CTA")}{head(null, "Domain")}{head(null, "Hook", "w-[30%]")}
          </tr>
        </thead>
        <tbody>
          {ads.map((a) => (
            <Fragment key={a.key}>
              <tr className={`cursor-pointer border-t border-line align-top hover:bg-panel-2 ${a.active ? "" : "opacity-70"}`} onClick={() => setOpen(open === a.key ? null : a.key)}>
                <td className="px-2 py-1.5">
                  {a.image ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={a.image} alt="" loading="lazy" referrerPolicy="no-referrer" className="h-9 w-14 rounded object-cover" />
                  ) : <div className="flex h-9 w-14 items-center justify-center rounded bg-panel-2 text-[10px] uppercase text-muted">{a.format}</div>}
                </td>
                <td className="px-2 py-1.5 font-semibold text-accent">{Math.round(a.ad_score)}</td>
                <td className="max-w-[12rem] truncate px-2 py-1.5 font-medium" title={a.advertiser}>
                  <Link href={adHref(profile, a)} onClick={(e) => e.stopPropagation()} className="hover:text-accent hover:underline">{a.advertiser || "—"}</Link>
                  {picks.has(a.key) && <span className="ml-1 text-viral" title={STUDY_RULE}>★</span>}{a.new && <span className="ml-1 text-[10px] text-rise">new</span>}
                </td>
                <td className="px-2 py-1.5 text-xs text-muted">{SOURCE[a.source] ?? a.source}<div className="text-[10px]">{a.platforms.join(", ")}</div></td>
                <td className={`px-2 py-1.5 text-xs ${a.active ? "text-above" : "text-muted"}`}>{a.active ? "running" : "stopped"}</td>
                <td className={`px-2 py-1.5 ${(a.days_running ?? 0) >= 30 ? "text-viral" : ""}`}>{a.days_running !== null ? Math.round(a.days_running) : "—"}</td>
                <td className="px-2 py-1.5 text-xs text-muted">{a.start?.slice(0, 10) ?? "—"}</td>
                <td className={`px-2 py-1.5 ${a.variants >= 3 ? "text-mega" : ""}`}>{a.variants}</td>
                <td className="px-2 py-1.5 text-xs">{a.reach !== null ? num(a.reach) : a.likes ? `${num(a.likes)} ♥` : "—"}</td>
                <td className="px-2 py-1.5 text-xs text-muted">{a.offers.map((o) => OFFER[o] ?? o).join(", ") || "—"}</td>
                <td className="px-2 py-1.5 text-xs">{a.cta || a.cta_text || "—"}</td>
                <td className="max-w-[9rem] truncate px-2 py-1.5 text-xs text-muted" title={a.landing_domain}>{a.landing_domain || "—"}</td>
                <td className="px-2 py-1.5"><p className="line-clamp-2">{a.hook || a.title || <span className="text-muted">no copy</span>}</p></td>
              </tr>
              {open === a.key && (
                <tr className="border-t border-line bg-panel-2/50">
                  <td colSpan={13} className="px-4 py-3 text-xs text-muted">
                    <div className="flex flex-wrap gap-x-6 gap-y-1">
                      <span>Found by: {a.found_by.map(queryLabel).join("; ")}</span>
                      {a.last_seen && <span>Scanned {when(a.last_seen)} · first seen {when(a.first_seen ?? null)}</span>}
                      {a.labels.length > 0 && <span>Labels: {a.labels.join(" ")}</span>}
                      {a.offer_text && a.offer_text.length > 0 && <span>Offer text: {a.offer_text.slice(0, 4).join("; ")}</span>}
                      <Link href={adHref(profile, a)} className="text-rise underline">Full analysis →</Link>
                      {a.url && <a href={a.url} target="_blank" rel="noreferrer" className="text-rise underline">View in {LIBRARY[a.source] ?? "the ad library"} ↗</a>}
                    </div>
                    {a.body && <p className="mt-2 max-w-4xl whitespace-pre-line text-text">{a.body}</p>}
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------- groups view ----------

type GroupSort = "count" | "longest" | "score" | "name";

function Groups({ ads, by, sort, dir, onFilter, profile, picks }: {
  ads: AdItem[]; by: GroupBy; sort: Sort; dir: "asc" | "desc"; onFilter?: (k: string) => void; profile: string; picks: Set<string>;
}) {
  const [gsort, setGsort] = useState<GroupSort>(by === "running" ? "name" : "count");
  const [open, setOpen] = useState<Set<string>>(new Set());
  useEffect(() => { setGsort(by === "running" ? "name" : "count"); setOpen(new Set()); }, [by]);
  const groups = useMemo(() => {
    const m = new Map<string, AdItem[]>();
    ads.forEach((a) => groupKeys(a, by).forEach((k) => m.set(k, [...(m.get(k) ?? []), a])));
    const rows = [...m.entries()].map(([key, xs]) => {
      const days = xs.map((a) => a.days_running).filter((d): d is number => d !== null);
      return {
        key, ads: sortAds(xs, sort, dir), count: xs.length, running: xs.filter((a) => a.active).length,
        longest: days.length ? Math.max(...days) : null, long: xs.filter((a) => (a.days_running ?? 0) >= 30).length,
        best: Math.max(...xs.map((a) => a.ad_score)), advertisers: new Set(xs.map((a) => a.advertiser)).size,
        sources: Array.from(new Set(xs.map((a) => a.source))),
      };
    });
    if (by === "running" && gsort === "name") return rows.sort((a, b) => BUCKET_ORDER.indexOf(a.key) - BUCKET_ORDER.indexOf(b.key));
    if (by === "month" && gsort === "name") return rows.sort((a, b) => b.key.localeCompare(a.key));
    const k: Record<GroupSort, (r: (typeof rows)[number]) => number | string> = {
      count: (r) => r.count, longest: (r) => r.longest ?? -1, score: (r) => r.best, name: (r) => r.key.toLowerCase(),
    };
    return rows.sort((a, b) => {
      const x = k[gsort](a), y = k[gsort](b);
      return typeof x === "string" ? String(x).localeCompare(String(y)) : (y as number) - (x as number);
    });
  }, [ads, by, sort, dir, gsort]);
  const multi = ["placement", "offer", "query", "label"].includes(by);
  const toggle = (k: string) => setOpen((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n; });

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        <span>{groups.length} groups by {GROUP_LABEL[by].toLowerCase()}{multi ? " (an ad can be in several groups)" : ""} · order</span>
        <Seg value={gsort} onChange={(v) => setGsort(v)} options={[["count", "Most ads"], ["longest", "Longest run"], ["score", "Best score"], ["name", by === "running" || by === "month" ? "Natural" : "A–Z"]]} />
        <button onClick={() => setOpen(open.size ? new Set() : new Set(groups.slice(0, 10).map((g) => g.key)))} className="text-rise hover:underline">
          {open.size ? "Collapse all" : "Expand top 10"}
        </button>
      </div>
      {groups.map((g) => (
        <section key={g.key} className="rounded-2xl border border-line bg-panel">
          <button onClick={() => toggle(g.key)} className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5 text-left hover:bg-panel-2">
            <span className="min-w-[12rem] font-semibold">{open.has(g.key) ? "▾" : "▸"} {g.key}</span>
            <span className="text-sm"><b>{g.count}</b> <span className="text-muted">ads</span></span>
            <span className="text-sm text-above">{g.running} running</span>
            <span className="text-sm text-viral">{g.long ? `${g.long} × 30d+` : ""}</span>
            <span className="text-sm text-muted">longest {g.longest !== null ? `${Math.round(g.longest)} d` : "—"}</span>
            <span className="text-sm text-muted">best score {Math.round(g.best)}</span>
            {by !== "advertiser" && <span className="text-sm text-muted">{g.advertisers} advertiser{g.advertisers > 1 ? "s" : ""}</span>}
            <span className="ml-auto flex gap-1">{g.sources.map((s) => <span key={s} className="rounded bg-panel-2 px-1.5 text-[11px] text-muted">{SOURCE_SHORT[s] ?? s}</span>)}</span>
          </button>
          {open.has(g.key) && (
            <div className="border-t border-line p-3">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {g.ads.slice(0, 8).map((a) => <AdCard key={a.key} ad={a} profile={profile} worth={picks.has(a.key)} />)}
              </div>
              {g.ads.length > 8 && (
                <p className="mt-2 text-xs text-muted">
                  Top 8 of {g.ads.length} by the current sort.{" "}
                  {onFilter && <button onClick={() => onFilter(g.key)} className="text-rise hover:underline">Show all {g.ads.length} of {g.key}</button>}
                </p>
              )}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}

// ---------- small parts ----------

function AdCard({ ad, profile, worth = false }: { ad: AdItem; profile: string; worth?: boolean }) {
  const [open, setOpen] = useState(false);
  const long = (ad.days_running ?? 0) >= 30;
  return (
    <article className={`flex flex-col overflow-hidden rounded-2xl border bg-panel ${long ? "border-viral/40" : "border-line"} ${ad.active ? "" : "opacity-70"}`}>
      <Link href={adHref(profile, ad)} className="relative block aspect-video bg-panel-2" title="Open the full analysis">
        {ad.image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={ad.image} alt="" loading="lazy" referrerPolicy="no-referrer" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-1 px-4 text-center text-sm text-muted">
            <span className="text-xs uppercase tracking-wide">{ad.format || "ad"}</span>
            <span>No preview from this source. Open the analysis →</span>
          </div>
        )}
        <div className="absolute left-2 top-2 flex flex-wrap gap-1.5">
          <span className="rounded-full border border-accent bg-accent px-2 py-0.5 text-xs font-semibold text-ink">{Math.round(ad.ad_score)}</span>
          {ad.new && <span className="rounded-full border border-rise bg-rise px-2 py-0.5 text-xs font-semibold text-ink">new</span>}
          {worth && <span className="rounded-full border border-viral bg-ink/90 px-2 py-0.5 text-xs text-viral" title={STUDY_RULE}>★ study</span>}
          <span className={`rounded-full border px-2 py-0.5 text-xs ${ad.active ? "border-above bg-above text-ink" : "border-line bg-ink/90 text-muted"}`}>
            {ad.active ? "running" : "stopped"}
          </span>
        </div>
        <span className="absolute bottom-2 right-2 rounded bg-ink/80 px-1.5 py-0.5 text-[11px] text-muted">{SOURCE[ad.source] ?? ad.source} · {ad.format}</span>
      </Link>
      <div className="flex flex-1 flex-col gap-2.5 p-3.5">
        <div className="flex items-start gap-2">
          <p className="line-clamp-3 flex-1 font-medium leading-snug">{ad.hook || ad.title || <span className="text-muted">No ad copy from this source</span>}</p>
          {ad.url && <a href={ad.url} target="_blank" rel="noreferrer" className="text-muted hover:text-text" title={`View in ${LIBRARY[ad.source] ?? "the ad library"}`}>↗</a>}
        </div>
        <p className="truncate text-sm text-muted">{ad.advertiser || "Unknown advertiser"}{ad.landing_domain ? ` · ${ad.landing_domain}` : ""}</p>
        <dl className="grid grid-cols-3 gap-1.5 text-center">
          <Metric label="days running" value={ad.days_running !== null ? `${Math.round(ad.days_running)}` : "—"} tone={long ? "text-viral" : undefined} />
          <Metric label="variants" value={`${ad.variants}`} tone={ad.variants >= 3 ? "text-mega" : undefined} />
          {ad.reach === null && ad.likes ? <Metric label="likes" value={num(ad.likes)} /> : <Metric label={ad.reach_label || "reach"} value={num(ad.reach)} />}
        </dl>
        {ad.labels.length > 0 && (
          <div className="flex flex-wrap gap-1">{ad.labels.map((l) => <span key={l} className="rounded-full bg-panel-2 px-2 py-0.5 text-[11px]">{l}</span>)}</div>
        )}
        {ad.offers.length > 0 && (
          <p className="text-xs"><span className="text-muted">Offer:</span> {ad.offers.map((o) => OFFER[o] ?? o).join(", ")}
            {ad.offer_text && ad.offer_text.length > 0 && <span className="text-muted"> ({ad.offer_text.slice(0, 3).join("; ")})</span>}</p>
        )}
        <p className="text-xs text-muted">
          {(ad.cta || ad.cta_text) && <><span>CTA:</span> <span className="text-text">{ad.cta || ad.cta_text}</span> · </>}
          {ad.platforms.length > 0 ? ad.platforms.join(", ") : "platforms unknown"}
          {ad.start && <> · since {ad.start.slice(0, 10)}</>}
        </p>
        <p className="truncate text-[11px] text-muted" title={ad.found_by.map(queryLabel).join("; ")}>Found by: {ad.found_by.map(queryLabel).join("; ")}</p>
        {(ad.last_seen || ad.first_seen) && (
          <p className="text-[11px] text-muted" title={`Last scanned ${when(ad.last_seen ?? null)} · first seen ${when(ad.first_seen ?? null)}`}>
            🕒 Scanned <b suppressHydrationWarning className="font-medium text-text/80">{ago(ad.last_seen ?? ad.first_seen)}</b>
            {ad.first_seen && ad.first_seen !== ad.last_seen && <> · first seen {when(ad.first_seen)}</>}
          </p>
        )}
        {ad.body && ad.body !== ad.hook && (
          <button onClick={() => setOpen(!open)} className="mt-auto text-left text-xs text-rise hover:underline">
            {open ? "Hide ad copy" : "Show ad copy"}
          </button>
        )}
        {open && <p className="whitespace-pre-line text-xs text-muted">{ad.body}</p>}
        <div className={`${ad.body && ad.body !== ad.hook ? "" : "mt-auto "}flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-t border-line pt-2.5 text-xs`}>
          <Link href={adHref(profile, ad)} className="font-medium text-accent hover:underline">Full analysis →</Link>
          {ad.url && (
            <a href={ad.url} target="_blank" rel="noreferrer" className="text-rise hover:underline"
              title="The ad's public page in its library: the creative as it runs, its dates and where it shows">
              View in {LIBRARY[ad.source] ?? "the ad library"} ↗
            </a>
          )}
        </div>
      </div>
    </article>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg bg-panel-2 px-1 py-1.5">
      <dt className="truncate text-[10px] uppercase tracking-wide text-muted">{label}</dt>
      <dd className={`text-sm font-semibold ${tone ?? "text-text"}`}>{value}</dd>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-panel p-4 text-sm text-muted">
      <h3 className="mb-2 font-semibold text-text">{title}</h3>
      {children}
    </section>
  );
}
