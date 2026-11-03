import { NextResponse, type NextRequest } from "next/server";
import { localOnly, runCli } from "@/lib/cli";

export const dynamic = "force-dynamic";

/** Local only: search the full history (all runs, all profiles) through the Python CLI. */
export async function GET(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const q = (req.nextUrl.searchParams.get("q") ?? "").trim().slice(0, 200);
  const profile = req.nextUrl.searchParams.get("profile") ?? "";
  if (!q) return NextResponse.json({ ok: true, hits: [] });
  const args = ["search", q, "--json", "--limit", "40"];
  if (/^[\w.-]+$/.test(profile)) args.push("--profile", profile);
  const r = await runCli(args, undefined, 60_000);
  try {
    return NextResponse.json({ ok: true, hits: JSON.parse(r.output) });
  } catch {
    return NextResponse.json({ ok: true, hits: [] });
  }
}
