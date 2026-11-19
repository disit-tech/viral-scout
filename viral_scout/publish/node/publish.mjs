// One approved vertical video → Instagram Reels + Facebook Page Reel + YouTube Shorts + LinkedIn video. See docs/publish-and-jobs.md.
// Normally started by `python -m viral_scout publish <profile> post` (only for platforms the profile opted in).
//   node publish.mjs <video.mp4> --caption-file <caption.md> [--only instagram,facebook,youtube]
//        [--video-url https://…] [--cover-url https://…] [--cover cover.jpg] [--thumb-offset 1500]
//        [--at "2026-10-25 18:00"] [--wait] [--privacy public|unlisted|private] [--ai-label] [--dry-run]
//        [--tz America/Springfield] [--log <published.jsonl>] [--category 27] [--lang en]
import { appendFileSync, existsSync, mkdirSync, readFileSync, statSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { basename, dirname, extname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { captionProblems, hashtags, loadEnv, parseAt, parseCaption, PLATFORMS, youtubeTitle } from "./lib.mjs";
import { linkedinPost } from "./linkedin.mjs";

const get = loadEnv();
const V = get("META_GRAPH_VERSION") || "v26.0";

// ───────────── Arguments ─────────────
const argv = process.argv.slice(2);
const flags = {};
const pos = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (!a.startsWith("--")) pos.push(a);
  else if (["--dry-run", "--wait", "--ai-label"].includes(a)) flags[a.slice(2)] = true;
  else flags[a.slice(2)] = argv[++i];
}
const die = (msg) => {
  console.error(`✖ ${msg}`);
  process.exit(1);
};
const video = pos[0] && resolve(pos[0]);
if (!video || !existsSync(video)) die("Usage: node publish.mjs <video.mp4> --caption-file <caption.md> [--dry-run]  (see docs/publish-and-jobs.md; text/photo posts: post.mjs)");
const tz = flags.tz || "America/Springfield";
const logFile = resolve(flags.log || fileURLToPath(new URL("./out/published.jsonl", import.meta.url)));
if (!flags["caption-file"] || !existsSync(flags["caption-file"])) die("--caption-file <file> is required");
if (![".mp4", ".mov"].includes(extname(video).toLowerCase())) die("Video must be .mp4 or .mov");
if (flags.cover && !existsSync(flags.cover)) die(`--cover ${flags.cover}: file not found`);
for (const k of ["video-url", "cover-url"]) if (flags[k] && !/^https:\/\//.test(flags[k])) die(`--${k} must be a public https:// URL`);

const caption = parseCaption(readFileSync(flags["caption-file"], "utf8"));
const ai = caption.ai || Boolean(flags["ai-label"]);
const only = (flags.only ?? PLATFORMS.join(",")).split(",").map((s) => s.trim().toLowerCase());
const bad = only.filter((p) => !PLATFORMS.includes(p));
if (bad.length) die(`Unknown network: ${bad.join(", ")} (use ${PLATFORMS.join(", ")})`);
const at = flags.at ? parseAt(flags.at, tz) : null;
if (at && at.getTime() < Date.now() + 60_000) die(`--at ${at.toISOString()} is not in the future`);
const privacy = flags.privacy ?? "public";
if (!["public", "unlisted", "private"].includes(privacy)) die("--privacy: public | unlisted | private");
const dry = Boolean(flags["dry-run"]);
const size = statSync(video).size;

// ───────────── Checks ─────────────
function probe() {
  try {
    const out = execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate:format=duration", "-of", "json", video], { encoding: "utf8" });
    const j = JSON.parse(out);
    const [n, d] = (j.streams?.[0]?.r_frame_rate ?? "0/1").split("/").map(Number);
    return { duration: Number(j.format?.duration), width: j.streams?.[0]?.width, height: j.streams?.[0]?.height, fps: d ? n / d : 0 };
  } catch {
    return null; // no ffprobe: the networks check the file themselves
  }
}
const info = probe();
const warn = [];
const skip = {}; // platform → reason it can't take this file
if (info) {
  const { duration: s, width: w, height: h } = info;
  if (Math.abs(w / h - 9 / 16) > 0.02) warn.push(`aspect ${w}×${h} is not 9:16 (Reels/Shorts look best at 1080×1920)`);
  if (s < 3) for (const p of PLATFORMS) skip[p] = `${s.toFixed(1)} s is under 3 s`;
  if (s > 900) skip.instagram = `${s.toFixed(0)} s is over the 15-minute Reels limit`;
  if (s > 90) skip.facebook = `${s.toFixed(0)} s is over the 90-second Facebook Reels limit`;
  if (s > 900) skip.linkedin = `${s.toFixed(0)} s is over LinkedIn's 15-minute limit`;
  if (s > 180) skip.youtube = `${s.toFixed(0)} s is over 3 minutes: not a Short`;
  if (w > 1920) warn.push(`width ${w} > 1920 (Instagram maximum)`);
}
if (size > 300 * 1024 * 1024) skip.instagram = `${(size / 1048576).toFixed(0)} MB is over Instagram's 300 MB`;
const problems = captionProblems(caption);
if (problems.length) die(`Caption: ${problems.join("; ")}`);
if (ai && !/\bAI\b/.test(caption.instagram)) warn.push('AI-made video: Instagram has no API label, so the caption must say it (e.g. "AI version of me, script written by me")');

const env = {
  instagram: ["INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID"],
  facebook: ["FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_TOKEN"],
  youtube: ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"],
  linkedin: ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR"],
};
const missing = (p) => env[p].filter((k) => !get(k));

// ───────────── Plan ─────────────
const title = youtubeTitle(caption.youtube, caption.title);
console.log(`\n📼 ${basename(video)} · ${(size / 1048576).toFixed(1)} MB${info ? ` · ${info.width}×${info.height} · ${info.duration.toFixed(1)} s · ${info.fps.toFixed(0)} fps` : " · (no ffprobe: size/duration not checked)"}`);
console.log(`🕒 ${at ? `${at.toISOString()} (${flags.at} ${tz})${flags.wait ? ", waiting in this window" : ""}` : "now"} · AI label: ${ai ? "yes" : "no"}`);
for (const p of only) {
  const m = missing(p);
  const why = skip[p] ?? (m.length ? `not configured (${m.join(", ")})` : null);
  console.log(`\n${why ? "⏭️ " : "✅"} ${p}${why ? `: skipped, ${why}` : ""}`);
  if (p === "youtube") console.log(`   title: ${title}\n   privacy: ${at && !flags.wait ? `private → public at ${at.toISOString()}` : privacy}${ai ? " · containsSyntheticMedia" : ""}`);
  if (p === "instagram")
    console.log(`   upload: ${flags["video-url"] ? `from ${flags["video-url"]}` : "local file (resumable; experimental with Instagram Login, see docs/publish-and-jobs.md)"}${flags["cover-url"] ? ` · cover ${flags["cover-url"]}` : flags["thumb-offset"] ? ` · cover frame ${flags["thumb-offset"]} ms` : ""}`);
  if (at && !flags.wait && p !== "youtube") console.log("   ⚠️ no scheduling through the API for this network: rerun at that time, or add --wait");
  console.log(`   caption: ${caption[p].split("\n").join(" ⏎ ").slice(0, 160)}${caption[p].length > 160 ? "…" : ""}`);
}
for (const w of warn) console.log(`\n⚠️ ${w}`);
if (dry) {
  console.log("\nDry run: nothing was sent.");
  process.exit(0);
}

// ───────────── HTTP helpers ─────────────
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function json(url, init = {}) {
  const r = await fetch(url, init);
  const text = await r.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = { raw: text };
  }
  if (!r.ok || data.error) throw new Error(data.error?.message ?? data.error_description ?? `HTTP ${r.status} ${text.slice(0, 200)}`);
  return { data, headers: r.headers };
}
const form = (o) => new URLSearchParams(Object.entries(o).filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => [k, String(v)]));
const bytes = () => readFileSync(video);

