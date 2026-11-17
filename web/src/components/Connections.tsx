"use client";

import { useEffect, useRef, useState } from "react";

type Provider = "meta" | "google" | "tiktok";
type Progress = { state: "starting" | "waiting" | "paste" | "done" | "failed"; message: string; url?: string } | null;
type Msg = { ok: boolean; text: string } | null;
type MetaAccounts = {
  instagram: { id: string; username: string; page: string }[];
  ad_accounts: { account_id: string; name: string; currency: string; active: boolean }[];
  error?: string;
};
type TikTokAccounts = { advertiser_id: string; name: string }[] | { error: string };

const post = (body: object) =>
  fetch("/api/connect", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })
    .then((x) => x.json()).catch(() => ({ ok: false, output: "request failed" }));

/** Start a sign-in (the CLI opens it in this PC's browser) and follow its status file until it's done. */
function useSignIn(provider: Provider, onDone: () => void) {
  const [progress, setProgress] = useState<Progress>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  async function start() {
    setBusy(true);
    setProgress(null);
    await post({ provider, action: "start" });
    if (timer.current) clearInterval(timer.current);
    timer.current = setInterval(async () => {
      const r = await fetch(`/api/connect?provider=${provider}`).then((x) => x.json()).catch(() => null);
      const p: Progress = r?.progress ?? null;
      setProgress(p);
      if (p && ["done", "failed", "paste"].includes(p.state)) {
        if (timer.current) clearInterval(timer.current);
        setBusy(false);
        if (p.state === "done") onDone();
      }
    }, 2000);
  }
  return { progress, setProgress, busy, start };
}

export default function Connections({ isSet, onDone }: { isSet: (n: string) => boolean; onDone: () => void }) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold">Connect accounts</h2>
        <p className="text-sm text-muted">
          One sign-in per platform fills its keys below. Each needs a developer app made once by hand (the platforms have no API
          for that); the card says which keys. Tokens go to <code>.env</code> on this PC only.
        </p>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        <MetaCard isSet={isSet} onDone={onDone} />
        <GoogleCard isSet={isSet} onDone={onDone} />
        <TikTokCard isSet={isSet} onDone={onDone} />
      </div>
    </section>
  );
}

function Card({ title, fills, needs, ready, connected, busy, onStart, label, children }: {
  title: string; fills: string[]; needs: string[]; ready: boolean; connected: boolean; busy: boolean;
  onStart: () => void; label: string; children?: React.ReactNode;
}) {
  return (
    <div className={`flex flex-col gap-2 rounded-2xl border bg-panel p-4 ${connected ? "border-above/50" : "border-line"}`}>
      <div className="flex items-center gap-2">
        <h3 className="font-semibold">{title}</h3>
        <span className={`rounded-full px-2 py-0.5 text-[11px] ${connected ? "bg-above text-ink" : "bg-panel-2 text-muted"}`}>
          {connected ? "connected" : "not connected"}
        </span>
      </div>
      <p className="text-xs text-muted">Fills {fills.map((f, i) => <span key={f}>{i ? ", " : ""}<code>{f}</code></span>)}.</p>
      {!ready && (
        <p className="text-xs text-muted">
          First save {needs.map((n, i) => <span key={n}>{i ? " and " : ""}<a href={`#key-${n}`} className="text-rise hover:underline">{n}</a></span>)} below
          (how: <a href="https://github.com/disit-tech/viral-scout/blob/main/docs/setup.md#connect-accounts" target="_blank" rel="noreferrer" className="text-rise hover:underline">setup guide ↗</a>).
        </p>
      )}
      <button disabled={!ready || busy} onClick={onStart}
        className="mt-auto self-start rounded-lg bg-accent px-4 py-2 text-sm font-medium text-ink hover:opacity-90 disabled:opacity-40">
        {busy ? "Waiting for the browser…" : connected ? "Sign in again" : label}
      </button>
      {children}
    </div>
  );
}

function ProgressLine({ p }: { p: Progress }) {
  if (!p) return null;
  const cls = p.state === "failed" ? "text-mega" : p.state === "done" ? "text-above" : "text-muted";
  return (
    <p className={`whitespace-pre-line text-xs ${cls}`}>
      {p.message}
      {(p.state === "waiting" || p.state === "paste") && p.url && <> <a href={p.url} target="_blank" rel="noreferrer" className="text-rise hover:underline">open the sign-in ↗</a></>}
    </p>
  );
}

function MsgLine({ m }: { m: Msg }) {
  return m ? <p className={`whitespace-pre-line text-xs ${m.ok ? "text-above" : "text-mega"}`}>{m.text}</p> : null;
}

const select = "rounded-lg border border-line bg-panel-2 px-2 py-1.5 text-sm text-text";

