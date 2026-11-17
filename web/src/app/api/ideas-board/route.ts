import { NextResponse, type NextRequest } from "next/server";
import { localOnly, runCli } from "@/lib/cli";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const lastJson = (out: string) => {
  try {
    return JSON.parse(out.split("\n").filter((l) => l.startsWith("{")).pop() ?? "{}");
  } catch {
    return { error: out.slice(-400) };
  }
};

/** Local only. GET → every business's ideas and films (`python -m viral_scout ideas board get`; the secret stays in
 *  Python). POST {ids, op, value?, project?} → one change (`ideas board set`): rate, comment, remove, tag, note, posted. */
export async function GET(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const r = await runCli(["ideas", "board", "get"], undefined, 110_000);
  const d = lastJson(r.output);
  return NextResponse.json(d, { status: d.error ? 502 : 200 });
}

export async function POST(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const b = await req.json().catch(() => ({}));
  const ids = Array.isArray(b.ids) ? b.ids.map(Number).filter((n: number) => Number.isInteger(n) && n > 0).slice(0, 100) : [];
  const op = String(b.op ?? "");
  if (!ids.length || !["rate", "remove", "tag", "comment", "note", "posted"].includes(op)) {
    return NextResponse.json({ error: "bad request" }, { status: 400 });
  }
  const body = JSON.stringify({ ids, op, value: String(b.value ?? "").slice(0, 2000), project: String(b.project ?? "") });
  const r = await runCli(["ideas", "board", "set"], body, 110_000);
  const d = lastJson(r.output);
  return NextResponse.json(d, { status: d.error ? 400 : 200 });
}
