---
name: studio-video
description: Make short vertical videos (TikTok, Reels, Shorts, Facebook) for any business profile in viral-scout - write a sourced script with hooks, cards and captions, cut and caption a recording into a 1080x1920 master, build an animated HyperFrames film, clone the owner's voice, plan the week, review what worked, or repurpose one recording into every channel. Every brand value comes from the profile's studio and video blocks. Use when the user asks for a video script, says they recorded a video or voice memo, wants a video edited, cut or rendered, wants an animated film, asks what to film this week or how the videos did, or wants one recording turned into posts.
---

# Studio video

Tool repo: `D:\repo\viral-scout` (docs/video.md). Run from there with `PYTHONIOENCODING=utf-8`.

Args: `<profile> <mode> [...]`
- `script <idea | topic | swipe note | tracker row>`: write one script file
- `edit <media> [script] [--section N]`: cut, cards, render a recording
- `film <idea | script>`: an animated HyperFrames film
- `voice <script>`: the owner's cloned voice for a script
- `week`: plan the next 5 videos
- `review`: what worked in the posted videos
- `repurpose <recording | transcript | script>`: one recording into every channel
- `check <file>`: compliance check of a script, caption or ad

No profile → `python -m viral_scout profiles` and pick the one matching `$OBSIDIAN_PROJECT`, else ask.

## 0. Read first, every mode

1. `python -m viral_scout video <profile> info`: the resolved `studio:` and `video:` blocks (brand, owner, modes, folders, voice, colors, CTA, AI label).
2. The profile's `business:` and, if set, `taste_note`.
3. `studio.instructions` (free text per business: voice, offer, pillars, CTA keyword, banned words, platforms, approvals). It **overrides the defaults in this skill**. It never overrides the hard rules below.
4. `studio.compliance`: the industry rules and the disclosure line. Missing → say so and use only the hard rules; never invent legal rules.
5. The video folder: `<studio.vault_dir>/05 Marketing/Video Studio/` (or the parent of `video.script_dir`): `video-tracker.md`, `hook-bank.md`, `scripts/`. Missing files are created from the formats below only when the mode writes to them.

Method reference (read the section a mode names): `$OBSIDIAN_VAULT/shared/playbooks/05 Marketing/video-generation.md`.

## Hard rules (no profile or instruction note can change these)

1. **Truth.** Every number has a primary source shown on screen or in the description. No source, no number. Facts that can change are re-checked on the day.
2. **Never copy.** No other creators' or competitors' footage, audio, music, words, creatives, logos or trademarks. Borrow formats and angles only. Never imply affiliation with a brand, utility or agency.
3. **AI disclosure.** AI voice, AI avatar or a realistic AI scene: platform AI label ON and the first caption line is `video.ai_label`. Never AI customers, reviews, "our work", or a person somewhere they weren't. Clone only the consenting owner's voice, for videos only, never calls or voicemails.
4. **Compliance check before approval.** A script or caption is not ready until the compliance step (below) says PASS.
5. **A human approves and posts.** Never post, upload, schedule, send, or spend money (no paid APIs, no Apify runs, no paid avatar service) from this skill.
6. Music only from the platform's commercial library, added in the app. Never in the master.
7. People and homes: written consent for faces, house numbers and plates.

## Production modes (`video.modes` lists the ones this business allows)

| Mode | Human does | AI label | Tool |
|---|---|---|---|
| REAL | films on the phone | no | `video <profile> edit` camera mode |
| FILM (default with no camera) | voice memo, or a cloned voice | only if the voice is AI | HyperFrames, `film` mode below |
| VOICE+CARDS | voice memo | only if the voice is AI | `video <profile> make` voice mode: **a draft or timing check, not a post** |
| TWIN | one-time training clip + consent | yes | external paid avatar service: only if listed and the owner asks; never run it from here |

A mode not in `video.modes` is not offered. Trust videos (who we are, prices, comparisons, replies) stay REAL.

## script

