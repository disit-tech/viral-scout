"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ProfileFields } from "@/lib/types";

// ---------- what each section edits (paths match viral_scout/profile_edit.py FIELDS) ----------

type Kind = "str" | "text" | "int" | "bool" | "window" | "geo" | "regex" | "list" | "tags" | "regex_list" | "adv";
type Field = { path: string; label: string; kind: Kind; help?: string; placeholder?: string; paid?: boolean; advanced?: boolean };
type Section = { id: string; title: string; intro: string; fields: Field[]; open?: string };

const SECTIONS: Section[] = [
  {
    id: "business", title: "Business", open: "",
    intro: "Who this is for. Every AI breakdown, idea and ad angle is adapted to the description, so put the services, area, customers and hard rules here.",
    fields: [
      { path: "display_name", label: "Display name", kind: "str", placeholder: "Northforge Home Services", help: "Shown on the dashboard. The ID (file names, vault folder, links) stays the same." },
      { path: "business", label: "Description", kind: "text", help: "Services, area, customers, tone, and what must never be shown or promised." },
      { path: "output_dir", label: "Reports folder", kind: "str", advanced: true, help: "Where reports and idea notes go. ${OBSIDIAN_VAULT} is expanded." },
      { path: "swipe_dir", label: "Swipe file folder", kind: "str", advanced: true },
      { path: "taste_note", label: "Taste note", kind: "str", advanced: true, help: "Note with your feedback on ideas; the AI reads it before suggesting more." },
    ],
  },
  {
    id: "videos", title: "Videos", open: "/videos",
    intro: "Where to look for viral posts. YouTube is free (yt-dlp, or the free YouTube Data API for keyword search). TikTok goes through Apify, which is paid.",
    fields: [
      { path: "discover.youtube.keywords", label: "YouTube keywords", kind: "list", help: "Searched with the YouTube Data API (Shorts need the key)." },
      { path: "discover.youtube.hashtags", label: "YouTube hashtags", kind: "tags", help: "Hashtag feeds, without the #." },
      { path: "discover.youtube.window", label: "Look back", kind: "window" },
      { path: "discover.youtube.shorts", label: "Shorts only", kind: "bool" },
      { path: "discover.youtube.per_query", label: "Results per query", kind: "int", advanced: true },
      { path: "discover.tiktok.keywords", label: "TikTok keywords", kind: "list", paid: true },
      { path: "discover.tiktok.hashtags", label: "TikTok hashtags", kind: "tags", paid: true },
      { path: "watch.youtube", label: "Watch list: YouTube creators", kind: "list", placeholder: "@handle or channel URL", help: "Every run checks their latest posts against their own usual." },
      { path: "watch.instagram", label: "Watch list: Instagram", kind: "list", help: "Needs IG_GRAPH_TOKEN (official Graph API)." },
      { path: "watch.tiktok", label: "Watch list: TikTok", kind: "list", paid: true },
      { path: "seeds", label: "Tracked links", kind: "list", placeholder: "https://…", help: "Posts re-measured every run (also added by the Track button)." },
      { path: "own.youtube", label: "Your YouTube channels", kind: "list", help: "Your own posts, against your own usual (the “Your posts” tab)." },
      { path: "own.urls", label: "Your post links", kind: "list" },
      { path: "filters.min_views", label: "Minimum views", kind: "int" },
      { path: "filters.max_age_days", label: "Max age (days)", kind: "int" },
      { path: "filters.must_match", label: "Must mention (topic words)", kind: "regex", help: "Words separated by | . A post must match one, or it is dropped as off-topic." },
      { path: "filters.exclude", label: "Exclude patterns", kind: "regex_list", help: "Posts matching any of these are dropped (gaming, recipes, live streams…)." },
    ],
  },
  {
    id: "ads", title: "Ads", open: "/ads",
    intro: "Competitors and searches for the ads scout. Runs weekly on Mondays through Apify (paid): each competitor or keyword is one ad-library search.",
    fields: [
      { path: "ads.advertisers", label: "Competitors", kind: "adv", paid: true, help: "Page name as it appears in the ad library. Optional pattern when the page name varies (e.g. one page per city)." },
      { path: "ads.keywords", label: "Keyword searches", kind: "list", paid: true },
      { path: "ads.domains", label: "Competitor domains (Google ads)", kind: "list", paid: true, placeholder: "example.com" },
      { path: "ads.countries", label: "Countries", kind: "list", placeholder: "US" },
      { path: "ads.topic", label: "Topic words (noise filter)", kind: "list", help: "Ads found by keyword searches must mention one of these. Competitor ads are always kept." },
      { path: "ads.exclude_advertisers", label: "Exclude advertisers", kind: "regex_list" },
      { path: "ads.days", label: "Look back (days)", kind: "int" },
      { path: "ads.per_query", label: "Ads per search", kind: "int", advanced: true },
      { path: "ads.top", label: "Ads in the report", kind: "int", advanced: true },
    ],
  },
  {
    id: "demand", title: "Search demand", open: "/demand",
    intro: "Google Trends via Apify (about $0.005 per term), refreshed at most every few days: when each service rises and peaks in your area.",
    fields: [
      { path: "demand.terms", label: "Services to track", kind: "list", paid: true, help: "One seasonal curve each." },
      { path: "demand.compare", label: "Compare wordings", kind: "list", help: "Up to 5 phrasings on one shared scale: which words people actually search." },
      { path: "demand.geo", label: "Area (Trends geo)", kind: "geo", placeholder: "US-IL-602", help: "US, a state (US-IL) or a metro (US-IL-602 = Chicago)." },
      { path: "demand.time", label: "Time range", kind: "str", placeholder: "today 5-y", advanced: true },
      { path: "demand.every_days", label: "Refresh every (days)", kind: "int" },
      { path: "demand.lead_weeks", label: "Lead time (weeks)", kind: "int", help: "“Start posting by” = this many weeks before demand starts rising." },
    ],
  },
  {
    id: "perf", title: "Local & your performance", open: "/performance",
    intro: "Local competitors from Google Places, and the ad account for your own results.",
    fields: [
      { path: "local.query", label: "Local search", kind: "str", placeholder: "gutter cleaning" },
      { path: "local.near", label: "Near", kind: "str", placeholder: "City, ST" },
      { path: "local.limit", label: "Competitors to list", kind: "int" },
      { path: "perf.meta_ad_account_id", label: "Meta ad account ID", kind: "str", help: "The account whose ads are yours (the token can see several)." },
    ],
  },
];

