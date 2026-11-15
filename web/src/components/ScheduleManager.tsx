"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

type Task = {
  name: string; kind: "profile" | "publish" | "other"; profile: string | null; state: string;
  day: string | null; time: string | null; analyze: boolean; next_run: string | null; last_run: string | null;
  last_result: number; wake: boolean; log_file: string | null; log_tail: string[];
};
type Data = { ok: boolean; now?: string; tasks?: Task[]; profiles?: string[]; output?: string };
type Op = { op: string; name?: string; profile?: string; day?: string; time?: string; analyze?: boolean };

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Daily"];
const ADS_DAY = "Monday"; // run-daily.ps1 -AdsDay default

const when = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "–";

/** Task Scheduler's LastTaskResult → words. */
function result(code: number, lastRun: string | null): { text: string; bad: boolean } {
  if (!lastRun || code === 0x41303) return { text: "never run", bad: false };
  if (code === 0) return { text: "succeeded", bad: false };
  if (code === 0x41301) return { text: "running", bad: false };
  if (code === 0x41306) return { text: "stopped", bad: true };
  return { text: `failed (0x${(code >>> 0).toString(16)})`, bad: true };
}

async function post(body: Op): Promise<{ ok: boolean; output: string }> {
  try {
    const r = await fetch("/api/schedule", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
    const d = await r.json().catch(() => ({ ok: false, output: `HTTP ${r.status}` }));
    return { ok: !!d.ok, output: d.output ?? "" };
  } catch {
    return { ok: false, output: "request failed (is the dashboard server running?)" };
  }
}

export default function ScheduleManager() {
  const [data, setData] = useState<Data | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    const r: Data = await fetch("/api/schedule").then((x) => x.json()).catch(() => ({ ok: false, output: "Could not reach the dashboard server" }));
    setData(r);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(() => document.visibilityState === "visible" && load(), 15_000);
    return () => clearInterval(t);
  }, [load]);

  const act = useCallback(async (key: string, body: Op) => {
    setBusy(key); setMsg(null);
    const r = await post(body);
    setMsg({ ok: r.ok, text: r.output || (r.ok ? "done" : "failed") });
    await load();
    setBusy(null);
  }, [load]);

  if (!data) return <p className="mt-6 text-muted">Loading…</p>;
  if (!data.ok) return <p className="mt-6 text-mega">{data.output}</p>;
  const tasks = data.tasks ?? [];
  const on = tasks.filter((t) => t.state !== "Disabled").length;
  const missing = [...(data.profiles ?? []), "publish"].filter((p) => !tasks.some((t) => t.name === `viral-scout ${p}`));

  return (
    <div className="mt-5 space-y-5">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className={`rounded-full border px-2.5 py-0.5 text-xs ${on ? "border-above/40 text-above" : "border-line text-muted"}`}>
          {on ? `${on} of ${tasks.length} on` : `all ${tasks.length} paused`}
        </span>
        {tasks.length > 0 && (
          <>
            <button disabled={!!busy || on === tasks.length} onClick={async () => {
              if (!confirm("Turn on every task? Each scheduled run uses paid sources (Apify) and the Claude CLI.")) return;
              for (const t of tasks.filter((t) => t.state === "Disabled")) await act("all", { op: "enable", name: t.name });
            }} className="rounded-md border border-line px-2.5 py-1 text-xs hover:bg-panel disabled:opacity-40">Turn all on</button>
            <button disabled={!!busy || on === 0} onClick={async () => {
              for (const t of tasks.filter((t) => t.state !== "Disabled")) await act("all", { op: "disable", name: t.name });
            }} className="rounded-md border border-line px-2.5 py-1 text-xs hover:bg-panel disabled:opacity-40">Pause all</button>
          </>
        )}
        <span className="text-xs text-muted">Live runs and their logs: <Link href="/activity" className="text-rise underline">Activity</Link></span>
      </div>

      {msg && <p className={`text-sm ${msg.ok ? "text-above" : "text-mega"}`}>{msg.text}</p>}

      {tasks.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-line p-6 text-sm text-muted">
          No viral-scout tasks in Task Scheduler. Add one below, or register them all with{" "}
          <code className="text-text">scripts/schedule.ps1 -Profiles a,b -Analyze -Publish</code>.
        </div>
      ) : (
        <div className="space-y-3">{tasks.map((t) => <TaskCard key={t.name} t={t} busy={busy} act={act} />)}</div>
      )}

      {missing.length > 0 && <AddTask options={missing} busy={busy} act={act} />}

      <p className="text-xs text-muted">
        A task can wake a sleeping PC (wake timers must be allowed in the power plan), not one that is shut down. If the PC
        was off, the task runs as soon as it is back. Profiles run one after another, about 30 min apart, because YouTube
        rate-limits bursts; keep publish last.
      </p>
    </div>
  );
}

