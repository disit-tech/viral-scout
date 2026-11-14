# Setup and keys

## Install

```
git clone https://github.com/disit-tech/viral-scout
cd viral-scout
pip install -r requirements.txt
cp .env.example .env
```

You need Python 3.10+. Instagram and YouTube change often, so pointing `VIRAL_SCOUT_YTDLP` in `.env` at a yt-dlp clone (`git clone https://github.com/yt-dlp/yt-dlp`) gives you newer extractors than the pip package.

On Windows, set `PYTHONIOENCODING=utf-8` for terminal output with emoji and Cyrillic. The scripts already do this.

Test it:
```
python -m viral_scout profiles
python -m viral_scout run example-language-school
```

## Keys (all optional)

Each key unlocks one source. When a key is missing, that source is listed under **Skipped sources** and the rest still runs.

### YouTube Data API key (free, recommended)
This unlocks **keyword search for Shorts**, with a time window, sorted by views, per language. yt-dlp can't read YouTube's Shorts search results.

1. Go to the Google Cloud console and create a project.
2. In APIs & Services → Library, enable **YouTube Data API v3**.
3. In Credentials, create an **API key**. Restrict it to YouTube Data API v3.
4. Add `YOUTUBE_API_KEY=...` to `.env`.

The free quota is 10,000 units a day, and one keyword costs about 102 units. So about 90 keywords a day, or about 45 if you run twice daily.

### Instagram Graph API (free, needs a business setup)
This unlocks the **watch list for Instagram professional accounts**: recent reels with likes, comments and followers.

What you need:
- an Instagram Business or Creator account linked to a Facebook Page,
- a Meta app with `instagram_basic` and `pages_read_engagement`,
- a long-lived access token.

Add `IG_GRAPH_TOKEN=...` and `IG_GRAPH_USER_ID=...` (your Instagram business account id) to `.env`.

Limits: it only reads **professional** accounts, and it returns likes, not views.

### Apify (paid per result)
This unlocks **TikTok** hashtags, keyword search and profiles. Get a token at apify.com → Settings → Integrations, and add `APIFY_TOKEN=...` to `.env`. The default actor is `clockworks~tiktok-scraper`; change it with `APIFY_TIKTOK_ACTOR`. Check the actor's price per result before you schedule it.

### Google Places API (free monthly credit, then paid)
Unlocks **local competitors**: `python -m viral_scout competitors <profile> "gutter cleaning" --near "Norridge, IL"`. Enable "Places API (New)" in Google Cloud, create a key restricted to it, and add `GOOGLE_PLACES_API_KEY=...`. Each run makes one Text Search request plus one plain request to each competitor's own homepage, to find their YouTube, Instagram, TikTok and Facebook links.

### Trending hashtags (optional)
- **TikTok:** pick a trends actor in the Apify store, then set `APIFY_TRENDS_ACTOR=user~actor` (it uses `APIFY_TOKEN`) and pass its input in the profile under `trends.apify_input`.
- **Instagram:** with the Graph API keys, list hashtags under `trends.instagram_hashtags`. Their top reels join the run. Meta allows 30 unique hashtags per 7 days, and the tool counts them.

