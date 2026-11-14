"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Item } from "@/lib/types";
import { age, ago, num, tier, times, when } from "@/lib/format";
import { PLATFORM, creatorName, firstSeen, foundLabel, lastScanned, reach } from "@/lib/posts";
import PostCard from "./PostCard";
import { More, Seg, Select, Stat, downloadCsv, readUrl, writeUrl } from "./FilterControls";

// ---------- filter state (kept in the URL, shared by the Outliers / Fastest / Rising / Tracked / Your posts tabs) ----------

type View = "cards" | "table" | "groups";
type Sort = "rank" | "outlier" | "views" | "per_day" | "rise" | "engagement" | "comments" | "followers"
  | "newest" | "oldest" | "found" | "scanned" | "duration" | "creator";
type GroupBy = "creator" | "platform" | "found_by" | "tier" | "posted" | "month" | "found_day" | "scanned_day" | "duration" | "size";
type F = {
  q: string; plat: string[]; minTier: "all" | "above" | "viral" | "mega"; maxAge: number; minViews: number;
  seenWithin: number; found: string; creator: string; newOnly: boolean; hideSaved: boolean; emerging: boolean;
  hasHook: boolean; hide: string[]; view: View; group: GroupBy; sort: Sort; dir: "desc" | "asc";
};
const DEFAULT: F = {
  q: "", plat: [], minTier: "all", maxAge: 0, minViews: 0, seenWithin: 0, found: "all", creator: "all",
  newOnly: false, hideSaved: false, emerging: false, hasHook: false, hide: [],
  view: "cards", group: "creator", sort: "rank", dir: "desc",
};
const LAYOUT_KEYS = ["view", "group", "sort", "dir"];

const TIER_RANK = { all: 0, above: 1.5, viral: 3, mega: 10 } as const;
const DAY = 864e5;
const daysSince = (iso: string | null) => (iso ? (Date.now() - new Date(iso).getTime()) / DAY : null);

const ageBucket = (d: number | null) =>
  d === null ? "unknown date" : d < 1 ? "last 24 h" : d < 7 ? "1–7 days" : d < 30 ? "7–30 days" : d < 90 ? "30–90 days" : "90+ days";
const AGE_ORDER = ["last 24 h", "1–7 days", "7–30 days", "30–90 days", "90+ days", "unknown date"];
const durBucket = (s: number | null | undefined) =>
  !s ? "unknown length" : s < 15 ? "under 15 s" : s < 30 ? "15–30 s" : s < 60 ? "30–60 s" : s < 180 ? "1–3 min" : "3 min+";
const DUR_ORDER = ["under 15 s", "15–30 s", "30–60 s", "1–3 min", "3 min+", "unknown length"];
const sizeBucket = (f: number | null) =>
  f === null ? "followers unknown" : f < 1e4 ? "under 10K followers" : f < 1e5 ? "10K–100K" : f < 1e6 ? "100K–1M" : "1M+ followers";
const SIZE_ORDER = ["under 10K followers", "10K–100K", "100K–1M", "1M+ followers", "followers unknown"];
const TIER_ORDER = ["🔥 mega (10×+)", "⚡ viral (3–10×)", "↑ above (1.5–3×)", "usual or below", "no baseline"];
const tierLabel = (o: number | null) =>
  o === null ? "no baseline" : o >= 10 ? TIER_ORDER[0] : o >= 3 ? TIER_ORDER[1] : o >= 1.5 ? TIER_ORDER[2] : TIER_ORDER[3];
const day = (iso: string | null) => (iso ? iso.slice(0, 10) : "unknown");