// ───────────── Instagram Reels (Instagram API with Instagram Login) ─────────────
async function instagram() {
  const token = get("INSTAGRAM_ACCESS_TOKEN");
  const ig = get("INSTAGRAM_USER_ID");
  const api = token.startsWith("IG") ? `https://graph.instagram.com/${V}` : `https://graph.facebook.com/${V}`;
  const auth = { Authorization: `Bearer ${token}` };
  const common = { media_type: "REELS", caption: caption.instagram, share_to_feed: "true", cover_url: flags["cover-url"], thumb_offset: flags["cover-url"] ? undefined : flags["thumb-offset"] };

  let container;
  if (flags["video-url"]) {
    container = (await json(`${api}/${ig}/media`, { method: "POST", headers: auth, body: form({ ...common, video_url: flags["video-url"] }) })).data.id;
  } else {
    try {
      container = (await json(`${api}/${ig}/media`, { method: "POST", headers: auth, body: form({ ...common, upload_type: "resumable" }) })).data.id;
    } catch (e) {
      // Meta documents resumable upload only for Facebook Login apps; a token error is just a token error.
      const tokenIssue = /OAuth|access token|session/i.test(e.message);
      throw new Error(tokenIssue ? e.message : `${e.message}. Local upload may not be accepted with Instagram Login: put the file at a public https URL and pass --video-url <url>.`);
    }
    await json(`https://rupload.facebook.com/ig-api-upload/${V}/${container}`, {
      method: "POST",
      headers: { Authorization: `OAuth ${token}`, offset: "0", file_size: String(size), "Content-Type": "application/octet-stream" },
      body: bytes(),
    });
  }
  // Meta: check about once a minute, no longer than 5 minutes.
  for (let i = 0; ; i++) {
    const s = (await json(`${api}/${container}?fields=status_code,status`, { headers: auth })).data;
    if (s.status_code === "FINISHED") break;
    if (s.status_code === "ERROR" || s.status_code === "EXPIRED") throw new Error(`container ${s.status_code}: ${s.status ?? ""}`);
    if (i >= 20) throw new Error(`still ${s.status_code} after 5 minutes (container ${container}; it can be published within 24 h)`);
    await sleep(15_000);
  }
  const id = (await json(`${api}/${ig}/media_publish`, { method: "POST", headers: auth, body: form({ creation_id: container }) })).data.id;
  const link = await json(`${api}/${id}?fields=permalink`, { headers: auth }).then((r) => r.data.permalink).catch(() => null);
  return { id, link };
}

