import { spawn } from "node:child_process";
import path from "node:path";
import { NextResponse, type NextRequest } from "next/server";
import { REPO, localOnly, runCli } from "@/lib/cli";

export const dynamic = "force-dynamic";

const SCRIPT = path.join(REPO, "scripts", "tasks.ps1");
const DAYS = ["Daily", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const WEEKDAYS = DAYS.slice(1);
// "viral-scout <profile>[.<job>]", or an older idea task of another repo ("Homeworks Ideas"); tasks.ps1 checks that
// a non-viral-scout name really runs an ideas-daily.ps1 or a site's scripts/jobs/run.ps1 before touching it.
const TASK = /^[\w .-]{1,80}$/;

/** Run scripts/tasks.ps1 with a fixed argv (no shell). Windows only: Task Scheduler. */
function tasks(args: string[]): Promise<{ code: number; output: string }> {
  return new Promise((resolve) => {
    const exe = process.platform === "win32" ? "powershell.exe" : "pwsh";
    const p = spawn(/*turbopackIgnore: true*/ exe, ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", SCRIPT, ...args], {
      cwd: REPO, windowsHide: true,
    });
    let out = "", err = "";
    const timer = setTimeout(() => p.kill(), 30_000);
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (err += d));
    p.on("close", (code) => { clearTimeout(timer); resolve({ code: code ?? 1, output: (code ? err || out : out).trim() }); });
    p.on("error", (e) => { clearTimeout(timer); resolve({ code: 1, output: String(e) }); });
  });
}

/** Local only. GET → every "viral-scout *" task with its trigger, state, last result and log tail. */
export async function GET(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  if (process.platform !== "win32") return NextResponse.json({ ok: false, output: "Task Scheduler is Windows only; use cron (docs/setup.md#scheduling)" });
  const [r, ov] = await Promise.all([tasks(["list"]), runCli(["jobs", "--overview"], undefined, 60_000)]);
  let ideas: unknown[] = [];
  try {
    ideas = JSON.parse(ov.output.split("\n").filter((l) => l.startsWith("[")).pop() ?? "[]");
  } catch { /* the task list still works without the idea generator section */ }
  try {
    return NextResponse.json({ ok: true, ...JSON.parse(r.output), ideas });
  } catch {
    return NextResponse.json({ ok: false, output: r.output.slice(-500) }, { status: 500 });
  }
}

/** Local only. POST {op, name?, profile?, day?, time?, analyze?}. Every value is validated before it reaches PowerShell. */
export async function POST(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const b = await req.json().catch(() => ({}));
  const op = String(b.op ?? ""), name = String(b.name ?? ""), profile = String(b.profile ?? "");
  const day = b.day == null ? "" : String(b.day), time = b.time == null ? "" : String(b.time);
  const bad = (m: string) => NextResponse.json({ ok: false, output: m }, { status: 400 });

  if (day && !DAYS.includes(day)) return bad("bad day");
  if (time && !/^([01]\d|2[0-3]):[0-5]\d$/.test(time)) return bad("time must be HH:mm");
  const extra = [...(day ? ["-Day", day] : []), ...(time ? ["-Time", time] : []), ...(typeof b.analyze === "boolean" ? ["-Analyze", b.analyze ? "1" : "0"] : [])];

  let args: string[];
  if (["enable", "disable", "run", "stop", "remove", "set"].includes(op)) {
    if (!TASK.test(name)) return bad("bad task name");
    args = [op, "-Name", name, ...(op === "set" ? extra : [])];
  } else if (op === "add") {
    if (!/^[\w.-]+$/.test(profile)) return bad("bad profile");
    args = ["add", "-Profile", profile, ...extra];
  } else if (op === "ideas") {
    // Idea generator: edit jobs.ideas in the profile, then register/update/remove its task (new ones paused).
    if (!/^[\w.-]+$/.test(profile)) return bad("bad profile");
    const set: string[] = [];
    if (typeof b.enabled === "boolean") set.push("--enabled", b.enabled ? "1" : "0");
    if (b.at != null) {
      if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(String(b.at))) return bad("time must be HH:mm");
      set.push("--at", String(b.at));
    }
    if (b.days != null) {
      const d = Array.isArray(b.days) ? b.days.map(String) : [String(b.days)];
      if (!(d.length === 1 && d[0] === "daily") && (!d.length || d.some((x: string) => !WEEKDAYS.includes(x)))) return bad("days: daily or weekday names");
      set.push("--days", d.join(","));
    }
    if (b.count != null) {
      const n = Number(b.count);
      if (!Number.isInteger(n) || n < 1 || n > 20) return bad("count: 1 to 20");
      set.push("--count", String(n));
    }
    if (set.length) {
      const e = await runCli(["jobs", profile, "schedule", "ideas", ...set]);
      const res = (() => { try { return JSON.parse(e.output.split("\n").filter((l) => l.startsWith("{")).pop() ?? "{}"); } catch { return {}; } })();
      if (e.code !== 0 || res.error) return bad(res.error ?? e.output.slice(-300));
    }
    const s = await tasks(["studio-sync", "-Profile", profile]);
    return NextResponse.json({ ok: s.code === 0, output: s.output }, { status: s.code === 0 ? 200 : 400 });
  } else return bad("unknown op");

  const r = await tasks(args);
  return NextResponse.json({ ok: r.code === 0, output: r.output }, { status: r.code === 0 ? 200 : 400 });
}
