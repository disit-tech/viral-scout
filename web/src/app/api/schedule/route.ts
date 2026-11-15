import { spawn } from "node:child_process";
import path from "node:path";
import { NextResponse, type NextRequest } from "next/server";
import { REPO, localOnly } from "@/lib/cli";

export const dynamic = "force-dynamic";

const SCRIPT = path.join(REPO, "scripts", "tasks.ps1");
const DAYS = ["Daily", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const TASK = /^viral-scout [\w.-]+$/;

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
  const r = await tasks(["list"]);
  try {
    return NextResponse.json({ ok: true, ...JSON.parse(r.output) });
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
  } else return bad("unknown op");

  const r = await tasks(args);
  return NextResponse.json({ ok: r.code === 0, output: r.output }, { status: r.code === 0 ? 200 : 400 });
}
