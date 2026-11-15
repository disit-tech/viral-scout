# Setup and keys

Install, point it at your Obsidian vault, add the keys you want, then schedule the weekly run. Only the install is required: every key is optional, and a missing one just skips its source.

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

The dashboard: `cd web && npm install && npm run dev` → http://localhost:3210. See [dashboard](dashboard.md).

## Obsidian vault

Set `OBSIDIAN_VAULT` to your vault's root folder (the one that holds `.obsidian/`). Profiles point their reports, ideas notes and swipe file at it with `${OBSIDIAN_VAULT}`, for example `output_dir: ${OBSIDIAN_VAULT}/projects/mybusiness/05 Marketing/viral`. New business on the dashboard lists the vault's `projects/` folders, and the scheduled AI step gets access to the vault through it.

Set it as a **user environment variable**, so the CLI, the dashboard and the scheduled tasks all see it:
```powershell
[Environment]::SetEnvironmentVariable("OBSIDIAN_VAULT", "D:\Obsidian\vault", "User")   # Windows; then restart the terminal and npm run dev
export OBSIDIAN_VAULT=~/Obsidian/vault                                                 # macOS/Linux: add to ~/.zshrc or ~/.bashrc
```
Putting `OBSIDIAN_VAULT=...` in `.env` (or saving it on the **Setup** page) works for the Python CLI only. The dashboard server and `run-daily.ps1` read the real environment. **Test** on the Setup page checks that the folder is a vault.

No vault? Leave it unset and drop `${OBSIDIAN_VAULT}` from the profile: reports go to `reports/<profile>/` in the repo. If a profile still uses `${OBSIDIAN_VAULT}` while it isn't set, the run prints a warning and uses that default, so nothing lands in a folder literally named `${OBSIDIAN_VAULT}`.

For test runs, point `OBSIDIAN_VAULT` at a scratch folder so reports don't land in the real vault.

## Keys (all optional)

Each key unlocks one source. When a key is missing, that source is listed under **Skipped sources** and the rest still runs.

**The easy way:** on the local dashboard, open **/setup**. Every key is listed with what it unlocks, its cost, how to get it and its docs link, and you can save and test each one. The CLI equivalent is `python -m viral_scout keys`, `keys test` and `keys set NAME -` (the value is read from stdin). Keys go into `.env`, which is git-ignored.

### YouTube Data API (free, recommended)
Unlocks **keyword search for Shorts**, with a time window, sorted by views, per language. yt-dlp can't read YouTube's Shorts search results.

1. Go to the Google Cloud console and create a project.
2. In APIs & Services → Library, enable **YouTube Data API v3**.
3. In Credentials, create an **API key**. Restrict it to YouTube Data API v3.
4. Add `YOUTUBE_API_KEY=...` to `.env`.

The free quota is 10,000 units a day, and one keyword costs about 102 units. So about 90 keywords a day, or about 45 if you run twice daily.

### Instagram Graph API (free, needs a business setup)
Unlocks the **watch list for Instagram professional accounts**: recent reels with likes, comments and followers.

What you need:
- an Instagram Business or Creator account linked to a Facebook Page,
- a Meta app with `instagram_basic` and `pages_read_engagement`,
- a long-lived access token.

Add `IG_GRAPH_TOKEN=...` and `IG_GRAPH_USER_ID=...` (your Instagram business account id) to `.env`.

Limits: it only reads **professional** accounts, and it returns likes, not views.

### Apify (paid per result)
Unlocks **TikTok** hashtags, keyword search and profiles, and the paid ads and search demand routes below. Get a token at apify.com → Settings → Integrations, and add `APIFY_TOKEN=...` to `.env`. The default TikTok actor is `clockworks~tiktok-scraper`; change it with `APIFY_TIKTOK_ACTOR`. Check the actor's price per result before you schedule it.

