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

6. The shared method notes for your mode (table below).
7. `video.formats` (in the `info` output): formats the owner marked as good references. For `script`, `film` and `week`, read each format's `references` swipe notes ("Why it works") and its `guide` section in docs/video.md, and follow its `structure`, `length` and `topics` when the topic fits.
8. **One goal per video.** Every video serves one goal: `views` (reach strangers), `follows` (a series people come back for), `trust` (the owner, the process, real jobs) or `leads` (a check → the CTA). `video.goals` in the profile says what each goal means for this business. A video that tries to do all of them does none well. Pick the goal first, write it in the script's frontmatter (`goal:`), then let it decide the format, hook, ending and CTA: a views video keeps the brand to the last seconds and has no hard CTA, and a leads video ends on a check the viewer can do plus `studio.cta`. `week` balances the goals across the 5 slots.

## Shared method notes (read the ones your mode needs)

The method behind this skill lives in the owner's vault under `$OBSIDIAN_VAULT/shared/`. This skill is the short form; when a mode below lists a note, read it (the sections named) before you start. Missing note → say so and go on with this skill.

| Note | What it holds | Read it for |
|---|---|---|
| `shared/playbooks/05 Marketing/video-generation.md` | the full system: modes (§2), accordion method and hooks (§3), the script file (§4), voice (§5), filming (§6), editing (§7), films (§8), one recording → every channel (§9), publishing (§10), measuring (§11), rules for every business (§13) | every mode: the section that matches it |
| `shared/reference/video-craft-lessons.md` | the 12 craft rules (packaging, the first seconds, retention, story, sound, one change per video) and how they map to our videos | `script`, `film`, `week`, `review` |
| `shared/playbooks/05 Marketing/daily-animated-film-pipeline.md` | how one finished film a day is made unattended: topic choice, the build, the review, the post pack, lessons | `film` (and the film job) |
| `shared/playbooks/05 Marketing/platform-approaches.md` | one idea, a different post per platform: what changes on TikTok, Reels, Shorts, Facebook, Threads, LinkedIn | `script` (captions), `repurpose` |
| `shared/playbooks/07 Jurisdiction/compliance-check-routine.md` | the fixed check before anything reaches customers: what to check, PASS / FIX / BLOCK | the compliance step, `check` |
| `shared/playbooks/07 Jurisdiction/marketing-compliance-checklist.md` | the generic marketing rules (endorsements and disclosures, claims, testimonials, experts) under the business's own compliance note | the compliance step, `check` |
| `shared/playbooks/07 Jurisdiction/photo-video-release-template.md` | the consent form for faces, homes, stories and testimonials | `edit` and `script` with REAL footage of people or their homes |
| `shared/playbooks/05 Marketing/social-profiles-kit.md` | bios, disclosure line in every video description, upload defaults per platform | `repurpose`, captions |
| `shared/playbooks/05 Marketing/idea-generator-telegram.md` | how ideas are rated in Telegram and how a ✅ idea becomes a script | `script` from an idea, `week` |

Business rules (`studio.instructions`) override these notes where they differ; the hard rules below override everything.

## Hard rules (no profile or instruction note can change these)

1. **Truth.** Every number has a primary source shown on screen or in the description. No source, no number. Facts that can change are re-checked on the day.
2. **Never copy.** No other creators' or competitors' footage, audio, music, words, creatives, logos or trademarks. Borrow formats and angles only. Never imply affiliation with a brand, utility or agency.
3. **AI disclosure.** AI voice, AI avatar or a realistic AI scene: platform AI label ON and the first caption line is `video.ai_label`. Never AI customers, reviews, "our work", or a person somewhere they weren't. Clone only the consenting owner's voice, for videos only, never calls or voicemails.
4. **Compliance check before approval.** A script or caption is not ready until the compliance step (below) says PASS.
5. **A human approves and posts.** Never post, upload or schedule anything public, never message customers, never spend money (no paid APIs, no Apify runs, no paid avatar service). Sending a draft to the owner's own review group (`notes send`, the ideas bot) is fine: that is how the owner reviews it.
6. No music in the master. Platform-library music is added by the owner in the app when posting. The one exception is `--music`, off by default: only a track the owner made or licensed for this use, never a download from the web or another creator's post.
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

