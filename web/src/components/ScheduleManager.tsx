"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

type Task = {
  name: string; kind: "profile" | "publish" | "studio" | "legacy" | "other"; profile: string | null; state: string;
  job?: string | null; repeat?: string | null; what?: string | null; script?: string | null; posts_only?: boolean;
  execute?: string | null; arguments?: string | null; working_dir?: string | null; author?: string | null; time_limit?: string | null;
  script_about?: string[]; instructions?: string | null; instructions_about?: string[];
  day: string | null; time: string | null; analyze: boolean; next_run: string | null; last_run: string | null;
  last_result: number; wake: boolean; log_file: string | null; log_tail: string[];
};
/** A profile with an ideas: block and its idea generator settings (python -m viral_scout jobs --overview). */
type IdeaProfile = {
  profile: string; name?: string; configured?: boolean; enabled?: boolean; at?: string; days?: string | string[];
  retry_until?: string; count?: number; delivery?: string; error?: string; has_ideas?: boolean; dirs?: string[];
};
type Data = { ok: boolean; now?: string; tasks?: Task[]; profiles?: string[]; ideas?: IdeaProfile[]; output?: string };
type Op = {
  op: string; name?: string; profile?: string; day?: string; time?: string; analyze?: boolean;
  enabled?: boolean; at?: string; days?: string | string[]; count?: number;
};

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
  // Group by business (default) or by type; remembered per browser (storage can be blocked: then just the default).
  const [group, setGroupState] = useState<"business" | "type">("business");
  useEffect(() => {
    try { if (localStorage.getItem("schedule-group") === "type") setGroupState("type"); } catch { /* no storage */ }
  }, []);
  const setGroup = (g: "business" | "type") => {
    setGroupState(g);
    try { localStorage.setItem("schedule-group", g); } catch { /* no storage */ }
  };
  // Show all tasks, only the ones that are on (incl. running), or only the paused ones; remembered like the grouping.
  const [show, setShowState] = useState<"all" | "on" | "paused">("all");
  useEffect(() => {
    try { const v = localStorage.getItem("schedule-show"); if (v === "on" || v === "paused") setShowState(v); } catch { /* no storage */ }
  }, []);
  const setShow = (v: "all" | "on" | "paused") => {
    setShowState(v);
    try { localStorage.setItem("schedule-show", v); } catch { /* no storage */ }
  };

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
  const all = data.ideas ?? [];                          // every profile (folders), with ideas settings where it has ideas:
  const ideas = all.filter((p) => p.has_ideas !== false && !p.error);
  const legacy = tasks.filter((t) => t.kind === "legacy");
  const studio = tasks.filter((t) => t.kind === "studio" && t.job !== "ideas");
  const scout = tasks.filter((t) => t.kind !== "studio" && t.kind !== "legacy");
  const missing = [...(data.profiles ?? []), "publish"].filter((p) => !tasks.some((t) => t.name === `viral-scout ${p}`));
  const ideaTask = (p: string) => tasks.find((t) => t.name === `viral-scout ${p}.ideas`);
  const pauseAll = async (list: Task[]) => { for (const t of list.filter((t) => t.state !== "Disabled")) await act("all", { op: "disable", name: t.name }); };

  // An idea generator without a task counts as paused (it isn't set up, so it doesn't run).
  const isOn = (state?: string) => Boolean(state) && state !== "Disabled";
  const pass = (state?: string) => show === "all" || (show === "on" ? isOn(state) : !isOn(state));
  const vis = (list: Task[]) => list.filter((t) => pass(t.state));
  const ideaShown = (p: IdeaProfile) => pass(ideaTask(p.profile)?.state);
  const countOn = tasks.filter((t) => isOn(t.state)).length;
  const counts = { all: tasks.length + ideas.filter((p) => !ideaTask(p.profile)).length, on: countOn,
    paused: tasks.length - countOn + ideas.filter((p) => !ideaTask(p.profile)).length };
  const card = (t: Task) => (t.kind === "legacy" ? <LegacyCard key={t.name} t={t} busy={busy} act={act} /> : <TaskCard key={t.name} t={t} busy={busy} act={act} />);
  const ideaCard = (p: IdeaProfile) => <IdeaCard key={p.profile} p={p} task={ideaTask(p.profile)} busy={busy} act={act} />;

  // Business view: every task under the profile it belongs to; the rest (publish, unmatched) under "Shared and other".
  const owner = (t: Task) => ownerOf(t, all);
  const businesses = all.filter((p) => !p.error).map((p) => {
    const own = tasks.filter((t) => owner(t) === p.profile);
    return {
      p, own,
      scout: own.filter((t) => t.kind === "profile"), studio: own.filter((t) => t.kind === "studio" && t.job !== "ideas"),
      legacy: own.filter((t) => t.kind === "legacy"),
    };
  }).filter((b) => b.own.length || b.p.has_ideas !== false);
  const shared = tasks.filter((t) => !owner(t));

  return (
    <div className="mt-5 space-y-5">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className={`rounded-full border px-2.5 py-0.5 text-xs ${on ? "border-above/40 text-above" : "border-line text-muted"}`}>
          {on ? `${on} of ${tasks.length} on` : `all ${tasks.length} paused`}
        </span>
        {tasks.length > 0 && (
          <>
            <button disabled={!!busy || !tasks.some((t) => t.kind !== "legacy" && t.state === "Disabled")} onClick={async () => {
              if (!confirm("Turn on every viral-scout task? Each scheduled run uses paid sources (Apify) and the Claude CLI. Older tasks from other folders stay as they are.")) return;
              for (const t of tasks.filter((t) => t.kind !== "legacy" && t.state === "Disabled")) await act("all", { op: "enable", name: t.name });
            }} className="rounded-md border border-line px-2.5 py-1 text-xs hover:bg-panel disabled:opacity-40">Turn all on</button>
            <button disabled={!!busy || on === 0} onClick={() => pauseAll(tasks)}
              className="rounded-md border border-line px-2.5 py-1 text-xs hover:bg-panel disabled:opacity-40">Pause all</button>
          </>
        )}
        <div className="flex items-center gap-1 text-xs" role="group" aria-label="Group by">
          <span className="text-muted">Group by</span>
          {(["business", "type"] as const).map((g) => (
            <button key={g} onClick={() => setGroup(g)} aria-pressed={group === g}
              className={`rounded-md border px-2 py-0.5 ${group === g ? "border-accent/60 text-accent" : "border-line text-muted hover:text-text"}`}>
              {g === "business" ? "Business" : "Type"}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1 text-xs" role="group" aria-label="Show">
          <span className="text-muted">Show</span>
          {(["all", "on", "paused"] as const).map((v) => (
            <button key={v} onClick={() => setShow(v)} aria-pressed={show === v}
              className={`rounded-md border px-2 py-0.5 ${show === v ? "border-accent/60 text-accent" : "border-line text-muted hover:text-text"}`}>
              {v === "all" ? "All" : v === "on" ? "On" : "Paused"} <span className="opacity-70">{counts[v]}</span>
            </button>
          ))}
        </div>
        <span className="text-xs text-muted">Live runs and their logs: <Link href="/activity" className="text-rise underline">Activity</Link></span>
      </div>

      {msg && <p className={`text-sm ${msg.ok ? "text-above" : "text-mega"}`}>{msg.text}</p>}

      {group === "business" ? (
        <>
          {businesses.map(({ p, own, scout, studio, legacy }) => {
            const onHere = own.filter((t) => t.state !== "Disabled").length;
            const ideaHere = p.has_ideas !== false && ideaShown(p);
            if (show !== "all" && !vis(own.filter((t) => !(t.kind === "studio" && t.job === "ideas"))).length && !ideaHere) return null;
            return (
              <section key={p.profile} className="space-y-2 rounded-2xl border border-line/60 p-3 sm:p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-semibold">{p.name ?? p.profile}</h2>
                  {p.name && p.name !== p.profile && <span className="text-xs text-muted">{p.profile}</span>}
                  <span className={`rounded-full border px-2 py-0.5 text-[11px] ${onHere ? "border-above/40 text-above" : "border-line text-muted"}`}>
                    {own.length === 0 ? "nothing scheduled" : onHere ? `${onHere} of ${own.length} on` : `${own.length} paused`}
                  </span>
                  {onHere > 0 && (
                    <button disabled={!!busy} onClick={() => pauseAll(own)}
                      className="ml-auto rounded-md border border-line px-2.5 py-1 text-xs hover:bg-panel disabled:opacity-40">Pause all for {p.name ?? p.profile}</button>
                  )}
                </div>
                {vis(scout).length > 0 && <Sub label="Weekly scouting run">{vis(scout).map(card)}</Sub>}
                {ideaHere && <Sub label="Idea generator">{ideaCard(p)}</Sub>}
                {vis(studio).length > 0 && <Sub label="Studio jobs">{vis(studio).map(card)}</Sub>}
                {vis(legacy).length > 0 && <Sub label="Older tasks (other folders)">{vis(legacy).map(card)}</Sub>}
              </section>
            );
          })}
          {vis(shared).length > 0 && (
            <section className="space-y-2 rounded-2xl border border-line/60 p-3 sm:p-4">
              <h2 className="font-semibold">Shared and other</h2>
              <p className="text-xs text-muted">Tasks for all businesses (publish), and older tasks that couldn&apos;t be matched to a profile.</p>
              {vis(shared).map(card)}
            </section>
          )}
          {tasks.length === 0 && !businesses.length && <Empty />}
        </>
      ) : (
        <>
          {scout.length === 0 ? <Empty /> : vis(scout).length > 0 && <Sub label="Weekly scouting runs">{vis(scout).map(card)}</Sub>}

          {ideas.filter(ideaShown).length > 0 && (
            <Sub label="Idea generator" intro={<>
              The <code className="text-text">/studio-ideas</code> job per business: it reads your ratings and the latest viral-scout data,
              writes new scored ideas and sends them for rating. It runs the Claude CLI (your subscription, no Apify) at most once per
              run day, retrying hourly until {ideas.find((i) => i.retry_until)?.retry_until ?? "20:00"} if the PC was asleep. Settings are
              saved in the profile (<code className="text-text">jobs.ideas</code>). New ones start paused.
            </>}>{ideas.filter(ideaShown).map(ideaCard)}</Sub>
          )}

          {vis(studio).length > 0 && (
            <Sub label="Studio jobs" intro={<>
              Unattended Claude jobs per business (script, notes, film, blog) and the morning post pack. Their times come from the
              profile&apos;s <code className="text-text">jobs:</code> block; to change them, edit the profile and run{" "}
              <code className="text-text">scripts/schedule-studio.ps1 -Profile &lt;name&gt;</code> again. None of them posts anything.
            </>}>{vis(studio).map(card)}</Sub>
          )}

          {vis(legacy).length > 0 && (
            <Sub label="Older idea and content tasks (other folders)" intro={<>
              Registered by the business sites before the idea generator moved here. They run scripts outside viral-scout, so they
              can be paused, run or removed here but not rescheduled. Once a business&apos;s idea generator is set up, pause or
              remove its older task so ideas aren&apos;t made twice.
            </>}>{vis(legacy).map(card)}</Sub>
          )}
        </>
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

function Sub({ label, intro, children }: { label: string; intro?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</h3>
      {intro && <p className="text-xs text-muted">{intro}</p>}
      {children}
    </div>
  );
}

function Empty() {
  return (
    <div className="rounded-2xl border border-dashed border-line p-6 text-sm text-muted">
      No viral-scout tasks in Task Scheduler. Add one below, or register them all with{" "}
      <code className="text-text">scripts/schedule.ps1 -Profiles a,b -Analyze -Publish</code>.
    </div>
  );
}

/** Which profile a task belongs to: its -Profile; for an older task of another repo, the profile whose folder holds its
 *  script (add_dirs, the vault project), else a distinctive word of the profile name in the task name. */
function ownerOf(t: Task, profiles: IdeaProfile[]): string | null {
  if (t.kind !== "legacy") return t.kind === "publish" ? null : t.profile;
  const path = (t.script ?? "").replace(/\\/g, "/").toLowerCase();
  const byDir = profiles.find((p) => (p.dirs ?? []).some((d) => path.startsWith(d + "/")));
  if (byDir) return byDir.profile;
  const name = t.name.toLowerCase();
  const words = (p: IdeaProfile) =>
    [p.profile, p.name ?? ""].flatMap((s) => s.replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase().split(/[^a-z0-9]+/)).filter((w) => w.length >= 5);
  return profiles.find((p) => words(p).some((w) => name.includes(w)))?.profile ?? null;
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
  const studio = t.kind === "studio";
  const title = t.kind === "publish" ? "Publish dashboard" : studio ? `${t.profile} · ${t.job === "post" ? "morning post pack" : t.job}` : t.profile ?? t.name;
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
                : studio
                ? (t.job === "post" ? `Send today's post pack for ${t.profile} now (if it was not sent yet)?` : `Run the ${t.job} job for ${t.profile} now? It starts the Claude CLI (your subscription) unless today's run is already done or another job holds the lock.`)
                : `Run ${t.profile} now? This uses paid sources (Apify TikTok${new Date().toLocaleDateString("en-US", { weekday: "long" }) === ADS_DAY ? ", plus the ads scout and search demand because today is the ads day" : ""})${t.analyze ? " and the Claude CLI for the ideas note" : ""}.`;
              if (confirm(why)) act(t.name, { op: "run", name: t.name });
            }} className={`${btn} border-line hover:bg-panel-2`}>Run now</button>
          )}
          <button disabled={dis} onClick={() => confirm(`Remove "${t.name}" from Task Scheduler?`) && act(t.name, { op: "remove", name: t.name })}
            className={`${btn} border-line text-muted hover:border-mega/40 hover:text-mega`}>Remove</button>
        </div>
      </div>

      {studio ? (
        <div className="flex flex-wrap items-center gap-2 border-t border-line px-4 py-2.5 text-xs text-muted">
          <span>{t.what?.replace(/^viral-scout studio: /, "") || `${t.day ?? ""} ${t.time ?? ""}`}</span>
          {t.log_file && (
            <button onClick={() => setLog(!log)} className="ml-auto text-xs text-muted hover:text-text">
              {log ? "hide last log ▲" : "last log ▼"}
            </button>
          )}
        </div>
      ) : (
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
      )}

      {log && t.log_tail.length > 0 && (
        <div className="border-t border-line px-4 py-3">
          <p className="mb-1 text-[11px] text-muted">data/logs/{t.log_file} (last {t.log_tail.length} lines)</p>
          <pre className="max-h-72 overflow-auto rounded-lg bg-ink p-3 font-mono text-[11px] leading-relaxed text-muted">{t.log_tail.join("\n")}</pre>
        </div>
      )}
      <About t={t} />
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

const btn = "rounded-md border px-2.5 py-1 text-xs disabled:opacity-40";
const WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

/** "PT15M" / "PT1H" (Task Scheduler repetition) → words. */
function every(iso?: string | null) {
  const m = iso?.match(/^PT(?:(\d+)H)?(?:(\d+)M)?$/);
  if (!m) return "";
  const min = Number(m[1] ?? 0) * 60 + Number(m[2] ?? 0);
  return min === 60 ? "hourly" : min % 60 ? `every ${min} min` : `every ${min / 60} h`;
}

function Pill({ state, label }: { state: string; label?: string }) {
  const running = state === "Running", paused = state === "Disabled";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[11px] ${running ? "border-above/40 bg-above/15 text-above" : paused ? "border-line text-muted" : "border-above/30 bg-above/10 text-above"}`}>
      {label ?? (running ? "running" : paused ? "paused" : "on")}
    </span>
  );
}

const norm = (d?: string | string[]) => (d == null || d === "daily" ? [] : Array.isArray(d) ? d : [d]);

function IdeaCard({ p, task, busy, act }: { p: IdeaProfile; task?: Task; busy: string | null; act: (k: string, b: Op) => Promise<void> }) {
  const [days, setDays] = useState<string[]>(norm(p.days));       // [] = every day
  const [at, setAt] = useState(p.at ?? "08:00");
  const [count, setCount] = useState(p.count ?? 5);
  const [log, setLog] = useState(false);
  const key = `ideas:${p.profile}`;
  const saved = norm(p.days).join();
  useEffect(() => { setDays(saved ? saved.split(",") : []); setAt(p.at ?? "08:00"); setCount(p.count ?? 5); }, [saved, p.at, p.count]);

  if (p.error) return <div className="rounded-2xl border border-mega/40 bg-panel p-4 text-sm text-mega">{p.profile}: {p.error}</div>;
  const dirty = !!task && (at !== p.at || count !== p.count || days.join() !== saved);
  const dis = !!busy;
  const res = task ? result(task.last_result, task.last_run) : null;
  const toggle = (d: string) => setDays(days.includes(d) ? days.filter((x) => x !== d) : WEEK.filter((x) => x === d || days.includes(x)));
  const daysValue = days.length ? days : "daily";
  const label = p.name ?? p.profile;

  return (
    <div className={`rounded-2xl border bg-panel ${task?.state === "Running" ? "border-above/50" : task && task.state !== "Disabled" ? "border-above/25" : "border-line"}`}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3">
        <span className="font-semibold">{label}</span>
        {task ? <Pill state={task.state} /> : <Pill state="Disabled" label="not set up" />}
        {task && (
          <span className="text-xs text-muted">
            {task.state === "Disabled" ? "would run" : "next"} {when(task.next_run)} · last {when(task.last_run)}{" "}
            {res && <span className={res.bad ? "text-mega" : ""}>({res.text})</span>}
          </span>
        )}
        <div className="ml-auto flex flex-wrap gap-1.5">
          {!task ? (
            <button disabled={dis} onClick={() => act(key, { op: "ideas", profile: p.profile, enabled: true, at, days: daysValue, count })}
              className={`${btn} border-accent/50 text-accent hover:bg-accent/10`}>{busy === key ? "Setting up…" : "Set up (paused)"}</button>
          ) : (
            <>
              {task.state === "Disabled" ? (
                <button disabled={dis} onClick={() => act(key, { op: "enable", name: task.name })}
                  className={`${btn} border-above/40 text-above hover:bg-above/10`}>Turn on</button>
              ) : (
                <button disabled={dis} onClick={() => act(key, { op: "disable", name: task.name })} className={`${btn} border-line hover:bg-panel-2`}>Pause</button>
              )}
              {task.state === "Running" ? (
                <button disabled={dis} onClick={() => act(key, { op: "stop", name: task.name })} className={`${btn} border-mega/40 text-mega hover:bg-mega/10`}>Stop</button>
              ) : (
                <button disabled={dis} onClick={() => confirm(`Make ${count} ideas for ${label} now? It starts the Claude CLI (your subscription), unless today's run is already done or another studio job is running.`)
                  && act(key, { op: "run", name: task.name })} className={`${btn} border-line hover:bg-panel-2`}>Run now</button>
              )}
              <button disabled={dis} onClick={() => confirm(`Remove the idea generator task for ${label}? Its settings stay in the profile, switched off.`)
                && act(key, { op: "ideas", profile: p.profile, enabled: false })}
                className={`${btn} border-line text-muted hover:border-mega/40 hover:text-mega`}>Remove</button>
            </>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-line px-4 py-2.5 text-sm">
        <span className="text-xs text-muted">Runs</span>
        <div className="flex flex-wrap gap-1">
          <button onClick={() => setDays([])}
            className={`rounded-md border px-2 py-0.5 text-xs ${days.length === 0 ? "border-accent/60 text-accent" : "border-line text-muted hover:text-text"}`}>every day</button>
          {WEEK.map((d) => (
            <button key={d} onClick={() => toggle(d)} title={d}
              className={`rounded-md border px-2 py-0.5 text-xs ${days.includes(d) ? "border-accent/60 text-accent" : "border-line text-muted hover:text-text"}`}>{d.slice(0, 3)}</button>
          ))}
        </div>
        <label className="flex items-center gap-1.5 text-xs text-muted">
          at
          <input type="time" value={at} onChange={(e) => setAt(e.target.value)}
            className="rounded-md border border-line bg-panel-2 px-2 py-1 text-sm text-text [color-scheme:dark]" />
        </label>
        <label className="flex items-center gap-1.5 text-xs text-muted">
          ideas per run
          <input type="number" min={1} max={20} value={count} onChange={(e) => setCount(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
            className="w-16 rounded-md border border-line bg-panel-2 px-2 py-1 text-sm text-text" />
        </label>
        {dirty && (
          <>
            <button disabled={dis || !at} onClick={() => act(key, { op: "ideas", profile: p.profile, at, days: daysValue, count })}
              className={`${btn} border-accent/50 text-accent hover:bg-accent/10`}>{busy === key ? "Saving…" : "Save"}</button>
            <button disabled={dis} onClick={() => { setDays(saved ? saved.split(",") : []); setAt(p.at ?? "08:00"); setCount(p.count ?? 5); }}
              className="text-xs text-muted hover:text-text">cancel</button>
          </>
        )}
        <span className="text-xs text-muted">· {p.delivery === "telegram" ? "sent to the ideas bot" : "results stay in the vault"}</span>
        {task?.log_file && (
          <button onClick={() => setLog(!log)} className="ml-auto text-xs text-muted hover:text-text">{log ? "hide last log ▲" : "last log ▼"}</button>
        )}
      </div>

      {log && task && task.log_tail.length > 0 && (
        <div className="border-t border-line px-4 py-3">
          <p className="mb-1 text-[11px] text-muted">data/logs/{task.log_file} (last {task.log_tail.length} lines)</p>
          <pre className="max-h-72 overflow-auto rounded-lg bg-ink p-3 font-mono text-[11px] leading-relaxed text-muted">{task.log_tail.join("\n")}</pre>
        </div>
      )}
      <About t={task} fallback={{
        what: JOB_TEXT.ideas.what,
        cost: CLAUDE_COST,
        output: `${JOB_TEXT.ideas.output} Set up registers the task "viral-scout ${p.profile}.ideas", which runs scripts/studio.ps1 -Profile ${p.profile} -Job ideas in the viral-scout folder, with the instructions in viral_scout/jobs/prompts/ideas.md.`,
      }} />
    </div>
  );
}

function LegacyCard({ t, busy, act }: { t: Task; busy: string | null; act: (k: string, b: Op) => Promise<void> }) {
  const dis = !!busy;
  const res = result(t.last_result, t.last_run);
  const what = t.job ? `${t.job} job` : t.posts_only ? "post packs" : "ideas";
  const rep = every(t.repeat);
  const sched = t.day === "Time" ? rep || "repeating" : `${t.day === "Daily" ? "daily" : t.day ?? ""} ${t.time ?? ""}${rep ? `, then ${rep}` : ""}`;
  return (
    <div className={`flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl border bg-panel px-4 py-2.5 ${t.state === "Disabled" ? "border-line" : "border-above/25"}`}>
      <span className="font-medium">{t.name}</span>
      <Pill state={t.state} />
      <span className="text-xs text-muted">
        {what} · {sched} · last {when(t.last_run)} <span className={res.bad ? "text-mega" : ""}>({res.text})</span>
      </span>
      <div className="ml-auto flex flex-wrap gap-1.5">
        {t.state === "Disabled" ? (
          <button disabled={dis} onClick={() => confirm(`Turn "${t.name}" back on? It runs Claude from ${t.script} on its own schedule.`) && act(t.name, { op: "enable", name: t.name })}
            className={`${btn} border-line hover:bg-panel-2`}>Turn on</button>
        ) : (
          <button disabled={dis} onClick={() => act(t.name, { op: "disable", name: t.name })} className={`${btn} border-above/40 text-above hover:bg-above/10`}>Pause</button>
        )}
        {t.state === "Running" ? (
          <button disabled={dis} onClick={() => act(t.name, { op: "stop", name: t.name })} className={`${btn} border-mega/40 text-mega hover:bg-mega/10`}>Stop</button>
        ) : (
          <button disabled={dis} onClick={() => confirm(`Run "${t.name}" now? It starts the Claude CLI (your subscription).`) && act(t.name, { op: "run", name: t.name })}
            className={`${btn} border-line hover:bg-panel-2`}>Run now</button>
        )}
        <button disabled={dis} onClick={() => confirm(`Remove "${t.name}" from Task Scheduler? Only the task goes; ${t.script} stays.`) && act(t.name, { op: "remove", name: t.name })}
          className={`${btn} border-line text-muted hover:border-mega/40 hover:text-mega`}>Remove</button>
      </div>
      <span className="w-full truncate font-mono text-[11px] text-muted" title={t.script ?? ""}>{t.script}</span>
      <div className="-mx-4 -mb-2.5 w-[calc(100%+2rem)]"><About t={t} /></div>
    </div>
  );
}

/** What each job does, what it costs and where its results go, in plain words. */
const JOB_TEXT: Record<string, { what: string; output: string }> = {
  ideas: {
    what: "Idea generator. Claude reads your past ratings, the business's notes in the vault and viral-scout's latest data (viral videos, competitors' ads, search demand, swipe file), then writes new scored ideas and sends them for you to rate.",
    output: "New ideas go to the ideas API and its Telegram bot (or into the vault when delivery is off); a daily note in the vault says what was done.",
  },
  script: {
    what: "Writes one video scenario (the script: hook, lines, cards) for an idea you approved, and sends it to you for ✅ approve or ✏️ changes.",
    output: "The scenario in the vault and as a Telegram message.",
  },
  notes: {
    what: "Looks every 15 minutes for notes you sent (in Telegram) and scenarios you approved. Claude only starts when something is waiting, e.g. to turn an approved scenario into a video draft.",
    output: "Replies in Telegram; drafts in the vault.",
  },
  film: {
    what: "Makes one finished animated film for tomorrow's post. If the PC was asleep it retries hourly; once today's film is done it skips.",
    output: "The video file and its captions in the business's video folder; a message when it's ready.",
  },
  blog: {
    what: "Writes one blog guide draft a week and sends it for ✅ Publish or ✏️ Changes.",
    output: "The draft in the vault and a Telegram message; nothing is published without your ✅.",
  },
  post: {
    what: "Morning post pack: today's planned posts with their captions, sent to you to post. No Claude.",
    output: "A Telegram message (or a note in the vault). Nothing is posted automatically.",
  },
};
const CLAUDE_COST = "The Claude CLI on your subscription (no API key, no Apify).";

function explain(t: Task): { what: string; cost: string; output: string } {
  if (t.kind === "profile") {
    return {
      what: `Weekly scouting run for ${t.profile}: finds what's trending on its topic (YouTube; Instagram and TikTok when their keys are set), re-measures the posts it tracks to see what's growing, and writes the report. On Mondays it also runs the ads scout (competitors' long-running ads) and search demand (Google Trends).`
        + (t.analyze ? " Then Claude reads the results and writes the AI ideas note." : ""),
      cost: "Apify per result (TikTok, ads, Google Trends), capped by APIFY_MAX_USD_PER_RUN; YouTube API quota (free)" + (t.analyze ? "; and the Claude CLI on your subscription for the ideas note." : "."),
      output: `The report (and ideas note) in the profile's reports folder in the vault; the dashboard data; log in data/logs/${t.profile}-<date>.log.`,
    };
  }
  if (t.kind === "publish") {
    return {
      what: "Exports every business's latest results and deploys the private, password-protected copy of this dashboard to Vercel (project viral-scout). It does not touch the public demo.",
      cost: "Free (Vercel Hobby plan).",
      output: "The private dashboard is updated. Nothing is posted anywhere.",
    };
  }
  const job = t.job ?? (t.posts_only ? "post" : t.kind === "legacy" ? "ideas" : "");
  const base = JOB_TEXT[job];
  const from = t.kind === "legacy" ? " Registered by another repo; its own description is below." : "";
  if (t.kind === "legacy" && !t.job) {
    return {
      what: (t.posts_only
        ? "Older post-pack run: makes the content packs (posts per platform) for ideas you marked ✅ or 📝."
        : "Older daily idea run.") + from + " Some of these now only hand over to viral-scout's idea generator.",
      cost: CLAUDE_COST,
      output: "See the script description below (most write to the ideas API / Telegram and log under data/logs/ideas-<profile>-<date>.log).",
    };
  }
  return {
    what: (base?.what ?? `Studio job "${job}".`) + from,
    cost: job === "post" ? "Free." : CLAUDE_COST,
    output: base?.output ?? "See the instructions below.",
  };
}

/** "What is this?": plain explanation, then exactly what Task Scheduler runs and the script's own description. */
function About({ t, fallback }: { t?: Task; fallback?: { what: string; cost: string; output: string } }) {
  const e = t ? explain(t) : fallback;
  if (!e) return null;
  const row = "grid gap-0.5 sm:grid-cols-[8rem_1fr] sm:gap-3";
  const label = "text-muted";
  const mono = "break-all font-mono text-[11px] text-text";
  return (
    <details className="group border-t border-line px-4 py-2 text-xs">
      <summary className="cursor-pointer select-none text-muted hover:text-text">
        <span className="group-open:hidden">What is this? ▼</span><span className="hidden group-open:inline">What is this? ▲</span>
      </summary>
      <div className="mt-2 space-y-2 pb-1">
        <div className={row}><span className={label}>What it does</span><span className="text-text">{e.what}</span></div>
        <div className={row}><span className={label}>Costs</span><span>{e.cost}</span></div>
        <div className={row}><span className={label}>Results go to</span><span>{e.output}</span></div>
        {t && (
          <>
            <div className={row}><span className={label}>Task Scheduler</span><span className={mono}>{t.name}{t.author ? ` (by ${t.author})` : ""}</span></div>
            {t.script && <div className={row}><span className={label}>Script</span><span className={mono}>{t.script}</span></div>}
            <div className={row}><span className={label}>Runs</span><span className={mono}>{t.execute} {t.arguments}</span></div>
            {t.working_dir && <div className={row}><span className={label}>In folder</span><span className={mono}>{t.working_dir}</span></div>}
            {t.time_limit && t.time_limit !== "PT0S" && <div className={row}><span className={label}>Time limit</span><span>{t.time_limit.replace(/^PT/, "").toLowerCase()}</span></div>}
            {t.instructions && (
              <div className={row}><span className={label}>Claude&apos;s instructions</span><span className={mono}>{t.instructions}</span></div>
            )}
            {(t.script_about?.length ?? 0) > 0 && (
              <div className={row}>
                <span className={label}>The script says</span>
                <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-ink p-2 font-mono text-[11px] leading-relaxed text-muted">{t.script_about!.join("\n")}</pre>
              </div>
            )}
            {(t.instructions_about?.length ?? 0) > 0 && (
              <div className={row}>
                <span className={label}>Instructions start</span>
                <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-ink p-2 font-mono text-[11px] leading-relaxed text-muted">{t.instructions_about!.join("\n")}</pre>
              </div>
            )}
          </>
        )}
      </div>
    </details>
  );
}