function groupKeys(i: Item, g: GroupBy, run: string | null): string[] {
  switch (g) {
    case "creator": return [creatorName(i)];
    case "platform": return [PLATFORM[i.platform] ?? i.platform];
    case "found_by": return i.found_by.length ? i.found_by.map(foundLabel) : ["unknown"];
    case "tier": return [tierLabel(i.outlier)];
    case "posted": return [ageBucket(daysSince(i.published))];
    case "month": return [i.published ? i.published.slice(0, 7) : "unknown date"];
    case "found_day": return [day(firstSeen(i))];
    case "scanned_day": return [day(lastScanned(i, run))];
    case "duration": return [durBucket(i.duration)];
    case "size": return [sizeBucket(i.followers)];
  }
}
const GROUP_LABEL: Record<GroupBy, string> = {
  creator: "Creator", platform: "Platform", found_by: "Found by (search)", tier: "Outlier tier", posted: "Posted (age)",
  month: "Posted month", found_day: "First seen (day)", scanned_day: "Last scanned (day)", duration: "Length", size: "Creator size",
};
const NATURAL: Partial<Record<GroupBy, (a: string, b: string) => number>> = {
  tier: (a, b) => TIER_ORDER.indexOf(a) - TIER_ORDER.indexOf(b),
  posted: (a, b) => AGE_ORDER.indexOf(a) - AGE_ORDER.indexOf(b),
  duration: (a, b) => DUR_ORDER.indexOf(a) - DUR_ORDER.indexOf(b),
  size: (a, b) => SIZE_ORDER.indexOf(a) - SIZE_ORDER.indexOf(b),
  month: (a, b) => b.localeCompare(a), found_day: (a, b) => b.localeCompare(a), scanned_day: (a, b) => b.localeCompare(a),
};

const SORT_LABEL: Record<Sort, string> = {
  rank: "tab order", outlier: "× usual", views: "views", per_day: "views per day", rise: "rise per day", engagement: "engagement",
  comments: "comments", followers: "followers", newest: "newest post", oldest: "oldest post", found: "first seen", scanned: "last scanned",
  duration: "length", creator: "creator A–Z",
};
const ts = (iso: string | null) => (iso ? new Date(iso).getTime() : 0);
function sorter(sort: Sort, rank: Map<string, number>, run: string | null): (i: Item) => number | string {
  switch (sort) {
    case "rank": return (i) => -(rank.get(i.key) ?? 1e9);
    case "outlier": return (i) => i.outlier ?? -1;
    case "views": return (i) => reach(i) ?? -1;
    case "per_day": return (i) => i.per_day ?? -1;
    case "rise": return (i) => i.rise_per_day ?? -1;
    case "engagement": return (i) => i.engagement ?? -1;
    case "comments": return (i) => i.comments ?? -1;
    case "followers": return (i) => i.followers ?? -1;
    case "newest": return (i) => ts(i.published);
    case "oldest": return (i) => (i.published ? -ts(i.published) : -Infinity);
    case "found": return (i) => ts(firstSeen(i));
    case "scanned": return (i) => ts(lastScanned(i, run));
    case "duration": return (i) => i.duration ?? -1;
    case "creator": return (i) => creatorName(i).toLowerCase();
  }
}
function sortPosts(list: Item[], sort: Sort, dir: "asc" | "desc", rank: Map<string, number>, run: string | null) {
  const fn = sorter(sort, rank, run);
  const m = dir === "desc" ? -1 : 1;
  return [...list].sort((x, y) => {
    const a = fn(x), b = fn(y);
    if (typeof a === "string" || typeof b === "string") return String(a).localeCompare(String(b)) * -m;
    return (a - b) * m;
  });
}

const pct = (v: number | null) => (v === null ? "—" : `${(v * 100).toFixed(v < 0.1 ? 1 : 0)}%`);

// ---------- the board ----------

