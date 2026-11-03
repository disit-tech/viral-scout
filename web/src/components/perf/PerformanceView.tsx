"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { Kpi, KpiDef, Perf, PerfRecord, Test } from "@/lib/perf";
import { fmtKpi } from "@/lib/perf-format";
import RetentionChart from "./RetentionChart";

type Kind = "organic" | "paid";
const PLATFORM: Record<string, string> = { youtube: "YouTube", instagram: "Instagram", facebook: "Meta", tiktok: "TikTok" };
const STATUS: Record<Test["status"], { icon: string; cls: string; word: string }> = {
  pass: { icon: "✓", cls: "border-above/50 text-above", word: "pass" },
  warn: { icon: "!", cls: "border-viral/50 text-viral", word: "warn" },
  fail: { icon: "✕", cls: "border-mega/60 text-mega", word: "fail" },
  "n/a": { icon: "·", cls: "border-line text-muted", word: "n/a" },
};
const ROW_KPIS: Record<Kind, string[]> = {
  organic: ["views", "hook_rate", "avg_watch_time", "avg_pct_viewed", "completion_rate", "engagement_rate", "share_rate", "save_rate", "follower_conversion"],
  paid: ["spend", "impressions", "hook_rate", "thruplay_rate", "completion_rate", "link_ctr", "cpc_link", "cpm", "cvr", "cpa", "roas", "contribution_margin"],
};

