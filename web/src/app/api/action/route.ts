import { NextResponse, type NextRequest } from "next/server";
import { localOnly, runCli } from "@/lib/cli";

export const dynamic = "force-dynamic";

const STATUSES = new Set(["idea", "scripted", "filmed", "posted", "skip"]);

/** Local only: save / dismiss / track / status through the Python CLI, then refresh the exported data. */
export async function POST(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
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
  const r = await runCli(args);
  if (r.code === 0) await runCli(["export", profile]);
  return NextResponse.json({ ok: r.code === 0, output: r.output }, { status: r.code === 0 ? 200 : 500 });
}
