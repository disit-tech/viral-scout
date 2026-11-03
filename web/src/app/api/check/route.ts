import { mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { NextResponse, type NextRequest } from "next/server";
import { REPO, localOnly, runCli } from "@/lib/cli";

export const dynamic = "force-dynamic";
export const maxDuration = 600;

const VIDEO = /\.(mp4|mov|m4v|webm|mkv)$/i;

/** Local only: upload your own draft video → pre-publish check (ffmpeg + Whisper) → the check JSON. */
export async function POST(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const form = await req.formData();
  const profile = String(form.get("profile") ?? "");
  const platform = String(form.get("platform") ?? "any");
  const file = form.get("file");
  if (!/^[\w.-]+$/.test(profile) || !["any", "tiktok", "reels", "shorts"].includes(platform)) {
    return NextResponse.json({ ok: false, output: "bad profile or platform" }, { status: 400 });
  }
  if (!(file instanceof File) || !VIDEO.test(file.name) || file.size > 1_000_000_000) {
    return NextResponse.json({ ok: false, output: "Choose a video file (mp4, mov, m4v, webm, mkv) under 1 GB." }, { status: 400 });
  }
  const dir = path.join(REPO, "data", "uploads");
  await mkdir(dir, { recursive: true });
  const safe = file.name.replace(/[^\w.-]+/g, "-").slice(-80);
  const dest = path.join(dir, `${Date.now()}-${safe}`);
  await writeFile(dest, Buffer.from(await file.arrayBuffer()));

  const r = await runCli(["check", profile, dest, "--platform", platform], undefined, 590_000);
  const id = r.output.match(/id: check:([\w-]+)/)?.[1];
  if (r.code !== 0 || !id) return NextResponse.json({ ok: false, output: r.output.slice(-600) }, { status: 500 });
  const report = JSON.parse(await readFile(path.join(REPO, "data", "checks", profile, id, "check.json"), "utf-8"));
  delete report.file;
  return NextResponse.json({ ok: true, check: report });
}

/** Local only: frame images of a check (for the page). */
export async function GET(req: NextRequest) {
  const deny = localOnly(req);
  if (deny) return deny;
  const profile = req.nextUrl.searchParams.get("profile") ?? "";
  const slug = req.nextUrl.searchParams.get("slug") ?? "";
  const frame = req.nextUrl.searchParams.get("frame") ?? "";
  if (![profile, slug].every((x) => /^[\w.-]+$/.test(x)) || !/^frame-[\w]+\.jpg$/.test(frame)) {
    return NextResponse.json({ ok: false }, { status: 400 });
  }
  const f = path.join(REPO, "data", "checks", profile, slug, frame);
  try {
    await stat(f);
    return new NextResponse(new Uint8Array(await readFile(f)), { headers: { "content-type": "image/jpeg" } });
  } catch {
    const list = await readdir(path.dirname(f)).catch(() => []);
    return NextResponse.json({ ok: false, frames: list }, { status: 404 });
  }
}
