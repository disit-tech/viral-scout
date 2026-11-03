# viral-scout

Finds what's going viral on a topic right now, for any business. One YAML profile per business; one Markdown report per run (Obsidian-friendly) plus JSON for other tools.

Docs: [references](docs/references.md) · [marketing workflow](docs/marketing-workflow.md) · [dashboard](docs/dashboard.md) · [how it works](docs/how-it-works.md) · [setup and keys](docs/setup.md) · [profiles](docs/profiles.md) · [similar tools](docs/similar-tools.md)

It answers three questions:

1. **What's big on the topic right now, whoever posted it?** Independent discovery: keyword search and hashtag feeds, ranked by views per day.
2. **What's taking off right now?** Every run stores a snapshot of each post's numbers in SQLite, so the next run measures growth per day ("Rise/day").
3. **Which formats work, not just which accounts are big?** Each post is compared with its creator's median post (or follower count). 3× or more is an outlier.

Plus a **watch list** of creators you follow and **seeds**: posts someone sent you, re-measured every run.

And it turns numbers into something you can film:

- **Hooks and transcripts**: what the strongest posts say in their first 4 seconds, and the full transcript (YouTube's public captions in the video's own language; post captions for Instagram/TikTok).
- **AI breakdown and ideas** (the `/viral-scout` Claude Code skill): format, hook type, 3-beat structure and why people watch to the end for the top posts, then 5 ideas adapted to the business described in the profile. Runs on your Claude Code subscription; no extra API key.
- **Swipe file**: `save` writes one Obsidian note per post (stats, thumbnail, hook, transcript, "why it works", "our version", status idea → scripted → filmed → posted) plus a `swipe.base` table/cards view. `dismiss` hides a post from future reports.
- **Telegram alerts** for new mega-outliers and fast risers (official Bot API; each post alerted once).
- **Suggested hashtags** that keep appearing on the hits but aren't in your profile yet.
- **Hook / CTA / pace**: what's said in the first 4 s and the last 5 s, plus words per minute; **percentile** among the creator's posts.
- **Local Whisper transcripts** for Instagram/TikTok audio (optional, free, CPU) and **cached frames** so the AI step can read on-screen text.
- **Quota meter**: YouTube API units, Apify results, requests and Whisper time per run, with warnings at 80% of your caps.
- **Comment mining**: the questions viewers ask under the hits are ideas your audience already asked for.
- **More ways to judge a hit**: × the niche median, age-matched views/day (YouTube API), 🌱 emerging creators, and **your own posts against your own usual**.
- **Trending hashtags** (Apify) and **Instagram hashtag top posts** (Graph API), when the keys are set.
- **Local competitors**: nearby businesses in your niche (Google Places API) and their public social channels, as watch-list candidates.
- **Search** across everything ever collected; **New research** from a description; a **Setup** page for keys (dashboard and CLI).
- **MCP server** (`python -m viral_scout.mcp_server`): Claude or any agent can run scouts, read results and manage the swipe file.
- **Web dashboard** (`web/`, Next.js): cards with thumbnails, hooks and growth sparklines, ideas, a swipe board. Local with actions, or published read-only to Vercel's free plan behind a password. See [docs/dashboard.md](docs/dashboard.md).

### How "viral" is scored

| Measure | Formula | Why |
|---|---|---|
| Per day | views ÷ age (age floored at 6 h) | fair between old and new posts |
| × usual | views ÷ the creator's **median** recent views (else ÷ followers) | median ignores the creator's own one-off hits; same idea as 1of10 / vidIQ / Virlo |
| Labels | ↑ ≥1.5×, ⚡ ≥3×, 🔥 ≥10× | Virlo's bands |
| Outlier rank | ln(× usual) × ln(creator baseline) | Virlo's weighting: a 20× hit on a 50-view channel ranks below 5× on a 100K channel |
| Rise/day | growth between two runs ÷ days | what is taking off *now* |
| ⏳ early | under 6 hours old | numbers still settling |

## Sources

