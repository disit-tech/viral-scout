import { NextResponse, type NextRequest } from "next/server";
import { localOnly, runCli } from "@/lib/cli";

export const dynamic = "force-dynamic";

const lastJson = (out: string) => JSON.parse(out.slice(out.indexOf("{")));

/** Local only. GET [?profile=] → are the ideas and video bots of every business (or one) connected and used?
 * (python -m viral_scout ideas <profile|all> status, which asks the bot service's /api/status). */
export async function GET(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const profile = req.nextUrl.searchParams.get("profile") ?? "all";
  if (!/^[\w.-]+$/.test(profile)) return NextResponse.json({ ok: false, error: "bad request" }, { status: 400 });
  const r = await runCli(["ideas", profile, "status"], undefined, 60_000);
  try {
    const data = lastJson(r.output);
    return NextResponse.json({ ok: true, ...(profile === "all" ? data : { profiles: [data] }) });
  } catch {
    return NextResponse.json({ ok: false, error: r.output.slice(-400) }, { status: 500 });
  }
}

/** Local only. POST {profile, role: "ideas" | "video"} → a test message through that bot to the group. */
export async function POST(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const b = await req.json().catch(() => ({}));
  const profile = String(b.profile ?? "");
  const role = String(b.role ?? "");
  if (!/^[\w.-]+$/.test(profile) || profile === "all" || !["ideas", "video"].includes(role)) {
    return NextResponse.json({ ok: false, error: "bad request" }, { status: 400 });
  }
  const r = await runCli(["ideas", profile, "status", "--test", role], undefined, 60_000);
  try {
    const data = lastJson(r.output);
    if (data.error) return NextResponse.json({ ok: false, error: data.error }, { status: 502 });
    return NextResponse.json({ ok: true, profile: data });
  } catch {
    return NextResponse.json({ ok: false, error: r.output.slice(-400) }, { status: 500 });
  }
}
