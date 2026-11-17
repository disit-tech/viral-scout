import { NextResponse, type NextRequest } from "next/server";
import { localOnly, runCli } from "@/lib/cli";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

/** Local only. POST {profile, id, force?} → `python -m viral_scout score run <profile> <id>`: the Claude Code CLI
 *  headless scores the post on the 20-criteria scorecard (about a minute); the run also shows on the Activity page. */
export async function POST(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const b = await req.json().catch(() => ({}));
  const profile = String(b.profile ?? ""), id = String(b.id ?? "");
  if (!/^[\w.-]+$/.test(profile) || !/^[\w.:-]{3,120}$/.test(id)) {
    return NextResponse.json({ ok: false, output: "bad request" }, { status: 400 });
  }
  const r = await runCli(["score", "run", profile, id, ...(b.force ? ["--force"] : [])], undefined, 480_000);
  return NextResponse.json({ ok: r.code === 0, output: r.output.slice(-1500) }, { status: r.code === 0 ? 200 : 500 });
}