| Source | What | Needs |
|---|---|---|
| YouTube hashtag feeds (`/hashtag/<tag>/shorts`) | Shorts for a hashtag | nothing (yt-dlp) |
| YouTube channels | latest Shorts/videos of watched channels, with median | nothing (yt-dlp) |
| YouTube keyword search | Shorts by keyword, last week/month, sorted by views, per language | `YOUTUBE_API_KEY` (free). yt-dlp can't read YouTube's Shorts search results |
| Any post URL (Instagram reel, TikTok, YouTube) | views/likes/comments/date of one post | nothing (yt-dlp) |
| Instagram watch list | another professional account's recent reels, likes, comments, followers | `IG_GRAPH_TOKEN` + `IG_GRAPH_USER_ID` (official Graph API, Business Discovery) |
| TikTok discovery + watch list | hashtags, keyword search, profiles | `APIFY_TOKEN` (Apify, paid per result) |
| Telegram alerts | push new outliers/risers | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`, or `alerts.env_file` to reuse an existing bot |

What it deliberately doesn't do: call Instagram's or TikTok's private web APIs, spoof app headers, or log in with someone's account behind their back. Instagram profiles and TikTok lists only come through the official API or a paid provider that handles it.

### Keys
Copy `.env.example` to `.env` (git-ignored):
- **YouTube Data API key** (free, 10,000 units/day; one keyword ≈ 102 units): Google Cloud console → new project → APIs & Services → Library → enable "YouTube Data API v3" → Credentials → Create credentials → API key. Restrict it to that API.
- **Instagram Graph API**: needs your own Instagram Business/Creator account linked to a Facebook Page and a Meta app with `instagram_basic` + `pages_read_engagement`. Business Discovery reads other *professional* accounts only, and gives likes, not views.
- **Apify**: apify.com → Settings → Integrations → API token. Default actor `clockworks~tiktok-scraper`.

## Use

```
python -m viral_scout run <profile>              # full run → report
python -m viral_scout run <profile> --no-discover # only watch list, seeds, re-checks
python -m viral_scout add <profile> <url> ...      # track posts someone sent you
python -m viral_scout save <profile> <ID|url> --note "why it works"   # → swipe file note
python -m viral_scout dismiss <profile> <ID|url> ...                  # never show again
python -m viral_scout status <profile> <note.md> scripted               # move a swipe note
python -m viral_scout export [profiles]                                # data for the dashboard
python -m viral_scout profiles
```

Requirements: Python 3.10+, `pip install -r requirements.txt`. Set `VIRAL_SCOUT_YTDLP` to a yt-dlp clone to use newer extractors than the pip package (recommended).

Daily run on Windows: `scripts/run-daily.ps1 -Profile <name> [-Analyze]` (logs in `data/logs/`). `-Analyze` then runs the skill headless to write the ideas note. Register it in Task Scheduler with "wake the computer to run" on.

In Claude Code: `/viral-scout <profile>` runs, analyzes and writes the ideas note; `/viral-scout <profile> analyze` only analyzes the latest run.

## Profiles

`profiles/<name>.yaml`, see `profiles/_template.yaml` and `profiles/example-language-school.yaml`. Business profiles are git-ignored (only `_template` and `example-*` are committed), so your keywords and watch lists stay local. `${ENV}` is expanded, so `output_dir: ${OBSIDIAN_VAULT}/projects/x/...` writes into the vault.

Filters matter: hashtag feeds are full of spam (`#english` on gaming clips). `must_match` is checked against the title *without hashtags* plus the channel name; `exclude` against title + channel. Untitled hashtag results are checked again after their details are fetched.

## Report sections

- **Rising now**: growth since the previous run (needs two runs).
- **Fastest new posts on the topic**: independent discovery, by views per day.
- **Outliers**: 3× or more above the creator's usual.
- **Tracked links**: your seeds.
- **Hooks**: first words + transcript of the strongest posts, with thumbnails.
- **Suggested hashtags**: from the hits, not yet in the profile.
- **Creators who keep showing up**: candidates for the watch list.
- **Skipped sources / Errors**: what didn't run and why.

## How it compares

Built after looking at the open-source [viral-shorts MCP](https://github.com/Xeron2000/shorts), [viral_short_research_tool](https://github.com/wisnuhid7/viral_short_research_tool) and [ViralMint](https://github.com/openclaw-easy/ViralMint), and the paid 1of10, vidIQ Outliers, TubeLab, Virlo, Sandcastles and Apify hook scrapers. Same core (outliers vs the creator's median, hooks, transcripts, swipe file, alerts), but free on YouTube, multi-platform through official APIs or Apify, per-business profiles, growth tracking between runs, and output straight into Obsidian. Not yet: on-screen text (OCR) for silent videos, trending sounds, local Whisper transcription for Instagram/TikTok audio.

## Layout

```
viral_scout/        code (sources/ = one module per platform)
profiles/           one YAML per business
data/               SQLite history + latest JSON (git-ignored)
reports/            default report folder when a profile has no output_dir (git-ignored)
scripts/            run-daily.ps1
.claude/skills/     the /viral-scout skill for Claude Code
```
