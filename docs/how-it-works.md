# How it works

## Pipeline

One `run` goes through these steps (`viral_scout/run.py`):

```
1. Discover  ─┬─ YouTube Data API keyword search (Shorts, window, sorted by views, language)   [key]
              ├─ YouTube hashtag feeds via yt-dlp (/hashtag/<tag>/shorts)                       [free]
              └─ TikTok hashtags + search via Apify                                             [paid]
2. Watch     ─┬─ YouTube channels: latest 30 Shorts/videos + channel median                   [free]
              ├─ Instagram professional accounts via Graph API Business Discovery              [token]
              └─ TikTok profiles via Apify                                                      [paid]
3. Seeds     ── tracked URLs (any platform yt-dlp supports), re-measured every run              [free]
4. Re-check  ── recent posts from earlier runs, re-measured for growth                          [free]
5. Filter    ── dismissed, exclude regex, topic check (must_match), min views
6. Enrich    ── top YouTube finds: likes, comments, date, subscribers, caption link; re-filter
              ── creator baseline (median of the channel's recent posts) for the top 15
7. Score     ── per day, × usual, label, weighted rank, rise/day (vs the previous snapshot)
8. Hooks     ── transcripts + hooks for the posts that make the report (cached)
9. Save      ── SQLite: items, snapshots, transcripts, flags
10. Report   ── Markdown into the vault + JSON; Telegram alerts
```

Optional sources never fail a run. If a key is missing, the source is listed under **Skipped sources** in the report.

## Scoring

| Field | Formula | Notes |
|---|---|---|
| `reach` | views, or likes where views are hidden (Instagram Graph API) | likes are shown with ♥ |
| `per_day` | reach ÷ max(age in days, 0.25) | the 6-hour floor stops a 1-hour-old video from being extrapolated ×24 |
| `vs_channel` | reach ÷ the creator's median | the median over the latest ~30 posts. A median ignores the creator's own one-off hits, which a mean wouldn't |
| `vs_followers` | reach ÷ followers | used when there's no median |
| `outlier` (× usual) | `vs_channel`, else `vs_followers` | |
| `label` | ↑ ≥1.5×, ⚡ ≥3×, 🔥 ≥10× | |
| `weighted` | ln(outlier) × ln(baseline) | ranks the Outliers section. 20× on a 50-view channel ≈ 3.0 × 3.9 = 11.7; 5× on a 100K channel ≈ 1.6 × 11.5 = 18.5 |
| `rise_per_day` | (reach now − reach at the previous snapshot) ÷ days between them | ignored if the snapshots are under ~1 h apart; needs two runs |
| `engagement` | (likes + comments) ÷ views | |
| `early` ⏳ | age < 6 h | |
| `creator_pct` | share of the creator's recent posts with fewer views (0–100) | Virlo/TubeLab-style percentile |
| `vs_pace` | views/day ÷ the creator's median views/day over their last ~30 uploads | age-matched (vidIQ-style); needs the YouTube API key |
| `vs_topic` | views/day ÷ the median views/day of this run's discovered posts | how it does against the niche (Mysocial-style) |
| `emerging` 🌱 | followers ≤ 50K and × usual ≥ 3 | small creators to watch early |
| `wpm` | words in the transcript ÷ speaking time × 60 | pace; fast talkers vs slow explainers |

Report sections:
- **Rising now:** sorted by `rise_per_day`.
- **Fastest new posts:** discovered posts (not watched, not tracked) sorted by `per_day`.
- **Outliers:** `outlier` ≥ 3, sorted by `weighted`.
- **Tracked links:** your seeds.
- **Hooks:** the strongest posts from those sections.

## Hooks and transcripts (`viral_scout/transcripts.py`)

- **YouTube:** yt-dlp lists the public caption tracks. We pick the track in the **video's own language**: first `<lang>-orig`, then `<lang>`, then en/ru/uk/es, then any `-orig`. AI-dubbed videos list many `-orig` tracks, so the language has to come first. The `json3` track is downloaded. Text that starts before **4.0 s** becomes the hook (at most 25 words), and the whole text is the transcript (at most 4,000 characters).
- **Hook / CTA:** text starting before 4 s is the hook; text in the last 5 s is the CTA (`cta`).
- **Local Whisper** (optional): posts still without a transcript (Instagram/TikTok first) are transcribed from their public audio with faster-whisper, up to `transcribe.max_per_run` per run.
- **Frames:** thumbnails of the report's posts are cached in `data/frames/<profile>/`, so the skill can read on-screen text with Claude's vision.
- **Instagram/TikTok:** there are no public captions, so the first line of the post caption (8+ words, hashtags removed) stands in for the hook.
- **Throttling:** captions are fetched only for posts that make the report (`report.transcripts`, default 40), 2 seconds apart. The first HTTP 429 stops caption fetching for the rest of the run, and those posts are retried next run. Only a real transcript is cached as final.

