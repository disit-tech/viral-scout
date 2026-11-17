import { NextResponse, type NextRequest } from "next/server";
import { localOnly, runCli, startDetached } from "@/lib/cli";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

/**
 * Local only. POST {profile, action, platform?, campaign?, usd?, brief?}:
 *   pull                       read the ad accounts again (python -m viral_scout paid <p> pull)
 *   pause | resume | budget    one campaign; resume and budget only if the month stays under the cap
 *   ask                        Claude builds (and, within the cap, launches) a campaign from the brief, in the
 *                              background; it shows on the Activity page and in the change log
 */
export async function POST(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const b = await req.json().catch(() => ({}));
  const profile = String(b.profile ?? ""), action = String(b.action ?? "");
  const platform = String(b.platform ?? ""), campaign = String(b.campaign ?? "");
  if (!/^[\w.-]+$/.test(profile)) return NextResponse.json({ ok: false, output: "bad request" }, { status: 400 });
  if (action === "pull") {
    const r = await runCli(["paid", profile, "pull"], undefined, 180_000);
    return NextResponse.json({ ok: r.code === 0, output: r.output.slice(-1500) }, { status: r.code === 0 ? 200 : 500 });
  }
  if (action === "ask") {
    const extra = String(b.extra ?? "").slice(0, 2000);
    startDetached(["paid", profile, "ask", extra, "--by", "dashboard"]);
    return NextResponse.json({ ok: true, output: "Claude is on it: follow it on the Activity page. It reads the accounts, plans, checks the cap, then builds the campaign." });
  }
  if (!["pause", "resume", "budget"].includes(action) || !["meta", "tiktok"].includes(platform) || !/^[\w-]{1,40}$/.test(campaign)) {
    return NextResponse.json({ ok: false, output: "bad request" }, { status: 400 });
  }
  const args = ["paid", profile, action, platform, campaign];
  if (action === "budget") {
    const v = Number(b.usd);
    if (!Number.isFinite(v) || v <= 0 || v > 10000) return NextResponse.json({ ok: false, output: "daily budget: 1–10000 USD" }, { status: 400 });
    args.push(String(v));
  }
  const r = await runCli([...args, "--by", "dashboard"], undefined, 180_000);
  return NextResponse.json({ ok: r.code === 0, output: r.output.slice(-1500) }, { status: r.code === 0 ? 200 : r.code === 3 ? 409 : 500 });
}