export default function PostsBoard({ items, profile, local, run, onChange, empty }: {
  items: Item[];                 // the tab's posts, in the tab's own order (that order is the "tab order" sort)
  profile: string; local: boolean; run: string | null;
  onChange: (key: string, patch: Partial<Item>) => void; empty: React.ReactNode;
}) {
  const [f, setF] = useState<F>(DEFAULT);
  const [ready, setReady] = useState(false);
  const [limit, setLimit] = useState(60);
  useEffect(() => { setF({ ...DEFAULT, ...readUrl(DEFAULT) }); setReady(true); }, []);
  useEffect(() => { if (ready) writeUrl(f, DEFAULT); }, [f, ready]);
  useEffect(() => { setLimit(60); }, [f, items]);
  const set = <K extends keyof F>(k: K, v: F[K]) => setF((x) => ({ ...x, [k]: v }));

  const rank = useMemo(() => new Map(items.map((i, n) => [i.key, n])), [items]);
  const platforms = useMemo(() => {
    const c = new Map<string, number>();
    items.forEach((i) => c.set(i.platform, (c.get(i.platform) ?? 0) + 1));
    return [...c.entries()].sort((a, b) => b[1] - a[1]);
  }, [items]);
  const searches = useMemo(() => Array.from(new Set(items.flatMap((i) => i.found_by))).sort(), [items]);
  const creators = useMemo(() => Array.from(new Set(items.map(creatorName))).sort((a, b) => a.localeCompare(b)), [items]);

  // Every filter except the creator one: the creator table shows the alternatives under the other filters.
  const base = useMemo(() => {
    const needle = f.q.trim().toLowerCase();
    const hidden = new Set(f.hide);
    return items.filter((i) =>
      (!f.plat.length || f.plat.includes(i.platform)) &&
      (f.minTier === "all" || (i.outlier ?? 0) >= TIER_RANK[f.minTier]) &&
      (!f.maxAge || (daysSince(i.published) ?? Infinity) <= f.maxAge) &&
      (!f.minViews || (reach(i) ?? 0) >= f.minViews) &&
      (!f.seenWithin || (daysSince(firstSeen(i)) ?? Infinity) <= f.seenWithin) &&
      (f.found === "all" || i.found_by.includes(f.found)) &&
      (!f.newOnly || i.new) && (!f.hideSaved || !i.saved) && (!f.emerging || i.emerging) && (!f.hasHook || i.hook) &&
      !hidden.has(creatorName(i)) &&
      (!needle || `${i.title} ${i.channel} ${i.hook ?? ""} ${i.cta ?? ""} ${i.description ?? ""} ${i.found_by.join(" ")}`
        .toLowerCase().includes(needle)));
  }, [items, f]);
  const list = useMemo(() => sortPosts(f.creator === "all" ? base : base.filter((i) => creatorName(i) === f.creator), f.sort, f.dir, rank, run),
    [base, f.creator, f.sort, f.dir, rank, run]);

  const active = (Object.keys(DEFAULT) as (keyof F)[]).filter((k) => !LAYOUT_KEYS.includes(k) && JSON.stringify(f[k]) !== JSON.stringify(DEFAULT[k])).length;
  const scans = list.map((i) => lastScanned(i, run)).filter((x): x is string => Boolean(x)).sort();
  const stat = {
    shown: list.length, viral: list.filter((i) => (i.outlier ?? 0) >= 3).length,
    creators: new Set(list.map(creatorName)).size, fresh: list.filter((i) => i.new).length,
    scanned: scans.length ? scans[scans.length - 1] : run,
  };

  if (!items.length) return <>{empty}</>;

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-5">
        <Stat label={`posts${active ? " (filtered)" : ""}`} value={`${num(stat.shown)}${active ? ` / ${num(items.length)}` : ""}`} />
        <Stat label="⚡ 3×+ usual" value={num(stat.viral)} tone="text-viral" />
        <Stat label="creators" value={num(stat.creators)} />
        <Stat label="new since last run" value={num(stat.fresh)} tone="text-rise" />
        <Stat label={`last scanned · ${when(stat.scanned)}`} value={ago(stat.scanned)} tone="text-above" />
      </div>

      <section className="sticky top-[57px] z-10 space-y-2.5 rounded-2xl border border-line bg-ink/95 p-3 backdrop-blur">
        <div className="flex flex-wrap items-center gap-2">
          <input value={f.q} onChange={(e) => set("q", e.target.value)} placeholder="Search title, creator, hook, caption, search…"
            className="w-72 rounded-lg border border-line bg-panel px-3 py-1.5 text-sm outline-none focus:border-accent" />
          {platforms.map(([p, n]) => {
            const on = f.plat.includes(p);
            return (
              <button key={p} onClick={() => set("plat", on ? f.plat.filter((x) => x !== p) : [...f.plat, p])}
                className={`rounded-full border px-3 py-1 text-xs ${on ? "border-accent bg-accent/15 text-accent" : "border-line text-muted hover:text-text"}`}>
                {PLATFORM[p] ?? p} <span className="opacity-70">{n}</span>
              </button>
            );
          })}
          <Seg value={f.minTier} onChange={(v) => set("minTier", v)}
            options={[["all", "Any ×"], ["above", "1.5×+"], ["viral", "3×+"], ["mega", "10×+"]]} />
          <Seg value={String(f.minViews)} onChange={(v) => set("minViews", Number(v))}
            options={[["0", "Any views"], ["10000", "10K+"], ["100000", "100K+"], ["1000000", "1M+"]]} />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-muted">Posted
            <Seg value={String(f.maxAge)} onChange={(v) => set("maxAge", Number(v))}
              options={[["0", "Any time"], ["1", "24 h"], ["7", "7 d"], ["30", "30 d"], ["90", "90 d"]]} />
          </label>
          <label className="flex items-center gap-1.5 text-xs text-muted">First seen
            <Seg value={String(f.seenWithin)} onChange={(v) => set("seenWithin", Number(v))}
              options={[["0", "Any time"], ["1", "24 h"], ["3", "3 d"], ["7", "7 d"], ["30", "30 d"]]} />
          </label>
          <Select value={f.creator} onChange={(v) => set("creator", v)} all="All creators" options={creators} />
          <Select value={f.found} onChange={(v) => set("found", v)} all="All searches" options={searches}
            labels={Object.fromEntries(searches.map((s) => [s, foundLabel(s)]))} />
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <Check on={f.newOnly} onChange={(v) => set("newOnly", v)}>New since last run</Check>
          <Check on={f.hideSaved} onChange={(v) => set("hideSaved", v)}>Hide saved</Check>
          <Check on={f.emerging} onChange={(v) => set("emerging", v)}>🌱 Emerging creators</Check>
          <Check on={f.hasHook} onChange={(v) => set("hasHook", v)}>Has a hook / transcript</Check>
          {active > 0 && (
            <button onClick={() => setF({ ...DEFAULT, view: f.view, group: f.group, sort: f.sort, dir: f.dir })}
              className="text-xs text-rise hover:underline">Clear {active} filter{active > 1 ? "s" : ""}</button>
          )}
          {!local && <span className="text-xs text-muted">Read-only: buttons copy the command to run on your PC.</span>}
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
              {(Object.keys(SORT_LABEL) as Sort[]).map((s) => <option key={s} value={s}>{SORT_LABEL[s]}</option>)}
            </select>
            <button onClick={() => set("dir", f.dir === "desc" ? "asc" : "desc")} className="rounded-lg border border-line px-2 py-1.5 text-text" title="Reverse">
              {f.dir === "desc" ? "↓" : "↑"}
            </button>
          </label>
          <span className="text-xs text-muted">{num(list.length)} shown</span>
          <button onClick={() => downloadCsv(`${profile}-posts.csv`, list, csvCols(run))} className="ml-auto rounded-lg border border-line px-3 py-1.5 text-xs text-muted hover:text-text">
            ⬇ CSV ({num(list.length)})
          </button>
        </div>
      </section>

      <CreatorTable posts={base} selected={f.creator}
        onSelect={(c) => set("creator", f.creator === c ? "all" : c)}
        onHide={(c) => setF((x) => ({ ...x, hide: [...x.hide, c], creator: x.creator === c ? "all" : x.creator }))} />

      {list.length === 0 ? (
        <div className="rounded-xl border border-dashed border-line p-8 text-center text-muted">Nothing matches the filters.</div>
      ) : f.view === "cards" ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {list.slice(0, limit).map((i) => <PostCard key={i.key} item={i} profile={profile} local={local} run={run} onChange={onChange} />)}
          </div>
          <More shown={Math.min(limit, list.length)} total={list.length} onMore={() => setLimit(limit + 60)} />
        </>
      ) : f.view === "table" ? (
        <>
          <PostsTable posts={list.slice(0, limit * 2)} sort={f.sort} dir={f.dir} profile={profile} run={run}
            onSort={(s) => setF((x) => ({ ...x, sort: s, dir: x.sort === s && x.dir === "desc" ? "asc" : "desc" }))} />
          <More shown={Math.min(limit * 2, list.length)} total={list.length} onMore={() => setLimit(limit + 60)} />
        </>
      ) : (
        <Groups posts={list} by={f.group} profile={profile} local={local} run={run} onChange={onChange}
          onFilter={f.group === "creator" ? (k) => set("creator", k) : undefined} />
      )}
    </div>
  );
}

