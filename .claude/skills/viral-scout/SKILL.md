---
name: viral-scout
description: Find what's going viral on a topic right now (YouTube Shorts, Instagram reels, TikTok) for any business, then break down why the top videos work and turn them into ideas for that business. Independent keyword/hashtag discovery, creator watch list, tracked links, outliers vs the creator's usual, growth between runs, hooks and transcripts, swipe file, Telegram alerts. Use when the user asks what's trending or viral in their niche, wants outlier videos, hooks or formats to copy, sends reel/short links to track or save, or wants a new business set up for trend monitoring.
---

# Viral scout

Tool repo: `D:\repo\viral-scout` (README there). Run from that folder with `PYTHONIOENCODING=utf-8`.

Args: `<profile> [analyze] [urls...]`. No profile → `python -m viral_scout profiles` and pick the one matching the active project (`$OBSIDIAN_PROJECT`), else ask. `analyze` = skip the run, analyze the latest report (used by the scheduled run).

## 1. Collect
- URLs in the request → `python -m viral_scout add <profile> <urls>` and add them to the profile's `seeds:`.
- `python -m viral_scout run <profile>` (3–8 min; run in background). It prints the report path; `data/<profile>-latest.json` has every post with hook, transcript, scores.

## 2. Analyze (the part that makes it useful)
Read the profile (`business:`, `taste_note:` if set) and the latest JSON. Take the strongest 8–10 posts: Rising now first, then Outliers (🔥/⚡), then Fastest. Skip off-topic ones the filters missed (and offer `dismiss`).

For each, from title + hook + CTA + transcript (+ description), **and look at its `frame` image** (Read the local path in the JSON): many Shorts/reels carry the hook as on-screen text ("CRISPS vs FRIES vs CHIPS") or show the format visually (split screen, before/after, text cards). Note the on-screen text and visual format. Use `wpm` (pace), `creator_pct`, `vs_pace` (age-matched), `vs_topic` (× the niche) and `emerging` when they explain why it worked. Read `questions` / `top_comments`: viewer questions are ready-made ideas, objections show what to address.
- **Format** (one of: talking head tip, skit/POV, A-vs-B contrast, list/phrase pack, myth-buster, reaction, story, tutorial, question-to-comments, other)
- **Hook type** (question, bold claim, mistake call-out, contrast, relatable situation, curiosity gap, shock) and the hook words
- **On-screen text / visual** (from the frame)
- **Structure** in 3 beats (hook → body → payoff/CTA; the `cta` field is what's said in the last 5 s) and **why people watch to the end**

Then write **5 ideas adapted to the business**: each with title, which viral post it borrows from (link), hook line (in the language the business films in), 3-beat outline, on-screen text, and why it fits `business:`. Respect the taste note and hard rules (e.g. never reuse others' footage).

Write it to the vault next to the report as `<date>-viral-ideas.md` (frontmatter `type: viral-ideas`, `profile`, `date`, link to the report), with sections: Patterns this week (formats/hooks that repeat), Breakdown (table: post · format · hook type · why it works), What viewers ask (the best questions from the comments, each with the idea it suggests), Ideas (the 5), Your posts (if the profile has `own:`: which of yours beat your usual and why), Watch list candidates (🌱 emerging creators first), Suggested hashtags worth adding.

## 2b. Score the strongest posts (creative scorecard, 100 points)
For the top 5–8 posts (and any post the user names: `/viral-scout <profile> score <post_id>`): look at the frame image, hook, CTA, transcript, comments and numbers, then rate the 20 criteria 1–5 with one concrete line each. Get the shape with `python -m viral_scout score template`, fill it, and save with `python -m viral_scout score set <profile> <post_id>` (JSON on stdin). Include `summary` (one sentence) and `fix_first` (the single change that would help most, phrased for THIS business). Be calibrated: 5 = best-in-class, 3 = ordinary; don't inflate. It's a subjective creative assessment: say so, and never present it as a prediction.

## 2c. Pre-publish check of the user's own draft (`/viral-scout <profile> check <file or check id>`)
Run `python -m viral_scout check <profile> <file>` (or use an existing check id). Read the check JSON in data/checks/<profile>/<id>/ and Read its frame images (first, 1s, 3s, middle, last): judge first-frame impact, on-screen text, captions (readable, high contrast, inside safe zones), branding, visual quality. Score it with the scorecard (`score set <profile> check:<id>`). Then give the 3 most important fixes in order, mixing technical results (format, loudness, pacing, silence in the hook, CTA) and creative ones.

## 3. Save and clean up
- Save the 2–3 best references: `python -m viral_scout save <profile> <ID> --note "<format>: <why it works>"`; then set `format:` in each saved note's frontmatter.
- Off-topic posts: `python -m viral_scout dismiss <profile> <ID> ...`.
- Creators who keep showing up / suggested hashtags: propose profile edits; apply only if the user agrees (or in a scheduled run: list them in the ideas note only).

## 4. Report back (short)
3–5 lines: the strongest pattern, the best idea, where the notes are, which source a key would unlock (YouTube API key is free; Instagram Graph needs a business account; TikTok via Apify is paid).

## Other commands worth offering
- `python -m viral_scout search "<words>"`: find past hits on a theme across all businesses before writing ideas.
- `python -m viral_scout competitors <profile>`: local competitors and their channels (needs GOOGLE_PLACES_API_KEY).
- `python -m viral_scout keys`: which sources are unlocked; the dashboard's /setup page manages keys.

## New business
Fastest: `python -m viral_scout new <name> --business "..." --keywords "a; b; c" [--research] --run` (or the dashboard's /new page): it derives hashtags, the topic filter and spam rules. Then tune as below.
Copy `profiles/_template.yaml` to `profiles/<name>.yaml` (git-ignored). Fill `business:`, keywords (formats + the customer's situations, in every language the audience speaks, with `languages:`), hashtags, `must_match` (topic words, so hashtag spam is dropped), `exclude`, `output_dir`/`swipe_dir` in the vault. Run once, tune the filters from what slipped through.

## MCP alternative
If the `viral-scout` MCP server is connected (`claude mcp add viral-scout -s user -- python <repo>/scripts/mcp_server.py`), the same steps are tools: list_profiles, start_run → get_job (poll ~30 s), get_results, get_post, get_ideas, save_post, dismiss_posts, track_links, set_swipe_status, usage.

## Rules
- Never call Instagram's or TikTok's private web APIs or spoof headers; only yt-dlp on public posts, the official APIs, or Apify.
- Don't use the user's browser cookies unless they ask.
- Viral posts are references for formats, never footage to reuse.
- Never overwrite a swipe note the user edited (the tool already won't).
