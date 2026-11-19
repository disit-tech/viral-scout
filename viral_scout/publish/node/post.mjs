// A text post, or a photo post (one .jpg/.png) → Facebook Page + LinkedIn. Instagram has no API for a local image
// (it fetches a public image URL), so photo posts go there only by hand. Started by `python -m viral_scout publish
// <profile> autopost` for the posts queue.
//   node post.mjs --caption-file post.md [--photo photo.jpg] [--only facebook,linkedin] [--log published.jsonl] [--dry-run]
import { appendFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";
import { loadEnv, parseCaption } from "./lib.mjs";
import { linkedinPost } from "./linkedin.mjs";

const get = loadEnv();
const V = get("META_GRAPH_VERSION") || "v26.0";
const argv = process.argv.slice(2);
const flags = {};
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === "--dry-run") flags["dry-run"] = true;
  else if (argv[i].startsWith("--")) flags[argv[i].slice(2)] = argv[++i];
}
const die = (m) => {
  console.error(`✖ ${m}`);
  process.exit(1);
};
const POST_PLATFORMS = ["facebook", "linkedin"];
if (!flags["caption-file"] || !existsSync(flags["caption-file"])) die("--caption-file <post.md> is required");
const caption = parseCaption(readFileSync(flags["caption-file"], "utf8"));
const photo = flags.photo ? resolve(flags.photo) : "";
if (photo && (!existsSync(photo) || !/\.(jpe?g|png)$/i.test(photo))) die(`--photo ${photo}: a .jpg or .png file is needed`);
const only = (flags.only ?? POST_PLATFORMS.join(",")).split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
const bad = only.filter((p) => !POST_PLATFORMS.includes(p));
if (bad.length) die(`Text/photo posts go to ${POST_PLATFORMS.join(", ")} only (not ${bad.join(", ")})`);
const env = { facebook: ["FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_TOKEN"], linkedin: ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR"] };
const missing = (p) => env[p].filter((k) => !get(k));
const problems = only.flatMap((p) => (!caption[p] ? [`${p}: empty text`] : p === "linkedin" && caption.linkedin.length > 3000 ? ["linkedin: text > 3000 characters"] : []));
if (problems.length) die(problems.join("; "));

for (const p of only) console.log(`${missing(p).length ? "⏭️" : "✅"} ${p}${missing(p).length ? ` (missing ${missing(p).join(", ")})` : ""}: ${caption[p].split("\n").join(" ⏎ ").slice(0, 140)}${photo ? ` + ${basename(photo)}` : ""}`);
if (flags["dry-run"]) {
  console.log("Dry run: nothing was sent.");
  process.exit(0);
}

async function json(url, init = {}) {
  const r = await fetch(url, init);
  const text = await r.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = { raw: text };
  }
  if (!r.ok || data.error) throw new Error(data.error?.message ?? `HTTP ${r.status} ${text.slice(0, 200)}`);
  return data;
}

async function facebook() {
  const token = get("FACEBOOK_PAGE_TOKEN");
  const page = get("FACEBOOK_PAGE_ID");
  const api = `https://graph.facebook.com/${V}`;
  let id;
  if (photo) {
    const fd = new FormData();
    fd.set("message", caption.facebook);
    fd.set("published", "true");
    fd.set("access_token", token);
    fd.set("source", new Blob([readFileSync(photo)]), basename(photo));
    const d = await json(`${api}/${page}/photos`, { method: "POST", body: fd });
    id = d.post_id || d.id;
  } else {
    id = (await json(`${api}/${page}/feed`, { method: "POST", body: new URLSearchParams({ message: caption.facebook, access_token: token }) })).id;
  }
  return { id, link: `https://www.facebook.com/${id}` };
}

async function linkedin() {
  return linkedinPost({ token: get("LINKEDIN_ACCESS_TOKEN"), author: get("LINKEDIN_AUTHOR"), version: get("LINKEDIN_API_VERSION"), text: caption.linkedin, media: photo ? { image: photo } : {} });
}

const run = { facebook, linkedin };
const logFile = flags.log ? resolve(flags.log) : "";
if (logFile) mkdirSync(dirname(logFile), { recursive: true });
let failed = false;
for (const p of only.filter((x) => !missing(x).length)) {
  try {
    const r = await run[p]();
    console.log(`✅ ${p} published ${r.link ?? r.id}`);
    if (logFile) appendFileSync(logFile, `${JSON.stringify({ time: new Date().toISOString(), platform: p, id: r.id, permalink: r.link, post: basename(flags["caption-file"]), kind: photo ? "photo" : "text" })}\n`);
  } catch (e) {
    failed = true;
    console.log(`✖ ${p} failed: ${e.message.slice(0, 300)}`);
  }
}
process.exit(failed ? 1 : 0);
