import { NextResponse, type NextRequest } from "next/server";
import { localOnly, runCli } from "@/lib/cli";

export const dynamic = "force-dynamic";

/** Local only. GET → running and recent jobs with their live log, plus Apify actor runs and spend.
 *  GET ?jobs=1 → jobs only (no Apify calls): the nav's "running" dot. */
export async function GET(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const jobsOnly = req.nextUrl.searchParams.get("jobs") === "1";
  const r = await runCli(["activity", ...(jobsOnly ? ["--jobs-only"] : [])], undefined, 30_000);
  try {
    return NextResponse.json({ ok: true, ...JSON.parse(r.output) });
  } catch {
    return NextResponse.json({ ok: false, output: r.output.slice(-500) }, { status: 500 });
  }
}