function MetaCard({ isSet, onDone }: { isSet: (n: string) => boolean; onDone: () => void }) {
  const [accounts, setAccounts] = useState<MetaAccounts | null>(null);
  const [ig, setIg] = useState("");
  const [ad, setAd] = useState("");
  const [msg, setMsg] = useState<Msg>(null);
  const load = () => fetch("/api/connect?provider=meta&accounts=1").then((x) => x.json()).then((r) => setAccounts(r?.accounts ?? null)).catch(() => {});
  const s = useSignIn("meta", () => { onDone(); load(); });
  const connected = isSet("META_USER_TOKEN");
  useEffect(() => { if (connected) load(); }, [connected]);

  async function save() {
    setMsg(null);
    const r = await post({ provider: "meta", action: "use", ig: ig || undefined, ad_account: ad || undefined });
    setMsg({ ok: r.ok, text: r.output });
    if (r.ok) onDone();
  }
  const many = accounts && !accounts.error && (accounts.instagram.length > 1 || accounts.ad_accounts.length > 1);
  return (
    <Card title="Meta" label="Sign in with Facebook" busy={s.busy} onStart={s.start} connected={connected}
      ready={isSet("META_APP_ID") && isSet("META_APP_SECRET")} needs={["META_APP_ID", "META_APP_SECRET"]}
      fills={["IG_GRAPH_TOKEN", "IG_GRAPH_USER_ID", "META_AD_ACCOUNT_ID", "META_ADS_TOKEN", "META_AD_LIBRARY_TOKEN"]}>
      <ProgressLine p={s.progress} />
      {accounts?.error && <p className="text-xs text-mega">{accounts.error}</p>}
      {many && (
        <div className="flex flex-col gap-2">
          {accounts!.instagram.length > 1 && (
            <select value={ig} onChange={(e) => setIg(e.target.value)} className={select} aria-label="Instagram account">
              <option value="">Instagram: keep current</option>
              {accounts!.instagram.map((a) => <option key={a.id} value={a.id}>@{a.username} ({a.page})</option>)}
            </select>
          )}
          {accounts!.ad_accounts.length > 1 && (
            <select value={ad} onChange={(e) => setAd(e.target.value)} className={select} aria-label="Default ad account">
              <option value="">Ad account: keep current</option>
              {accounts!.ad_accounts.map((a) => <option key={a.account_id} value={a.account_id}>{a.name} · {a.currency}{a.active ? "" : " (inactive)"}</option>)}
            </select>
          )}
          <button disabled={!ig && !ad} onClick={save}
            className="self-start rounded-lg border border-accent/60 px-3 py-1.5 text-sm text-accent hover:bg-accent/10 disabled:opacity-40">Use these</button>
        </div>
      )}
      <MsgLine m={msg} />
    </Card>
  );
}

function GoogleCard({ isSet, onDone }: { isSet: (n: string) => boolean; onDone: () => void }) {
  const s = useSignIn("google", onDone);
  return (
    <Card title="Google" label="Sign in with Google" busy={s.busy} onStart={s.start}
      connected={isSet("YT_OAUTH_REFRESH_TOKEN") && isSet("GOOGLE_ADS_REFRESH_TOKEN")}
      ready={isSet("YT_OAUTH_CLIENT_ID") && isSet("YT_OAUTH_CLIENT_SECRET")} needs={["YT_OAUTH_CLIENT_ID", "YT_OAUTH_CLIENT_SECRET"]}
      fills={["YT_OAUTH_REFRESH_TOKEN", "GOOGLE_ADS_REFRESH_TOKEN"]}>
      <ProgressLine p={s.progress} />
    </Card>
  );
}

function TikTokCard({ isSet, onDone }: { isSet: (n: string) => boolean; onDone: () => void }) {
  const [accounts, setAccounts] = useState<TikTokAccounts | null>(null);
  const [adv, setAdv] = useState("");
  const [address, setAddress] = useState("");
  const [msg, setMsg] = useState<Msg>(null);
  const load = () => fetch("/api/connect?provider=tiktok&accounts=1").then((x) => x.json()).then((r) => setAccounts(r?.accounts ?? null)).catch(() => {});
  const s = useSignIn("tiktok", () => { onDone(); load(); });
  const connected = isSet("TIKTOK_ADS_TOKEN");
  const ready = isSet("TIKTOK_APP_ID") && isSet("TIKTOK_APP_SECRET");
  useEffect(() => { if (connected && ready) load(); }, [connected, ready]);

  async function paste() {
    setMsg(null);
    const r = await post({ provider: "tiktok", action: "paste", address });
    setMsg({ ok: r.ok, text: r.output });
    if (r.ok) { setAddress(""); s.setProgress(null); onDone(); load(); }
  }
  async function use() {
    setMsg(null);
    const r = await post({ provider: "tiktok", action: "use", advertiser: adv });
    setMsg({ ok: r.ok, text: r.output });
    if (r.ok) onDone();
  }
  const list = Array.isArray(accounts) ? accounts : [];
  return (
    <Card title="TikTok Ads" label="Sign in with TikTok" busy={s.busy} onStart={s.start} connected={connected}
      ready={ready} needs={["TIKTOK_APP_ID", "TIKTOK_APP_SECRET"]} fills={["TIKTOK_ADS_TOKEN", "TIKTOK_ADVERTISER_ID"]}>
      <ProgressLine p={s.progress} />
      {s.progress?.state === "paste" && (
        <div className="flex gap-1.5">
          <input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Paste the address you landed on…"
            className="min-w-0 flex-1 rounded-lg border border-line bg-panel-2 px-2.5 py-1.5 text-sm outline-none focus:border-accent" />
          <button disabled={!address} onClick={paste}
            className="rounded-lg border border-accent/60 px-3 text-sm text-accent hover:bg-accent/10 disabled:opacity-40">Finish</button>
        </div>
      )}
      {accounts && !Array.isArray(accounts) && <p className="text-xs text-mega">{accounts.error}</p>}
      {list.length > 1 && (
        <div className="flex gap-1.5">
          <select value={adv} onChange={(e) => setAdv(e.target.value)} className={`${select} min-w-0 flex-1`} aria-label="Default advertiser">
            <option value="">Default advertiser: keep current</option>
            {list.map((a) => <option key={a.advertiser_id} value={a.advertiser_id}>{a.name} ({a.advertiser_id})</option>)}
          </select>
          <button disabled={!adv} onClick={use}
            className="rounded-lg border border-accent/60 px-3 text-sm text-accent hover:bg-accent/10 disabled:opacity-40">Use</button>
        </div>
      )}
      <MsgLine m={msg} />
    </Card>
  );
}
