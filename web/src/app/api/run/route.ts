import { readFile } from "node:fs/promises";
import path from "node:path";
import { NextResponse, type NextRequest } from "next/server";
import { REPO, localOnly, startDetached } from "@/lib/cli";

export const dynamic = "force-dynamic";

/** Free jobs only. Paid runs (Apify: ads, TikTok, search demand) stay on the Monday schedule or the CLI. */
const JOBS: Record<string, (p: string, status: string) => string[]> = {
  videos: (p, s) => ["run", p, "--free", "--quiet", "--status-file", s],          // YouTube + re-checks, no Apify
  "ads-rescore": (p, s) => ["ads", p, "--rescore", "--quiet", "--status-file", s],  // re-filter/score the last ads run
};
const statusFile = (p: string, job: string) => path.join(REPO, "data", "jobs", `${p}-${job}.json`);
const ok = (p: string, job: string) => /^[\w.-]+$/.test(p) && job in JOBS;

export async function GET(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const p = req.nextUrl.searchParams.get("profile") ?? "", job = req.nextUrl.searchParams.get("job") ?? "";
  if (!ok(p, job)) return NextResponse.json({ ok: false }, { status: 400 });
  try {
    return NextResponse.json({ ok: true, job: JSON.parse(await readFile(statusFile(p, job), "utf-8")) });
  } catch {
    return NextResponse.json({ ok: true, job: null });
  }
}

export async function POST(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const b = await req.json().catch(() => ({}));
  const p = String(b.profile ?? ""), job = String(b.job ?? "");
  if (!ok(p, job)) return NextResponse.json({ ok: false, output: "unknown job" }, { status: 400 });
  try {
    const cur = JSON.parse(await readFile(statusFile(p, job), "utf-8"));
    const fresh = Date.now() - new Date(cur.updated).getTime() < 30 * 60_000;
    if (cur.status === "running" && fresh) return NextResponse.json({ ok: true, already: true });
  } catch { /* no earlier job */ }
  startDetached(JOBS[job](p, statusFile(p, job)));
  return NextResponse.json({ ok: true });
}
