import { NextResponse, type NextRequest } from "next/server";
import { localOnly, runCli } from "@/lib/cli";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

const ACTIONS = new Set(["transcribe", "analyze", "save"]);

/** Local only. POST {profile, key, action: transcribe|analyze|save, force?} → runs `python -m viral_scout ad ...`.
 *  analyze calls the Claude Code CLI headless (about a minute); the run also shows on the Activity page. */
export async function POST(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const b = await req.json().catch(() => ({}));
  const profile = String(b.profile ?? ""), key = String(b.key ?? ""), action = String(b.action ?? "");
  if (!/^[\w.-]+$/.test(profile) || !/^[\w.:-]{3,120}$/.test(key) || !ACTIONS.has(action)) {
    return NextResponse.json({ ok: false, output: "bad request" }, { status: 400 });
  }
  const r = await runCli(["ad", profile, key, action, ...(b.force ? ["--force"] : [])], undefined, 480_000);
  return NextResponse.json({ ok: r.code === 0, output: r.output.slice(-1500) }, { status: r.code === 0 ? 200 : 500 });
}
