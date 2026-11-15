"use client";

import { useCallback, useEffect, useState } from "react";

type Bot = {
  slug: string;
  token: boolean;
  username?: string | null;
  where: "service" | "forward" | "elsewhere" | "none" | "unknown";
  webhook?: string | null;
  pending?: number;
  lastError?: string | null;
  lastErrorAt?: string | null;
  shared?: boolean;
};
type When = { id?: number; at: string | null; kind?: string; value?: string | null; status?: string } | null;
type Row = {
  profile: string;
  error?: string;
  service?: string;
  label?: string;
  ideas?: Bot;
  video?: Bot;
  oldBot?: Bot | null;
  sharedConfigured?: { ideas: string | null; video: string | null };
  activity?: {
    lastIdeaPosted: When;
    waitingForRating: number;
    lastTap: When;
    lastComment: When;
    lastNote: When;
    openNotes: number;
  };
  test?: { ok: boolean; message_id?: number };
};

const WHERE: Record<Bot["where"], { text: string; tone: string; help: string }> = {
  service: { text: "connected", tone: "text-above", help: "Telegram sends this bot's taps and replies to the bot service." },
  forward: { text: "via its own site", tone: "text-above", help: "The bot's webhook is its own site, which forwards idea taps to the service." },
  elsewhere: { text: "handled by another site", tone: "text-viral", help: "Telegram sends this bot's taps and replies to another site (shown next to it), not to the bot service. It can still work there; move the webhook to the service to see it here." },
  none: { text: "no webhook", tone: "text-mega", help: "Telegram has nowhere to send taps and replies: buttons won't react." },
  unknown: { text: "no token", tone: "text-mega", help: "The bot service has no token for this bot yet." },
};

function ago(iso: string | null | undefined) {
  if (!iso) return "never";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 90) return "just now";
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  if (s < 129600) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
}

function BotLine({ role, bot, onTest, busy }: { role: string; bot?: Bot | null; onTest?: () => void; busy?: boolean }) {
  if (!bot) return null;
  const w = WHERE[bot.where] ?? WHERE.unknown;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line py-2 text-sm first:border-t-0">
      <span className="w-24 shrink-0 text-muted">{role}</span>
      <span className="font-medium text-text">{bot.username ? `@${bot.username}` : bot.slug}</span>
      {bot.shared === false && role !== "Old bot" && <span className="rounded-full border border-line px-2 py-0.5 text-xs text-muted" title="This business still uses its own bot: the shared one has no token yet">own bot</span>}
      <span className={`${w.tone} font-medium`} title={w.help}>● {w.text}</span>
      {bot.webhook && <span className="truncate text-xs text-muted" title="Where Telegram sends its updates">{bot.webhook}</span>}
      {!!bot.pending && <span className="text-xs text-viral" title="Updates Telegram could not deliver yet">{bot.pending} waiting at Telegram</span>}
      {bot.lastError && <span className="text-xs text-mega" title={bot.lastErrorAt ?? ""}>last error: {bot.lastError} ({ago(bot.lastErrorAt)})</span>}
      {onTest && bot.token && (
        <button onClick={onTest} disabled={busy}
          className="ml-auto rounded-lg border border-line px-2.5 py-1 text-xs text-muted hover:bg-panel-2 hover:text-text disabled:opacity-50"
          title="Sends a short test message through this bot to the group">
          {busy ? "Sending…" : "Send test message"}
        </button>
      )}
    </div>
  );
}

export default function BotsPanel() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setError(null);
    const r = await fetch("/api/bots").then((x) => x.json()).catch(() => null);
    if (!r?.ok) setError(r?.error ?? "Could not reach the dashboard API.");
    else setRows(r.profiles ?? []);
  }, []);

  useEffect(() => { load(); }, [load]);

  async function test(profile: string, role: "ideas" | "video") {
    setBusy(`${profile}:${role}`);
    const r = await fetch("/api/bots", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile, role }) })
      .then((x) => x.json()).catch(() => null);
    setNote((n) => ({ ...n, [profile]: r?.ok ? `✓ Test message sent by the ${role} bot. Check the group.` : `✗ ${r?.error ?? "failed"}` }));
    setBusy(null);
  }

  if (error) return <div className="mt-6 rounded-xl border border-mega/40 p-4 text-sm text-mega">{error}</div>;
  if (!rows) return <div className="mt-6 text-sm text-muted">Asking the bot service and Telegram…</div>;
  if (!rows.length) return <div className="mt-6 text-sm text-muted">No business has an <code>ideas:</code> block in its profile yet.</div>;

  return (
    <div className="mt-6 space-y-4">
      <div className="flex justify-end">
        <button onClick={() => { setRows(null); load(); }} className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted hover:bg-panel hover:text-text">Check again</button>
      </div>
      {rows.map((r) => {
        const a = r.activity;
        return (
          <section key={r.profile} className="rounded-2xl border border-line bg-panel p-4 sm:p-5">
            <div className="flex flex-wrap items-baseline gap-2">
              <h2 className="text-lg font-semibold">{r.label?.replace(/·\s*$/, "").trim() || r.profile}</h2>
              <span className="text-xs text-muted">profile {r.profile}</span>
            </div>
            {r.error ? (
              <p className="mt-2 text-sm text-mega">{r.error}</p>
            ) : (
              <>
                <div className="mt-3">
                  <BotLine role="Ideas bot" bot={r.ideas} onTest={() => test(r.profile, "ideas")} busy={busy === `${r.profile}:ideas`} />
                  <BotLine role="Video bot" bot={r.video} onTest={() => test(r.profile, "video")} busy={busy === `${r.profile}:video`} />
                  <BotLine role="Old bot" bot={r.oldBot} />
                </div>
                {a && (
                  <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-5">
                    <div><dt className="text-xs text-muted">Last idea posted</dt><dd>{ago(a.lastIdeaPosted?.at)}{a.lastIdeaPosted?.id ? ` · #${a.lastIdeaPosted.id}` : ""}</dd></div>
                    <div><dt className="text-xs text-muted">Waiting for your rating</dt><dd>{a.waitingForRating}</dd></div>
                    <div><dt className="text-xs text-muted">Last button tap</dt><dd>{ago(a.lastTap?.at)}{a.lastTap?.value ? ` · ${a.lastTap.value}` : ""}</dd></div>
                    <div><dt className="text-xs text-muted">Last comment</dt><dd>{ago(a.lastComment?.at)}</dd></div>
                    <div><dt className="text-xs text-muted">Notes for Claude</dt><dd>{a.openNotes} open · last {ago(a.lastNote?.at)}</dd></div>
                  </dl>
                )}
                {note[r.profile] && <p className="mt-3 text-sm text-muted">{note[r.profile]}</p>}
              </>
            )}
          </section>
        );
      })}
      <p className="text-xs text-muted">
        &quot;Connected&quot; means Telegram delivers that bot&apos;s button taps and replies to the bot service. A test message proves the bot can post;
        rating a new idea (or replying to the bot) proves the way back. Setup: <a className="text-rise underline" href="/docs/telegram-service">Telegram ideas service</a>.
      </p>
    </div>
  );
}