1. Pick the topic: the argument, a swipe note, a tracker row, or the latest viral-scout ideas note (`/viral-scout <profile> analyze` output) for a proven format and hook type. Search past hits: `python -m viral_scout search "<words>"`. From a reference, decide per part what carries over: hook type, structure and editing can be adapted, the topic is swapped for ours, the words and delivery are never copied.
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
   **Headline (frame 0):** "<≤6 words on screen, static>"
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
   - Hooks: 3 types from the hook bank (stakes, counterintuitive fact, number, unfinished sentence, myth-buster, relatable situation). Once the tracker has 10+ posted videos, put first the hook types that won for this business (best watch % in "What worked"), then the generic list. Never "In this video…". Hook in the first 2 s; cover text and first frame are hook decisions.
   - The hook lands three ways at once: the frame-0 headline, the picture and the spoken line. They carry one message in different words. The spoken line adds to the headline; it never just reads it out.
   - Plain spoken sentences, one idea, 30-60 s. **For an AI voice spell numbers out** ("forty eight", "seventeenth"); the captions turn them back into digits.
   - Rhythm: mix line lengths (very short lines of 1-3 words between medium and long ones). Three lines of about the same length in a row → shorten one. Step lists are the exception.
   - Every caption carries the source line and the disclosure line from `studio.instructions` (or `studio.compliance`); the CTA uses `studio.cta`.
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
5. Look at it: 4-6 frames (`ffmpeg -ss <t> -i <slug>.mp4 -frames:v 1 f.png`), Read them: cards readable, captions not covered, readable text and faces inside the safe area (about 5% margin at the sides and top, nothing in the bottom 20%), no ADD SOURCE, hook text at frame 0.
6. `python -m viral_scout check <profile> "<master.mp4>"` and fix what fails (loudness, silence in the hook, length).
7. Tracker row ✂️ edited with the output path (🎬 means shot, or "🎬 film rendered" for a film); "AI label ON" if the voice or a realistic visual is AI. In chat: the folder, flubs cut, anything missing. Stop.

## voice

`python -m viral_scout video <profile> voice profile "<out.wav>" "<script.md>" --section N [--cfg 0.5 0.3]` (`profile` = `video.voice.reference`). Several `--cfg` values give one take each: the owner picks by ear. Takes run about 20% long; the cut tightens pauses. Then `edit` or `film`.

## film (FILM)

Follow the method in the playbook §8 and the HyperFrames skills (hyperframes, hyperframes-cli). They ship inside the HyperFrames package: `$VIRAL_SCOUT_VIDEO_NODE_MODULES/hyperframes/dist/skills/` when that env var is set (the tools then run from a business's existing install), else `viral_scout/video/node/node_modules/hyperframes/dist/skills/`. A business's first film is built live with the owner and becomes its quality bar; reuse its structure and code, design new scenes each time.
1. Script as above, mode FILM; compliance PASS.
2. Voice: the owner's memo, or `voice` above.
3. Film folder: `python -m viral_scout video <profile> film new <slug> --from <reference film>` copies the reference's SPEC, code, fonts and sound effects into `<video.films_dir>/<slug>/` (renders, word times, its voice, REVIEW.md and POST.md are left out). No reference yet → create the folder. Rewrite `SPEC.md` for this film: GOAL · OUTPUT · TIME · STORY · LOOK (the profile's colors and fonts) · OBJECTS · MOTION · SHOTS (second by second, keyed to words) · SOUND · BANNED · QA frames.
4. `python -m viral_scout video <profile> film words <slug> <voice.wav> <script.md> --section N`: writes `work-words.json` (the voice is the clock) and `voice-check.md`. Missing or extra speech, or a word over 0.8 s (a hidden repeat), → regenerate that line or mute it, then run `words` again. A `heard differently: so → Do` line is Whisper mishearing the first or last word of a sentence: the script's word is kept, just listen to that spot.
5. Build `index.html` + `compositions/`; captions from `work-words.json` on dark plates, inside the safe area (about 5% margin at the sides and top, out of the bottom 20%). Frame 0 already shows the headline at full opacity and the main object: animate after the first frame, never into it.
6. `video <profile> film check <slug>` until 0 errors. Snapshots at the SPEC's QA frames; review like a viewer, 2+ rounds, each written in `REVIEW.md` (frame 0 empty or still fading in, nothing still for > 2 s, empty thirds, unreadable text, text outside the safe area, captions over the action, a number without a source tag, an ending that isn't the CTA).
7. `video <profile> film render <slug>`: it reports loudness against about -14 LUFS / -1 dBTP. A ⚠ line → change the voice and sound effect levels in the composition and render again. Last resort, the audio only: `ffmpeg -i <in.mp4> -c:v copy -af loudnorm=I=-14:TP=-1:LRA=11 <out.mp4>`, then `python -m viral_scout check <profile> <out.mp4>`. Transcribe the final audio once more (`film words` on the master) to confirm it says exactly the script.
8. Sound effects: CC0 or CC BY with credit in `assets/sfx/CREDITS.md`, never NonCommercial. No music in the master.
9. The "Don't / Do" still, only when the topic has an honest pair: take a ❌ frame and a ✅ frame from the render (`ffmpeg -ss <t> -i <mp4> -frames:v 1 x.png`), then `video <profile> still --top … --bottom … --top-text "DON'T …" --bottom-text "DO …" --source "<short source>" --out <film>/still.png`. Crop between the film's own heading and its captions (`--top-y` / `--bottom-y` about 0.3-0.45). Labels of 3-5 words that match each picture. Read the PNG: nothing cut off, no film text behind the labels, the source and brand tags don't overlap. No honest pair → no still.
10. `POST.md` in the film folder: how to post, AI label, every platform's caption, pinned comment. Tracker row 🎬 film rendered with the mp4 path and the post date. Stop.

