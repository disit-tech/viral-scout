// Pure helpers for publish.mjs (no network): env, caption file, YouTube title, times. Tested by test.mjs.
import { readFileSync, existsSync } from "node:fs";

/**
 * process.env first, then the env file named by PUBLISH_ENV_FILE (optional). `python -m viral_scout publish` maps the
 * profile's token names to the standard ones (INSTAGRAM_ACCESS_TOKEN, …) and passes them in process.env.
 */
export function loadEnv() {
  const file = process.env.PUBLISH_ENV_FILE || "";
  const local = file && existsSync(file)
    ? Object.fromEntries(
        readFileSync(file, "utf8")
          .split(/\r?\n/)
          .filter((l) => l.includes("=") && !l.startsWith("#"))
          .map((l) => [l.slice(0, l.indexOf("=")).trim(), l.slice(l.indexOf("=") + 1).trim().replace(/^"|"$/g, "")]),
      )
    : {};
  return (k) => (process.env[k] ?? local[k] ?? "").trim();
}

export const PLATFORMS = ["instagram", "facebook", "youtube"];

/**
 * Caption file:
 *   ai: true                 ← optional header lines (key: value) at the very top
 *   title: YouTube title     ← optional; otherwise the first line of the YouTube caption
 *   <default caption, used everywhere>
 *   ## Instagram             ← optional per-network overrides (whole caption for that network)
 *   ## Facebook
 *   ## YouTube
 */
export function parseCaption(text) {
  const lines = text.replace(/^﻿/, "").replace(/\r/g, "").split("\n");
  const meta = {};
  let i = 0;
  while (i < lines.length && /^(ai|title)\s*:/i.test(lines[i])) {
    const at = lines[i].indexOf(":");
    meta[lines[i].slice(0, at).trim().toLowerCase()] = lines[i].slice(at + 1).trim();
    i++;
  }
  const parts = { base: [] };
  let cur = "base";
  for (; i < lines.length; i++) {
    const h = lines[i].match(/^##\s*(instagram|facebook|youtube)\s*$/i);
    if (h) {
      cur = h[1].toLowerCase();
      parts[cur] = [];
    } else parts[cur].push(lines[i]);
  }
  const clean = (arr) => (arr ? arr.join("\n").trim() : "");
  const base = clean(parts.base);
  return {
    ai: /^(true|yes|1)$/i.test(meta.ai ?? ""),
    title: meta.title ?? "",
    instagram: clean(parts.instagram) || base,
    facebook: clean(parts.facebook) || base,
    youtube: clean(parts.youtube) || base,
  };
}

/** YouTube title: ≤ 100 characters, no < >, ends with #Shorts. Cut at a word with "…" when too long. */
export function youtubeTitle(caption, explicit = "") {
  const first = (explicit || caption.split("\n").find((l) => l.trim()) || "").replace(/[<>]/g, "").replace(/\s+/g, " ").trim();
  const tag = " #Shorts";
  const base = first.replace(/\s*#shorts\b/gi, "").trim();
  const max = 100 - tag.length;
  if (base.length <= max) return base + tag;
  const cut = base.slice(0, max - 1);
  return `${cut.slice(0, cut.lastIndexOf(" ") > 40 ? cut.lastIndexOf(" ") : cut.length).replace(/[\s,.;:–-]+$/, "")}…${tag}`;
}

/** Hashtags in a caption (for the "#tags" field on YouTube and the Instagram limit of 30). */
export const hashtags = (s) => [...s.matchAll(/#([\p{L}\p{N}_]+)/gu)].map((m) => m[1]);

/** Problems that would make a network reject the caption. */
export function captionProblems(c) {
  const out = [];
  if (!c.instagram) out.push("instagram: empty caption");
  if (c.instagram.length > 2200) out.push(`instagram: caption ${c.instagram.length} > 2200 characters`);
  if (hashtags(c.instagram).length > 30) out.push(`instagram: ${hashtags(c.instagram).length} hashtags > 30`);
  if (!c.youtube) out.push("youtube: empty caption");
  if (Buffer.byteLength(c.youtube) > 5000) out.push("youtube: description > 5000 bytes");
  return out;
}

/**
 * "2026-10-25 18:00" = wall time in `tz` (the business's time zone, publish.timezone) → Date. Strings with Z or an offset are taken as is.
 */
export function parseAt(s, tz = "America/Springfield") {
  if (/[zZ]|[+-]\d\d:?\d\d$/.test(s.trim())) return new Date(s);
  const m = s.trim().match(/^(\d{4})-(\d\d)-(\d\d)[ T](\d\d):(\d\d)$/);
  if (!m) throw new Error(`--at "${s}": use "YYYY-MM-DD HH:mm" (${tz} time)`);
  const wall = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]);
  const offsetAt = (t) => {
    const p = Object.fromEntries(
      new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
        .formatToParts(new Date(t))
        .map((x) => [x.type, x.value]),
    );
    return Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute) - t;
  };
  let t = wall - offsetAt(wall);
  t = wall - offsetAt(t); // second pass settles DST edges
  return new Date(t);
}