export default function PerformanceView({ perf, local }: { perf: Perf; local: boolean }) {
  const kinds = (["organic", "paid"] as Kind[]).filter((k) => perf.records.some((r) => r.kind === k));
  const [kind, setKind] = useState<Kind>(kinds.includes("paid") ? "paid" : "organic");
  const defs = useMemo(() => new Map(perf.kpi_defs.map((d) => [d.id, d])), [perf.kpi_defs]);
  const rows = perf.records
    .filter((r) => r.kind === kind)
    .sort((a, b) => (kind === "paid" ? (b.spend ?? 0) - (a.spend ?? 0) : (b.views ?? 0) - (a.views ?? 0)));
  const acc = perf.account[kind];
  const meds = perf.medians[kind];

  return (
    <div className="space-y-6">
      <Header perf={perf} kinds={kinds} kind={kind} setKind={setKind} />

      {!perf.records.length && <EmptyState name={perf.name} />}

      {acc && (
        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">
            KPIs · {kind === "paid" ? "paid" : "organic"} · {acc.records} {kind === "paid" ? "ads" : "videos"}
          </h2>
          <p className="mb-3 text-xs text-muted">Big number = account total (Σ numerators ÷ Σ denominators). Small = median video, the benchmark used below. Hover a card for the formula and denominator.</p>
          <div className="space-y-4">
            {Object.entries(perf.groups).map(([g, gname]) => {
              const ids = perf.kpi_defs.filter((d) => d.group === g && (acc.kpis[d.id] || meds.all[d.id] !== undefined)).map((d) => d.id);
              const mer = g === "E" && acc.mer;
              if (!ids.length && !mer) return null;
              return (
                <div key={g}>
                  <h3 className="mb-1.5 text-xs font-semibold text-text"><span className="text-accent">{g}</span> · {gname}</h3>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
                    {ids.map((id) => <KpiCard key={id} def={defs.get(id)!} total={acc.kpis[id]} median={meds.all[id]} n={meds.n[id]} />)}
                    {mer && (
                      <KpiCard def={defs.get("mer")!} total={{ value: mer.value, num: null, den: null, denominator: mer.basis }} median={undefined} n={undefined} />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {kind === "paid" && Object.keys(perf.unit_economics).length > 0 && (
        <section className="rounded-2xl border border-line bg-panel p-4">
          <h2 className="mb-2 font-semibold">Unit economics</h2>
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {Object.entries(perf.unit_economics).map(([k, v]) => (
              <div key={k} className="rounded-lg bg-panel-2 p-2.5" title={`${v.formula}. ${v.note}`}>
                <div className="text-[11px] text-muted">{k.replaceAll("_", " ")}</div>
                <div className="text-lg font-semibold tabular-nums">{k === "break_even_roas" ? fmtKpi("x", v.value) : fmtKpi("money", v.value)}</div>
                <div className="text-[10px] text-muted">{v.formula}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {perf.records.length > 0 && (
        <section className="rounded-2xl border border-line bg-panel p-4">
          <h2 className="mb-2 font-semibold">{kind === "paid" ? `Paid priorities (goal: ${perf.priorities.goal})` : "Organic priorities"}</h2>
          <ol className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
            {perf.priorities[kind].map((p, i) => (
              <li key={p.what}><span className="text-muted">{i + 1}.</span> <strong>{p.what}</strong>{p.why ? <span className="text-muted"> · {p.why}</span> : null}</li>
            ))}
          </ol>
        </section>
      )}

      {rows.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">{kind === "paid" ? "Ads" : "Videos"}: the 5 tests, retention and diagnosis</h2>
          <div className="grid gap-4 xl:grid-cols-2">
            {rows.map((r) => <RecordCard key={r.key} r={r} defs={defs} />)}
          </div>
        </section>
      )}

      <section className="grid gap-4 lg:grid-cols-2">
        <details className="rounded-2xl border border-line bg-panel p-4">
          <summary className="cursor-pointer font-semibold">Platform definitions differ</summary>
          <ul className="mt-3 space-y-2 text-sm">
            {perf.platform_differences.map(([a, b]) => <li key={a}><strong>{a}</strong>: <span className="text-muted">{b}</span></li>)}
          </ul>
        </details>
        <ImportHelp name={perf.name} local={local} />
      </section>

      {(perf.sources.skipped.length > 0 || perf.sources.errors.length > 0) && (
        <section className="rounded-2xl border border-line bg-panel p-4 text-sm">
          {perf.sources.skipped.length > 0 && (<>
            <h2 className="mb-1 font-semibold">Skipped sources</h2>
            <ul className="mb-3 list-disc space-y-0.5 pl-5 text-muted">{perf.sources.skipped.map((s) => <li key={s}>{s}</li>)}</ul>
          </>)}
          {perf.sources.errors.length > 0 && (<>
            <h2 className="mb-1 font-semibold">Errors</h2>
            <ul className="list-disc space-y-0.5 pl-5 text-mega">{perf.sources.errors.slice(0, 20).map((s) => <li key={s}>{s}</li>)}</ul>
          </>)}
        </section>
      )}
    </div>
  );
}

function Header({ perf, kinds, kind, setKind }: { perf: Perf; kinds: Kind[]; kind: Kind; setKind: (k: Kind) => void }) {
  const stored = Object.entries(perf.sources.stored);
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <Link href={`/p/${perf.name}`} className="text-xs text-muted hover:text-text">← {perf.name}</Link>
        <h1 className="mt-1 text-2xl font-bold tracking-tight">Your performance</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Your own videos and ads, from official APIs and your own exports, against <strong className="text-text">your own medians</strong>, not industry averages.
          {" "}Updated {new Date(perf.date).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })} · last {perf.days} days · goal {perf.goal}.
        </p>
        {stored.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
            {stored.map(([s, v]) => (
              <span key={s} className="rounded-full border border-line px-2 py-0.5 text-muted">{s.replace("csv:", "CSV ")} · {v.records}</span>
            ))}
          </div>
        )}
      </div>
      {kinds.length > 0 && (
        <div role="tablist" aria-label="Organic or paid" className="flex rounded-lg border border-line p-0.5 text-sm">
          {(["organic", "paid"] as Kind[]).map((k) => (
            <button key={k} role="tab" aria-selected={kind === k} disabled={!kinds.includes(k)} onClick={() => setKind(k)}
              className={`rounded-md px-3 py-1 capitalize disabled:opacity-30 ${kind === k ? "bg-panel-2 text-text" : "text-muted hover:text-text"}`}>
              {k}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function KpiCard({ def, total, median, n }: { def: KpiDef; total?: Kpi; median?: number; n?: number }) {
  if (!def) return null;
  const tip = `${def.label} = ${def.formula}${total?.denominator ? `\nDenominator: ${total.denominator}` : ""}${def.note ? `\n${def.note}` : ""}`;
  return (
    <div tabIndex={0} title={tip} className="group relative rounded-xl border border-line bg-panel p-2.5 outline-none focus:border-accent">
      <div className="truncate text-[11px] text-muted">{def.label}</div>
      <div className="text-lg font-semibold tabular-nums">{fmtKpi(def.unit, total?.value ?? median)}</div>
      {median !== undefined && <div className="text-[10px] text-muted">median {fmtKpi(def.unit, median)}{n ? ` · n=${n}` : ""}</div>}
      <div role="tooltip" className="pointer-events-none invisible absolute left-0 top-full z-10 mt-1 w-64 rounded-lg border border-line bg-panel-2 p-2 text-[11px] leading-snug opacity-0 shadow-lg transition group-hover:visible group-hover:opacity-100 group-focus:visible group-focus:opacity-100">
        <div className="font-mono text-text">{def.formula}</div>
        {total?.denominator && <div className="mt-1 text-muted">Denominator: {total.denominator}</div>}
        {def.note && <div className="mt-1 text-muted">{def.note}</div>}
      </div>
    </div>
  );
}

function RecordCard({ r, defs }: { r: PerfRecord; defs: Map<string, KpiDef> }) {
  const p = r.diagnosis.problem;
  return (
    <article className="rounded-2xl border border-line bg-panel p-4">
      <div className="flex items-start gap-3">
        {r.thumbnail && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={r.thumbnail} alt="" className="h-16 w-12 shrink-0 rounded-md object-cover" loading="lazy" />
        )}
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold leading-snug">
            {r.url ? <a href={r.url} target="_blank" rel="noreferrer" className="hover:underline">{r.title || r.id}</a> : (r.title || r.id)}
          </h3>
          <p className="text-xs text-muted">
            {PLATFORM[r.platform] ?? r.platform} · {r.source.replace("csv:", "CSV ")}
            {r.duration ? ` · ${Math.round(r.duration)} s` : ""}{r.campaign ? ` · ${r.campaign}` : ""}
            {r.date_start ? ` · ${r.date_start}${r.date_stop && r.date_stop !== r.date_start ? ` → ${r.date_stop}` : ""}` : ""}
          </p>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-5 gap-1" aria-label="The 5 tests">
        {r.tests.map((t) => {
          const s = STATUS[t.status];
          const unit = t.metric ? defs.get(t.metric)?.unit : undefined;
          return (
            <div key={t.test} className={`rounded-lg border px-1.5 py-1 text-center ${s.cls}`}
              title={t.metric ? `${defs.get(t.metric)?.label ?? t.metric}: ${fmtKpi(unit, t.value)} vs ${fmtKpi(unit, t.benchmark)} (${t.basis})` : t.basis}>
              <div className="text-[10px] uppercase tracking-wide">{t.test === "Business impact" ? "Business" : t.test}</div>
              <div className="text-xs font-semibold"><span aria-hidden>{s.icon}</span> {s.word}</div>
              {t.metric && <div className="truncate text-[10px] text-muted">{fmtKpi(unit, t.value)}</div>}
            </div>
          );
        })}
      </div>

      <dl className="mt-3 grid grid-cols-3 gap-x-3 gap-y-1 text-xs sm:grid-cols-4">
        {ROW_KPIS[r.kind].map((id) => {
          const def = defs.get(id);
          const k = r.kpis[id];
          const v = id === "spend" ? r.spend : k?.value;
          if (v === null || v === undefined) return null;
          return (
            <div key={id} title={def ? `${def.formula}${k?.denominator ? ` · denominator: ${k.denominator}` : ""}` : ""}>
              <dt className="text-muted">{def?.label ?? "Spend"}</dt>
              <dd className="font-semibold tabular-nums">{fmtKpi(def?.unit ?? "money", v)}</dd>
            </div>
          );
        })}
      </dl>

      {r.curve && (
        <div className="mt-3">
          <RetentionChart curve={r.curve} duration={r.duration} />
          {r.curve_summary && <p className="mt-1 text-xs text-muted">{r.curve_summary}</p>}
        </div>
      )}

      <div className="mt-3 rounded-xl bg-panel-2 p-3 text-sm">
        {p ? (
          <>
            <div className="font-semibold"><span className="text-mega">Biggest problem:</span> {p.title}</div>
            <div className="text-xs text-muted">{p.evidence}</div>
            <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs">{p.investigate.map((x) => <li key={x}>{x}</li>)}</ul>
            {r.diagnosis.findings.length > 1 && (
              <p className="mt-2 text-xs text-muted">Also: {r.diagnosis.findings.slice(1).map((f) => f.title).join(" · ")}</p>
            )}
          </>
        ) : (
          <div className="text-xs"><span className="font-semibold text-above">No clear problem</span> <span className="text-muted">against your own medians. Keep it as the control; test one variable at a time against it.</span></div>
        )}
        {r.fatigue?.detected && (
          <p className="mt-2 text-xs text-viral">Fatigue: frequency {r.fatigue.frequency[0]} → {r.fatigue.frequency[1]}, CTR {r.fatigue.ctr[0]}% → {r.fatigue.ctr[1]}%</p>
        )}
      </div>

      {r.diagnosis.caveats.length + r.notes.length > 0 && (
        <details className="mt-2 text-xs text-muted">
          <summary className="cursor-pointer">Caveats ({r.diagnosis.caveats.length + r.notes.length})</summary>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            {[...r.diagnosis.caveats, ...r.notes].map((c) => <li key={c}>{c}</li>)}
            {r.view_definition && <li>{r.view_definition}</li>}
          </ul>
        </details>
      )}
    </article>
  );
}

function ImportHelp({ name, local }: { name: string; local: boolean }) {
  return (
    <details className="rounded-2xl border border-line bg-panel p-4" open={false}>
      <summary className="cursor-pointer font-semibold">Import a CSV (no keys needed)</summary>
      <div className="mt-3 space-y-2 text-sm text-muted">
        <p>Export from the platform, then run on your PC{local ? "" : " (the published site is read-only)"}:</p>
        <pre className="overflow-x-auto rounded-lg bg-panel-2 p-2 text-xs text-text">python -m viral_scout perf import {name} export.csv --source meta|tiktok|youtube|generic</pre>
        <ul className="list-disc space-y-1 pl-5 text-xs">
          <li><strong className="text-text">Meta Ads Manager</strong>: Ads tab → Columns: add Video engagement + Conversions (3-second video plays, ThruPlays, Video plays at 25–100%, Link clicks, Landing page views, Purchases, Purchases conversion value) → Reports → Export table data (.csv). Break down by Day for fatigue.</li>
          <li><strong className="text-text">TikTok Ads Manager</strong>: Ads → Custom columns: Video views, 2-second / 6-second video views, Video views at 25–100%, Average play time per video view, Clicks (destination), Conversions → Export. Add “By Day” for fatigue.</li>
          <li><strong className="text-text">YouTube Studio</strong>: Analytics → Advanced mode → Content → add Impressions, Impressions CTR, Average percentage viewed, Stayed to watch, Shares, Subscribers gained → Export → Comma-separated values (Table data.csv).</li>
          <li><strong className="text-text">Generic</strong>: one row per video/ad with columns named like the schema (impressions, views_3s, spend, purchases, revenue, …).</li>
        </ul>
        <p className="text-xs">Column mappings and every formula: <Link href="/docs/performance" className="text-rise underline">docs → performance</Link>.</p>
      </div>
    </details>
  );
}

function EmptyState({ name }: { name: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-muted">
      <p className="text-base text-text">No performance data yet.</p>
      <p className="mt-1">Add your own keys on <Link href="/setup" className="text-rise underline">Setup</Link> (Instagram insights, YouTube Analytics, Meta ads, TikTok ads) and run</p>
      <pre className="mx-auto mt-2 w-fit rounded-lg bg-panel-2 px-3 py-1.5 text-xs text-text">python -m viral_scout perf {name}</pre>
      <p className="mt-2">or import a CSV export (below).</p>
    </div>
  );
}
