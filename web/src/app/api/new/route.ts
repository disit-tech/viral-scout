import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { NextResponse, type NextRequest } from "next/server";
import { REPO, localOnly, runCli, startDetached } from "@/lib/cli";

export const dynamic = "force-dynamic";

const jobFile = (name: string) => path.join(REPO, "data", "jobs", `${name}.json`);

/** Local only. GET ?name= → job status; GET (no name) → vault project folders.
 *  POST {name, keywords, …, run?} → create the profile, and start the first run unless run is false.
 *  POST {startRun: <profile>} → start the first run of a profile created earlier with "Create only". */
export async function GET(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const name = req.nextUrl.searchParams.get("name");
  if (name) {
    if (!/^[\w.-]+$/.test(name)) return NextResponse.json({ ok: false }, { status: 400 });
    try {
      return NextResponse.json({ ok: true, job: JSON.parse(await readFile(jobFile(name), "utf-8")) });
    } catch {
      return NextResponse.json({ ok: true, job: null });
    }
  }
  const vault = process.env.OBSIDIAN_VAULT;
  let projects: string[] = [];
  if (vault) {
    try {
      projects = (await readdir(path.join(vault, "projects"), { withFileTypes: true }))
        .filter((d) => d.isDirectory() && !d.name.startsWith(".")).map((d) => d.name);
    } catch { /* no vault */ }
  }
  return NextResponse.json({ ok: true, projects });
}

export async function POST(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const b = await req.json().catch(() => ({}));
  if (b.startRun) {
    const p = String(b.startRun);
    if (!/^[\w.-]+$/.test(p)) return NextResponse.json({ ok: false, output: "bad profile" }, { status: 400 });
    startDetached(["run", p, "--quiet", "--status-file", jobFile(p)]);
    return NextResponse.json({ ok: true, profile: p, started: true });
  }
  const name = String(b.name ?? "").trim();
  const keywords = String(b.keywords ?? "").trim();
  if (!name || name.length > 60 || !keywords || keywords.length > 3000) {
    return NextResponse.json({ ok: false, output: "Name and at least one keyword are required." }, { status: 400 });
  }
  const args = ["new", name, "--business", String(b.business ?? "").slice(0, 2000), "--keywords", keywords];
  if (b.hashtags) args.push("--hashtags", String(b.hashtags).slice(0, 1000));
  if (b.languages) args.push("--languages", String(b.languages).slice(0, 1000));
  if (b.vaultProject && /^[\w .-]+$/.test(b.vaultProject)) args.push("--vault-project", b.vaultProject);
  if (b.window && /^(week|month|year)$/.test(b.window)) args.push("--window", b.window);
  if (b.research) args.push("--research");
  const r = await runCli(args);
  const m = r.output.match(/created profile ([\w.-]+)/);
  if (r.code !== 0 || !m) return NextResponse.json({ ok: false, output: r.output.slice(-400) }, { status: 500 });
  const profile = m[1];
  if (b.run === false) return NextResponse.json({ ok: true, profile, started: false });   // "Create only": nothing runs yet
  startDetached(["run", profile, "--quiet", "--status-file", jobFile(profile)]);
  return NextResponse.json({ ok: true, profile, started: true });
}
