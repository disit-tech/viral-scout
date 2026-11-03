import { spawn } from "node:child_process";
import path from "node:path";
import { NextResponse, type NextRequest } from "next/server";
import { isLocal } from "./data";

export const REPO = path.resolve(/*turbopackIgnore: true*/ process.cwd(), "..");
const PY = process.env.VIRAL_SCOUT_PYTHON || "python";

/** Run `python -m viral_scout ...args` (fixed argv, no shell). Optional stdin for secrets. */
export function runCli(args: string[], stdin?: string, timeoutMs = 120_000): Promise<{ code: number; output: string }> {
  return new Promise((resolve) => {
    const p = spawn(/*turbopackIgnore: true*/ PY, ["-m", "viral_scout", ...args], {
      cwd: REPO,
      env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      windowsHide: true,
    });
    let out = "";
    const timer = setTimeout(() => p.kill(), timeoutMs);
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (out += d));
    p.on("close", (code) => { clearTimeout(timer); resolve({ code: code ?? 1, output: out.trim() }); });
    p.on("error", (e) => { clearTimeout(timer); resolve({ code: 1, output: String(e) }); });
    if (stdin !== undefined) p.stdin.end(stdin + "\n");
  });
}

/** Start a long CLI run in the background (survives the request); progress goes to a status file. */
export function startDetached(args: string[]) {
  const p = spawn(/*turbopackIgnore: true*/ PY, ["-m", "viral_scout", ...args], {
    cwd: REPO,
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    windowsHide: true,
    detached: true,
    stdio: "ignore",
  });
  p.unref();
}

/** Local-only guard: not on Vercel, and only from localhost. Returns a response to send, or null if allowed. */
export function localOnly(req: NextRequest): NextResponse | null {
  if (!isLocal) return NextResponse.json({ ok: false, output: "Only available on the local dashboard" }, { status: 403 });
  const host = req.headers.get("host") ?? "";
  if (!/^(localhost|127\.0\.0\.1)(:\d+)?$/.test(host)) {
    return NextResponse.json({ ok: false, output: "Only from localhost" }, { status: 403 });
  }
  return null;
}
