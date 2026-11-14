"use client";

import { useEffect, useRef, useState } from "react";

type PlanStep = { source: string; steps: number; what: string };
type Progress = {
  step: string | null; sources: string[]; queries_done: number; found: number; errors: number;
  total_steps?: number; plan?: PlanStep[];
};
type Job = {
  id: string; profile: string; kind: string; pid: number; started: string; finished?: string;
  status: "running" | "done" | "failed" | "stopped"; error?: string | null; cmd: string; log: string;
  elapsed_s: number; quiet_s: number | null; log_lines: string[]; log_bytes: number; progress: Progress;
};
type ApifyRun = { actor: string; status: string; started: string; seconds: number; usd: number; id: string };
type Apify = {
  configured: boolean; error?: string; used_usd?: number; limit_usd?: number; cycle_end?: string; running?: number;
  window_usd?: number; window_hours?: number; runs?: ApifyRun[]; cap_per_run?: string;
};
type Data = { ok: boolean; now: string; jobs: Job[]; apify?: Apify; output?: string };

const KIND: Record<string, string> = { ads: "Ads scout", run: "Scouting run", perf: "Own performance" };
const SOURCE: Record<string, string> = {
  apify_meta: "Facebook / Instagram", apify_google: "Google", apify_tiktok_top: "TikTok Top Ads",
  meta_api: "Meta API (EU)", tiktok_api: "TikTok API (EEA)",
};