**Spend controls:** `APIFY_MAX_USD_PER_RUN` (default 0.50, 0 = no cap) is sent with every Apify run as its maximum charge. `VIRAL_SCOUT_MCP_PAID=1` lets MCP clients start paid runs (off by default). Both are on the Setup page. See [costs and spend controls](ads-scout.md#costs-and-spend-controls).

### Trending hashtags (optional)
- **TikTok:** pick a trends actor in the Apify store, then set `APIFY_TRENDS_ACTOR=user~actor` (it uses `APIFY_TOKEN`) and pass its input in the profile under `trends.apify_input`.
- **Instagram:** with the Graph API keys, list hashtags under `trends.instagram_hashtags`. Their top reels join the run. Meta allows 30 unique hashtags per 7 days, and the tool counts them.

### Ads scout (optional)
`python -m viral_scout ads <profile>` reads competitor ads. Every source is optional. Details, coverage and costs are in [ads-scout.md](ads-scout.md).
- **Meta Ad Library API (free):** confirm your identity at facebook.com/ID, create a Meta for Developers app, get a user token in the Graph API Explorer (make it long-lived), then set `META_AD_LIBRARY_TOKEN=...`. It returns **ads delivered in the EU** plus political/issue ads. US commercial ads aren't available through the API.
- **TikTok Commercial Content API (free, by application):** apply on TikTok for Developers. After approval, set `TIKTOK_RESEARCH_CLIENT_KEY` and `TIKTOK_RESEARCH_CLIENT_SECRET`. It covers ads shown in the EEA, without ad copy.
- **Apify (paid):** with `APIFY_TOKEN`, set the actor for each route. The input and output mappings are written and tested for these three:
  - `APIFY_ADS_ACTOR=apify~facebook-ads-scraper`: Meta Ad Library, any country including the US ($3.40–5.80 per 1,000 ads, by Apify plan)
  - `APIFY_GOOGLE_ADS_ACTOR=automation-lab~google-ads-scraper`: Google Ads Transparency Center by competitor domain and name ($1.30 per 1,000 ads)
  - `APIFY_TIKTOK_ADS_ACTOR=pulsedata~tiktok-creative-center-top-ads-scraper`: TikTok Creative Center Top Ads for an industry ($2 per 1,000 ads). Set `ads.tiktok_top_input.industries` in each profile, because it has no keyword search.

  Usage counts toward `budget.apify_items_per_month`.

### Search demand (paid, about $0.005 per term)
Google Trends through `APIFY_TOKEN` and Apify's own `apify~google-trends-scraper` (override with `APIFY_GOOGLE_TRENDS_ACTOR`), only for profiles with a `demand:` block. See [search-demand.md](search-demand.md).

### Google Places API (free monthly credit, then paid)
Unlocks **local competitors**: `python -m viral_scout competitors <profile> "gutter cleaning" --near "Norridge, IL"`. Enable "Places API (New)" in Google Cloud, create a key restricted to it, and add `GOOGLE_PLACES_API_KEY=...`. Each run makes one Text Search request plus one plain request to each competitor's own homepage, to find their YouTube, Instagram, TikTok and Facebook links.

### Your own performance (optional, free)
Reads **your own** accounts' private metrics for the [Your performance](performance.md) report. Each pair is optional:
- **Instagram insights:** the `IG_GRAPH_TOKEN` above, with `instagram_manage_insights` (and `instagram_manage_comments` for comment sentiment) added.
- **YouTube Analytics:** a Desktop OAuth client (`YT_OAUTH_CLIENT_ID`, `YT_OAUTH_CLIENT_SECRET`), then `python -m viral_scout perf auth youtube` once; it saves `YT_OAUTH_REFRESH_TOKEN`. Step by step in [performance.md](performance.md#youtube-oauth-setup-once).
- **Meta ads:** `META_ADS_TOKEN` (system-user token with `ads_read`) and `META_AD_ACCOUNT_ID`.
- **TikTok ads:** `TIKTOK_ADS_TOKEN` (TikTok for Business developer app with Reporting) and `TIKTOK_ADVERTISER_ID`.
- **No keys at all:** `python -m viral_scout perf import <profile> export.csv --source meta|tiktok|youtube|generic`.

### Telegram alerts (free)
1. Create a bot with @BotFather to get the token.
2. Send the bot any message.
3. Open `https://api.telegram.org/bot<token>/getUpdates` and copy `message.chat.id`.
4. Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` to `.env`, and an `alerts:` block to the profile ([alerts](profiles.md#alerts)).

To reuse a bot another app already has, point the profile at that app's env file instead of copying the secret:
```yaml
alerts:
  env_file: D:/repo/my-site/.env.local
  token_env: TELEGRAM_BOT_TOKEN
  chat_env: TELEGRAM_CHAT_ID
```

### Your own cookies (only if needed)
`VIRAL_SCOUT_COOKIES=path/to/cookies.txt` passes **your own** Netscape cookies file to yt-dlp, for when a site starts asking for a login on public posts. viral-scout never reads your browser's cookies by itself.

## Scheduling

Runs are **weekly**, Monday by default: one Monday snapshot (trending posts, competitor ads, search demand, ideas note) gives a week of content, and daily runs would bill Apify every day. Each business gets one task, run one after another about 30 minutes apart (YouTube rate-limits bursts), and an optional final task publishes the dashboard.

### Windows (Task Scheduler)
Register them all at once:
```powershell
scripts/schedule.ps1 -Profiles englishSchool,northForge,nfSolarPanels -Start 07:00 -GapMinutes 30 -Analyze -Publish
scripts/schedule.ps1 -Profiles northForge -Day Daily     # daily instead (-Day Monday ... Sunday | Daily)
scripts/schedule.ps1 -Remove                             # remove them all
```
- `-Analyze` runs the `/viral-scout` skill headless after each run (Claude Code CLI, your subscription) to write the ideas note.
- `-Publish` adds a `viral-scout publish` task after the last business: it exports and deploys the read-only dashboard ([publish to Vercel](dashboard.md#publish-to-vercel)).
- Keep `-Day` on the ads day of `run-daily.ps1` (`-AdsDay`, Monday), so each weekly run includes the ads scout and search demand.

Then manage them one by one on the local dashboard's **Schedule** page (`/schedule`): turn on or pause, change day and time, toggle the ideas note, run now, stop, add or remove. It calls `scripts/tasks.ps1` (`list | enable | disable | run | stop | set | add | remove`), which you can also run directly.

Each task runs `scripts/run-daily.ps1 -Profile <name> [-Analyze]`, which you can run by hand too. Logs go to `data/logs/<profile>-<date>.log`, and the live log of any run is on the Activity page.

A task can only wake a PC that is **asleep**, not one that's shut down; if the PC was off, it runs as soon as it's back. Allow wake timers in the power plan: Power Options → Sleep → Allow wake timers.

### macOS/Linux (cron)
```
30 7 * * 1 cd ~/viral-scout && python -m viral_scout run mybusiness --quiet >> data/logs/cron.log 2>&1
35 8 * * 1 cd ~/viral-scout && python -m viral_scout ads mybusiness >> data/logs/cron.log 2>&1
```

## Optional extras

### Local transcription (free)
`pip install faster-whisper`, then add `transcribe: {whisper: true, model: base}` to the profile. Posts without captions (Instagram reels, TikTok, uncaptioned Shorts) are transcribed on the CPU: about 5 s per minute of audio with `base`. The model downloads once (~150 MB). Audio is decoded with the system `ffmpeg`, which must be on PATH, and the file is deleted straight after.

### Claude Code skill
The skill lives in `.claude/skills/viral-scout/` in this repo. To use it from any project, link it into your global skills:
- Windows: `New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\viral-scout" -Target "<repo>\.claude\skills\viral-scout"`
- macOS/Linux: `ln -s <repo>/.claude/skills/viral-scout ~/.claude/skills/viral-scout`

Then run `/viral-scout <profile>`.

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

## Getting the results elsewhere
- **Obsidian:** the reports are Markdown in each profile's `output_dir` (for example `projects/northForge/05 Marketing/viral/` in the vault). Any agent with the Obsidian MCP or file access can read them.
- **JSON:** `data/<profile>-latest.json`, `data/<profile>-ads-latest.json` and the dashboard copies in `web/data/` (`python -m viral_scout export`).
- **MCP:** the server above.
- **Dashboard:** locally at http://localhost:3210, or published read-only on Vercel behind a password for people without access to this PC. See [dashboard](dashboard.md).
