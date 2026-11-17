import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { NextResponse, type NextRequest } from "next/server";
import { REPO, localOnly, runCli, startDetached } from "@/lib/cli";

export const dynamic = "force-dynamic";

// Sign-in progress (no tokens in it): written by `keys connect meta --status-file`.
const STATUS = path.join(REPO, "data", "connect-meta.json");

/** Local only. GET: sign-in progress + the accounts it reaches (no tokens). POST {action:"start"} | {action:"use", ig?, ad_account?}. */
export async function GET(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const progress = await readFile(STATUS, "utf-8").then((s) => JSON.parse(s)).catch(() => null);
  let accounts = null;
  if (req.nextUrl.searchParams.get("accounts")) {
    const r = await runCli(["keys", "meta", "accounts"], undefined, 60_000);
    try { accounts = JSON.parse(r.output); } catch { accounts = { error: r.output.replace(/^error:\s*/, "").slice(0, 300) }; }
  }
  return NextResponse.json({ ok: true, progress, accounts });
}

const ID = /^@?[A-Za-z0-9._]{1,60}$/;

export async function POST(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const b = await req.json().catch(() => ({}));
  if (b.action === "start") {
    // The sign-in opens in this PC's browser and calls back to http://localhost:8765/ (the CLI's loopback server).
    await mkdir(path.dirname(STATUS), { recursive: true });
    await writeFile(STATUS, JSON.stringify({ state: "starting", message: "Opening the Facebook sign-in…", updated: Date.now() / 1000 }));
    startDetached(["keys", "connect", "meta", "--status-file", STATUS]);
    return NextResponse.json({ ok: true, output: "Sign-in opened in your browser" });
  }
  if (b.action === "use") {
    const args = ["keys", "meta", "use"];
    if (b.ig) { if (!ID.test(String(b.ig))) return bad(); args.push("--ig", String(b.ig)); }
    if (b.ad_account) { if (!ID.test(String(b.ad_account))) return bad(); args.push("--ad-account", String(b.ad_account)); }
    if (b.replace_ads_token) args.push("--replace-ads-token");
    const r = await runCli(args, undefined, 60_000);
    return NextResponse.json({ ok: r.code === 0, output: r.output.replace(/^error:\s*/, "") }, { status: r.code === 0 ? 200 : 500 });
  }
  return bad();
}

function bad() {
  return NextResponse.json({ ok: false, output: "bad request" }, { status: 400 });
}
