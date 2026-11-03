# viral-scout

Finds what's going viral on a topic right now, for any business. One YAML profile per business; one Markdown report per run (Obsidian-friendly) plus JSON for other tools.

It answers three questions:

1. **What's big on the topic right now, whoever posted it?** Independent discovery: keyword search and hashtag feeds, ranked by views per day.
2. **What's taking off right now?** Every run stores a snapshot of each post's numbers in SQLite, so the next run measures growth per day ("Rise/day").
3. **Which formats work, not just which accounts are big?** Each post is compared with its creator's median post (or follower count). 3× or more is an outlier.

Plus a **watch list** of creators you follow and **seeds**: posts someone sent you, re-measured every run.

## Sources

| Source | What | Needs |
|---|---|---|
| YouTube hashtag feeds (`/hashtag/<tag>/shorts`) | Shorts for a hashtag | nothing (yt-dlp) |
| YouTube channels | latest Shorts/videos of watched channels, with median | nothing (yt-dlp) |
| YouTube keyword search | Shorts by keyword, last week/month, sorted by views, per language | `YOUTUBE_API_KEY` (free). yt-dlp can't read YouTube's Shorts search results |
| Any post URL (Instagram reel, TikTok, YouTube) | views/likes/comments/date of one post | nothing (yt-dlp) |
| Instagram watch list | another professional account's recent reels, likes, comments, followers | `IG_GRAPH_TOKEN` + `IG_GRAPH_USER_ID` (official Graph API, Business Discovery) |
| TikTok discovery + watch list | hashtags, keyword search, profiles | `APIFY_TOKEN` (Apify, paid per result) |

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
python -m viral_scout profiles
```

Requirements: Python 3.10+, `pip install -r requirements.txt`. Set `VIRAL_SCOUT_YTDLP` to a yt-dlp clone to use newer extractors than the pip package (recommended).

Daily run on Windows: `scripts/run-daily.ps1 -Profile <name>` (logs in `data/logs/`). Register it in Task Scheduler with "wake the computer to run" on.

## Profiles

`profiles/<name>.yaml`, see `profiles/_template.yaml` and `profiles/example-language-school.yaml`. Business profiles are git-ignored (only `_template` and `example-*` are committed), so your keywords and watch lists stay local. `${ENV}` is expanded, so `output_dir: ${OBSIDIAN_VAULT}/projects/x/...` writes into the vault.

Filters matter: hashtag feeds are full of spam (`#english` on gaming clips). `must_match` is checked against the title *without hashtags* plus the channel name; `exclude` against title + channel. Untitled hashtag results are checked again after their details are fetched.

## Report sections

- **Rising now**: growth since the previous run (needs two runs).
- **Fastest new posts on the topic**: independent discovery, by views per day.
- **Outliers**: 3× or more above the creator's usual.
- **Tracked links**: your seeds.
- **Creators who keep showing up**: candidates for the watch list.
- **Skipped sources / Errors**: what didn't run and why.

## Layout

```
viral_scout/        code (sources/ = one module per platform)
profiles/           one YAML per business
data/               SQLite history + latest JSON (git-ignored)
reports/            default report folder when a profile has no output_dir (git-ignored)
scripts/            run-daily.ps1
.claude/skills/     the /viral-scout skill for Claude Code
```
