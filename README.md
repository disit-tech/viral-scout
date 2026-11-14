# viral-scout

Finds what's going viral on a topic right now, for any business. One YAML profile per business; one Markdown report per run (Obsidian-friendly) plus JSON for other tools.

Docs: [ads scout](docs/ads-scout.md) · [references](docs/references.md) · [originality and duplicate detection](docs/originality-and-duplicate-detection.md) · [marketing workflow](docs/marketing-workflow.md) · [dashboard](docs/dashboard.md) · [how it works](docs/how-it-works.md) · [setup and keys](docs/setup.md) · [profiles](docs/profiles.md) · [similar tools](docs/similar-tools.md)
Docs: [your performance](docs/performance.md) · [references](docs/references.md) · [originality and duplicate detection](docs/originality-and-duplicate-detection.md) · [marketing workflow](docs/marketing-workflow.md) · [dashboard](docs/dashboard.md) · [how it works](docs/how-it-works.md) · [setup and keys](docs/setup.md) · [profiles](docs/profiles.md) · [similar tools](docs/similar-tools.md)

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
- **Search posts** across everything ever collected; **New business** (or a one-off quick research) from a description; a **Setup** page for keys (dashboard and CLI).
- **Video analysis page**: click any tile for the full breakdown: the 5 tests, a **20-criteria / 100-point creative scorecard** (AI), every number explained, growth, hook/CTA, viewer questions, transcript. See [docs/video-quality-framework.md](docs/video-quality-framework.md).
- **Pre-publish check** for your own drafts (`check` command or the dashboard's Check a video page): format, loudness, peaks, silences, cuts and pacing, pattern interrupts, speech start, CTA, frames for the AI scorecard.
- **Ads scout** (`python -m viral_scout ads <profile>`): the paid side. Competitor and category ads that keep running on **Facebook/Instagram, Google (Search, YouTube, Display) and TikTok**: the Meta Ad Library API for EU ads, the TikTok Commercial Content API for EEA ads, and three Apify actors for the US: `apify~facebook-ads-scraper`, `automation-lab~google-ads-scraper` (by competitor domain and name) and `pulsedata~tiktok-creative-center-top-ads-scraper` (top ads for an industry). Scored on days running, variants and reach, with hook, offer, CTA, landing domain and format extracted. Report, JSON, an Ads page per business, and ad ideas from the skill. See [docs/ads-scout.md](docs/ads-scout.md).
- **Ad detail page**: click any ad for why it's worth studying, a copy breakdown (hook, problem, offer, proof, urgency, what shows before "See more"), its variants, the advertiser's timeline and offer mix, and the same angle at other advertisers. Computed from the collected data, no extra cost. Plus, per ad: a **transcript** of video ads (local Whisper, free; the weekly run does the top ones itself), an **AI breakdown with our version** (Claude Code CLI, your subscription) and **save to the swipe file**: `python -m viral_scout ad <profile> <key> transcribe|analyze|save`, or the buttons on the ad page.
- **Search demand** (`python -m viral_scout demand <profile>`): Google Trends for the business's area (a metro such as Chicago, a state or the country). When each service starts rising, peaks and ends (up to two seasons per term), a *start posting by* date, now vs last year and vs normal, rising **buyer** searches, and which wording people use. Weekly, about $0.005 per term via Apify's Google Trends actor. Dashboard page, vault note, MCP `demand_results`. See [docs/search-demand.md](docs/search-demand.md).
- **Activity page** (`/activity`, local dashboard): what is running right now with its live log and progress, plus Apify actor runs and spend this cycle. Every run writes a live log to `data/activity/`, whoever started it.
- **Spend controls**: every Apify run carries a spend cap (`APIFY_MAX_USD_PER_RUN`, default $0.50), scheduled runs are weekly by default, and paid MCP tools are off unless `VIRAL_SCOUT_MCP_PAID=1`. See [costs](docs/ads-scout.md#costs-and-spend-controls).
- **Your performance** ([docs](docs/performance.md)): the private numbers only your own accounts have (hook rate, watch time, retention curve, completion, shares/saves, CTR, CVR, CPA, CAC, ROAS) from the Instagram Graph API, YouTube Analytics (OAuth), the Meta Marketing API, the TikTok API for Business, or your own CSV exports. KPIs A–E with formulas and denominators, diagnostics against your own medians, the 5 tests, retention drop-offs, creative fatigue, unit economics.
- **MCP server** (`python -m viral_scout.mcp_server`): Claude or any agent can read results, run free tools and manage the swipe file. Paid tools (`start_run`, `ads_run`, `local_competitors`, `create_project` with `start`) refuse unless the server runs with `VIRAL_SCOUT_MCP_PAID=1`, because it's registered at user scope and any agent in any repo could otherwise spend the Apify budget.
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
| Meta Ad Library API (ads scout) | ads delivered in the EU + political ads: copy, dates, platforms, EU reach. **No US commercial ads** | `META_AD_LIBRARY_TOKEN` (free, identity-verified) |
| TikTok Commercial Content API (ads scout) | TikTok ads shown in the EEA: dates, reach, media (no copy) | `TIKTOK_RESEARCH_CLIENT_KEY` + `_SECRET` (free, by application) |
| Meta Ad Library / Google Transparency / TikTok Top Ads via Apify (ads scout) | US and other ads where no official API exists | `APIFY_TOKEN` + `APIFY_ADS_ACTOR=apify~facebook-ads-scraper` / `APIFY_GOOGLE_ADS_ACTOR=automation-lab~google-ads-scraper` / `APIFY_TIKTOK_ADS_ACTOR=pulsedata~tiktok-creative-center-top-ads-scraper` (paid per ad) |
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
python -m viral_scout ads <profile>                # best-performing ads in the niche → ads report
python -m viral_scout add <profile> <url> ...      # track posts someone sent you
python -m viral_scout save <profile> <ID|url> --note "why it works"   # → swipe file note
python -m viral_scout dismiss <profile> <ID|url> ...                  # never show again
python -m viral_scout status <profile> <note.md> scripted               # move a swipe note
python -m viral_scout export [profiles]                                # data for the dashboard
python -m viral_scout profiles
python -m viral_scout perf <profile>                                   # your own videos and ads → performance report
python -m viral_scout perf import <profile> export.csv --source meta   # or tiktok | youtube | generic
python -m viral_scout perf auth youtube                                # one-time OAuth for YouTube Analytics
```

Requirements: Python 3.10+, `pip install -r requirements.txt`. Set `VIRAL_SCOUT_YTDLP` to a yt-dlp clone to use newer extractors than the pip package (recommended).

Scheduled run on Windows: `scripts/run-daily.ps1 -Profile <name> [-Analyze]` (logs in `data/logs/`). `-Analyze` then runs the skill headless to write the ideas note. `scripts/schedule.ps1 -Profiles a,b,c -Analyze -Publish` registers **weekly** Monday tasks (`-Day Daily` for daily): one Monday snapshot of trending posts and competitor ads, then a week of content made from it. See [setup](docs/setup.md#scheduling).

**Getting the results elsewhere:** other repos and agents read them through the `viral-scout` MCP server (user scope, so every Claude Code session on this PC has it), the Markdown reports in the Obsidian vault, or the JSON in `data/` and `web/data/`. People without access to this PC use the dashboard published on Vercel. See [setup](docs/setup.md#mcp-server-optional).

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
viral_scout/        code (sources/ = one module per platform, perf/ = own performance)
tests/              tests (python tests/test_perf.py runs without pytest)
profiles/           one YAML per business
data/               SQLite history + latest JSON (git-ignored)
reports/            default report folder when a profile has no output_dir (git-ignored)
scripts/            run-daily.ps1
.claude/skills/     the /viral-scout skill for Claude Code
```
