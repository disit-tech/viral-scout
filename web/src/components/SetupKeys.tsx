"use client";

import { useEffect, useState } from "react";

type Key = { name: string; group: string; set: boolean; masked: string; cost: string; unlocks: string; get: string; docs: string };

export default function SetupKeys() {
  const [keys, setKeys] = useState<Key[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    const r = await fetch("/api/keys").then((x) => x.json()).catch(() => null);
    if (r?.ok) setKeys(r.keys);
    else setError(r?.output ?? "Could not read key status");
  }
  useEffect(() => { load(); }, []);

  if (error) return <p className="mt-6 text-mega">{error}</p>;
  if (!keys) return <p className="mt-6 text-muted">Loading…</p>;

  const groups = Array.from(new Set(keys.map((k) => k.group)));
  return (
    <div className="mt-6 space-y-5">
      {groups.map((g) => (
        <section key={g} className="rounded-2xl border border-line bg-panel p-4">
          <h2 className="mb-3 font-semibold">{g}</h2>
          <div className="space-y-4">
            {keys.filter((k) => k.group === g).map((k) => <KeyRow key={k.name} k={k} onSaved={load} />)}
          </div>
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
    <div className="grid gap-2 md:grid-cols-[1fr_1.2fr]">
      <div>
        <div className="flex items-center gap-2">
          <code className="text-sm text-text">{k.name}</code>
          <span className={`rounded-full px-2 py-0.5 text-[11px] ${k.set ? "bg-above text-ink" : "bg-panel-2 text-muted"}`}>
            {k.set ? `set ${k.masked}` : "not set"}
          </span>
          {k.cost && <span className="text-[11px] text-muted">{k.cost}</span>}
        </div>
        <p className="mt-1 text-xs text-muted">{k.unlocks}</p>
        <p className="mt-1 text-xs text-muted">How: {k.get} <a href={k.docs} target="_blank" rel="noreferrer" className="text-rise hover:underline">docs ↗</a></p>
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex gap-1.5">
          <input type="password" autoComplete="off" value={value} onChange={(e) => setValue(e.target.value)}
            placeholder={k.set ? "Replace value…" : "Paste value…"}
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
