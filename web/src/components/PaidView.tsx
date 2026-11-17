"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ago, when } from "@/lib/format";
import { PLATFORM_NAMES, usd, type Account, type Brief, type Campaign, type Paid, type PaidPlatform } from "@/lib/paid-format";

const GOALS = ["leads", "sales", "traffic", "awareness", "messages", "calls"];
type Msg = { ok: boolean; text: string } | null;

async function post(body: object) {
  return fetch("/api/paid", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })
    .then((r) => r.json()).catch(() => ({ ok: false, output: "request failed" }));
}

/** The Paid ads page: the month against the cap, every connected account's campaigns, the brief Claude works from,
 *  and the change log. Buttons run `python -m viral_scout paid …` (local dashboard only). */
export default function PaidView({ paid, local }: { paid: Paid; local: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState<Msg>(null);
  const p = paid.profile;

  async function act(key: string, body: object) {
    setBusy(key);
    setMsg(null);
    const r = await post({ profile: p, ...body });
    setBusy("");
    setMsg({ ok: r.ok, text: String(r.output ?? "").trim().split("\n").filter(Boolean).slice(-3).join(" · ") });
    router.refresh();
  }

  const m = paid.month;
  const pct = (v: number) => (paid.cap > 0 ? Math.min(100, (v / paid.cap) * 100) : 0);
  const over = paid.cap > 0 && m.projected > paid.cap;

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-line bg-panel p-4">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold">Paid ads</h1>
          <span className="text-xs text-muted" suppressHydrationWarning title={paid.snapshot ? when(paid.snapshot.pulled) : undefined}>
            {paid.snapshot ? `accounts read ${ago(paid.snapshot.pulled)}` : "accounts not read yet"}
          </span>
          {local && (
            <button disabled={!!busy} onClick={() => act("pull", { action: "pull" })}
              className="ml-auto rounded-lg border border-line px-3 py-1.5 text-sm hover:bg-panel-2 disabled:opacity-40">
              {busy === "pull" ? "Reading accounts…" : "↻ Read accounts now"} <span className="text-xs text-muted">free</span>
            </button>
          )}
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-4">
          <Stat label="monthly cap" value={paid.cap > 0 ? usd(paid.cap) : "not set"} warn={paid.cap <= 0} />
          <Stat label="spent this month" value={usd(m.spent, 2)} />
          <Stat label="running ads will add" value={usd(m.running, 2)} hint={`${m.days_left} days left, at today's budgets`} />
          <Stat label="projected month" value={usd(m.projected, 2)} warn={over} />
        </div>
        <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-panel-2" aria-hidden>
          <div className="flex h-full">
            <div className="h-full bg-accent" style={{ width: `${pct(m.spent)}%` }} />
            <div className="h-full bg-accent/40" style={{ width: `${Math.max(0, pct(m.projected) - pct(m.spent))}%` }} />
          </div>
        </div>
        <p className={`mt-2 text-sm ${over || paid.cap <= 0 ? "text-mega" : "text-muted"}`}>{m.check}</p>
        <p className="mt-1 text-[11px] text-muted">
          The cap is a hard limit across every platform: Claude, the dashboard and the CLI refuse to start or raise a budget
          that would take the projected month over it. Pausing always works. Scheduled jobs never spend.
        </p>
        {msg && <p className={`mt-2 text-sm ${msg.ok ? "text-above" : "text-mega"}`}>{msg.text}</p>}
      </section>

      <AskClaude paid={paid} local={local} busy={busy} onAsk={(extra) => act("ask", { action: "ask", extra })} />

      {paid.platforms.map((pl) => (
        <AccountCard key={pl} platform={pl} account={paid.snapshot?.platforms[pl]} accountId={paid.accounts[pl]}
          local={local} busy={busy} act={act} />
      ))}

      <BriefForm paid={paid} local={local} />

      <section className="rounded-2xl border border-line bg-panel p-4 text-sm">
        <h2 className="mb-2.5 font-semibold">Change log</h2>
        {paid.log.length === 0 ? <p className="text-muted">No changes yet. Every launch, pause, resume, budget change and refusal lands here, with who did it.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-muted"><tr><th className="py-1 pr-3">when</th><th className="pr-3">who</th><th className="pr-3">what</th><th className="pr-3">platform</th><th>details</th></tr></thead>
              <tbody>
                {paid.log.map((r, i) => (
                  <tr key={i} className="border-t border-line align-top">
                    <td className="py-1.5 pr-3 whitespace-nowrap" suppressHydrationWarning title={when(r.at)}>{ago(r.at)}</td>
                    <td className="pr-3">{r.by}</td>
                    <td className={`pr-3 font-medium ${r.action === "refused" ? "text-mega" : r.action === "launch" ? "text-above" : ""}`}>{r.action}</td>
                    <td className="pr-3">{r.platform || "—"}</td>
                    <td>{r.text}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value, hint, warn }: { label: string; value: string; hint?: string; warn?: boolean }) {
  return (
    <div className="rounded-lg bg-panel-2 px-3 py-2" title={hint}>
      <div className={`text-lg font-semibold ${warn ? "text-mega" : ""}`}>{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-muted">{label}</div>
    </div>
  );
}

function AskClaude({ paid, local, busy, onAsk }: { paid: Paid; local: boolean; busy: string; onAsk: (extra: string) => void }) {
  const [extra, setExtra] = useState("");
  const b = paid.brief;
  const missing = (["goal", "daily_budget_usd", "geo", "audience"] as const).filter((k) => !b[k]);
  return (
    <section className="rounded-2xl border border-accent/40 bg-panel p-4 text-sm">
      <h2 className="mb-1 font-semibold">Ask Claude to build a campaign</h2>
      <p className="text-muted">
        Claude reads the ad accounts, your competitors&apos; long-running ads, search demand and your own results, writes a plan from the
        brief below, checks the cap, then builds the campaign through Meta&apos;s official connector and launches it if it fits. You can
        pause it here at any time.
      </p>
      <p className="mt-2">
        Brief: <b>{b.goal ?? "goal?"}</b> · <b>{b.daily_budget_usd ? `${usd(b.daily_budget_usd)}/day` : "budget?"}</b> · <b>{b.geo ?? "area?"}</b> · <b>{b.audience ?? "audience?"}</b>
        {b.offer ? <> · offer: {b.offer}</> : null}
      </p>
      {missing.length > 0 && <p className="mt-1 text-mega">Fill in the brief first: {missing.join(", ").replaceAll("_usd", "").replaceAll("_", " ")}.</p>}
      {local ? (
        <div className="mt-3 space-y-2">
          <textarea value={extra} onChange={(e) => setExtra(e.target.value)} rows={2} maxLength={2000}
            placeholder="Anything for this campaign only (e.g. 'promote the winter checklist video', 'test 2 hooks')"
            className="w-full rounded-lg border border-line bg-panel-2 p-2 text-sm" />
          <button disabled={!!busy || missing.length > 0 || paid.cap <= 0} onClick={() => onAsk(extra)}
            className="rounded-lg border border-accent/60 px-3 py-1.5 text-accent hover:bg-accent/10 disabled:opacity-40">
            {busy === "ask" ? "Starting…" : "Build campaign with Claude"} <span className="text-xs opacity-70">Claude subscription · spends ad budget within the cap</span>
          </button>
          <Link href="/activity" target="_blank" className="ml-3 text-xs text-rise hover:underline">watch on Activity ↗</Link>
          {paid.cap <= 0 && <p className="text-xs text-mega">Set a monthly cap below first: without one nothing may start.</p>}
        </div>
      ) : <p className="mt-2 text-xs text-muted">In Claude Code: <code>/ads {paid.profile}</code></p>}
    </section>
  );
}

function AccountCard({ platform, account, accountId, local, busy, act }: {
  platform: PaidPlatform; account?: Account; accountId?: string; local: boolean; busy: string;
  act: (key: string, body: object) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const camps = account?.campaigns ?? [];
  const shown = showAll ? camps : camps.filter((c) => c.running || c.month_spend > 0);
  const state = !accountId ? ["no account id", "text-muted"] : account?.ok ? ["connected", "text-above"] : account?.missing === "key" ? ["needs a key", "text-viral"] : account ? ["can't read", "text-mega"] : ["not read yet", "text-muted"];
  const writable = platform !== "google";
  return (
    <section className="rounded-2xl border border-line bg-panel p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-semibold">{PLATFORM_NAMES[platform]}</h2>
        <span className={`rounded-full border border-line px-2 py-0.5 text-[11px] ${state[1]}`}>{state[0]}</span>
        {account?.name && <span className="text-xs text-muted">{account.name} · {account.account}</span>}
        {account?.manage_url && <a href={account.manage_url} target="_blank" rel="noreferrer" className="ml-auto text-xs text-rise hover:underline">open in the ads app ↗</a>}
      </div>
      {!accountId && <p className="mt-2 text-muted">Add the account id in the brief below (Meta: act_… · Google: 123-456-7890 · TikTok: advertiser id).</p>}
      {account && !account.ok && <p className="mt-2 text-muted">{account.error}{account.missing === "key" && <> · <Link href="/setup" className="text-rise hover:underline">Setup →</Link></>}</p>}
      {platform === "google" && <p className="mt-1 text-[11px] text-muted">Google Ads is read by Claude through Google&apos;s official connector (read-only); changes stay in the Google Ads app. While a Google account is listed, the cap check can&apos;t total the month and refuses new spend.</p>}
      {account?.ok && (
        <>
          <p className="mt-2 text-muted">{usd(account.month_spend, 2)} this month · {camps.filter((c) => c.running).length} running of {camps.length} campaigns</p>
          {shown.length > 0 ? (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-muted">
                  <tr><th className="py-1 pr-3">campaign</th><th className="pr-3">status</th><th className="pr-3">budget</th><th className="pr-3">spent (month)</th><th className="pr-3">{account.result_label ?? "results"}</th><th className="pr-3">cost each</th><th className="pr-3">clicks</th>{local && writable && <th />}</tr>
                </thead>
                <tbody>
                  {shown.map((c) => <Row key={c.id} c={c} platform={platform} local={local && writable} busy={busy} act={act} />)}
                </tbody>
              </table>
            </div>
          ) : <p className="mt-2 text-muted">Nothing running or spent this month.</p>}
          {camps.length > shown.length || showAll ? (
            <button onClick={() => setShowAll(!showAll)} className="mt-2 text-xs text-rise hover:underline">{showAll ? "only running / spending" : `show all ${camps.length}`}</button>
          ) : null}
        </>
      )}
    </section>
  );
}

function Row({ c, platform, local, busy, act }: { c: Campaign; platform: PaidPlatform; local: boolean; busy: string; act: (key: string, body: object) => void }) {
  const key = `${platform}:${c.id}`;
  const budget = c.daily_budget ? `${usd(c.daily_budget, 2)}/day` : c.budget_remaining ? `${usd(c.budget_remaining, 2)} left` : "—";
  return (
    <tr className="border-t border-line">
      <td className="py-1.5 pr-3">{c.name}</td>
      <td className={`pr-3 ${c.running ? "text-above" : "text-muted"}`}>{c.running ? "▶ running" : `⏸ ${c.status.toLowerCase()}`}</td>
      <td className="pr-3 whitespace-nowrap">{budget}{c.budget_level !== "campaign" && c.daily_budget ? <span className="text-muted"> ({c.budget_level}s)</span> : null}</td>
      <td className="pr-3">{usd(c.month_spend, 2)}</td>
      <td className="pr-3">{c.results ?? "—"}</td>
      <td className="pr-3">{usd(c.cost_per_result, 2)}</td>
      <td className="pr-3">{c.clicks.toLocaleString("en-US")}</td>
      {local && (
        <td className="whitespace-nowrap text-right">
          {c.running ? (
            <button disabled={!!busy} onClick={() => act(key, { action: "pause", platform, campaign: c.id })}
              className="rounded border border-line px-2 py-0.5 hover:bg-panel-2 disabled:opacity-40">{busy === key ? "…" : "Pause"}</button>
          ) : (
            <button disabled={!!busy} onClick={() => act(key, { action: "resume", platform, campaign: c.id })}
              title="Only if the month stays under the cap" className="rounded border border-line px-2 py-0.5 hover:bg-panel-2 disabled:opacity-40">{busy === key ? "…" : "Resume"}</button>
          )}
          {c.budget_level === "campaign" && c.daily_budget != null && (
            <button disabled={!!busy} className="ml-1 rounded border border-line px-2 py-0.5 hover:bg-panel-2 disabled:opacity-40"
              onClick={() => {
                const v = window.prompt(`New daily budget for "${c.name}" (USD). Refused if the month would go over the cap.`, String(c.daily_budget));
                if (v) act(key, { action: "budget", platform, campaign: c.id, usd: Number(v) });
              }}>Budget</button>
          )}
        </td>
      )}
    </tr>
  );
}

function BriefForm({ paid, local }: { paid: Paid; local: boolean }) {
  const router = useRouter();
  const [b, setB] = useState<Brief>(paid.brief);
  const [cap, setCap] = useState(String(paid.cap || ""));
  const [acc, setAcc] = useState<Partial<Record<PaidPlatform, string>>>(paid.accounts);
  const [plats, setPlats] = useState<PaidPlatform[]>(paid.platforms);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  const field = "w-full rounded-lg border border-line bg-panel-2 px-2 py-1.5 text-sm";

  async function save() {
    setSaving(true);
    setMsg(null);
    const g = await fetch(`/api/profile?profile=${encodeURIComponent(paid.profile)}`).then((r) => r.json()).catch(() => ({}));
    const set: Record<string, unknown> = { "paid.monthly_cap_usd": Number(cap || 0), "paid.platforms": plats };
    for (const k of ["goal", "geo", "audience", "offer", "landing", "notes"] as const) if ((b[k] ?? "") !== (paid.brief[k] ?? "")) set[`paid.brief.${k}`] = b[k] ?? "";
    if (b.daily_budget_usd !== paid.brief.daily_budget_usd) set["paid.brief.daily_budget_usd"] = Number(b.daily_budget_usd || 0);
    for (const k of ["meta", "google", "tiktok"] as const) if ((acc[k] ?? "") !== (paid.accounts[k] ?? "")) set[`paid.accounts.${k}`] = (acc[k] ?? "").trim();
    const r = await fetch("/api/profile", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ profile: paid.profile, base: g.base, set }) }).then((x) => x.json()).catch(() => ({ ok: false, error: "request failed" }));
    setSaving(false);
    setMsg({ ok: r.ok, text: r.ok ? `Saved (${(r.changed ?? []).length} changes).` : String(r.error ?? "failed") });
    if (r.ok) router.refresh();
  }

  return (
    <section id="brief" className="rounded-2xl border border-line bg-panel p-4 text-sm">
      <h2 className="mb-1 font-semibold">Brief, cap and accounts</h2>
      <p className="mb-3 text-muted">What Claude starts from: goal, budget, area, audience. Saved in this business&apos;s profile (<code>paid:</code>).</p>
      <fieldset disabled={!local} className="grid gap-3 sm:grid-cols-2">
        <label>Goal<select className={field} value={b.goal ?? ""} onChange={(e) => setB({ ...b, goal: e.target.value })}>
          <option value="">—</option>{GOALS.map((g) => <option key={g}>{g}</option>)}</select></label>
        <label>Daily budget per campaign (USD)<input type="number" min={1} className={field} value={b.daily_budget_usd ?? ""} onChange={(e) => setB({ ...b, daily_budget_usd: Number(e.target.value) })} /></label>
        <label>Area (geo)<input className={field} value={b.geo ?? ""} placeholder="Chicago metro, 25 mi around 60601" onChange={(e) => setB({ ...b, geo: e.target.value })} /></label>
        <label>Offer<input className={field} value={b.offer ?? ""} placeholder="free outage checklist" onChange={(e) => setB({ ...b, offer: e.target.value })} /></label>
        <label className="sm:col-span-2">Audience<textarea rows={2} className={field} value={b.audience ?? ""} placeholder="homeowners 35–65 who lost power last winter" onChange={(e) => setB({ ...b, audience: e.target.value })} /></label>
        <label>Landing page<input className={field} value={b.landing ?? ""} placeholder="https://…" onChange={(e) => setB({ ...b, landing: e.target.value })} /></label>
        <label>Notes for Claude<input className={field} value={b.notes ?? ""} placeholder="never mention prices" onChange={(e) => setB({ ...b, notes: e.target.value })} /></label>
        <label>Monthly cap, all platforms (USD)<input type="number" min={0} className={field} value={cap} placeholder="0 = nothing may start" onChange={(e) => setCap(e.target.value)} /></label>
        <div>Platforms
          <div className="mt-1 flex gap-3">{(["meta", "google", "tiktok"] as const).map((pl) => (
            <label key={pl} className="flex items-center gap-1"><input type="checkbox" checked={plats.includes(pl)}
              onChange={(e) => setPlats(e.target.checked ? [...plats, pl] : plats.filter((x) => x !== pl))} />{pl}</label>))}</div>
        </div>
        {(["meta", "google", "tiktok"] as const).map((pl) => (
          <label key={pl}>{PLATFORM_NAMES[pl]} account id<input className={field} value={acc[pl] ?? ""} onChange={(e) => setAcc({ ...acc, [pl]: e.target.value })}
            placeholder={pl === "meta" ? "act_1234567890" : pl === "google" ? "123-456-7890" : "7000000000000000000"} /></label>
        ))}
      </fieldset>
      {local && (
        <div className="mt-3 flex items-center gap-3">
          <button disabled={saving} onClick={save} className="rounded-lg border border-accent/60 px-3 py-1.5 text-accent hover:bg-accent/10 disabled:opacity-40">{saving ? "Saving…" : "Save"}</button>
          {msg && <span className={msg.ok ? "text-above" : "text-mega"}>{msg.text}</span>}
        </div>
      )}
    </section>
  );
}
