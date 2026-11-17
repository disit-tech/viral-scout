import { NextResponse, type NextRequest } from "next/server";
import { localOnly, runCli } from "@/lib/cli";

export const dynamic = "force-dynamic";

/** Local only. GET ?profile= → the editable fields and their base hash (python -m viral_scout profile <name> get). */
export async function GET(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const profile = req.nextUrl.searchParams.get("profile") ?? "";
  if (!/^[\w.-]+$/.test(profile)) return NextResponse.json({ ok: false, error: "bad request" }, { status: 400 });
  const r = await runCli(["profile", profile, "get"]);
  try {
    const data = JSON.parse(r.output.split("\n").filter((l) => l.startsWith("{")).pop() ?? "{}");
    if (data.error || r.code !== 0) return NextResponse.json({ ok: false, error: data.error ?? r.output.slice(-300) }, { status: 400 });
    return NextResponse.json({ ok: true, ...data });
  } catch {
    return NextResponse.json({ ok: false, error: r.output.slice(-300) }, { status: 500 });
  }
}

/** Local only. POST {profile, base, set: {path: value}} → profiles/<name>.yaml edited in place (comments kept), then export. */
export async function POST(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const b = await req.json().catch(() => ({}));
  const profile = String(b.profile ?? "");
  if (b.delete === true && /^[\w.-]+$/.test(profile)) {   // Settings → Delete business: moved to data/deleted/, tasks removed
    const r = await runCli(["profile", profile, "delete", "--confirm", String(b.confirm ?? "")], undefined, 240_000);
    let out: { ok?: boolean; error?: string; folder?: string; tasks_removed?: string[] } = {};
    try { out = JSON.parse(r.output.split("\n").filter((l) => l.startsWith("{")).pop() ?? "{}"); } catch { out = { error: r.output.slice(-300) }; }
    return NextResponse.json(out.error ? { ok: false, error: out.error } : { ok: true, ...out }, { status: out.error ? 400 : 200 });
  }
  if (!/^[\w.-]+$/.test(profile) || typeof b.set !== "object" || !b.set) {
    return NextResponse.json({ ok: false, error: "bad request" }, { status: 400 });
  }
  const body = JSON.stringify({ base: String(b.base ?? ""), set: b.set });
  if (body.length > 200_000) return NextResponse.json({ ok: false, error: "too large" }, { status: 413 });
  const r = await runCli(["profile", profile, "set"], body);
  let out: { changed?: string[]; base?: string; error?: string } = {};
  try {
    out = JSON.parse(r.output.split("\n").filter((l) => l.startsWith("{")).pop() ?? "{}");
  } catch { out = { error: r.output.slice(-400) }; }
  if (r.code !== 0 || out.error) return NextResponse.json({ ok: false, error: out.error ?? r.output.slice(-400) }, { status: 400 });
  if (out.changed?.length) await runCli(["export", profile]);
  return NextResponse.json({ ok: true, changed: out.changed ?? [], base: out.base });
}