### Ads scout keys (optional)
`python -m viral_scout ads <profile>` reads competitor ads. Every source is optional. Details, coverage and costs are in [ads-scout.md](ads-scout.md).
- **Meta Ad Library API (free):** confirm your identity at facebook.com/ID, create a Meta for Developers app, get a user token in the Graph API Explorer (make it long-lived), then set `META_AD_LIBRARY_TOKEN=...`. It returns **ads delivered in the EU** plus political/issue ads. US commercial ads aren't available through the API.
- **TikTok Commercial Content API (free, by application):** apply on TikTok for Developers. After approval, set `TIKTOK_RESEARCH_CLIENT_KEY` and `TIKTOK_RESEARCH_CLIENT_SECRET`. It covers ads shown in the EEA, without ad copy.
- **Apify (paid):** with `APIFY_TOKEN`, set the actor for each route. The input and output mappings are written and tested for these three:
  - `APIFY_ADS_ACTOR=apify~facebook-ads-scraper`: Meta Ad Library, any country including the US ($3.40–5.80 per 1,000 ads, by Apify plan)
  - `APIFY_GOOGLE_ADS_ACTOR=automation-lab~google-ads-scraper`: Google Ads Transparency Center by competitor domain and name ($1.30 per 1,000 ads)
  - `APIFY_TIKTOK_ADS_ACTOR=pulsedata~tiktok-creative-center-top-ads-scraper`: TikTok Creative Center Top Ads for an industry ($2 per 1,000 ads). Set `ads.tiktok_top_input.industries` in each profile, because it has no keyword search.
  Usage counts toward `budget.apify_items_per_month`. See [costs and spend controls](ads-scout.md#costs-and-spend-controls).
- **Spend controls:** `APIFY_MAX_USD_PER_RUN` (default 0.50, 0 = no cap) is sent with every Apify run as its maximum charge. `VIRAL_SCOUT_MCP_PAID=1` lets MCP clients start paid runs (off by default). Both are on the dashboard's Setup page.
### Your own performance (optional, free)
Reads **your own** accounts' private metrics for the [Your performance](performance.md) report. Each pair is optional:
- **Instagram insights:** the `IG_GRAPH_TOKEN` above, with `instagram_manage_insights` (and `instagram_manage_comments` for comment sentiment) added.
- **YouTube Analytics:** a Desktop OAuth client (`YT_OAUTH_CLIENT_ID`, `YT_OAUTH_CLIENT_SECRET`), then `python -m viral_scout perf auth youtube` once; it saves `YT_OAUTH_REFRESH_TOKEN`. Step by step in [performance.md](performance.md#youtube-oauth-setup-once).
- **Meta ads:** `META_ADS_TOKEN` (system-user token with `ads_read`) and `META_AD_ACCOUNT_ID`.
- **TikTok ads:** `TIKTOK_ADS_TOKEN` (TikTok for Business developer app with Reporting) and `TIKTOK_ADVERTISER_ID`.
- **No keys at all:** `python -m viral_scout perf import <profile> export.csv --source meta|tiktok|youtube|generic`.

### The easy way: the Setup page
On the local dashboard (`cd web && npm run dev`), open **/setup**. Every key is listed with what it unlocks, its cost, how to get it and its docs link, and you can save and test each one. The CLI equivalent is `python -m viral_scout keys`, `keys test` and `keys set NAME -` (the value is read from stdin).

### Telegram alerts (free)
1. Create a bot with @BotFather to get the token.
2. Send the bot any message.
3. Open `https://api.telegram.org/bot<token>/getUpdates` and copy `message.chat.id`.
4. Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` to `.env`, and an `alerts:` block to the profile.

To reuse a bot another app already has, point the profile at that app's env file instead of copying the secret:
```yaml
alerts:
  env_file: D:/repo/my-site/.env.local
  token_env: TELEGRAM_BOT_TOKEN
  chat_env: TELEGRAM_CHAT_ID
```

### Your own cookies (only if needed)
`VIRAL_SCOUT_COOKIES=path/to/cookies.txt` passes **your own** Netscape cookies file to yt-dlp, for when a site starts asking for a login on public posts. viral-scout never reads your browser's cookies by itself.

## Local transcription (optional, free)
`pip install faster-whisper`, then add `transcribe: {whisper: true, model: base}` to the profile. Posts without captions (Instagram reels, TikTok, uncaptioned Shorts) are transcribed on the CPU: about 5 s per minute of audio with `base`. The model downloads once (~150 MB). Audio is decoded with the system `ffmpeg`, which must be on PATH, and the file is deleted straight after.

## MCP server (optional)
`pip install mcp`, then register it once in Claude Code:
```
claude mcp add viral-scout -s user -- python <repo>/scripts/mcp_server.py
```
The launcher works from any folder. Registered at user scope (`-s user`), it is available in **every Claude Code session in every repo** on this PC. That is how other repos and agents read the results. It gives Claude (or any MCP client) these tools:
- `list_profiles`, `get_results`, `get_post`, `get_ideas`, `search`, `usage`: read the latest runs
- `ads_results`: the ads scout results
- `save_post`, `dismiss_posts`, `track_links`, `set_swipe_status`: the swipe file
- `perf_run` (then `get_job`), `perf_results`, `perf_diagnose`: your own videos and ads (free official APIs)
- `create_project`: a new profile (free; `start=True` is a paid run)
- **Paid, off by default:** `start_run`, `ads_run` (then `get_job`) and `local_competitors`. They spend Apify or Google Places credit, so for MCP clients they return the latest results and the CLI command instead. To allow them, set `VIRAL_SCOUT_MCP_PAID=1` in `.env` (or `claude mcp add ... -e VIRAL_SCOUT_MCP_PAID=1`) and restart the server, which restarts with the Claude Code session. Paid runs stay available from the CLI and the scheduled task.

Other ways to get the results:
- **Obsidian:** the reports are Markdown in each profile's `output_dir` (for example `projects/northForge/05 Marketing/viral/` in the vault). Any agent with the Obsidian MCP or file access can read them.
- **JSON:** `data/<profile>-latest.json`, `data/<profile>-ads-latest.json` and the dashboard copies in `web/data/` (`python -m viral_scout export`).
- **Dashboard:** locally at http://localhost:3210, or published read-only on Vercel behind a password for people without access to this PC. See [dashboard](dashboard.md).

## Scheduling

### Windows (Task Scheduler)
One command for all your profiles, staggered (YouTube rate-limits bursts), with the AI analysis and a final publish. It registers **weekly** tasks, Monday by default. One Monday snapshot (trending posts, competitor ads, ideas note) gives a week of content, and daily runs would bill Apify every day:
```powershell
scripts/schedule.ps1 -Profiles englishSchool,northForge,nfSolarPanels -Start 07:00 -GapMinutes 30 -Analyze -Publish
scripts/schedule.ps1 -Profiles northForge -Day Daily     # daily instead (-Day Monday ... Sunday | Daily)
scripts/schedule.ps1 -Remove     # remove them all
Disable-ScheduledTask -TaskName "viral-scout northForge"  # pause one (Enable-ScheduledTask to resume)
```
Keep `-Day` on the ads day of `run-daily.ps1` (`-AdsDay`, Monday), so each weekly run includes the ads snapshot.
Or by hand:
`scripts/run-daily.ps1 -Profile <name> [-Analyze]` writes logs to `data/logs/<profile>-<date>.log`. `-Analyze` then runs the `/viral-scout` skill headless through the Claude Code CLI (on your subscription) to write the ideas note.

In PowerShell:
```powershell
$action  = New-ScheduledTaskAction -Execute "pwsh.exe" `
  -Argument '-NoProfile -ExecutionPolicy Bypass -File "D:\repo\viral-scout\scripts\run-daily.ps1" -Profile mybusiness -Analyze'
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 7:30am
$set     = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable
Register-ScheduledTask -TaskName "viral-scout mybusiness" -Action $action -Trigger $trigger -Settings $set
```

A task can only wake a PC that is **asleep**, not one that's shut down. Also allow wake timers in the power plan: Power Options → Sleep → Allow wake timers.

### macOS/Linux (cron)
```
30 7 * * * cd ~/viral-scout && python -m viral_scout run mybusiness --quiet >> data/logs/cron.log 2>&1
```

## Claude Code skill

The skill lives in `.claude/skills/viral-scout/` in this repo. To use it from any project, link it into your global skills:
- Windows: `New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\viral-scout" -Target "<repo>\.claude\skills\viral-scout"`
- macOS/Linux: `ln -s <repo>/.claude/skills/viral-scout ~/.claude/skills/viral-scout`

Then run `/viral-scout <profile>`.
