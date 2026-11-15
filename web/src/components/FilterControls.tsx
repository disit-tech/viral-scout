"use client";

// Small filter-bar parts shared by the ads board and the posts board.

import { num } from "@/lib/format";

export function Seg<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: [T, string][] }) {
  return (
    <div className="flex overflow-hidden rounded-lg border border-line text-xs">
      {options.map(([v, label]) => (
        <button key={v} onClick={() => onChange(v)}
          className={`px-2.5 py-1.5 ${value === v ? "bg-accent/15 text-accent" : "text-muted hover:bg-panel hover:text-text"}`}>{label}</button>
      ))}
    </div>
  );
}

export function Select({ value, onChange, all, options, labels }: {
  value: string; onChange: (v: string) => void; all: string; options: string[]; labels?: Record<string, string>;
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="max-w-56 rounded-lg border border-line bg-panel px-2 py-1.5 text-sm">
      <option value="all">{all}</option>
      {options.map((o) => <option key={o} value={o}>{labels?.[o] ?? o}</option>)}
    </select>
  );
}

export function More({ shown, total, onMore }: { shown: number; total: number; onMore: () => void }) {
  if (shown >= total) return null;
  return (
    <button onClick={onMore} className="w-full rounded-xl border border-line py-2.5 text-sm text-rise hover:bg-panel">
      Show more ({num(shown)} of {num(total)})
    </button>
  );
}

export function Stat({ label, value, tone = "text-text" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-xl border border-line bg-panel px-3 py-2">
      <div suppressHydrationWarning className={`text-xl font-semibold ${tone}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
    </div>
  );
}

/** Filter state kept in the query string, so a link reopens the same view. Arrays join with "|". */
export function readUrl<F extends Record<string, unknown>>(defaults: F): Partial<F> {
  if (typeof window === "undefined") return {};
  const p = new URLSearchParams(window.location.search);
  const out: Record<string, unknown> = {};
  for (const k of Object.keys(defaults)) {
    const v = p.get(k);
    if (v === null) continue;
    const d = defaults[k];
    if (Array.isArray(d)) out[k] = v ? v.split("|") : [];
    else if (typeof d === "number") out[k] = Number(v) || 0;
    else if (typeof d === "boolean") out[k] = v === "1";
    else out[k] = v;
  }
  return out as Partial<F>;
}

export function writeUrl<F extends Record<string, unknown>>(f: F, defaults: F, drop: string[] = []) {
  const p = new URLSearchParams(window.location.search);
  drop.forEach((k) => p.delete(k));
  for (const k of Object.keys(defaults)) {
    const v = f[k], d = defaults[k];
    if (JSON.stringify(v) === JSON.stringify(d)) { p.delete(k); continue; }
    p.set(k, Array.isArray(v) ? v.join("|") : typeof v === "boolean" ? (v ? "1" : "0") : String(v));
  }
  const qs = p.toString();
  window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
}

const csvCell = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""').replace(/\s+/g, " ")}"`;
export function downloadCsv<T>(name: string, rows: T[], cols: [string, (r: T) => unknown][]) {
  const text = [cols.map((c) => c[0]).join(","), ...rows.map((r) => cols.map(([, fn]) => csvCell(fn(r))).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob(["﻿" + text], { type: "text/csv;charset=utf-8" }));
  const el = Object.assign(document.createElement("a"), { href: url, download: name });
  el.click();
  URL.revokeObjectURL(url);
}