// ───────────── Facebook Page Reel (video_reels: start → upload → finish) ─────────────
async function facebook() {
  const token = get("FACEBOOK_PAGE_TOKEN");
  const page = get("FACEBOOK_PAGE_ID");
  const api = `https://graph.facebook.com/${V}`;
  const start = (await json(`${api}/${page}/video_reels`, { method: "POST", body: form({ upload_phase: "start", access_token: token }) })).data;
  const videoId = start.video_id;
  await json(start.upload_url ?? `https://rupload.facebook.com/video-upload/${V}/${videoId}`, {
    method: "POST",
    headers: { Authorization: `OAuth ${token}`, offset: "0", file_size: String(size), "Content-Type": "application/octet-stream" },
    body: bytes(),
  });
  const status = async () => (await json(`${api}/${videoId}?fields=status&access_token=${encodeURIComponent(token)}`)).data.status ?? {};
  for (let i = 0; i < 12; i++) {
    const s = await status();
    if (s.video_status === "error" || s.uploading_phase?.status === "error") throw new Error(`upload error: ${JSON.stringify(s)}`);
    if (s.uploading_phase?.status === "complete" || s.video_status === "ready") break;
    await sleep(5_000);
  }
  await json(`${api}/${page}/video_reels`, {
    method: "POST",
    body: form({ upload_phase: "finish", video_id: videoId, video_state: "PUBLISHED", description: caption.facebook, access_token: token }),
  });
  // Processing continues after "finish"; wait (up to 5 min) so a failure shows here, not silently.
  for (let i = 0; i < 30; i++) {
    const s = await status();
    if (s.video_status === "error" || s.processing_phase?.status === "error" || s.publishing_phase?.status === "error") throw new Error(`processing error: ${JSON.stringify(s)}`);
    if (s.video_status === "ready" || s.video_status === "published" || s.publishing_phase?.status === "complete") break;
    await sleep(10_000);
  }
  const p = await json(`${api}/${videoId}?fields=permalink_url&access_token=${encodeURIComponent(token)}`).then((r) => r.data.permalink_url).catch(() => null);
  return { id: videoId, link: p ? (p.startsWith("http") ? p : `https://www.facebook.com${p}`) : null };
}