## Filters

- **`exclude`** (regex) is matched against title + channel. Use it for exams, kids' content, live streams, news.
- **`must_match`** (regex) is matched against the title **with hashtags removed**, plus the channel name. Hashtag feeds are full of unrelated clips tagged `#english`, and removing the hashtags is what stops them.
- **Untitled posts:** hashtag feeds return no titles. Those posts skip the topic check until enrichment fills in the title, then all filters run again.
- **Watched creators** skip the topic and minimum-views checks. Tracked links skip all filters.

## Data (`data/<profile>.sqlite`)

| Table | What |
|---|---|
| `items` | one row per post: key (`platform:id`), url, title, channel, followers, published, found_by, first/last seen, `tracked`, `dismissed`, `saved`, `alerted`, `hook`, `transcript`, `description` |
| `snapshots` | (key, timestamp) → views, likes, comments. Each run adds one snapshot per post seen |
| `runs` | timestamp, profile, a summary |
| `perf_records` | own performance: the latest normalized record per own video/ad (API pulls and CSV imports) |
| `perf_snapshots` | own performance: (key, timestamp) → a few KPIs and counts, written when they change, for trends and fatigue |

`data/<profile>-latest.json` holds every post from the last run with all scores, the hook and the transcript. The skill reads it.

## Code map

| File | Role |
|---|---|
| `__main__.py` | the CLI: run, add, save, dismiss, profiles |
| `config.py` | profile loading, defaults, `${ENV}` expansion, `.env` |
| `run.py` | the pipeline above, plus save, dismiss and add |
| `models.py` | `Item` and every score |
| `db.py` | SQLite store |
| `report.py` | Markdown + JSON, sections, suggested hashtags |
| `transcripts.py` | captions → hook + transcript |
| `swipe.py` | swipe notes + `swipe.base` |
| `alerts.py` | Telegram |
| `whisper.py` | local transcription (optional) |
| `frames.py` | thumbnail / first-frame cache |
| `usage.py` | per-run counters and budget warnings |
| `export.py` | data for the dashboard |
| `mcp_server.py` | MCP tools |
| `search.py` | BM25 search over everything collected |
| `keys.py` | key registry, live tests, `.env` writes |
| `newproject.py` | profile generation from a description and keywords |
| `comments.py` | comment mining |
| `trends.py` | trending hashtags (Apify) and Instagram hashtag top posts (Graph API) |
| `places.py` | local competitors (Google Places API) and their social links |
| `ads/` | the ads scout: Meta/TikTok APIs and Apify routes, hook/offer extraction, ad_score, report ([ads-scout.md](ads-scout.md)) |
| `ytdlp.py` | loads yt-dlp (the clone in `$VIRAL_SCOUT_YTDLP`, or the pip package) |
| `sources/youtube.py` | hashtag feeds, channel lists, enrichment, caption link (yt-dlp) |
| `sources/youtube_api.py` | YouTube Data API search |
| `sources/instagram.py` | Graph API Business Discovery |
| `sources/tiktok.py` | Apify |
| `sources/links.py` | any single post URL |
| `perf/` | own performance: `kpis.py` (formulas), `diagnose.py`, `instagram.py`, `youtube.py` (+ OAuth), `meta_ads.py`, `tiktok_ads.py`, `csvimport.py`, `store.py`, `run.py`, `report.py`, `cli.py`. See [performance.md](performance.md) |

**Adding a platform:** write a module in `sources/` that returns `Item`s, wire it into `run.scout`, and add a line to `skipped` when its key is missing.

## Access rules

viral-scout only uses:
- public pages through yt-dlp,
- official APIs (YouTube Data API, Instagram Graph API, Telegram Bot API),
- paid providers that handle the platform themselves (Apify).

It never calls Instagram's or TikTok's private web APIs, never spoofs app headers, and never logs in with someone's account behind their back. `VIRAL_SCOUT_COOKIES` exists only for the user's own cookies file, set by the user.

## Known limits

- yt-dlp can't read YouTube's **Shorts search results**, so keyword search for Shorts needs the API key. Without it, only hashtag feeds and channels run.
- **Instagram profiles** can only be read through the Graph API, and only for professional accounts, with likes but no views. A single reel URL works without it.
- **TikTok** lists (profiles, hashtags, search) fail in yt-dlp, so they need Apify. A single TikTok URL works as a seed.
- **Rise/day** needs at least two runs, ideally a day apart.
- **YouTube rate-limits caption downloads.** Large runs fill in hooks over several runs.