type Vals = Record<string, unknown>;
const same = (a: unknown, b: unknown) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
const empty = (k: Kind): unknown => (["list", "tags", "regex_list", "adv"].includes(k) ? [] : k === "bool" ? false : "");

export default function SettingsForm({ initial }: { initial: ProfileFields }) {
  const router = useRouter();
  const [base, setBase] = useState(initial.base);
  const [saved, setSaved] = useState<Vals>(initial.fields);
  const [vals, setVals] = useState<Vals>(initial.fields);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<Record<string, { ok: boolean; text: string }>>({});

  const all = useMemo(() => SECTIONS.flatMap((s) => s.fields), []);
  const dirty = (f: Field) => !same(vals[f.path] ?? empty(f.kind), saved[f.path] ?? empty(f.kind));
  const dirtyCount = all.filter(dirty).length;

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (dirtyCount) e.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirtyCount]);

  async function save(s: Section) {
    const changed = s.fields.filter(dirty);
    if (!changed.length) return;
    setBusy(s.id);
    const set = Object.fromEntries(changed.map((f) => [f.path, vals[f.path] ?? empty(f.kind)]));
    const r = await fetch("/api/profile", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ profile: initial.name, base, set }) })
      .then((x) => x.json()).catch(() => ({ ok: false, error: "request failed" }));
    setBusy(null);
    if (!r.ok) { setNotice((n) => ({ ...n, [s.id]: { ok: false, text: r.error ?? "Not saved" } })); return; }
    setBase(r.base);
    setSaved((x) => ({ ...x, ...set }));
    setNotice((n) => ({ ...n, [s.id]: { ok: true, text: r.changed.length ? `Saved ${r.changed.length} field${r.changed.length > 1 ? "s" : ""}. A backup of the old profile is in data/profile-backups/. Takes effect on the next run.` : "Nothing changed." } }));
    router.refresh();
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[200px_1fr]">
      <aside className="lg:sticky lg:top-[72px] lg:self-start">
        <nav className="flex gap-1 overflow-x-auto text-sm lg:flex-col">
          {SECTIONS.map((s) => {
            const n = s.fields.filter(dirty).length;
            return (
              <a key={s.id} href={`#${s.id}`} className="whitespace-nowrap rounded-lg px-3 py-1.5 text-muted hover:bg-panel hover:text-text">
                {s.title}{n > 0 && <span className="ml-1.5 text-viral">• {n}</span>}
              </a>
            );
          })}
        </nav>
        <div className="mt-4 hidden space-y-1 text-xs text-muted lg:block">
          <p>ID <code className="text-text">{initial.name}</code></p>
          <p>File <code className="break-all text-text">profiles/{initial.name}.yaml</code>. Comments in it are kept.</p>
          {dirtyCount > 0 && <p className="text-viral">{dirtyCount} unsaved change{dirtyCount > 1 ? "s" : ""}</p>}
        </div>
      </aside>

      <div className="min-w-0 space-y-6">
        {SECTIONS.map((s) => {
          const n = s.fields.filter(dirty).length;
          const basic = s.fields.filter((f) => !f.advanced), adv = s.fields.filter((f) => f.advanced);
          return (
            <section key={s.id} id={s.id} className="scroll-mt-20 rounded-2xl border border-line bg-panel">
              <header className="flex flex-wrap items-start justify-between gap-2 border-b border-line px-4 py-3">
                <div className="min-w-0 max-w-3xl">
                  <h2 className="font-semibold">{s.title}</h2>
                  <p className="mt-0.5 text-xs text-muted">{s.intro}</p>
                </div>
                {s.open !== undefined && <Link href={`/p/${initial.name}${s.open}`} className="text-xs text-muted hover:text-text">Open {s.title.toLowerCase()} →</Link>}
              </header>
              <div className="space-y-4 p-4">
                {basic.map((f) => <Row key={f.path} f={f} value={vals[f.path]} dirty={dirty(f)} onChange={(v) => setVals((x) => ({ ...x, [f.path]: v }))} />)}
                {adv.length > 0 && (
                  <details className="rounded-xl border border-line px-3 py-2">
                    <summary className="cursor-pointer text-xs text-muted">Advanced ({adv.length})</summary>
                    <div className="mt-3 space-y-4">
                      {adv.map((f) => <Row key={f.path} f={f} value={vals[f.path]} dirty={dirty(f)} onChange={(v) => setVals((x) => ({ ...x, [f.path]: v }))} />)}
                    </div>
                  </details>
                )}
              </div>
              <footer className="sticky bottom-0 flex flex-wrap items-center gap-3 rounded-b-2xl border-t border-line bg-panel/95 px-4 py-2.5 backdrop-blur">
                <button onClick={() => save(s)} disabled={!n || busy === s.id}
                  className="rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-ink disabled:cursor-default disabled:opacity-40">
                  {busy === s.id ? "Saving…" : n ? `Save ${n} change${n > 1 ? "s" : ""}` : "Saved"}
                </button>
                {n > 0 && (
                  <button onClick={() => setVals((x) => ({ ...x, ...Object.fromEntries(s.fields.map((f) => [f.path, saved[f.path]])) }))}
                    className="text-xs text-muted hover:text-text">Undo</button>
                )}
                {notice[s.id] && <span className={`text-xs ${notice[s.id].ok ? "text-above" : "text-mega"}`}>{notice[s.id].text}</span>}
              </footer>
            </section>
          );
        })}
      </div>
    </div>
  );
}