1. Pick the topic: the argument, a swipe note, a tracker row, or the latest viral-scout ideas note (`/viral-scout <profile> analyze` output) for a proven format and hook type. Search past hits: `python -m viral_scout search "<words>"`.
2. Facts: 1-3 primary sources (agency .gov pages, the utility, the manufacturer). WebSearch if needed. Unverifiable → cut it.
3. Write `<script_dir>/YYYY-MM-DD-<slug>.md` in this format (the cut reads it directly):
   ```markdown
   ---
   type: video-script
   status: draft            # draft → waiting-approval → approved → edited → posted
   created: YYYY-MM-DD
   rubric: <content pillar>
   mode: REAL | FILM + own voice | FILM + AI voice | VOICE+CARDS
   length: ~45 s
   tracker: <row #>
   sources: [primary URLs only]
   ---
   # <Title>
   > [!important] [VERIFY] facts that can change, and when to recheck them

   ### 1. <Title>
   **Alternative hooks:** (a) ... (b) ... (c) ...      ← 3 different hook types
   **Hook:** "<spoken, ≤15 words>"
   **Body:** "<spoken, ≤110 words, one idea, short sentences>"
   **CTA:** "<spoken: comment keyword first, link in bio as fallback>"
   **Cards:** stat `<number>` · kicker "…" · small "…" · source "…" → headline "*key* words" → list [...] → cta big "…", pill "…"
   **Cover:** "<≤4 words, *highlight*>"
   **Shot list / B-roll:** numbered shots with seconds; one signature shot
   **Captions:** TikTok · Reels · Shorts title + description · Facebook · pinned comment
   **AI label:** required / not needed
   > [!check] Compliance YYYY-MM-DD: PASS / FIX / BLOCK
   ```
   - Hooks: 3 types from the hook bank (stakes, counterintuitive fact, number, unfinished sentence, myth-buster, relatable situation). Never "In this video…". Hook in the first 2 s; cover text and first frame are hook decisions.
   - Plain spoken sentences, one idea, 30-60 s. **For an AI voice spell numbers out** ("forty eight", "seventeenth"); the captions turn them back into digits.
   - Every caption carries the source line and `studio`'s disclosure line; the CTA uses `studio.cta`.
4. Compliance step (below). Fix FIX items; rewrite anything BLOCK.
5. Tracker row: ✍️ scripted with a link (add the row if new). In chat: the hook, the 3 alternatives, the path. Stop: the owner approves.

## edit (REAL or VOICE+CARDS)

1. Read the script file, including Cards, Cover and sources.
2. `python -m viral_scout video <profile> cut "<media>" "<script.md>" [--section N] [--broll <folder>]`. Missing tools exit with code 3: run `python -m viral_scout video doctor` and tell the user the setup line from docs/video.md#install.
   - Every line should be ✓. A ✗ line is not in the recording: re-record or drop it.
   - **Read `dropped` in edit.json.** With an AI voice nothing should be dropped; a dropped word at the edge of a line means a number-word mismatch (see docs/video.md, number matching).
3. Edit `<output_dir>/<slug>/edit.json` (the auto draft stays in `edit.draft.json`):
   - `visuals[].card` from the script's Cards line: one idea per card, 1-4 big words, key word as `*word*`; kinds `stat` (big, kicker, small), `headline`, `list` (2-4 items), `cta` (big, pill).
   - `source` on every number card, never invented; no source → a headline without the number.
   - `cover.big` ≤ 4 words. Caption typos: change `words[].w` only, never the times.
4. Preview the cards: `video <profile> cards <slug>`, Read the PNGs. Then `video <profile> render <slug>`. A "cards without a real source" warning → back to step 3.
5. Look at it: 4-6 frames (`ffmpeg -ss <t> -i <slug>.mp4 -frames:v 1 f.png`), Read them: cards readable, captions not covered, nothing in the bottom 20%, no ADD SOURCE, hook text at frame 0.
6. `python -m viral_scout check <profile> "<master.mp4>"` and fix what fails (loudness, silence in the hook, length).
7. Tracker row 🎬 edited with the output path; "AI label ON" if the voice or a realistic visual is AI. In chat: the folder, flubs cut, anything missing. Stop.

## voice

`python -m viral_scout video <profile> voice profile "<out.wav>" "<script.md>" --section N [--cfg 0.5 0.3]` (`profile` = `video.voice.reference`). Several `--cfg` values give one take each: the owner picks by ear. Takes run about 20% long; the cut tightens pauses. Then `edit` or `film`.

## film (FILM)

