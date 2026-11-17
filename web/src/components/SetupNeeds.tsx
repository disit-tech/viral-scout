"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

/** What a feature still needs, with a shortcut per item (data: python -m viral_scout setup-check, viral_scout/setup_check.py).
 *  Drop it on any page: <SetupNeeds profile="x" sections={["demand"]} />. It renders nothing when that's all set up,
 *  and nothing on the published (read-only) site. */

type Fix =
  | { kind: "key"; name: string; use: string }
  | { kind: "field"; path: string }
  | { kind: "page"; href: string }
  | { kind: "doc"; href: string }
  | { kind: "command"; text: string };
export type SetupItem = { id: string; label: string; done: boolean; optional: boolean; detail: string; fix: Fix | null };
export type SetupSection = { id: string; title: string; href: string; optional?: boolean; open: number; total: number; items: SetupItem[] };
export type SetupData = { global: SetupItem[]; profiles: Record<string, { display: string; error?: string; sections: SetupSection[] }> };

let cache: Record<string, Promise<SetupData | null>> = {};
export function loadSetup(profile = ""): Promise<SetupData | null> {
  cache[profile] ??= fetch(`/api/setup-check${profile ? `?profile=${encodeURIComponent(profile)}` : ""}`)
    .then((r) => (r.ok ? r.json() : null)).then((d) => (d && !d.error ? d : null)).catch(() => null);
  return cache[profile];
}
export const resetSetup = () => { cache = {}; };

const btn = "whitespace-nowrap rounded border border-line px-2 py-0.5 text-xs text-rise hover:bg-panel-2";

export function FixButton({ fix, profile }: { fix: Fix | null; profile?: string }) {
  const [copied, setCopied] = useState(false);
  if (!fix) return null;
  if (fix.kind === "key") return <Link href={`/setup?use=${fix.use}#key-${fix.name}`} className={btn}>Set the key →</Link>;
  if (fix.kind === "field") return profile ? <Link href={`/p/${encodeURIComponent(profile)}/settings#f-${fix.path}`} className={btn}>Fill it in →</Link> : null;
  if (fix.kind === "page") return <Link href={fix.href} className={btn}>Open →</Link>;
  if (fix.kind === "doc") return <Link href={fix.href} className={btn}>How →</Link>;
  return (
    <span className="flex min-w-0 items-center gap-1.5">
      <code className="truncate text-[11px] text-muted" title={fix.text}>{fix.text}</code>
      <button className={btn} onClick={() => { navigator.clipboard?.writeText(fix.text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
        {copied ? "copied ✓" : "Copy"}
      </button>
    </span>
  );
}

export function ItemRow({ i, profile }: { i: SetupItem; profile?: string }) {
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 py-1.5">
      <span className={i.done ? "text-above" : i.optional ? "text-muted" : "text-viral"}>{i.done ? "✓" : i.optional ? "○" : "✗"}</span>
      <span className="font-medium">{i.label}{i.optional && !i.done ? <span className="font-normal text-muted"> (optional)</span> : null}</span>
      {i.detail && <span className="min-w-0 truncate text-xs text-muted" title={i.detail}>{i.detail}</span>}
      {!i.done && <span className="ml-auto"><FixButton fix={i.fix} profile={profile} /></span>}
    </li>
  );
}

/** One checklist for some sections of one business (or the shared tools with `tools`). */
export default function SetupNeeds({ profile, sections, tools = false, title, showDone = false }: {
  profile?: string; sections?: string[]; tools?: boolean; title?: string; showDone?: boolean;
}) {
  const [data, setData] = useState<SetupData | null>(null);
  const [showOptional, setShowOptional] = useState(false);
  useEffect(() => { loadSetup(profile ?? "").then(setData); }, [profile]);
  if (!data) return null;

  const secs = profile ? (data.profiles[profile]?.sections ?? []).filter((s) => !sections || sections.includes(s.id)) : [];
  const items: SetupItem[] = [...(tools ? data.global : []), ...secs.flatMap((s) => s.items)];
  const open = items.filter((i) => !i.done && !i.optional);
  const optional = items.filter((i) => !i.done && i.optional);
  if (!open.length && !showDone && !optional.length) return null;
  if (!open.length && !showDone) {
    return (
      <p className="text-xs text-muted">
        ✓ Set up.{" "}
        <button onClick={() => setShowOptional(!showOptional)} className="text-rise hover:underline">{showOptional ? "hide" : `${optional.length} optional extra${optional.length > 1 ? "s" : ""}`}</button>
        {showOptional && <ul className="mt-1 divide-y divide-line rounded-xl border border-line bg-panel px-3 text-sm">{optional.map((i) => <ItemRow key={i.id + i.label} i={i} profile={profile} />)}</ul>}
      </p>
    );
  }
  const shown = [...items.filter((i) => !i.done && !i.optional), ...(showOptional ? optional : []), ...(showDone ? items.filter((i) => i.done) : [])];
  return (
    <section className={`rounded-2xl border bg-panel p-4 text-sm ${open.length ? "border-viral/50" : "border-above/40"}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-semibold">{title ?? "To set up"}</h2>
        <span className={open.length ? "text-muted" : "text-above"}>{open.length ? `${open.length} thing${open.length > 1 ? "s" : ""} needed` : "✓ all set up"}</span>
        {optional.length > 0 && (
          <button onClick={() => setShowOptional(!showOptional)} className="ml-auto text-xs text-muted hover:text-text">
            {showOptional ? "hide optional" : `+ ${optional.length} optional`}
          </button>
        )}
      </div>
      <ul className="mt-2 divide-y divide-line">{shown.map((i) => <ItemRow key={i.id + i.label} i={i} profile={profile} />)}</ul>
    </section>
  );
}