function TaskCard({ t, busy, act }: { t: Task; busy: string | null; act: (k: string, b: Op) => Promise<void> }) {
  const [day, setDay] = useState(t.day ?? "Monday");
  const [time, setTime] = useState(t.time ?? "07:00");
  const [analyze, setAnalyze] = useState(t.analyze);
  const [log, setLog] = useState(false);
  useEffect(() => { setDay(t.day ?? "Monday"); setTime(t.time ?? "07:00"); setAnalyze(t.analyze); }, [t.day, t.time, t.analyze]);

  const running = t.state === "Running";
  const paused = t.state === "Disabled";
  const dirty = day !== t.day || time !== t.time || analyze !== t.analyze;
  const multiDay = !!t.day && t.day.includes(",");
  const res = result(t.last_result, t.last_run);
  const dis = !!busy;
  const title = t.kind === "publish" ? "Publish dashboard" : t.profile ?? t.name;
  const btn = "rounded-md border px-2.5 py-1 text-xs disabled:opacity-40";

  return (
    <div className={`rounded-2xl border bg-panel ${running ? "border-above/50" : paused ? "border-line" : "border-above/25"}`}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3">
        <span className="font-semibold">{title}</span>
        <span className={`rounded-full border px-2 py-0.5 text-[11px] ${running ? "border-above/40 bg-above/15 text-above" : paused ? "border-line text-muted" : "border-above/30 bg-above/10 text-above"}`}>
          {running ? "running" : paused ? "paused" : "on"}
        </span>
        <span className="text-xs text-muted">
          {paused ? "would run" : "next"} {when(t.next_run)} · last {when(t.last_run)}{" "}
          <span className={res.bad ? "text-mega" : ""}>({res.text})</span>
        </span>
        <div className="ml-auto flex flex-wrap gap-1.5">
          {paused ? (
            <button disabled={dis} onClick={() => act(t.name, { op: "enable", name: t.name })}
              className={`${btn} border-above/40 text-above hover:bg-above/10`}>Turn on</button>
          ) : (
            <button disabled={dis} onClick={() => act(t.name, { op: "disable", name: t.name })}
              className={`${btn} border-line hover:bg-panel-2`}>Pause</button>
          )}
          {running ? (
            <button disabled={dis} onClick={() => act(t.name, { op: "stop", name: t.name })}
              className={`${btn} border-mega/40 text-mega hover:bg-mega/10`}>Stop</button>
          ) : (
            <button disabled={dis} onClick={() => {
              const why = t.kind === "publish"
                ? "Export the data and deploy the dashboard to Vercel now?"
                : `Run ${t.profile} now? This uses paid sources (Apify TikTok${new Date().toLocaleDateString("en-US", { weekday: "long" }) === ADS_DAY ? ", plus the ads scout and search demand because today is the ads day" : ""})${t.analyze ? " and the Claude CLI for the ideas note" : ""}.`;
              if (confirm(why)) act(t.name, { op: "run", name: t.name });
            }} className={`${btn} border-line hover:bg-panel-2`}>Run now</button>
          )}
          <button disabled={dis} onClick={() => confirm(`Remove "${t.name}" from Task Scheduler?`) && act(t.name, { op: "remove", name: t.name })}
            className={`${btn} border-line text-muted hover:border-mega/40 hover:text-mega`}>Remove</button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-line px-4 py-2.5 text-sm">
        <label className="flex items-center gap-1.5 text-xs text-muted">
          Runs
          <select value={multiDay ? "" : day} onChange={(e) => setDay(e.target.value)}
            className="rounded-md border border-line bg-panel-2 px-2 py-1 text-sm text-text">
            {multiDay && <option value="" disabled>{t.day}</option>}
            {DAYS.map((d) => <option key={d} value={d}>{d === "Daily" ? "every day" : `every ${d}`}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-xs text-muted">
          at
          <input type="time" value={time} onChange={(e) => setTime(e.target.value)}
            className="rounded-md border border-line bg-panel-2 px-2 py-1 text-sm text-text [color-scheme:dark]" />
        </label>
        {t.kind === "profile" && (
          <label className="flex items-center gap-1.5 text-xs text-muted" title="After the run, the /viral-scout skill writes the ideas note (Claude Code CLI, your subscription)">
            <input type="checkbox" checked={analyze} onChange={(e) => setAnalyze(e.target.checked)} />
            AI ideas note
          </label>
        )}
        {dirty && (
          <>
            <button disabled={dis || !day || !time} onClick={() => act(t.name, { op: "set", name: t.name, day, time, analyze: t.kind === "profile" ? analyze : undefined })}
              className={`${btn} border-accent/50 text-accent hover:bg-accent/10`}>{busy === t.name ? "Saving…" : "Save"}</button>
            <button disabled={dis} onClick={() => { setDay(t.day ?? "Monday"); setTime(t.time ?? "07:00"); setAnalyze(t.analyze); }}
              className="text-xs text-muted hover:text-text">cancel</button>
          </>
        )}
        {t.kind === "profile" && day && day !== ADS_DAY && day !== "Daily" && (
          <span className="text-xs text-viral">Ads scout and search demand only run on {ADS_DAY}s, so this day gets videos only.</span>
        )}
        {day === "Daily" && <span className="text-xs text-viral">Daily bills Apify every day.</span>}
        {t.log_file && (
          <button onClick={() => setLog(!log)} className="ml-auto text-xs text-muted hover:text-text">
            {log ? "hide last log ▲" : "last log ▼"}
          </button>
        )}
      </div>

      {log && t.log_tail.length > 0 && (
        <div className="border-t border-line px-4 py-3">
          <p className="mb-1 text-[11px] text-muted">data/logs/{t.log_file} (last {t.log_tail.length} lines)</p>
          <pre className="max-h-72 overflow-auto rounded-lg bg-ink p-3 font-mono text-[11px] leading-relaxed text-muted">{t.log_tail.join("\n")}</pre>
        </div>
      )}
    </div>
  );
}

function AddTask({ options, busy, act }: { options: string[]; busy: string | null; act: (k: string, b: Op) => Promise<void> }) {
  const [profile, setProfile] = useState(options[0]);
  const [day, setDay] = useState("Monday");
  const [time, setTime] = useState("07:00");
  const [analyze, setAnalyze] = useState(true);
  useEffect(() => { if (!options.includes(profile)) setProfile(options[0]); }, [options, profile]);

  return (
    <section className="rounded-2xl border border-dashed border-line p-4">
      <h2 className="mb-2 font-semibold">Add a task</h2>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <select value={profile} onChange={(e) => setProfile(e.target.value)} className="rounded-md border border-line bg-panel-2 px-2 py-1">
          {options.map((p) => <option key={p} value={p}>{p === "publish" ? "Publish dashboard" : p}</option>)}
        </select>
        <select value={day} onChange={(e) => setDay(e.target.value)} className="rounded-md border border-line bg-panel-2 px-2 py-1">
          {DAYS.map((d) => <option key={d} value={d}>{d === "Daily" ? "every day" : `every ${d}`}</option>)}
        </select>
        <input type="time" value={time} onChange={(e) => setTime(e.target.value)} className="rounded-md border border-line bg-panel-2 px-2 py-1 [color-scheme:dark]" />
        {profile !== "publish" && (
          <label className="flex items-center gap-1.5 text-xs text-muted">
            <input type="checkbox" checked={analyze} onChange={(e) => setAnalyze(e.target.checked)} /> AI ideas note
          </label>
        )}
        <button disabled={!!busy || !profile || !time}
          onClick={() => act("add", { op: "add", profile, day, time, analyze: profile !== "publish" && analyze })}
          className="rounded-md border border-accent/50 px-2.5 py-1 text-xs text-accent hover:bg-accent/10 disabled:opacity-40">
          {busy === "add" ? "Adding…" : "Add (paused)"}
        </button>
      </div>
      <p className="mt-2 text-xs text-muted">New tasks start paused; turn one on when you want it to run.</p>
    </section>
  );
}
