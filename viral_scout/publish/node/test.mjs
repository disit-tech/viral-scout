// node --test viral_scout/publish/node/test.mjs: caption parsing, YouTube titles, times (no network).
import { test } from "node:test";
import assert from "node:assert/strict";
import { captionProblems, hashtags, parseAt, parseCaption, youtubeTitle } from "./lib.mjs";

test("caption: header lines + default everywhere", () => {
  const c = parseCaption("ai: true\ntitle: Panels go dark\nWhy solar panels go dark. Comment BACKUP. #solar\n");
  assert.equal(c.ai, true);
  assert.equal(c.title, "Panels go dark");
  assert.equal(c.instagram, "Why solar panels go dark. Comment BACKUP. #solar");
  assert.equal(c.youtube, c.instagram);
});

test("caption: per-network sections override, CRLF ok", () => {
  const c = parseCaption("Base text\r\n\r\n## Instagram\r\nIG text\r\n## YouTube\r\nYT line 1\r\nYT line 2\r\n");
  assert.equal(c.ai, false);
  assert.equal(c.instagram, "IG text");
  assert.equal(c.facebook, "Base text");
  assert.equal(c.youtube, "YT line 1\nYT line 2");
});

test("youtube title: adds #Shorts once, ≤ 100 chars, cuts at a word", () => {
  assert.equal(youtubeTitle("What one battery runs #shorts"), "What one battery runs #Shorts");
  const long = youtubeTitle("Why your solar panels turn off in a blackout and what a home battery changes for an the state family during storms");
  assert.ok(long.length <= 100, `${long.length}`);
  assert.ok(long.endsWith("… #Shorts"), long);
  assert.equal(youtubeTitle("ignored", "Explicit <title>"), "Explicit title #Shorts");
});

test("hashtags + problems", () => {
  assert.deepEqual(hashtags("a #solar b #home_battery #Summer2026"), ["solar", "home_battery", "Summer2026"]);
  const many = parseCaption(Array.from({ length: 31 }, (_, i) => `#t${i}`).join(" "));
  assert.match(captionProblems(many).join(), /hashtags > 30/);
  assert.deepEqual(captionProblems(parseCaption("ok")), []);
});

test("--at: wall time in the tz → UTC, DST aware", () => {
  assert.equal(parseAt("2026-10-25 18:00").toISOString(), "2026-10-25T23:00:00.000Z"); // CDT −5
  assert.equal(parseAt("2026-11-10 18:00").toISOString(), "2026-11-11T00:00:00.000Z"); // CST −6
  assert.equal(parseAt("2026-10-25T18:00:00Z").toISOString(), "2026-10-25T18:00:00.000Z");
  assert.throws(() => parseAt("tomorrow"));
  assert.equal(parseAt("2026-07-01 18:00", "Europe/Warsaw").toISOString(), "2026-07-01T16:00:00.000Z"); // CEST +2
});
