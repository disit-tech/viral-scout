import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { NextResponse, type NextRequest } from "next/server";
import { REPO, localOnly, runCli, startDetached } from "@/lib/cli";

export const dynamic = "force-dynamic";

const PROVIDERS = ["meta", "google", "tiktok"] as const;
type Provider = (typeof PROVIDERS)[number];
// Sign-in progress (no tokens in it): written by `keys connect <provider> --status-file`.
const status = (p: Provider) => path.join(REPO, "data", `connect-${p}.json`);
const provider = (v: unknown): Provider | null => (PROVIDERS.includes(v as Provider) ? (v as Provider) : null);
const clean = (s: string) => s.replace(/^error:\s*/, "").slice(0, 600);

/** Local only. GET ?provider=meta|google|tiktok[&accounts=1]: sign-in progress + the accounts it reaches (no tokens). */
export async function GET(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const p = provider(req.nextUrl.searchParams.get("provider") ?? "meta");
  if (!p) return bad();
  const progress = await readFile(status(p), "utf-8").then((s) => JSON.parse(s)).catch(() => null);
  let accounts = null;
  if (req.nextUrl.searchParams.get("accounts")) {
    const r = await runCli(["keys", p, "accounts"], undefined, 60_000);
    try { accounts = JSON.parse(r.output); } catch { accounts = { error: clean(r.output) }; }
  }
  return NextResponse.json({ ok: true, progress, accounts });
}

const ID = /^@?[A-Za-z0-9._-]{1,60}$/;

/** POST {provider, action:"start"} | {provider:"meta", action:"use", ig?, ad_account?} | {provider:"tiktok", action:"use", advertiser}
 *  | {provider:"tiktok", action:"paste", address}. */
export async function POST(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const b = await req.json().catch(() => ({}));
  const p = provider(b.provider ?? "meta");
  if (!p) return bad();
  if (b.action === "start") {
    // The sign-in opens in this PC's browser and calls back to a loopback server the CLI runs.
    await mkdir(path.dirname(status(p)), { recursive: true });
    await writeFile(status(p), JSON.stringify({ state: "starting", message: "Opening the sign-in…", updated: Date.now() / 1000 }));
    startDetached(["keys", "connect", p, "--status-file", status(p)]);
    return NextResponse.json({ ok: true, output: "Sign-in opened in your browser" });
  }
  if (p === "tiktok" && b.action === "paste") {
    const address = String(b.address ?? "").trim();
    if (!address || address.length > 2000 || /[\r\n]/.test(address)) return bad();
    // The address holds the auth code: stdin, never the command line.
    const r = await runCli(["keys", "connect", "tiktok", "--paste", "-", "--status-file", status(p)], address, 60_000);
    return NextResponse.json({ ok: r.code === 0, output: clean(r.output) }, { status: r.code === 0 ? 200 : 500 });
  }
  if (b.action === "use") {
    const args = ["keys", p, "use"];
    const add = (flag: string, v: unknown) => {
      if (!v) return true;
      if (!ID.test(String(v))) return false;
      args.push(flag, String(v));
      return true;
    };
    const ok = p === "meta" ? add("--ig", b.ig) && add("--ad-account", b.ad_account)
      : p === "tiktok" ? add("--advertiser", b.advertiser) : false;
    if (!ok) return bad();
    if (p === "meta" && b.replace_ads_token) args.push("--replace-ads-token");
    const r = await runCli(args, undefined, 60_000);
    return NextResponse.json({ ok: r.code === 0, output: clean(r.output) }, { status: r.code === 0 ? 200 : 500 });
  }
  return bad();
}

function bad() {
  return NextResponse.json({ ok: false, output: "bad request" }, { status: 400 });
}