// ---------- one field ----------

function Row({ f, value, dirty, onChange }: { f: Field; value: unknown; dirty: boolean; onChange: (v: unknown) => void }) {
  return (
    <div className="grid gap-1.5 md:grid-cols-[220px_1fr] md:gap-4">
      <div>
        <label className="text-sm font-medium">
          {f.label}{dirty && <span className="ml-1 text-viral" title="Unsaved">•</span>}
        </label>
        {f.paid && <span className="ml-1.5 rounded bg-viral/15 px-1.5 py-0.5 text-[10px] text-viral" title="Each entry costs Apify credits on the weekly run">paid</span>}
        {f.help && <p className="mt-0.5 text-xs text-muted">{f.help}</p>}
      </div>
      <div className="min-w-0"><Input f={f} value={value} onChange={onChange} /></div>
    </div>
  );
}

const inputCls = "w-full rounded-lg border border-line bg-panel-2 px-3 py-1.5 text-sm outline-none focus:border-accent";

function Input({ f, value, onChange }: { f: Field; value: unknown; onChange: (v: unknown) => void }) {
  switch (f.kind) {
    case "text":
      return <textarea value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} rows={7} className={`${inputCls} leading-relaxed`} />;
    case "int":
      return <input type="number" min={0} value={value === undefined || value === null ? "" : String(value)} placeholder={f.placeholder}
        onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))} className={`${inputCls} max-w-40`} />;
    case "bool":
      return <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} /> {value ? "On" : "Off"}</label>;
    case "window":
      return (
        <select value={String(value ?? "month")} onChange={(e) => onChange(e.target.value)} className={`${inputCls} max-w-40`}>
          {["day", "week", "month", "year"].map((w) => <option key={w} value={w}>{w}</option>)}
        </select>
      );
    case "regex":
      return <RegexInput value={String(value ?? "")} onChange={onChange} />;
    case "list": case "tags": case "regex_list":
      return <ListInput items={(value as string[]) ?? []} kind={f.kind} placeholder={f.placeholder} onChange={onChange} />;
    case "adv":
      return <AdvInput items={(value as (string | { name: string; match: string })[]) ?? []} onChange={onChange} />;
    default:
      return <input value={String(value ?? "")} placeholder={f.placeholder} onChange={(e) => onChange(e.target.value)} className={inputCls} />;
  }
}

