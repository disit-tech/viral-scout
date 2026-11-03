"use client";

import { useState } from "react";
import Link from "next/link";
import type { Item } from "@/lib/types";
import { age, num, tier, times } from "@/lib/format";
import Sparkline from "./Sparkline";
import { cli, runAction, type ActionBody } from "./actions";

const TIER = {
  mega: { text: "🔥 mega", cls: "bg-mega text-ink border-mega" },
  viral: { text: "⚡ viral", cls: "bg-viral text-ink border-viral" },
  above: { text: "↑ above", cls: "bg-above text-ink border-above" },
};

const TONE = { mega: "text-mega", viral: "text-viral", above: "text-above" } as const;

const PLATFORM: Record<string, string> = { youtube: "YouTube", instagram: "Instagram", tiktok: "TikTok" };

export default function PostCard({ item, profile, local, onChange }: {
  item: Item; profile: string; local: boolean; onChange: (key: string, patch: Partial<Item>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const t = tier(item.outlier);
  const reachLabel = item.views !== null ? "views" : "likes";
  const reach = item.views ?? item.likes;
  const detail = `/p/${profile}/v/${encodeURIComponent(item.id)}`;

  async function act(body: ActionBody, patch: Partial<Item>) {
    if (!local) {
      await navigator.clipboard?.writeText(cli(body)).catch(() => undefined);
      setMsg(`Copied: ${cli(body)}`);
      return;
    }
    setBusy(body.action);
    setMsg(null);
    const r = await runAction(body);
    setBusy(null);
    if (r.ok) onChange(item.key, patch);
    setMsg(r.ok ? (body.action === "save" ? "Saved to the swipe file" : "Done") : r.output.slice(0, 200));
  }

  return (
    <article className={`flex flex-col overflow-hidden rounded-2xl border bg-panel transition ${item.saved ? "border-above/50" : "border-line"} ${item.dismissed ? "opacity-40" : ""}`}>
      <Link href={detail} className="group relative block aspect-video bg-panel-2" title="Open the full analysis">
        {item.thumbnail ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={item.thumbnail} alt="" loading="lazy" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted">{PLATFORM[item.platform] ?? item.platform}</div>
        )}
        <div className="absolute left-2 top-2 flex gap-1.5">
          {t && <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold backdrop-blur ${TIER[t].cls}`}>{TIER[t].text} {times(item.outlier)}</span>}
          {item.new && <span className="rounded-full border border-rise bg-rise px-2 py-0.5 text-xs font-semibold text-ink">new</span>}
          {item.early && <span className="rounded-full border border-line bg-ink/90 px-2 py-0.5 text-xs text-text">⏳ early</span>}
        </div>
        <span className="absolute bottom-2 right-2 rounded bg-ink/80 px-1.5 py-0.5 text-[11px] text-muted">{PLATFORM[item.platform] ?? item.platform} · {age(item.published)}</span>
        <span className="absolute inset-0 flex items-center justify-center bg-ink/0 text-sm font-semibold text-transparent transition group-hover:bg-ink/55 group-hover:text-text">Open analysis →</span>
      </Link>

      <div className="flex flex-1 flex-col gap-2.5 p-3.5">
        <div className="flex items-start gap-2">
          <Link href={detail} className="line-clamp-2 flex-1 font-medium leading-snug hover:text-accent">{item.title || item.id}</Link>
          <a href={item.url} target="_blank" rel="noreferrer" title={`Open on ${PLATFORM[item.platform] ?? "the platform"}`} className="text-muted hover:text-text">↗</a>
        </div>
        <a href={item.channel_url || undefined} target="_blank" rel="noreferrer" className="truncate text-sm text-muted hover:text-text">
          {item.channel}{item.followers ? ` · ${num(item.followers)} followers` : ""}
        </a>

        <dl className="grid grid-cols-4 gap-1.5 text-center">
          <Metric label={reachLabel} value={num(reach)} />
          <Metric label="per day" value={num(item.per_day)} />
          <Metric label="× usual" value={times(item.outlier)} tone={t ? TONE[t] : undefined} />
          <Metric label="rise/day" value={item.rise_per_day ? `+${num(item.rise_per_day)}` : "—"} tone={item.rise_per_day ? "text-rise" : undefined} />
        </dl>

        {item.history.length > 1 && (
          <div className="flex items-center gap-2 text-xs text-muted"><Sparkline points={item.history} /> {item.history.length} measurements</div>
        )}

        {item.hook && (
          <blockquote className="border-l-2 border-accent pl-2.5 text-sm italic text-text/90">“{item.hook}”</blockquote>
        )}

        {(item.cta || item.wpm || item.creator_pct != null || item.vs_pace || item.vs_topic || item.emerging) && (
          <div className="space-y-1 text-xs text-muted">
            {item.cta && <p><span className="text-text/70">Ends with:</span> “{item.cta}”</p>}
            <p className="flex flex-wrap gap-x-3">
              {item.wpm ? <span>{item.wpm} words/min</span> : null}
              {item.creator_pct != null ? <span>beats {Math.round(item.creator_pct)}% of their posts</span> : null}
              {item.vs_pace ? <span>{times(item.vs_pace)} their usual views/day</span> : null}
              {item.vs_topic ? <span>{times(item.vs_topic)} the niche median</span> : null}
              {item.emerging ? <span className="text-rise">🌱 emerging creator</span> : null}
            </p>
          </div>
        )}

        {item.questions && item.questions.length > 0 && (
          <details className="text-xs">
            <summary className="cursor-pointer text-rise">Viewers ask ({item.questions.length})</summary>
            <ul className="mt-1 list-disc space-y-0.5 pl-4 text-muted">{item.questions.slice(0, 6).map((q, i) => <li key={i}>{q}</li>)}</ul>
          </details>
        )}

        {(item.transcript || item.description) && (
          <div>
            <button onClick={() => setOpen(!open)} className="text-xs text-rise hover:underline">
              {open ? "Hide" : "Show"} {item.transcript ? "transcript" : "caption"}
            </button>
            {open && (
              <p className="mt-1.5 max-h-56 overflow-auto whitespace-pre-line rounded-lg bg-panel-2 p-2.5 text-xs leading-relaxed text-muted">
                {item.transcript || item.description}
              </p>
            )}
          </div>
        )}

        <div className="mt-auto flex flex-wrap gap-1.5 pt-1">
          <Btn disabled={!!busy || item.saved} onClick={() => act({ profile, action: "save", ref: item.id }, { saved: true, tracked: true })}>
            {item.saved ? "✓ Saved" : busy === "save" ? "Saving…" : "Save"}
          </Btn>
          {!item.tracked && (
            <Btn disabled={!!busy} onClick={() => act({ profile, action: "track", ref: item.url }, { tracked: true })}>
              {busy === "track" ? "…" : "Track"}
            </Btn>
          )}
          <Btn subtle disabled={!!busy || item.dismissed} onClick={() => act({ profile, action: "dismiss", ref: item.id }, { dismissed: true })}>
            {item.dismissed ? "Dismissed" : busy === "dismiss" ? "…" : "Dismiss"}
          </Btn>
          <span className="ml-auto self-center font-mono text-[10px] text-muted">{item.id}</span>
        </div>
        {msg && <p className="break-all text-[11px] text-muted">{msg}</p>}
      </div>
    </article>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg bg-panel-2 px-1 py-1.5">
      <dd className={`text-sm font-semibold ${tone ?? ""}`}>{value}</dd>
      <dt className="text-[10px] uppercase tracking-wide text-muted">{label}</dt>
    </div>
  );
}

function Btn({ children, onClick, disabled, subtle }: { children: React.ReactNode; onClick: () => void; disabled?: boolean; subtle?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className={`rounded-lg border px-2.5 py-1 text-xs transition disabled:cursor-default disabled:opacity-60 ${subtle ? "border-line text-muted hover:text-text" : "border-accent/50 text-accent hover:bg-accent/10"}`}>
      {children}
    </button>
  );
}
