"use client";

import { useEffect, useRef, useState } from "react";

type Progress = { state: "starting" | "waiting" | "done" | "failed"; message: string; url?: string } | null;
type Accounts = {
  instagram: { id: string; username: string; page: string }[];
  ad_accounts: { account_id: string; name: string; currency: string; active: boolean }[];
  pages_without_instagram: string[];
  error?: string;
};

/** Sign in with Facebook once → every Meta key is filled (connect_meta.py). Local dashboard only. */
export default function ConnectMeta({ appSet, signedIn, onDone }: { appSet: boolean; signedIn: boolean; onDone: () => void }) {
  const [progress, setProgress] = useState<Progress>(null);
  const [accounts, setAccounts] = useState<Accounts | null>(null);
  const [ig, setIg] = useState("");
  const [ad, setAd] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  async function loadAccounts() {
    const r = await fetch("/api/connect?accounts=1").then((x) => x.json()).catch(() => null);
    setAccounts(r?.accounts ?? null);
  }
  useEffect(() => {
    if (signedIn) loadAccounts();
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [signedIn]);

  async function start() {
    setMsg(null);
    setBusy(true);
    await fetch("/api/connect", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ action: "start" }) });
    timer.current = setInterval(async () => {
      const r = await fetch("/api/connect").then((x) => x.json()).catch(() => null);
      const p: Progress = r?.progress ?? null;
      setProgress(p);
      if (p && (p.state === "done" || p.state === "failed")) {
        if (timer.current) clearInterval(timer.current);
        setBusy(false);
        if (p.state === "done") { onDone(); loadAccounts(); }
      }
    }, 2000);
  }

  async function save() {
    setBusy(true);
    setMsg(null);
    const r = await fetch("/api/connect", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ action: "use", ig: ig || undefined, ad_account: ad || undefined }) })
      .then((x) => x.json()).catch(() => ({ ok: false, output: "request failed" }));
    setBusy(false);
    setMsg({ ok: r.ok, text: r.output });
    if (r.ok) onDone();
  }

  return (
    <div className="rounded-2xl border border-accent/40 bg-panel p-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold">Connect Meta (Instagram + Facebook ads)</h2>
          <p className="text-sm text-muted">
            One Facebook sign-in fills <code>IG_GRAPH_TOKEN</code> (a Page token that doesn&apos;t expire), <code>IG_GRAPH_USER_ID</code>,{" "}
            <code>META_AD_ACCOUNT_ID</code>, <code>META_ADS_TOKEN</code> and, when your account may use it, <code>META_AD_LIBRARY_TOKEN</code>.
          </p>
        </div>
        <button disabled={!appSet || busy} onClick={start}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-ink hover:opacity-90 disabled:opacity-40">
          {signedIn ? "Sign in again" : "Sign in with Facebook"}
        </button>
      </div>
      {!appSet && (
        <p className="mt-2 text-xs text-muted">
          Once first: save <a href="#key-META_APP_ID" className="text-rise hover:underline">META_APP_ID</a> and{" "}
          <a href="#key-META_APP_SECRET" className="text-rise hover:underline">META_APP_SECRET</a> below, from a Meta for Developers
          app with Facebook Login for Business and <code>http://localhost:8765/</code> in its Valid OAuth Redirect URIs.
        </p>
      )}
      {progress && (
        <p className={`mt-2 whitespace-pre-line text-xs ${progress.state === "failed" ? "text-mega" : progress.state === "done" ? "text-above" : "text-muted"}`}>
          {progress.message}
          {progress.state === "waiting" && progress.url && <> <a href={progress.url} target="_blank" rel="noreferrer" className="text-rise hover:underline">open the sign-in ↗</a></>}
        </p>
      )}
      {accounts?.error && <p className="mt-2 text-xs text-mega">{accounts.error}</p>}
      {accounts && !accounts.error && (accounts.instagram.length > 1 || accounts.ad_accounts.length > 1) && (
        <div className="mt-3 flex flex-wrap items-end gap-2 text-sm">
          {accounts.instagram.length > 1 && (
            <label className="flex flex-col gap-1 text-xs text-muted">Instagram account
              <select value={ig} onChange={(e) => setIg(e.target.value)} className="rounded-lg border border-line bg-panel-2 px-2 py-1.5 text-sm text-text">
                <option value="">keep current</option>
                {accounts.instagram.map((a) => <option key={a.id} value={a.id}>@{a.username} ({a.page})</option>)}
              </select>
            </label>
          )}
          {accounts.ad_accounts.length > 1 && (
            <label className="flex flex-col gap-1 text-xs text-muted">Default ad account
              <select value={ad} onChange={(e) => setAd(e.target.value)} className="rounded-lg border border-line bg-panel-2 px-2 py-1.5 text-sm text-text">
                <option value="">keep current</option>
                {accounts.ad_accounts.map((a) => <option key={a.account_id} value={a.account_id}>{a.name} · {a.currency}{a.active ? "" : " (inactive)"}</option>)}
              </select>
            </label>
          )}
          <button disabled={busy || (!ig && !ad)} onClick={save}
            className="rounded-lg border border-accent/60 px-3 py-1.5 text-sm text-accent hover:bg-accent/10 disabled:opacity-40">Use these</button>
        </div>
      )}
      {msg && <p className={`mt-2 whitespace-pre-line text-xs ${msg.ok ? "text-above" : "text-mega"}`}>{msg.text}</p>}
    </div>
  );
}