function badRegex(s: string) {
  try { new RegExp(s.replace(/\(\?i\)/g, "")); return null; } catch (e) { return (e as Error).message; }
}

function RegexInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const words = value ? value.split("|") : [];
  const err = value ? badRegex(value) : null;
  return (
    <div className="space-y-1">
      <textarea value={value} onChange={(e) => onChange(e.target.value.replace(/\n/g, "|"))} rows={3} className={`${inputCls} font-mono text-xs`} />
      <p className={`text-[11px] ${err ? "text-mega" : "text-muted"}`}>{err ? `Not a valid pattern: ${err}` : `${words.length} word${words.length === 1 ? "" : "s"}`}</p>
    </div>
  );
}

function ListInput({ items, kind, placeholder, onChange }: { items: string[]; kind: Kind; placeholder?: string; onChange: (v: string[]) => void }) {
  const [draft, setDraft] = useState("");
  const norm = (s: string) => (kind === "tags" ? s.replace(/^#/, "").replace(/\s+/g, "").toLowerCase() : s.trim());
  function add(text: string) {
    const parts = (kind === "tags" ? text.split(/[\s,]+/) : text.split(/\n/)).map(norm).filter(Boolean);
    const next = [...items];
    parts.forEach((p) => { if (!next.includes(p)) next.push(p); });
    onChange(next);
    setDraft("");
  }
  const err = kind === "regex_list" && draft ? badRegex(draft) : null;
  return (
    <div className="space-y-2">
      {items.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {items.map((it, i) => (
            <li key={`${it}-${i}`} className={`flex items-center gap-1 rounded-full border border-line bg-panel-2 py-0.5 pl-2.5 pr-1 text-xs ${kind === "regex_list" ? "font-mono" : ""}`}>
              <span className="max-w-[28rem] truncate" title={it}>{kind === "tags" ? `#${it}` : it}</span>
              <button onClick={() => onChange(items.filter((_, j) => j !== i))} className="rounded-full px-1 text-muted hover:text-mega" aria-label={`Remove ${it}`}>✕</button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <input value={draft} placeholder={placeholder ?? (kind === "tags" ? "Add hashtags (space separated)" : "Add one, or paste several lines")}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && draft.trim()) { e.preventDefault(); if (!err) add(draft); } }}
          onPaste={(e) => { const t = e.clipboardData.getData("text"); if (t.includes("\n")) { e.preventDefault(); add(t); } }}
          className={`${inputCls} ${kind === "regex_list" ? "font-mono text-xs" : ""}`} />
        <button onClick={() => draft.trim() && !err && add(draft)} className="rounded-lg border border-line px-3 text-sm text-muted hover:text-text">Add</button>
      </div>
      <p className={`text-[11px] ${err ? "text-mega" : "text-muted"}`}>{err ? `Not a valid pattern: ${err}` : `${items.length} entr${items.length === 1 ? "y" : "ies"}`}</p>
    </div>
  );
}

type Adv = string | { name: string; match: string };
function AdvInput({ items, onChange }: { items: Adv[]; onChange: (v: Adv[]) => void }) {
  const rows = items.map((a) => (typeof a === "string" ? { name: a, match: "" } : { name: a.name ?? "", match: a.match ?? "" }));
  const emit = (r: { name: string; match: string }[]) => onChange(r.map((x) => (x.match ? { name: x.name, match: x.match } : x.name)));
  const upd = (i: number, k: "name" | "match", v: string) => emit(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  return (
    <div className="space-y-1.5">
      <div className="grid grid-cols-[1fr_1fr_auto] gap-1.5 text-[10px] uppercase tracking-wide text-muted">
        <span>Page name</span><span>Pattern (optional)</span><span />
      </div>
      {rows.map((r, i) => {
        const err = r.match ? badRegex(r.match) : null;
        return (
          <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-1.5">
            <input value={r.name} onChange={(e) => upd(i, "name", e.target.value)} className={inputCls} />
            <input value={r.match} onChange={(e) => upd(i, "match", e.target.value)} placeholder="e.g. ^LeafFilter"
              className={`${inputCls} font-mono text-xs ${err ? "border-mega" : ""}`} title={err ?? ""} />
            <button onClick={() => emit(rows.filter((_, j) => j !== i))} className="px-2 text-muted hover:text-mega" aria-label="Remove">✕</button>
          </div>
        );
      })}
      <button onClick={() => emit([...rows, { name: "", match: "" }])} className="rounded-lg border border-dashed border-line px-3 py-1 text-xs text-muted hover:text-text">
        + Add competitor
      </button>
      <p className="text-[11px] text-muted">{rows.filter((r) => r.name).length} competitors</p>
    </div>
  );
}
