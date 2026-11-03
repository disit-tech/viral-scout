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

For each, from title + hook + transcript (+ description):
- **Format** (one of: talking head tip, skit/POV, A-vs-B contrast, list/phrase pack, myth-buster, reaction, story, tutorial, question-to-comments, other)
- **Hook type** (question, bold claim, mistake call-out, contrast, relatable situation, curiosity gap, shock) and the hook words
- **Structure** in 3 beats (hook → body → payoff/CTA) and **why people watch to the end**

Then write **5 ideas adapted to the business**: each with title, which viral post it borrows from (link), hook line (in the language the business films in), 3-beat outline, on-screen text, and why it fits `business:`. Respect the taste note and hard rules (e.g. never reuse others' footage).

Write it to the vault next to the report as `<date>-viral-ideas.md` (frontmatter `type: viral-ideas`, `profile`, `date`, link to the report), with sections: Patterns this week (formats/hooks that repeat), Breakdown (table: post · format · hook type · why it works), Ideas (the 5), Watch list candidates, Suggested hashtags worth adding.

## 3. Save and clean up
- Save the 2–3 best references: `python -m viral_scout save <profile> <ID> --note "<format>: <why it works>"`; then set `format:` in each saved note's frontmatter.
- Off-topic posts: `python -m viral_scout dismiss <profile> <ID> ...`.
- Creators who keep showing up / suggested hashtags: propose profile edits; apply only if the user agrees (or in a scheduled run: list them in the ideas note only).

## 4. Report back (short)
3–5 lines: the strongest pattern, the best idea, where the notes are, which source a key would unlock (YouTube API key is free; Instagram Graph needs a business account; TikTok via Apify is paid).

## New business
Copy `profiles/_template.yaml` to `profiles/<name>.yaml` (git-ignored). Fill `business:`, keywords (formats + the customer's situations, in every language the audience speaks, with `languages:`), hashtags, `must_match` (topic words, so hashtag spam is dropped), `exclude`, `output_dir`/`swipe_dir` in the vault. Run once, tune the filters from what slipped through.

## Rules
- Never call Instagram's or TikTok's private web APIs or spoof headers; only yt-dlp on public posts, the official APIs, or Apify.
- Don't use the user's browser cookies unless they ask.
- Viral posts are references for formats, never footage to reuse.
- Never overwrite a swipe note the user edited (the tool already won't).
