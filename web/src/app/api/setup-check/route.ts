import { NextResponse, type NextRequest } from "next/server";
import { localOnly, runCli } from "@/lib/cli";

export const dynamic = "force-dynamic";

/** Local only. GET ?profile= → what still needs setting up, per feature (python -m viral_scout setup-check). */
export async function GET(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const profile = req.nextUrl.searchParams.get("profile") ?? "";
  if (profile && !/^[\w.-]+$/.test(profile)) return NextResponse.json({ error: "bad profile" }, { status: 400 });
  const r = await runCli(["setup-check", ...(profile ? [profile] : [])], undefined, 60_000);
  try {
    return NextResponse.json(JSON.parse(r.output.split("\n").filter((l) => l.startsWith("{")).pop() ?? "{}"));
  } catch {
    return NextResponse.json({ error: r.output.slice(-300) }, { status: 500 });
  }
}