function csvCols(run: string | null): [string, (i: Item) => unknown][] {
  return [
    ["outlier", (i) => i.outlier?.toFixed(2)], ["title", (i) => i.title], ["creator", (i) => i.channel], ["followers", (i) => i.followers],
    ["platform", (i) => PLATFORM[i.platform] ?? i.platform], ["views", (i) => i.views], ["likes", (i) => i.likes], ["comments", (i) => i.comments],
    ["per_day", (i) => (i.per_day === null ? "" : Math.round(i.per_day))], ["rise_per_day", (i) => (i.rise_per_day === null ? "" : Math.round(i.rise_per_day))],
    ["engagement", (i) => i.engagement?.toFixed(4)], ["duration_s", (i) => i.duration], ["published", (i) => i.published?.slice(0, 10)],
    ["first_seen", (i) => firstSeen(i)], ["last_scanned", (i) => lastScanned(i, run)], ["scans", (i) => i.history.length],
    ["hook", (i) => i.hook], ["cta", (i) => i.cta], ["found_by", (i) => i.found_by.join("; ")],
    ["saved", (i) => (i.saved ? "yes" : "")], ["new", (i) => (i.new ? "yes" : "")], ["url", (i) => i.url],
  ];
}

// ---------- creator table (follows the filters) ----------

