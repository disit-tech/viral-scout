---
name: viral-scout
description: Find what's going viral on a topic right now (YouTube Shorts, Instagram reels, TikTok) for any business, with independent keyword/hashtag discovery, a creator watch list, tracked links and growth since the last run. Use when the user asks what's trending or viral in their niche, wants outlier videos or formats to copy, sends reel/short links to track, or wants a new business set up for trend monitoring.
---

# Viral scout

Tool repo: `D:\repo\viral-scout` (README there). Run everything from that folder with `PYTHONIOENCODING=utf-8`.

Args: a profile name (`profiles/<name>.yaml`), optionally URLs to track. No profile given → `python -m viral_scout profiles` and pick the one matching the active project (`$OBSIDIAN_PROJECT`), else ask.

## Run
1. URLs in the request → `python -m viral_scout add <profile> <urls>` first (strip nothing; the tool cleans tracking params). Also add them to the profile's `seeds:` so they stay tracked.
2. `python -m viral_scout run <profile>` (takes 3–8 minutes; run in background). It prints the report path.
3. Read the report. It has: Rising now, Fastest new posts (independent search), Outliers (≥3× the creator's usual), Tracked links, Creators who keep showing up, Skipped sources, Errors.

## Report back (short)
- The 5 posts that matter most for this business, each with the number that makes it matter (per day, rise/day or × usual) and **what the format is** in one line (hook, structure, why it works). Open the post (`yt-dlp --skip-download --print description`) if the title doesn't explain it.
- Formats that repeat across several hits.
- Creators that keep showing up: offer to add them to `watch:`.
- Skipped sources: say which key would unlock them (YouTube API key is free; Instagram Graph needs a business account; TikTok via Apify is paid).

## New business
Copy `profiles/_template.yaml` to `profiles/<name>.yaml`. Fill keywords (formats + the customer's situations, in every language the audience speaks, with `languages:`), hashtags, `must_match` (topic words, so hashtag spam is dropped), `exclude`, and `output_dir` in the vault. Run once and tune the filters from what slipped through.

## Rules
- Never call Instagram's or TikTok's private web APIs or spoof headers; only yt-dlp on public posts, the official APIs, or Apify.
- Don't use the user's browser cookies unless they ask.
- Viral clips from other creators are references for formats, not footage to reuse.
