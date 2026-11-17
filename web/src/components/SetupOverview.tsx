"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ItemRow, loadSetup, type SetupData, type SetupSection } from "./SetupNeeds";

/** Business overview: every feature with what it still needs (required first), each item with its shortcut. */
export function BusinessSetup({ profile }: { profile: string }) {
  const [data, setData] = useState<SetupData | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [collapsed, setCollapsedState] = useState(false);
  useEffect(() => { loadSetup(profile).then(setData); }, [profile]);
  const secs = data?.profiles[profile]?.sections;
  if (!secs) return null;
  const tools = data!.global.filter((i) => !i.done && !i.optional);
  const need = secs.reduce((n, s) => n + s.open, 0) + tools.length;
  const ready = secs.filter((s) => s.open === 0).length;
  const setCollapsed = () => setCollapsedState(!collapsed);

  return (
    <section id="setup" className={`scroll-mt-20 rounded-2xl border bg-panel p-4 text-sm ${need ? "border-viral/50" : "border-above/40"}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold">Setup</h2>
        <span className={need ? "text-muted" : "text-above"}>
          {need ? `${ready} of ${secs.length} features ready · ${need} thing${need > 1 ? "s" : ""} needed` : "✓ every feature is set up"}
        </span>
        <button onClick={setCollapsed} className="ml-auto text-xs text-muted hover:text-text">{collapsed ? "show" : "hide"}</button>
      </div>
      {!collapsed && (
        <>
          {tools.length > 0 && (
            <div className="mt-2 rounded-xl border border-viral/40 px-3">
              <p className="pt-2 text-xs font-medium text-viral">Shared tools (every business)</p>
              <ul className="divide-y divide-line">{tools.map((i) => <ItemRow key={i.id} i={i} />)}</ul>
            </div>
          )}
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            {secs.map((s) => <SectionBox key={s.id} s={s} profile={profile} expanded={open === s.id} onToggle={() => setOpen(open === s.id ? null : s.id)} />)}
          </div>
        </>
      )}
    </section>
  );
}

function SectionBox({ s, profile, expanded, onToggle }: { s: SetupSection; profile: string; expanded: boolean; onToggle: () => void }) {
  const req = s.items.filter((i) => !i.done && !i.optional);
  const opt = s.items.filter((i) => !i.done && i.optional);
  const ok = s.open === 0;
  const shown = expanded ? s.items : req;
  return (
    <div className={`rounded-xl border px-3 py-2 ${ok ? "border-line" : "border-viral/40"}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={ok ? "text-above" : "text-viral"}>{ok ? "✓" : "✗"}</span>
        <Link href={s.href} className="font-medium hover:text-accent">{s.title}</Link>
        {s.optional && <span className="text-[11px] text-muted">(optional feature)</span>}
        <span className="text-xs text-muted">{ok ? "ready" : `${s.open} of ${s.total} needed`}</span>
        {(opt.length > 0 || s.items.some((i) => i.done)) && (
          <button onClick={onToggle} className="ml-auto text-[11px] text-muted hover:text-text">{expanded ? "less" : `details${opt.length ? ` (+${opt.length} optional)` : ""}`}</button>
        )}
      </div>
      {shown.length > 0 && <ul className="divide-y divide-line">{shown.map((i) => <ItemRow key={i.id} i={i} profile={profile} />)}</ul>}
    </div>
  );
}

/** Businesses page: the shared tools, and each business's setup at a glance (a link to its overview's Setup). */
export function GetStarted() {
  const [data, setData] = useState<SetupData | null>(null);
  useEffect(() => { loadSetup().then(setData); }, []);
  if (!data) return null;
  const tools = data.global.filter((i) => !i.done && !i.optional);
  const profs = Object.entries(data.profiles);
  const per = profs.map(([n, p]) => ({ n, p, need: p.sections.reduce((k, s) => k + s.open, 0), secs: p.sections.filter((s) => s.open > 0) }));
  const total = tools.length + per.reduce((k, x) => k + x.need, 0);
  if (!total) return null;
  return (
    <section className="rounded-2xl border border-viral/50 bg-panel p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold">Get started</h2>
        <span className="text-muted">{total} thing{total > 1 ? "s" : ""} still needed across {profs.length || "no"} business{profs.length === 1 ? "" : "es"}</span>
        <Link href="/setup" className="ml-auto text-xs text-rise hover:underline">All API keys →</Link>
      </div>
      {tools.length > 0 && <ul className="mt-2 divide-y divide-line">{tools.map((i) => <ItemRow key={i.id} i={i} />)}</ul>}
      {per.length > 0 && (
        <ul className="mt-2 divide-y divide-line">
          {per.map(({ n, p, need, secs }) => (
            <li key={n} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-1.5">
              <span className={need ? "text-viral" : "text-above"}>{need ? "✗" : "✓"}</span>
              <Link href={`/p/${encodeURIComponent(n)}#setup`} className="font-medium hover:text-accent">{p.display}</Link>
              <span className="text-xs text-muted">{need ? secs.map((s) => `${s.title} (${s.open})`).join(" · ") : "ready"}</span>
              {need > 0 && <Link href={`/p/${encodeURIComponent(n)}#setup`} className="ml-auto whitespace-nowrap rounded border border-line px-2 py-0.5 text-xs text-rise hover:bg-panel-2">Set up →</Link>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