type CRow = { name: string; posts: number; best: number | null; avg: number | null; views: number; followers: number | null; newest: string | null; fresh: number; platforms: string[]; url: string };
type CSort = "posts" | "best" | "avg" | "views" | "followers" | "newest" | "fresh" | "name";

function CreatorTable({ posts, selected, onSelect, onHide }: {
  posts: Item[]; selected: string; onSelect: (c: string) => void; onHide: (c: string) => void;
}) {
  const [sort, setSort] = useState<CSort>("posts");
  const [asc, setAsc] = useState(false);
  const [q, setQ] = useState("");
  const [all, setAll] = useState(false);
  const [open, setOpen] = useState(false);
  const rows = useMemo(() => {
    const m = new Map<string, Item[]>();
    posts.forEach((i) => { const k = creatorName(i); m.set(k, [...(m.get(k) ?? []), i]); });
    const out: CRow[] = [...m.entries()].map(([name, xs]) => {
      const o = xs.map((i) => i.outlier).filter((v): v is number => v !== null);
      const f = xs.map((i) => i.followers).filter((v): v is number => v !== null);
      const pub = xs.map((i) => i.published).filter((v): v is string => Boolean(v)).sort();
      return {
        name, posts: xs.length, best: o.length ? Math.max(...o) : null, avg: o.length ? o.reduce((s, v) => s + v, 0) / o.length : null,
        views: xs.reduce((s, i) => s + (reach(i) ?? 0), 0), followers: f.length ? Math.max(...f) : null,
        newest: pub.length ? pub[pub.length - 1] : null, fresh: xs.filter((i) => i.new).length,
        platforms: Array.from(new Set(xs.map((i) => i.platform))), url: xs.find((i) => i.channel_url)?.channel_url ?? "",
      };
    });
    const key = (r: CRow): number | string =>
      sort === "name" ? r.name.toLowerCase() : sort === "newest" ? ts(r.newest) : (r[sort] as number | null) ?? -1;
    return out.sort((a, b) => {
      const x = key(a), y = key(b);
      const c = typeof x === "string" ? String(x).localeCompare(String(y)) : (x as number) - (y as number);
      return asc ? c : -c;
    });
  }, [posts, sort, asc]);
  const needle = q.trim().toLowerCase();
  const shown = rows.filter((r) => !needle || r.name.toLowerCase().includes(needle));
  if (rows.length < 2) return null;
  const head = (k: CSort, label: string) => (
    <th className="cursor-pointer select-none px-3 py-2 hover:text-text" onClick={() => { if (sort === k) setAsc(!asc); else { setSort(k); setAsc(k === "name"); } }}>
      {label}{sort === k ? (asc ? " ↑" : " ↓") : ""}
    </th>
  );
  return (
    <section className="rounded-2xl border border-line bg-panel">
      <div className="flex flex-wrap items-center gap-2 px-3 py-3">
        <button onClick={() => setOpen(!open)} className="font-semibold hover:text-accent">
          {open ? "▾" : "▸"} Creators <span className="font-normal text-muted">({rows.length}, following the filters)</span>
        </button>
        {selected !== "all" && <span className="rounded-full bg-accent/15 px-2 py-0.5 text-xs text-accent">{selected}</span>}
        {open && <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find creator…"
          className="ml-auto w-48 rounded-lg border border-line bg-panel-2 px-2.5 py-1 text-sm outline-none focus:border-accent" />}
      </div>
      {open && (
        <>
          <div className="max-h-[28rem] overflow-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="sticky top-0 bg-panel-2 text-left text-xs uppercase tracking-wide text-muted">
                <tr>
                  {head("name", "Creator")}<th className="px-3 py-2">On</th>{head("posts", "Posts")}{head("best", "Best ×")}{head("avg", "Avg ×")}
                  {head("views", "Views (sum)")}{head("followers", "Followers")}{head("newest", "Newest post")}{head("fresh", "New")}<th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {(all || needle ? shown : shown.slice(0, 15)).map((r) => (
                  <tr key={r.name} className={`cursor-pointer border-t border-line hover:bg-panel-2 ${selected === r.name ? "bg-accent/10" : ""}`} onClick={() => onSelect(r.name)}>
                    <td className={`max-w-[16rem] truncate px-3 py-1.5 font-medium ${selected === r.name ? "text-accent" : ""}`}>
                      {r.name}
                      {r.url && <a href={r.url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="ml-1 text-muted hover:text-text">↗</a>}
                    </td>
                    <td className="px-3 py-1.5 text-xs text-muted">{r.platforms.map((p) => PLATFORM[p] ?? p).join(", ")}</td>
                    <td className="px-3 py-1.5">{r.posts}</td>
                    <td className={`px-3 py-1.5 ${tier(r.best) ? "text-viral" : ""}`}>{times(r.best)}</td>
                    <td className="px-3 py-1.5">{times(r.avg)}</td>
                    <td className="px-3 py-1.5">{num(r.views)}</td>
                    <td className="px-3 py-1.5">{num(r.followers)}</td>
                    <td className="px-3 py-1.5 text-xs text-muted">{r.newest ? `${age(r.newest)} ago` : "—"}</td>
                    <td className="px-3 py-1.5 text-rise">{r.fresh || "—"}</td>
                    <td className="px-3 py-1.5 text-right">
                      <button onClick={(e) => { e.stopPropagation(); onHide(r.name); }} className="text-xs text-muted hover:text-mega" title="Hide this creator's posts">hide</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!needle && shown.length > 15 && (
            <button onClick={() => setAll(!all)} className="w-full border-t border-line py-2 text-xs text-rise hover:bg-panel-2">
              {all ? "Show top 15" : `Show all ${shown.length} creators`}
            </button>
          )}
        </>
      )}
    </section>
  );
}

// ---------- table view ----------

function PostsTable({ posts, sort, dir, onSort, profile, run }: {
  posts: Item[]; sort: Sort; dir: "asc" | "desc"; onSort: (s: Sort) => void; profile: string; run: string | null;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const head = (s: Sort | null, label: string, cls = "") => (
    <th className={`px-2 py-2 ${s ? "cursor-pointer select-none hover:text-text" : ""} ${cls}`} onClick={s ? () => onSort(s) : undefined}>
      {label}{s && sort === s ? (dir === "desc" ? " ↓" : " ↑") : ""}
    </th>
  );
  return (
    <div className="overflow-x-auto rounded-2xl border border-line bg-panel">
      <table className="w-full min-w-[1150px] text-sm">
        <thead className="bg-panel-2 text-left text-xs uppercase tracking-wide text-muted">
          <tr>
            <th className="w-16 px-2 py-2" />{head("outlier", "× usual")}{head(null, "Title", "w-[28%]")}{head("creator", "Creator")}
            {head("views", "Views")}{head("per_day", "/day")}{head("rise", "Rise/day")}{head("engagement", "Eng.")}{head("duration", "Len")}
            {head("newest", "Posted")}{head("found", "First seen")}{head("scanned", "Scanned")}
          </tr>
        </thead>
        <tbody>
          {posts.map((i) => {
            const t = tier(i.outlier);
            const scanned = lastScanned(i, run);
            return (
              <Fragment key={i.key}>
                <tr className={`cursor-pointer border-t border-line align-top hover:bg-panel-2 ${i.dismissed ? "opacity-50" : ""}`} onClick={() => setOpen(open === i.key ? null : i.key)}>
                  <td className="px-2 py-1.5">
                    {i.thumbnail ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={i.thumbnail} alt="" loading="lazy" className="h-9 w-14 rounded object-cover" />
                    ) : <div className="flex h-9 w-14 items-center justify-center rounded bg-panel-2 text-[10px] text-muted">{PLATFORM[i.platform] ?? i.platform}</div>}
                  </td>
                  <td className={`px-2 py-1.5 font-semibold ${t ? { mega: "text-mega", viral: "text-viral", above: "text-above" }[t] : ""}`}>{times(i.outlier)}</td>
                  <td className="px-2 py-1.5">
                    <Link href={`/p/${profile}/v/${encodeURIComponent(i.id)}`} onClick={(e) => e.stopPropagation()} className="line-clamp-2 hover:text-accent hover:underline">{i.title || i.id}</Link>
                    <span className="text-[10px] text-muted">{PLATFORM[i.platform] ?? i.platform}</span>
                    {i.new && <span className="ml-1 text-[10px] text-rise">new</span>}{i.saved && <span className="ml-1 text-[10px] text-above">saved</span>}
                  </td>
                  <td className="max-w-[11rem] truncate px-2 py-1.5 text-muted" title={i.channel}>{i.channel}<div className="text-[10px]">{i.followers ? `${num(i.followers)} followers` : ""}</div></td>
                  <td className="px-2 py-1.5">{num(reach(i))}{i.views === null && i.likes !== null ? " ♥" : ""}</td>
                  <td className="px-2 py-1.5">{num(i.per_day)}</td>
                  <td className={`px-2 py-1.5 ${i.rise_per_day ? "text-rise" : ""}`}>{i.rise_per_day ? `+${num(i.rise_per_day)}` : "—"}</td>
                  <td className="px-2 py-1.5 text-xs">{pct(i.engagement)}</td>
                  <td className="px-2 py-1.5 text-xs text-muted">{i.duration ? `${Math.round(i.duration)}s` : "—"}</td>
                  <td className="px-2 py-1.5 text-xs text-muted" title={i.published ?? ""}>{i.published ? `${age(i.published)} ago` : "—"}</td>
                  <td className="px-2 py-1.5 text-xs text-muted" title={firstSeen(i) ?? ""}>{when(firstSeen(i))}</td>
                  <td suppressHydrationWarning className="px-2 py-1.5 text-xs text-muted" title={`${when(scanned)} · ${i.history.length} scan${i.history.length === 1 ? "" : "s"}`}>{ago(scanned)}</td>
                </tr>
                {open === i.key && (
                  <tr className="border-t border-line bg-panel-2/50">
                    <td colSpan={12} className="px-4 py-3 text-xs text-muted">
                      <div className="flex flex-wrap gap-x-6 gap-y-1">
                        <span>Found by: {i.found_by.map(foundLabel).join("; ")}</span>
                        <span>Scanned {i.history.length}× · last {when(scanned)}</span>
                        <Link href={`/p/${profile}/v/${encodeURIComponent(i.id)}`} className="text-rise underline">Full analysis →</Link>
                        <a href={i.url} target="_blank" rel="noreferrer" className="text-rise underline">Open on {PLATFORM[i.platform] ?? "the platform"} ↗</a>
                      </div>
                      {i.hook && <p className="mt-2 max-w-4xl italic text-text">“{i.hook}”</p>}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------- groups view ----------

type GroupSort = "count" | "best" | "views" | "name";

function Groups({ posts, by, profile, local, run, onChange, onFilter }: {
  posts: Item[]; by: GroupBy; profile: string; local: boolean; run: string | null;
  onChange: (key: string, patch: Partial<Item>) => void; onFilter?: (k: string) => void;
}) {
  const natural = Boolean(NATURAL[by]);
  const [gsort, setGsort] = useState<GroupSort>(natural ? "name" : "count");
  const [open, setOpen] = useState<Set<string>>(new Set());
  useEffect(() => { setGsort(NATURAL[by] ? "name" : "count"); setOpen(new Set()); }, [by]);
  const groups = useMemo(() => {
    const m = new Map<string, Item[]>();
    posts.forEach((i) => groupKeys(i, by, run).forEach((k) => m.set(k, [...(m.get(k) ?? []), i])));
    const rows = [...m.entries()].map(([key, xs]) => {
      const o = xs.map((i) => i.outlier).filter((v): v is number => v !== null);
      return {
        key, posts: xs, count: xs.length, best: o.length ? Math.max(...o) : null,
        views: xs.reduce((s, i) => s + (reach(i) ?? 0), 0), creators: new Set(xs.map(creatorName)).size,
        viral: xs.filter((i) => (i.outlier ?? 0) >= 3).length, fresh: xs.filter((i) => i.new).length,
      };
    });
    if (gsort === "name" && NATURAL[by]) return rows.sort((a, b) => NATURAL[by]!(a.key, b.key));
    const k: Record<GroupSort, (r: (typeof rows)[number]) => number | string> = {
      count: (r) => r.count, best: (r) => r.best ?? -1, views: (r) => r.views, name: (r) => r.key.toLowerCase(),
    };
    return rows.sort((a, b) => {
      const x = k[gsort](a), y = k[gsort](b);
      return typeof x === "string" ? String(x).localeCompare(String(y)) : (y as number) - (x as number);
    });
  }, [posts, by, gsort, run]);
  const toggle = (k: string) => setOpen((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n; });

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        <span>{groups.length} groups by {GROUP_LABEL[by].toLowerCase()}{by === "found_by" ? " (a post can be in several groups)" : ""} · order</span>
        <Seg value={gsort} onChange={(v) => setGsort(v)} options={[["count", "Most posts"], ["best", "Best ×"], ["views", "Most views"], ["name", natural ? "Natural" : "A–Z"]]} />
        <button onClick={() => setOpen(open.size ? new Set() : new Set(groups.slice(0, 10).map((g) => g.key)))} className="text-rise hover:underline">
          {open.size ? "Collapse all" : "Expand top 10"}
        </button>
      </div>
      {groups.map((g) => (
        <section key={g.key} className="rounded-2xl border border-line bg-panel">
          <button onClick={() => toggle(g.key)} className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5 text-left hover:bg-panel-2">
            <span className="min-w-[12rem] font-semibold">{open.has(g.key) ? "▾" : "▸"} {g.key}</span>
            <span className="text-sm"><b>{g.count}</b> <span className="text-muted">posts</span></span>
            <span className="text-sm text-viral">{g.viral ? `${g.viral} × 3×+` : ""}</span>
            <span className="text-sm text-muted">best {times(g.best)}</span>
            <span className="text-sm text-muted">{num(g.views)} views</span>
            {by !== "creator" && <span className="text-sm text-muted">{g.creators} creator{g.creators > 1 ? "s" : ""}</span>}
            {g.fresh > 0 && <span className="ml-auto text-sm text-rise">{g.fresh} new</span>}
          </button>
          {open.has(g.key) && (
            <div className="border-t border-line p-3">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {g.posts.slice(0, 8).map((i) => <PostCard key={i.key} item={i} profile={profile} local={local} run={run} onChange={onChange} />)}
              </div>
              {g.posts.length > 8 && (
                <p className="mt-2 text-xs text-muted">
                  Top 8 of {g.posts.length} by the current sort.{" "}
                  {onFilter && <button onClick={() => onFilter(g.key)} className="text-rise hover:underline">Show all {g.posts.length} of {g.key}</button>}
                </p>
              )}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}

function Check({ on, onChange, children }: { on: boolean; onChange: (v: boolean) => void; children: React.ReactNode }) {
  return (
    <label className="flex items-center gap-1.5 text-sm text-muted">
      <input type="checkbox" checked={on} onChange={(e) => onChange(e.target.checked)} /> {children}
    </label>
  );
}