function dur(s: number) {
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ${s % 60} s`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}
const time = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const usd = (n?: number) => (n == null ? "–" : `$${n.toFixed(2)}`);

export default function ActivityFeed() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updated, setUpdated] = useState<Date | null>(null);

  useEffect(() => {
    let stop = false;
    async function poll() {
      const r: Data | null = await fetch("/api/activity").then((x) => x.json()).catch(() => null);
      if (stop) return;
      if (r?.ok) { setData(r); setError(null); setUpdated(new Date()); }
      else setError(r?.output ?? "Could not read activity");
    }
    poll();
    const t = setInterval(() => document.visibilityState === "visible" && poll(), 3000);
    return () => { stop = true; clearInterval(t); };
  }, []);

  if (!data) return <p className="mt-6 text-muted">{error ?? "Loading…"}</p>;
  const running = data.jobs.filter((j) => j.status === "running");
  const recent = data.jobs.filter((j) => j.status !== "running");

  return (
    <div className="mt-5 space-y-5">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-above opacity-60" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-above" />
        </span>
        Live: updates every 3 s{updated ? ` · last update ${updated.toLocaleTimeString()}` : ""}
        {error && <span className="text-mega"> · {error}</span>}
      </div>

      <ApifyPanel a={data.apify} />

      <section>
        <h2 className="mb-2 font-semibold">Running now {running.length > 0 && <span className="text-muted">({running.length})</span>}</h2>
        {running.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-line p-6 text-sm text-muted">
            Nothing is running. Scheduled runs are weekly (Monday) and currently paused, and paid runs only start from the
            CLI or the scheduled task. A run started any other way shows up here within seconds.
          </div>
        ) : (
          <div className="space-y-4">{running.map((j) => <JobCard key={j.id} j={j} open />)}</div>
        )}
      </section>

      {recent.length > 0 && (
        <section>
          <h2 className="mb-2 font-semibold">Recent runs</h2>
          <div className="space-y-2">{recent.map((j) => <JobCard key={j.id} j={j} />)}</div>
        </section>
      )}
    </div>
  );
}

function StatusPill({ s }: { s: string }) {
  const cls: Record<string, string> = {
    running: "bg-above/15 text-above border-above/40", done: "bg-panel-2 text-text border-line",
    failed: "bg-mega/15 text-mega border-mega/40", stopped: "bg-mega/10 text-mega border-mega/30",
    RUNNING: "bg-above/15 text-above border-above/40", READY: "bg-above/10 text-above border-above/30",
    SUCCEEDED: "bg-panel-2 text-muted border-line", FAILED: "bg-mega/15 text-mega border-mega/40",
    "TIMED-OUT": "bg-mega/15 text-mega border-mega/40", ABORTED: "bg-mega/10 text-mega border-mega/30",
  };
  return <span className={`rounded-full border px-2 py-0.5 text-[11px] ${cls[s] ?? "border-line text-muted"}`}>{s.toLowerCase()}</span>;
}

function ApifyPanel({ a }: { a?: Apify }) {
  if (!a) return null;
  if (!a.configured) return <div className="rounded-2xl border border-line bg-panel p-4 text-sm text-muted">Apify: no APIFY_TOKEN, so no paid sources run.</div>;
  if (a.error) return <div className="rounded-2xl border border-line bg-panel p-4 text-sm text-mega">Apify: {a.error}</div>;
  const pct = a.limit_usd ? Math.min(100, ((a.used_usd ?? 0) / a.limit_usd) * 100) : 0;
  const runs = a.runs ?? [];
  return (
    <section className="rounded-2xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">Apify</h2>
        <span className="text-xs text-muted">
          {a.running ? <span className="text-above">{a.running} actor run{a.running > 1 ? "s" : ""} in progress · </span> : null}
          cap per run ${a.cap_per_run} · cycle resets {a.cycle_end}
        </span>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-panel-2">
          <div className={`h-full rounded-full ${pct >= 80 ? "bg-mega" : "bg-accent"}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="whitespace-nowrap text-sm"><b>{usd(a.used_usd)}</b> <span className="text-muted">of ${a.limit_usd} this cycle</span></span>
      </div>
      <p className="mt-1 text-xs text-muted">Last {a.window_hours} h: {usd(a.window_usd)} across {runs.length} actor run{runs.length === 1 ? "" : "s"}.</p>
      {runs.length > 0 && (
        <div className="mt-3 max-h-72 overflow-auto rounded-lg border border-line">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-panel-2 text-muted">
              <tr><th className="px-2 py-1.5">Started</th><th className="px-2">Actor</th><th className="px-2">Status</th><th className="px-2 text-right">Time</th><th className="px-2 text-right">Cost</th></tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className={`border-t border-line ${r.status === "RUNNING" ? "bg-above/5" : ""}`}>
                  <td className="px-2 py-1 text-muted">{time(r.started)}</td>
                  <td className="px-2"><a href={`https://console.apify.com/actors/runs/${r.id}`} target="_blank" rel="noreferrer" className="hover:underline">{r.actor}</a></td>
                  <td className="px-2"><StatusPill s={r.status} /></td>
                  <td className="px-2 text-right text-muted">{dur(r.seconds)}</td>
                  <td className="px-2 text-right">{r.status === "RUNNING" ? <span className="text-muted">billing…</span> : usd(r.usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function JobCard({ j, open = false }: { j: Job; open?: boolean }) {
  const [expanded, setExpanded] = useState(open);
  const [follow, setFollow] = useState(true);
  const box = useRef<HTMLPreElement>(null);
  const p = j.progress;
  const total = p.total_steps ?? 0;
  const pct = total ? Math.min(100, (p.queries_done / total) * 100) : 0;

  useEffect(() => {
    if (follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [j.log_lines, follow, expanded]);

  return (
    <div className={`rounded-2xl border bg-panel ${j.status === "running" ? "border-above/40" : "border-line"}`}>
      <button onClick={() => setExpanded(!expanded)} className="flex w-full flex-wrap items-center gap-2 px-4 py-3 text-left">
        <span className="font-semibold">{j.profile}</span>
        <span className="text-sm text-muted">{KIND[j.kind] ?? j.kind}</span>
        <StatusPill s={j.status} />
        <span className="text-xs text-muted">
          started {time(j.started)} · {j.status === "running" ? "running for" : "took"} {dur(j.elapsed_s)}
          {j.status === "running" && j.quiet_s != null && ` · last output ${dur(j.quiet_s)} ago`}
        </span>
        <span className="ml-auto text-xs text-muted">{expanded ? "hide log ▲" : "show log ▼"}</span>
      </button>

      {j.status === "running" && (
        <div className="space-y-2 px-4 pb-3">
          {total > 0 && (
            <div className="flex items-center gap-3">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-panel-2">
                <div className="h-full rounded-full bg-above transition-all" style={{ width: `${pct}%` }} />
              </div>
              <span className="whitespace-nowrap text-xs text-muted">{p.queries_done} of {total} steps · {p.found} ads so far</span>
            </div>
          )}
          {p.step && <p className="text-sm">Now: <span className="text-text">{p.step}</span></p>}
          {p.plan && (
            <ul className="flex flex-wrap gap-1.5 text-[11px]">
              {p.plan.map((s) => {
                const started = p.sources.includes(s.source);
                const current = p.sources[p.sources.length - 1] === s.source;
                return (
                  <li key={s.source} title={s.what}
                    className={`rounded-full border px-2 py-0.5 ${current ? "border-above/50 text-above" : started ? "border-line text-text" : "border-line text-muted"}`}>
                    {current ? "▶ " : started ? "✓ " : "· "}{SOURCE[s.source] ?? s.source}: {s.what}
                  </li>
                );
              })}
            </ul>
          )}
          {j.quiet_s != null && j.quiet_s > 120 && (
            <p className="text-xs text-muted">No new output for {dur(j.quiet_s)}: usually it&apos;s waiting on an Apify run (see the Apify table above).</p>
          )}
          {p.errors > 0 && <p className="text-xs text-mega">{p.errors} error line{p.errors > 1 ? "s" : ""} in the log so far.</p>}
        </div>
      )}
      {j.error && <p className="px-4 pb-2 text-xs text-mega">{j.error}</p>}

      {expanded && (
        <div className="border-t border-line px-4 py-3">
          <div className="mb-2 flex flex-wrap items-center gap-3 text-xs text-muted">
            <code className="truncate">{j.cmd}</code>
            <span>pid {j.pid}</span>
            <span>{(j.log_bytes / 1024).toFixed(1)} KB log</span>
            <label className="ml-auto flex items-center gap-1"><input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> follow</label>
          </div>
          <pre ref={box} className="max-h-96 overflow-auto rounded-lg bg-ink p-3 font-mono text-[12px] leading-relaxed text-text">
            {j.log_lines.length ? j.log_lines.join("\n") : "(no output yet)"}
          </pre>
          <p className="mt-1 truncate text-[11px] text-muted">Full log: {j.log}</p>
        </div>
      )}
    </div>
  );
}
