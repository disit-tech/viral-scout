"use client";

import { useEffect, useRef, useState } from "react";
import { PRICE, USES, byTier, costDetail, priceOf, useLabel } from "@/lib/keys-ui";
import { flash } from "@/lib/flash";
import Connections from "./Connections";

type Key = {
  name: string; group: string; set: boolean; masked: string; cost: string; unlocks: string; get: string; docs: string;
  secret?: boolean; tier?: string; price?: string; has_default?: boolean; uses?: string[];
};

export default function SetupKeys() {
  const [keys, setKeys] = useState<Key[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [use, setUse] = useState("all");
  const [price, setPrice] = useState("");   // "" = any cost; else a PRICE id (free, free_tier, paid, control)
  const [state, setState] = useState<"" | "set" | "unset">("");   // "" = both; a working default counts as set

  async function load() {
    const r = await fetch("/api/keys").then((x) => x.json()).catch(() => null);
    if (r?.ok) setKeys(r.keys);
    else setError(r?.output ?? "Could not read key status");
  }
  useEffect(() => {
    // Shortcuts from other pages: /setup?use=paid#key-META_ADS_TOKEN opens the filter and jumps to that key.
    const q = new URLSearchParams(window.location.search);
    const u = q.get("use");
    if (u) setUse(u);
    const st = q.get("state");
    if (st === "set" || st === "unset") setState(st);   // /setup?state=unset: only what's still missing
    load();
  }, []);

  // Jump to a key and flash it: on load (#key-X in the URL), on any #key-X link click on this page (the cards'
  // "First save X" links, docs), and on back/forward. A click on the same link again flashes again (nonce).
  const [target, setTarget] = useState<{ id: string; n: number } | null>(null);
  useEffect(() => {
    const fromHash = () => {
      const id = window.location.hash.slice(1);
      if (id.startsWith("key-")) setTarget({ id, n: Date.now() });
    };
    const onClick = (e: MouseEvent) => {
      const a = (e.target as HTMLElement).closest<HTMLAnchorElement>('a[href^="#key-"]');
      if (!a || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
      e.preventDefault();
      const id = a.getAttribute("href")!.slice(1);
      history.replaceState(null, "", `#${id}`);
      setTarget({ id, n: Date.now() });
    };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    document.addEventListener("click", onClick);
    return () => { window.removeEventListener("hashchange", fromHash); document.removeEventListener("click", onClick); };
  }, []);
  const flashed = useRef(0);   // nonce of the last target flashed: changing a filter later doesn't flash it again
  useEffect(() => {
    if (!keys || !target || flashed.current === target.n) return;
    const el = document.getElementById(target.id);
    if (!el) {
      // Hidden by a filter: clear the filters, and this runs again once the row is rendered.
      if (keys.some((k) => `key-${k.name}` === target.id) && (use !== "all" || price || state)) {
        setUse("all"); setPrice(""); setState("");
      }
      return;
    }
    flashed.current = target.n;
    flash(el);
  }, [keys, target, use, price, state]);

  if (error) return <p className="mt-6 text-mega">{error}</p>;
  if (!keys) return <p className="mt-6 text-muted">Loading…</p>;

  const tiers = byTier(keys);
  const byUse = (u: string) => (u === "all" ? keys : keys.filter((k) => k.uses?.includes(u)));
  const done = (k: Key) => k.set || Boolean(k.has_default);   // same rule as the tier counters
  const byState = (ks: Key[]) => (state === "set" ? ks.filter(done) : state === "unset" ? ks.filter((k) => !done(k)) : ks);
  const pool = byUse(use).filter((k) => !price || k.price === price);   // what the set / not set counts are out of
  const shown = byTier(byState(pool));
  const isSet = (n: string) => keys.some((k) => k.name === n && k.set);
  return (
    <div className="mt-6 space-y-8">
      <Connections isSet={isSet} onDone={load} />
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border border-line bg-panel px-4 py-3 text-sm">
        {tiers.map((t) => {
          const done = t.keys.filter((k) => k.set || k.has_default).length;   // some settings work on their defaults
          return (
            <a key={t.id} href={`#tier-${t.id}`} className="hover:text-accent">
              {t.title} <b className={done === t.keys.length ? "text-above" : "text-text"}>{done}/{t.keys.length}</b> <span className="text-muted">set</span>
            </a>
          );
        })}
        <span className="ml-auto flex flex-wrap items-center gap-1.5">
          {Object.entries(PRICE).map(([id, p]) => {
            const n = byUse(use).filter((k) => k.price === id).length;
            const on = price === id;
            return (
              <button key={id} onClick={() => setPrice(on ? "" : id)} disabled={!n && !on} aria-pressed={on}
                title={`${p.title}. ${on ? "Click again to show every key." : "Click to show only these."}`}
                className={`rounded-full border px-2 py-0.5 text-[11px] ${p.cls} ${on ? "ring-2 ring-current" : price ? "opacity-50 hover:opacity-100" : ""} disabled:cursor-default disabled:opacity-30`}>
                {p.label} <span className="opacity-70">{n}</span>
              </button>
            );
          })}
          {price && <button onClick={() => setPrice("")} className="text-[11px] text-muted hover:text-text">✕ clear</button>}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-1.5 text-sm">
        <span className="mr-1 text-muted">Show keys for</span>
        {[{ id: "all", label: "everything" }, ...USES].map((u) => {
          const n = u.id === "all" ? keys.length : keys.filter((k) => k.uses?.includes(u.id)).length;
          if (!n) return null;
          return (
            <button key={u.id} onClick={() => setUse(u.id)}
              className={`rounded-full border px-3 py-1 text-xs ${use === u.id ? "border-accent bg-accent/15 text-accent" : "border-line text-muted hover:text-text"}`}>
              {u.label} <span className="opacity-70">{n}</span>
            </button>
          );
        })}
        <span className="ml-auto flex items-center gap-1.5">
          {([["", "all", pool.length], ["set", "set", pool.filter(done).length], ["unset", "not set", pool.filter((k) => !done(k)).length]] as const).map(([id, label, n]) => (
            <button key={id || "any"} onClick={() => setState(id)} aria-pressed={state === id}
              title={id === "set" ? "Saved, or working on its default" : id === "unset" ? "Still missing (no value, no default)" : "Set and not set"}
              className={`rounded-full border px-3 py-1 text-xs ${state === id ? "border-accent bg-accent/15 text-accent" : "border-line text-muted hover:text-text"}`}>
              {label} <span className="opacity-70">{n}</span>
            </button>
          ))}
        </span>
      </div>
      {!shown.length && (
        <p className="rounded-xl border border-dashed border-line p-6 text-center text-sm text-muted">
          No keys match these filters.{" "}
          <button onClick={() => { setState(""); setPrice(""); setUse("all"); }} className="text-rise hover:underline">Show every key</button>
        </p>
      )}
      {shown.map((t) => (
        <section key={t.id} id={`tier-${t.id}`} className="scroll-mt-20 space-y-3">
          <div>
            <h2 className="text-lg font-semibold">{t.title}</h2>
            <p className="text-sm text-muted">{t.text}</p>
          </div>
          {t.groups.map(({ group, keys: ks }) => (
            <div key={group} className="rounded-2xl border border-line bg-panel p-4">
              <h3 className="mb-3 font-semibold">{group}</h3>
              <div className="space-y-4">
                {ks.map((k) => <KeyRow key={k.name} k={k} onSaved={load} />)}
              </div>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}

function KeyRow({ k, onSaved }: { k: Key; onSaved: () => void }) {
  const [value, setValue] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function call(action: "set" | "test", v?: string) {
    setBusy(true);
    setMsg(null);
    const r = await fetch("/api/keys", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ action, name: k.name, value: v }) }).then((x) => x.json()).catch(() => ({ ok: false, output: "request failed" }));
    setBusy(false);
    setMsg({ ok: r.ok, text: r.output });
    if (action === "set" && r.ok) { setValue(""); onSaved(); }
  }

  return (
    <div id={`key-${k.name}`} className="grid scroll-mt-24 gap-2 rounded-lg transition-colors duration-500 md:grid-cols-[1fr_1.2fr]">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <code className="text-sm text-text">{k.name}</code>
          <span className={`max-w-full truncate rounded-full px-2 py-0.5 text-[11px] ${k.set ? "bg-above text-ink" : "bg-panel-2 text-muted"}`}
            title={k.set && k.secret === false ? k.masked : undefined}>
            {k.set ? (k.secret === false ? k.masked : `set ${k.masked}`) : k.has_default ? "default" : "not set"}
          </span>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <PriceBadge k={k} />
          {k.uses?.map((u) => <span key={u} className="whitespace-nowrap rounded-full bg-panel-2 px-2 py-0.5 text-[11px] text-muted">{useLabel(u)}</span>)}
          {costDetail(k) && <span className="text-[11px] text-muted">{costDetail(k)}</span>}
        </div>
        <p className="mt-1 text-xs text-muted">{k.unlocks}</p>
        <p className="mt-1 text-xs text-muted">How: {k.get} <a href={k.docs} target="_blank" rel="noreferrer" className="text-rise hover:underline">docs ↗</a></p>
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex gap-1.5">
          <input type={k.secret === false ? "text" : "password"} autoComplete="off" value={value} onChange={(e) => setValue(e.target.value)}
            placeholder={k.secret === false ? (k.set ? "New value…" : "Value…") : k.set ? "Replace value…" : "Paste value…"}
            className="min-w-0 flex-1 rounded-lg border border-line bg-panel-2 px-2.5 py-1.5 text-sm outline-none focus:border-accent" />
          <button disabled={busy || !value} onClick={() => call("set", value)}
            className="rounded-lg border border-accent/60 px-3 text-sm text-accent hover:bg-accent/10 disabled:opacity-40">Save</button>
          <button disabled={busy || !k.set} onClick={() => call("test")}
            className="rounded-lg border border-line px-3 text-sm text-muted hover:text-text disabled:opacity-40">Test</button>
          {k.set && (
            <button disabled={busy} onClick={() => confirm(`Clear ${k.name}?`) && call("set", "")}
              className="rounded-lg border border-line px-2 text-sm text-muted hover:text-mega disabled:opacity-40" title="Clear">✕</button>
          )}
        </div>
        {msg && <p className={`text-xs ${msg.ok ? "text-above" : "text-mega"}`}>{msg.text}</p>}
      </div>
    </div>
  );
}

function PriceBadge({ k }: { k: { price?: string } }) {
  const p = priceOf(k);
  if (!p) return null;
  return <span title={p.title} className={`whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] ${p.cls}`}>{p.label}</span>;
}
