import { spawn } from "node:child_process";
import { mkdirSync, openSync, readFileSync } from "node:fs";
import path from "node:path";
import { NextResponse, type NextRequest } from "next/server";
import { REPO, localOnly, runCli, startDetached } from "@/lib/cli";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

const NAME = /^[\w.-]+$/;
const last = (out: string) => out.split("\n").filter((l) => l.startsWith("{")).pop() ?? "{}";

/** Local only. GET ?profile= → `publish <p> status --json` (settings, queues, which keys are set, recent posts). */
export async function GET(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const profile = req.nextUrl.searchParams.get("profile") ?? "";
  if (!NAME.test(profile)) return NextResponse.json({ error: "bad request" }, { status: 400 });
  const r = await runCli(["publish", profile, "status", "--json"], undefined, 60_000);
  try {
    return NextResponse.json(JSON.parse(last(r.output)));
  } catch {
    return NextResponse.json({ error: r.output.slice(-400) }, { status: 500 });
  }
}

/** A browser sign-in (Google / LinkedIn): check the app keys first, then start it in the background with its output in
 *  data/publish/<p>/connect-<svc>.log, and hand back the sign-in URL it printed (when no browser tab opens). */
async function signIn(profile: string, service: "google" | "linkedin" | "tiktok", extra: string[]) {
  const c = await runCli(["publish", profile, "connect", service, "--check"], undefined, 30_000);
  const chk = (() => { try { return JSON.parse(last(c.output)); } catch { return { ok: false, error: c.output.slice(-300) }; } })();
  if (!chk.ok) return NextResponse.json({ ok: false, output: chk.error }, { status: 400 });
  const dir = path.join(REPO, "data", "publish", profile);
  mkdirSync(dir, { recursive: true });
  const log = path.join(dir, `connect-${service}.log`);
  const fd = openSync(log, "w");
  const py = process.env.VIRAL_SCOUT_PYTHON || "python";
  const p = spawn(/*turbopackIgnore: true*/ py, ["-m", "viral_scout", "publish", profile, "connect", service, ...extra], {
    cwd: REPO, env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUNBUFFERED: "1" }, windowsHide: true, detached: true, stdio: ["ignore", fd, fd],
  });
  p.unref();
  let text = "";
  for (let i = 0; i < 20 && !/https:\/\/\S+/.test(text) && !/error:/.test(text); i++) {
    await new Promise((r) => setTimeout(r, 250));
    try { text = readFileSync(log, "utf-8"); } catch { /* not written yet */ }
  }
  const url = text.match(/https:\/\/\S+/)?.[0];
  if (/error:/.test(text)) return NextResponse.json({ ok: false, output: text.trim().split("\n").pop() }, { status: 400 });
  const name = service === "google" ? "Google" : service === "tiktok" ? "TikTok" : "LinkedIn";
  return NextResponse.json({ ok: true, url,
    output: `${name} sign-in started: a tab should open in your browser. No tab? Use the link below. After you allow it, reload this page (the step turns ✅).` });
}

function syncTasks(profile: string): Promise<{ code: number; output: string }> {
  return new Promise((resolve) => {
    if (process.platform !== "win32") return resolve({ code: 1, output: "Task Scheduler is Windows only" });
    const p = spawn(/*turbopackIgnore: true*/ "powershell.exe", ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
      path.join(REPO, "scripts", "tasks.ps1"), "studio-sync", "-Profile", profile], { cwd: REPO, windowsHide: true });
    let out = "";
    const timer = setTimeout(() => p.kill(), 60_000);
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (out += d));
    p.on("close", (code) => { clearTimeout(timer); resolve({ code: code ?? 1, output: out.trim() }); });
    p.on("error", (e) => { clearTimeout(timer); resolve({ code: 1, output: String(e) }); });
  });
}

/**
 * Local only. POST {profile, action, file?, page?, org?}:
 *   stop | resume <file>       🛑 / ✅ on the queue row of that mp4 or post file
 *   autopost                   post what is due now (in the background; the result lands in the published list)
 *   dry-run                    what autopost would do now, nothing sent
 *   connect-meta [page]        this business's Page + Instagram keys from the shared Facebook sign-in
 *   connect-google | connect-linkedin [org]   a sign-in opens in the browser on this PC
 *   sync-tasks                 register / update this business's Task Scheduler tasks (new ones start paused)
 */
export async function POST(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const b = await req.json().catch(() => ({}));
  const profile = String(b.profile ?? ""), action = String(b.action ?? "");
  const bad = (m: string) => NextResponse.json({ ok: false, output: m }, { status: 400 });
  if (!NAME.test(profile)) return bad("bad request");
  const reply = (r: { code: number; output: string }) =>
    NextResponse.json({ ok: r.code === 0, output: r.output.slice(-1500) }, { status: r.code === 0 ? 200 : 400 });

  if (action === "stop" || action === "resume") {
    const file = String(b.file ?? "");
    if (!file || file.length > 500 || /[\r\n]/.test(file)) return bad("bad file");
    const r = await runCli(["publish", profile, "row", action, file]);
    const d = (() => { try { return JSON.parse(last(r.output)); } catch { return { error: r.output.slice(-300) }; } })();
    return NextResponse.json({ ok: !!d.ok, output: d.ok ? `Row is now: ${d.status}` : d.error }, { status: d.ok ? 200 : 400 });
  }
  if (action === "dry-run") return reply(await runCli(["publish", profile, "autopost", "--dry-run"], undefined, 120_000));
  if (action === "autopost") {
    startDetached(["publish", profile, "autopost"]);
    return NextResponse.json({ ok: true, output: "Posting what is due now, in the background. Uploads take a few minutes: reload to see them under Recent posts." });
  }
  if (action === "connect-meta") {
    const page = String(b.page ?? "").trim();
    if (page.length > 120 || /[\r\n]/.test(page)) return bad("bad page");
    return reply(await runCli(["publish", profile, "connect", "meta", ...(page ? ["--page", page] : [])], undefined, 60_000));
  }
  if (action === "connect-google") return signIn(profile, "google", []);
  if (action === "connect-tiktok") return signIn(profile, "tiktok", []);
  if (action === "connect-threads") {
    const token = String(b.token ?? "").trim();
    if (!/^[\w.|-]{20,600}$/.test(token)) return bad("paste the whole token from the Threads User Token Generator");
    return reply(await runCli(["publish", profile, "connect", "threads"], token, 60_000));   // token on stdin, never in argv
  }
  if (action === "connect-linkedin") {
    const org = String(b.org ?? "").trim();
    if (org && !/^(urn:li:organization:)?\d{1,20}$/.test(org)) return bad("org: the company Page's numeric id");
    return signIn(profile, "linkedin", org ? ["--org", org] : []);
  }
  if (action === "sync-tasks") return reply(await syncTasks(profile));
  return bad("unknown action");
}
