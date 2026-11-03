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
The launcher works from any folder. It gives Claude (or any MCP client) these tools:
- `list_profiles`
- `start_run`, then `get_job` (runs take minutes, so the client starts one and polls)
- `get_results`, `get_post`, `get_ideas`, `usage`
- `save_post`, `dismiss_posts`, `track_links`, `set_swipe_status`

## Scheduling

### Windows (Task Scheduler)
One command for all your profiles, staggered (YouTube rate-limits bursts), with the AI analysis and a final publish:
```powershell
scripts/schedule.ps1 -Profiles englishSchool,northForge,nfSolarPanels -Start 07:00 -GapMinutes 30 -Analyze -Publish
scripts/schedule.ps1 -Remove     # remove them all
```
Or by hand:
`scripts/run-daily.ps1 -Profile <name> [-Analyze]` writes logs to `data/logs/<profile>-<date>.log`. `-Analyze` then runs the `/viral-scout` skill headless through the Claude Code CLI (on your subscription) to write the ideas note.

In PowerShell:
```powershell
$action  = New-ScheduledTaskAction -Execute "pwsh.exe" `
  -Argument '-NoProfile -ExecutionPolicy Bypass -File "D:\repo\viral-scout\scripts\run-daily.ps1" -Profile mybusiness -Analyze'
$trigger = New-ScheduledTaskTrigger -Daily -At 7:30am
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
