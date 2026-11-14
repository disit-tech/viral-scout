import { NextResponse, type NextRequest } from "next/server";
import { localOnly, runCli } from "@/lib/cli";

export const dynamic = "force-dynamic";

/** Local only. POST {profile, base, set: {path: value}} → profiles/<name>.yaml edited in place (comments kept), then export. */
export async function POST(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const b = await req.json().catch(() => ({}));
  const profile = String(b.profile ?? "");
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
