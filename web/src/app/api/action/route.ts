import { spawn } from "node:child_process";
import path from "node:path";
import { NextResponse, type NextRequest } from "next/server";
import { isLocal } from "@/lib/data";

export const dynamic = "force-dynamic";

const REPO = path.resolve(/*turbopackIgnore: true*/ process.cwd(), "..");
const STATUSES = new Set(["idea", "scripted", "filmed", "posted", "skip"]);

function run(args: string[]): Promise<{ code: number; output: string }> {
  return new Promise((resolve) => {
    const p = spawn(/*turbopackIgnore: true*/ process.env.VIRAL_SCOUT_PYTHON || "python", ["-m", "viral_scout", ...args], {
      cwd: REPO,
      env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      windowsHide: true,
    });
    let out = "";
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (out += d));
    p.on("close", (code) => resolve({ code: code ?? 1, output: out.trim() }));
    p.on("error", (e) => resolve({ code: 1, output: String(e) }));
  });
}

/** Local only: save / dismiss / track / status through the Python CLI, then refresh the exported data. */
export async function POST(req: NextRequest) {
  if (!isLocal) return NextResponse.json({ ok: false, output: "Read-only deployment" }, { status: 403 });
  const host = req.headers.get("host") ?? "";
  if (!/^(localhost|127\.0\.0\.1)(:\d+)?$/.test(host)) {
    return NextResponse.json({ ok: false, output: "Actions only from localhost" }, { status: 403 });
  }
  const b = await req.json().catch(() => ({}));
  const profile = String(b.profile ?? "");
  const ref = String(b.ref ?? "");
  if (!/^[\w.-]+$/.test(profile) || !ref || ref.length > 500) {
    return NextResponse.json({ ok: false, output: "bad request" }, { status: 400 });
  }
  let args: string[];
  switch (b.action) {
    case "save":
      args = ["save", profile, ref, ...(b.note ? ["--note", String(b.note).slice(0, 500)] : [])];
      break;
    case "dismiss":
      args = ["dismiss", profile, ref];
      break;
    case "track":
      args = ["add", profile, ref];
      break;
    case "status":
      if (!STATUSES.has(b.status)) return NextResponse.json({ ok: false, output: "bad status" }, { status: 400 });
      args = ["status", profile, ref, b.status];
      break;
    default:
      return NextResponse.json({ ok: false, output: "unknown action" }, { status: 400 });
  }
  const r = await run(args);
  if (r.code === 0) await run(["export", profile]);
  return NextResponse.json({ ok: r.code === 0, output: r.output }, { status: r.code === 0 ? 200 : 500 });
}
