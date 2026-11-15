# Content packs (one approved idea → ready-to-post texts per platform)

Read by `/studio-ideas` (SKILL.md step 3) for every idea that is ✅ `approved` or has `stage: "pack"`, on profiles with `ideas.packs.enabled`. The CLI refuses packs for other profiles, and the API only takes them for projects it allows.

## Before writing
- The idea itself (from `pull`): title, hook, angle, fact + source, visual, cta, `platforms`, and the owner's `comment` / `tags` / `feedback`. A pack request after an earlier pack means he wants a new version: read his replies and comments first.
- The taste note, the compliance note, the price source and the voice samples the instructions note names, and its **Packs** section (who speaks, names, towns, link pages, banned phrases, accounts that don't exist yet).
- The latest `*-viral-scout.md` and `*-ads-scout.md` from `market_data.newest`: borrow formats and angles, never footage or copy.

## Rules for every text (core)
- Prices only from the price source the instructions note names, written the way they are there ("from $249", "$150–250"). Time-limited offers: check today's date against the offer's dates.
- No reviews, star counts, job counts or "trusted by" until they are real. No customer photos, house numbers or faces without permission.
- No pressure or fake urgency ("only 2 spots left!") unless it's literally true and dated.
- Plain and specific. No AI tells: no "not X, but Y", no em-dash asides, no "elevate / seamless / hassle-free / game-changer", no rhetorical triplets, no one-line moral at the end. Short sentences. Emojis: at most 1–2 per post, none on LinkedIn except bullets.
- Every link carries its channel: `<site>/<page>?utm_source=<channel>&utm_medium=<post|page|group|gbp|video>&utm_campaign=<idea-slug>` (`<site>` = `studio.cta.link` unless the instructions note says otherwise).
- Post bodies are plain text (the platforms don't render Markdown): no `**bold**`, no `[links](…)`. Bullets as "•".
- The profile's `packs.banned_words` are errors in the CLI check. The instructions note may add phrases to avoid that the CLI can't catch.

## Platforms (one `##` section each, in this order)
Write a section only for the idea's `platforms` (the owner may have changed them in the CRM), plus `## Checks`. An idea with no `platforms`: write every section the instructions note lists as default. Key → section: `linkedin` → LinkedIn · `threads` → Threads · `facebook` → Facebook page · `fb_groups` → Facebook groups (one per language the instructions note names) · `nextdoor` → Nextdoor · `google` → Google Business Profile · `instagram` / `tiktok` / `youtube` → Reels / Shorts / TikTok (only the blocks for those platforms, plus Facebook Reels if `facebook` is in the list) · `yelp` → Yelp · `email` → Email · `print` → Print.

| Section | Who reads it | Length and format | Call to action |
|---|---|---|---|
| `## LinkedIn` | B2B buyers (the instructions note says which) | 120–250 words; the first 2 lines carry it (LinkedIn cuts at ~200 chars); short paragraphs, "•" bullets; **3–8 hashtags** at the end; max 3,000 chars | message us here, or the phone + link `utm_source=linkedin` |
| `## Threads` | locals scrolling, conversational | 1–3 short paragraphs, **≤ 500 chars per post**. A mini thread = `### 1/2`, `### 2/2` (each its own block). One topic tag at most. End with a question people can answer | a question, or the `studio.cta` |
| `## Facebook page` | people who follow or find the page | 60–150 words, hook line first, price, what happens next | phone + link `utm_source=facebook&utm_medium=page` |
| `## Facebook groups (<language>)` | local or language groups | Only when the idea fits the people in those groups (skip for B2B ideas and say so in Checks). Natural wording in that language, not a word-for-word translation. Check each group's rules on business posts | message with a photo + the page in that language, `utm_medium=group` |
| `## Nextdoor` | neighbors | "Hi neighbors," tone, 60–120 words, 2–4 town names from the service area, one price, the owner named once. About one business post every two weeks | the `studio.cta` + link `utm_source=nextdoor` |
| `## Google Business Profile` | people who found the business on Google | **≤ 1,500 chars**, the point in the first ~100–250 chars. Type **Update** with **one button: Call now, Book or Learn more** (say which in a `>` note). Type **Offer** only for a real price (title ≤ 58 chars, start/end dates, terms). No phone number in the text (use the Call now button) | the one button |
| `## Reels / Shorts / TikTok` | short video, filmed on a phone | `### Hook` (spoken + on-screen, first 2 seconds), `### Shots` (numbered, vertical 9:16, 15–35 s total, each doable by the person filming: what, from where, how long), `### On-screen text` (per shot, ≤ 7 words each), `### Voiceover` (if any, ≤ 80 words), then one block per platform: `### Instagram Reels` (caption + 3–5 hashtags), `### TikTok` (one-line caption + 3–5 hashtags), `### YouTube Shorts` (title ≤ 100 chars ending in #Shorts, then a 1–2 line description), `### Facebook Reels` (caption, 0–2 hashtags) | the `studio.cta` on the last card |
| `## Yelp` | people comparing on Yelp | Yelp has **no free organic posts** (Yelp Connect is paid). So: 2–5 job photos from this idea to upload, each with a one-line caption, and only for a finished job or reviews a reply template for a real review (`### Review reply`). Never ask for reviews in exchange for anything | none |
| `## Email` | the opt-in list | subject ≤ 60 chars, a preview line, 80–150 words, one link with `utm_source=email` | the one link |
| `## Print` | door hangers, flyers | headline ≤ 8 words, 3 bullets, price, phone, a QR short link | phone or QR |
| `## Checks` | the owner (not sent) | claims checked: prices vs the price source, the instructions note's banned claims, towns, dates, photos needed, which accounts don't exist yet | |

Notes for the owner inside a section go on lines starting with `>` (e.g. `> Photo: the full bucket next to the ladder`, `> Button: Call now`). They show in italics above the copy block, outside it. A `###` block with only `>` lines becomes the note of the next block.

## The vault note
Folder: the instructions note's packs folder (default `<studio.vault_dir>/05 Marketing/posts/`). Name: `YYYY-MM-DD-idea-<id>-<slug>.md` (a new version for the same idea: same name + `-v2`).
```markdown
---
type: post-pack
department: 05 Marketing
created: YYYY-MM-DD
idea: <id>
idea_title: "<title>"
status: draft
platforms: [linkedin, threads, facebook, nextdoor, gbp, short-video]
tags: [<project>, posts, social]
---

# Posts: <title> (idea #<id>)

Idea #<id> from the idea generator. Drafts: the owner posts them by hand.

## LinkedIn
> Photo: …
<post text>

## Threads
### 1/2
<post>
### 2/2
<post>
…
## Checks
- …
```
Anything above the first `##` is for the vault only. Sections called Checks, Claims checked, Notes or Перевірка are never sent. Then:
1. `python -m viral_scout ideas <profile> pack <id> "<note path>" --dry-run`: checks the profile's `packs.limits` (e.g. Threads 500 per post, Google 1,500, LinkedIn 3,000 and 3–8 hashtags), the API's limits (one Telegram message per section, 10 blocks, 3,500 chars per block) and `packs.banned_words` (plus em dashes as a warning). Fix every error and warning, rerun.
2. The same command without `--dry-run`: one Telegram message per section, as replies under the idea; the idea shows "📝 пости надіслано" and its button turns into "📝 Пости ще раз". `--store-only` stores it for the CRM without sending (a pack sent by hand earlier).
3. Add the note to the idea's tracker row (Notes: `posts [[…]]`).