Follow the method in the playbook §8 and the HyperFrames skills in `viral_scout/video/node/node_modules/hyperframes/dist/skills/` (hyperframes, hyperframes-cli). A business's first film is built live with the owner and becomes its quality bar; reuse its structure and code, design new scenes each time.
1. Script as above, mode FILM; compliance PASS.
2. Voice: the owner's memo, or `voice` above.
3. Film folder `<video.films_dir>/<slug>/` with `SPEC.md`: GOAL · OUTPUT · TIME · STORY · LOOK (the profile's colors and fonts) · OBJECTS · MOTION · SHOTS (second by second, keyed to words) · SOUND · BANNED · QA frames.
4. `python -m viral_scout video <profile> film words <slug> <voice.wav> <script.md> --section N`: writes `work-words.json` (the voice is the clock) and `voice-check.md`. Missing or extra speech, or a word over 0.8 s (a hidden repeat), → regenerate that line or mute it, then run `words` again.
5. Build `index.html` + `compositions/`; captions from `work-words.json` on dark plates, out of the bottom 20%.
6. `video <profile> film check <slug>` until 0 errors. Snapshots at the SPEC's QA frames; review like a viewer, 2+ rounds, each written in `REVIEW.md` (nothing still for > 2 s, empty thirds, unreadable text, captions over the action, a number without a source tag, an ending that isn't the CTA).
7. `video <profile> film render <slug>`: it reports loudness against about -14 LUFS / -1 dBTP. Transcribe the final audio once more (`film words` on the master) to confirm it says exactly the script.
8. Sound effects: CC0 or CC BY with credit in `assets/sfx/CREDITS.md`, never NonCommercial. No music in the master.
9. `POST.md` in the film folder: how to post, AI label, every platform's caption, pinned comment. Stop.

## week

1. Read the tracker (statuses, "What worked"), the content plan if any, the latest viral-scout ideas note and demand calendar (`data/<profile>-demand.json`: what is in season, `start_by` dates).
2. Pick 5 videos: ✍️ scripted first, then 💡 ideas, then new topics. No topic posted in the last 4 weeks. Month 1 after the first post: variety. From month 2: 1-2 slots are 🔁 re-cuts of the winners (new hook first).
3. Add new rows as 💡 and "week of YYYY-MM-DD" in Notes. In chat: a 5-row table (day · title · mode · status · the fact and source it rests on) and one line on batching the filming. Stop.

## review

1. Tracker rows 📤 posted in the last 7 days and their numbers at 48 h and 7 d (views, watch %, drop-off second, saves, shares, comments, leads). If the profile has own-performance data: `python -m viral_scout perf <profile> --no-pull` or the MCP `perf_results`.
2. Write "## What worked" in the tracker (newest first, dated): top video and why, weakest and what happens at its drop-off second, 3 things to repeat, 1 to stop. Mark rows 📈. From month 2 add the top 20% as 🔁 re-cut rows. Never invent numbers: list the empty cells for the owner to fill. Checklist content is judged by saves and shares.
3. In chat: 5 lines and the path. Stop.

## repurpose

Output folder `<studio.vault_dir>/05 Marketing/repurpose/YYYY-MM-DD-<slug>/`.
1. Text: copy a transcript or notes file as is to `transcript.txt`. Audio or video: `python -m viral_scout video <profile> transcribe "<recording>" --out "<folder>/transcript.txt"` (WhisperX; exit code 3 means it isn't installed: say so and stop).
2. `00-brief.md`: the one idea, audience, takeaways in order, every fact with its source ("Dropped: no source" list), the personal parts worth keeping.
3. Drafts, each with frontmatter `type: draft`, `status: draft`, `sources`: `01-short-video.md` (the script format above), `02-carousel.md` (6-8 slides: hook, points, sources, CTA), `03-blog-outline.md` (only if the topic carries a 900+ word guide; else one line why not), `04-newsletter.md` (120-200 words, one UTM link), `05-linkedin.md` (B2B or behind-the-scenes angle, ≤ 3 hashtags), `06-stories.md` (3 frames). Formats per channel may be set in `studio.instructions`.
4. Compliance step on every draft; result in `00-brief.md` under `## Compliance`.
5. One line in today's daily note; in chat the idea, the folder, the 3 hooks, dropped facts. Stop.

## Compliance step (also `check <file>`)

1. Read `studio.compliance` and the hard rules above.
2. Check every customer-facing line (script, cards, captions, description, pinned comment). Quote each problem.
3. Verdict PASS / FIX / BLOCK with a table `quote | rule | why | fix`. Unclear → FIX plus a "question for a lawyer".
4. On a vault file, append (don't rewrite the content):
   ```
   > [!check] Compliance YYYY-MM-DD: VERDICT
   > - <issue → fix>
   ```
5. Remind once: a checklist review, not legal advice.

## Before anything is called ready

- Script: compliance PASS, sources in the frontmatter, AI label decided.
- Master: `python -m viral_scout check <profile> <master.mp4>` run and read; frames looked at; `report.md` has no missing lines and no ADD SOURCE.
- Nothing posted, scheduled or paid for. The owner watches it with sound and posts it.