## week

1. Read the tracker (statuses, "What worked"), the content plan if any, the latest viral-scout ideas note and demand calendar (`data/<profile>-demand.json`: what is in season, `start_by` dates).
2. Pick 5 videos: ✍️ scripted first, then 💡 ideas, then new topics. No topic posted in the last 4 weeks. Never two videos of the same format on neighbouring days. Give each slot one goal: saves, trust, reach, expertise or leads. Month 1 after the first post: variety. From month 2: 1-2 slots are 🔁 re-cuts of the winners (new hook first).
3. Add new rows as 💡 and "week of YYYY-MM-DD" in Notes. In chat: a 5-row table (day · title · rubric · mode · goal · status · the fact and source it rests on) and one line on batching the filming. Stop.

## review

1. Tracker rows 📤 posted in the last 7 days and their numbers at 48 h and 7 d (views, watch %, drop-off second, saves, shares, comments, leads). If the profile has own-performance data: `python -m viral_scout perf <profile> --no-pull` or the MCP `perf_results`.
2. Read each video's retention curve by its shape and apply that shape's fix (table in docs/performance.md, "Curve shapes"): an early cliff points at the hook, a slow slide through the middle at the body, a late drop at the payoff. Mark every rise in the curve too (people rewound) and write what was on screen there: rises are what to repeat. Judge each video by its format's own metric (docs/video-quality-framework.md, "One metric per format"); a hook type is judged after 3 posts, not 1.
3. Write "## What worked" in the tracker (newest first, dated): top video and why, weakest with its curve shape and what happens at its drop-off second, 3 things to repeat, 1 to stop. Change one thing per re-cut. Mark rows 📈. From month 2 add the top 20% as 🔁 re-cut rows. Never invent numbers: list the empty cells for the owner to fill.
4. In chat: 5 lines and the path. Stop.

## repurpose

Slug: `--slug`, else 3 to 5 words of the main topic, lowercase with hyphens. Output folder `<studio.vault_dir>/05 Marketing/repurpose/YYYY-MM-DD-<slug>/`.
1. Text: copy a transcript or notes file as is to `transcript.txt`. Audio or video: `python -m viral_scout video <profile> transcribe "<recording>" --out "<folder>/transcript.txt"` (WhisperX; exit code 3 means it isn't installed: say so and stop).
2. `00-brief.md`: the one idea, audience, takeaways in order, every fact with its source ("Dropped: no source" list), the personal parts worth keeping.
3. Drafts, each with frontmatter `type: draft`, `status: draft`, `source: transcript.txt`, `sources: [...]`: `01-short-video.md` (the script format above), `02-carousel.md` (6-8 slides: hook, points, sources, CTA), `03-blog-outline.md` (only if the topic carries a 900+ word guide; else one line why not), `04-newsletter.md` (120-200 words, one UTM link), `05-linkedin.md` (B2B or behind-the-scenes angle, ≤ 3 hashtags), `06-stories.md` (3 frames, each ≤ 12 words on screen with a background idea and a sticker: (1) the hook plus a question sticker or poll, (2) the one useful fact with its source on screen, (3) the CTA; no realistic AI people). Formats per channel may be set in `studio.instructions`.
4. Compliance step on every draft. These are our own drafts, so fix FIX items yourself and rewrite BLOCK items in the draft, then write the verdicts in `00-brief.md` under `## Compliance`. A draft is not called ready until its verdict is PASS.
5. One line in today's daily note; in chat the idea, the folder, the 3 hooks, dropped facts, and each customer-facing draft that is not PASS yet (at least the video captions, the carousel caption and the newsletter). Stop.

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
- Repurpose drafts: each one PASS in `00-brief.md` under `## Compliance`.
- Master: `python -m viral_scout check <profile> <master.mp4>` run and read; frames looked at; `report.md` has no missing lines and no ADD SOURCE.
- Nothing posted, scheduled or paid for. Sent only to the owner for review. The owner watches it with sound and posts it.
