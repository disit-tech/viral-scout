import { NextResponse, type NextRequest } from "next/server";
import { localOnly, runCli } from "@/lib/cli";

export const dynamic = "force-dynamic";

const NAME = /^[A-Z][A-Z0-9_]{2,40}$/;

/** Local only. GET: key status (masked). POST {action:"set", name, value} | {action:"test", name}. */
export async function GET(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const r = await runCli(["keys"]);
  try {
    return NextResponse.json({ ok: true, keys: JSON.parse(r.output) });
  } catch {
    return NextResponse.json({ ok: false, output: r.output }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const b = await req.json().catch(() => ({}));
  const name = String(b.name ?? "");
  if (!NAME.test(name)) return NextResponse.json({ ok: false, output: "bad key name" }, { status: 400 });
  if (b.action === "set") {
    const value = String(b.value ?? "").trim();
    if (value.length > 1000 || /[\r\n]/.test(value)) return NextResponse.json({ ok: false, output: "bad value" }, { status: 400 });
    // The value goes through stdin, never through the command line.
    const r = await runCli(["keys", "set", name, "-"], value);
    return NextResponse.json({ ok: r.code === 0, output: r.output }, { status: r.code === 0 ? 200 : 500 });
  }
  if (b.action === "test") {
    const r = await runCli(["keys", "test", name], undefined, 60_000);
    try {
      const res = JSON.parse(r.output)[name];
      return NextResponse.json({ ok: Boolean(res?.ok), output: res?.message ?? r.output });
    } catch {
      return NextResponse.json({ ok: false, output: r.output.slice(0, 300) });
    }
  }
  return NextResponse.json({ ok: false, output: "unknown action" }, { status: 400 });
}