// ───────────── YouTube Shorts (Data API v3, resumable videos.insert) ─────────────
async function youtube() {
  const tok = (
    await json("https://oauth2.googleapis.com/token", {
      method: "POST",
      body: form({ client_id: get("YOUTUBE_CLIENT_ID"), client_secret: get("YOUTUBE_CLIENT_SECRET"), refresh_token: get("YOUTUBE_REFRESH_TOKEN"), grant_type: "refresh_token" }),
    })
  ).data.access_token;
  const scheduled = at && !flags.wait;
  const meta = {
    snippet: { title, description: caption.youtube, tags: hashtags(caption.youtube).slice(0, 15), categoryId: String(flags.category || "27"), defaultLanguage: flags.lang || "en", defaultAudioLanguage: flags.lang || "en" },
    status: {
      privacyStatus: scheduled ? "private" : privacy,
      ...(scheduled ? { publishAt: at.toISOString() } : {}),
      selfDeclaredMadeForKids: false,
      containsSyntheticMedia: ai,
    },
  };
  const init = await fetch("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status", {
    method: "POST",
    headers: { Authorization: `Bearer ${tok}`, "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Length": String(size), "X-Upload-Content-Type": "video/*" },
    body: JSON.stringify(meta),
  });
  const session = init.headers.get("location");
  if (!init.ok || !session) throw new Error(`upload start failed: HTTP ${init.status} ${(await init.text()).slice(0, 300)}`);
  const { data } = await json(session, { method: "PUT", headers: { "Content-Type": "video/*", "Content-Length": String(size) }, body: bytes() });
  if (flags.cover) {
    // Custom thumbnails need a verified channel; a failure here doesn't undo the upload.
    await json(`https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=${data.id}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tok}`, "Content-Type": /\.png$/i.test(flags.cover) ? "image/png" : "image/jpeg" },
      body: readFileSync(flags.cover),
    }).catch((e) => warn.push(`youtube cover not set: ${e.message}`));
  }
  return { id: data.id, link: `https://youtube.com/shorts/${data.id}`, note: data.status?.privacyStatus === "private" && !scheduled && privacy !== "private" ? "uploaded as PRIVATE (API project not audited by Google yet?)" : scheduled ? `goes public ${at.toISOString()}` : "" };
}

// ───────────── Run ─────────────
async function linkedin() {
  return linkedinPost({ token: get("LINKEDIN_ACCESS_TOKEN"), author: get("LINKEDIN_AUTHOR"), version: get("LINKEDIN_API_VERSION"),
    text: caption.linkedin, media: { video, title } });
}

const run = { instagram, facebook, youtube, linkedin };
const todo = only.filter((p) => !skip[p] && !missing(p).length);
if (at && flags.wait) {
  const ms = at.getTime() - Date.now();
  console.log(`\n⏳ Waiting ${Math.round(ms / 60_000)} min until ${flags.at} (keep this window open)…`);
  await sleep(ms);
}
mkdirSync(dirname(logFile), { recursive: true });
const rows = [];
for (const p of todo) {
  if (at && !flags.wait && p !== "youtube") {
    rows.push({ network: p, result: "⏭️ not scheduled", link: "rerun at the time or use --wait" });
    continue;
  }
  process.stdout.write(`\n→ ${p}… `);
  try {
    const r = await run[p]();
    console.log("done");
    rows.push({ network: p, result: "✅ published", link: r.link ?? r.id, note: r.note ?? "" });
    appendFileSync(logFile, `${JSON.stringify({ time: new Date().toISOString(), platform: p, id: r.id, permalink: r.link, video: basename(video), scheduledFor: p === "youtube" && at && !flags.wait ? at.toISOString() : null })}\n`);
  } catch (e) {
    console.log("failed");
    rows.push({ network: p, result: "✖ failed", link: "", note: e.message.slice(0, 200) });
  }
}
for (const p of only.filter((x) => !todo.includes(x))) rows.push({ network: p, result: "⏭️ skipped", link: "", note: skip[p] ?? `missing ${missing(p).join(", ")}` });
console.log();
console.table(rows);
for (const w of warn) console.log(`⚠️ ${w}`);
process.exit(rows.some((r) => r.result.startsWith("✖")) ? 1 : 0);
