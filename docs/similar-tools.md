# Similar tools: how they work and what we took

Research from November 2026, based on public READMEs, documentation and product pages. Nothing behind a login was checked. Prices and features change, so check the linked pages before relying on them.

## The common pattern

Almost every tool in this space does the same three things:

1. **Find outliers.** It compares a video's views with what that creator usually gets. The baseline is the creator's median (the sturdier choice) or their mean, and sometimes it's matched by age.
2. **Pull the hook and transcript.** The hook is the first ~3 seconds, and it's the part people copy.
3. **Turn hits into work.** An LLM breaks down why the video worked and writes adapted scripts, and the hits go into saved collections ("swipe files") and alerts.

## Open source

### viral-shorts MCP ([Xeron2000/shorts](https://github.com/Xeron2000/shorts))
- **Data:** YouTube Data API v3 only. `search.list` costs 100 quota units; `videos.list` and `channels.list` cost 1 each.
- **Scoring:**
  - VPH = views ÷ hours since publish. 1K VPH means potential, 5K high, 10K "super viral".
  - Engagement = (likes + comments) ÷ views.
  - Viral score = VPH × a time weight × (1 + an engagement boost), with newer videos weighted higher.
- **Output:** a Markdown table from an MCP client, on demand. No scheduling.

### viral_short_research_tool ([wisnuhid7](https://github.com/wisnuhid7/viral_short_research_tool))
- **Data:** YouTube Data API v3; it deliberately avoids scrapers.
- **Scoring:** velocity (views/hour) counts 45%, reach (views ÷ subscribers) 30%, engagement 25%. Videos under 3 hours old get a confidence penalty.
- **Extracts:** GPT-4o-mini splits each video into hook (the first 3 s), body and CTA, plus presentation style. The result is cached per video and per prompt version.
- **Output:** suggested keywords taken from the tags and title words of top videos; saved collections with notes; CSV and Markdown export; a quota meter.

### ViralMint ([openclaw-easy/ViralMint](https://github.com/openclaw-easy/ViralMint), AGPL-3.0)
- **Data:** the YouTube API; TikTok and Douyin through TikHub, a paid API (its cookie fallback breaks the platforms' terms); yt-dlp; Google Trends.
- **Scoring:** outliers at 3–20× the channel's baseline, plus an "AI virality" score. The formulas aren't published.
- **Extracts:** local faster-whisper transcripts. An LLM pulls out the hook, structure, tone, retention risks and suggested titles.
- **Output:** alerts via Telegram, Slack or Discord. It also cuts and renders clips, which makes it a full production pipeline.

## Commercial

| Tool | Platforms | How "viral" is measured | Beyond numbers | Price |
|---|---|---|---|---|
| [1of10](https://1of10.com/blog/1of10-review/) | YouTube (+ Shorts) | views ÷ the channel's typical views; shows ~6–100× | Chrome overlay, tracked channels with notifications, bookmarks and folders, AI title/thumbnail/idea generators | $29–69/mo |
| [vidIQ Outliers](https://support.vidiq.com/en/articles/9660010-outliers) | YouTube | views vs the channel's average over a similar timeframe (age-matched); bands <2×, 2–5×, 5–10×, >10× | filters for score, views, subscribers, VPH, length, publish window | subscription |
| [TubeLab API](https://tubelab.net/docs/api/reference/search-outliers) | YouTube | returns both `zScore` and `averageViewsRatio`, with positive and negative outlier flags | semantic search, `type=short`, LLM labels (faceless, quality), a transcript endpoint | credits |
| [Virlo](https://dev.virlo.ai/docs/satellite/video-outlier) | TikTok, YouTube, Instagram | **outlier = views ÷ the creator's median of up to 100 recent videos**; 1.5× above average, 3× viral, 10× mega viral; **weighted = ln(outlier) × ln(median)**; also a percentile and z-score | trending hashtags, sounds and hooks; scheduled niche "research agents"; webhooks; MCP | $0.50 per check |
| [Sandcastles.ai](https://sandcastles.ai) | IG, TikTok, YT Shorts | "top 1%" outliers (formula not disclosed); tracks competitor channels every 6 h (1 h on top tiers) | transcripts, breakdowns of hook, story, format and style, hook templates, script writer, collections, MCP | $49–499/mo |
| [Apify TikTok hook scraper](https://apify.com/church_of_loujess/tiktok-viral-hook-script-scraper) | TikTok | views ÷ followers, outlier at 3× or more; engagement = (likes + comments + shares + saves) ÷ views | parses TikTok's own captions: anything in the first 3.5 s becomes `openingHookText`, then body and CTA; hook archetype; words per minute; sound ID | ~$0.01–0.025 per post |
| [TikTok Creative Center](https://ads.tiktok.com/help/article/how-to-use-trends) | TikTok | trending hashtags, songs, creators and videos by region, industry and period | trendlines and audience data; no public API or export | free (login recommended) |
| Exolyt, Pentos | TikTok | hashtag and sound trends, competitor dashboards (data source not disclosed) | none noted | subscription |

Other sources we checked:
- **Google Trends:** the official API is an alpha that you have to apply for ([announcement](https://developers.google.com/search/blog/2025/07/trends-api)). The community `pytrends` library is reported broken.
- **Instagram Graph API hashtag search:** official, but it needs the Public Content Access feature and is limited to 30 unique hashtags per 7 days ([docs](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-hashtag-search)).

### omivibe.com (checked because it was suggested)
[omivibe.com](https://omivibe.com) is a **B2B lead-generation and cold-email** product, not a video or trend tool:
- It finds leads from Google Maps and a B2B database.
- AI writes a personal email to each lead, sent from your own Gmail or Outlook.
- It writes and posts LinkedIn content automatically.
- It has an MCP server whose tools run as async jobs and check quota before acting.
- Price: $49–349/mo.

The useful ideas it gave us: drafts that come straight out of findings, a confirmation step before anything is published, budget warnings at 80% of a cap, and an MCP server with a start-a-job-then-poll pattern.

## What viral-scout took

| Idea | From | In viral-scout |
|---|---|---|
| Outlier = views ÷ the creator's **median** | Virlo, 1of10, vidIQ | `× usual` column |
| Bands of 1.5× / 3× / 10× | Virlo | ↑ / ⚡ / 🔥 labels |
| Rank by ln(outlier) × ln(baseline) | Virlo | Outliers section order |
| Penalty for very new videos | wisnuhid7 | ⏳ under 6 h; per-day floored at 6 h |
| Hook = the first ~3–4 s of captions | Apify hook scraper, wisnuhid7 | Hooks section, the `hook` field |
| LLM breakdown + adapted scripts, cached | wisnuhid7, ViralMint, Sandcastles | the `/viral-scout` skill (Claude Code, no extra key); transcripts cached in SQLite |
| Swipe file / collections | 1of10, Sandcastles | `save` → Obsidian note + `swipe.base` |
| Tracked channels + notifications | 1of10, Sandcastles, ViralMint | watch list + Telegram alerts |
| Keyword suggestions from hits | wisnuhid7 | suggested hashtags |

What we do that most of them don't:
- **Growth between runs** ("rise/day"). Most tools only see a snapshot.
- **Per-business profiles**, including the business description the AI uses.
- **Free on YouTube**, and **output into Obsidian**.

## Added in round 2 (after this research)

| Feature | From | In viral-scout |
|---|---|---|
| Hook / body / **CTA** split of the transcript, **words per minute** | Apify hook scraper | `cta` (last 5 s), `wpm`; shown in the report, the dashboard and the JSON |
| **Percentile** among the creator's recent posts | Virlo, TubeLab | `creator_pct` ("beats 87% of their posts") |
| **Local Whisper transcripts** for Instagram/TikTok audio | ViralMint | `transcribe.whisper` (faster-whisper, CPU, int8; audio decoded by the system ffmpeg) |
| **On-screen text** of silent hooks | Sandcastles, TubeLab (vision LLM) | thumbnails cached in `data/frames/`; the skill reads them with Claude's vision, so no OCR install is needed |
| **Quota meter and budget warnings** | wisnuhid7 (quota meter), omivibe (80% alerts) | `usage` per run (YouTube API units, Apify results, page requests, Whisper seconds), warnings at 80% of `budget:` caps |
| **MCP server** with start-then-poll jobs | Virlo, Sandcastles, omivibe | `python -m viral_scout.mcp_server` (11 tools) |
| **Web dashboard** with collections and status board | 1of10, Sandcastles | `web/` (Next.js), local with actions, or read-only on Vercel |

## Refresh: newer competitors (November 2026)

**New tools found:**
- **Mysocial Outliers:** creator median plus a **topic median**, top comments, an MCP server.
- **Trendhaus:** TikTok "Post DNA", a hook library, **comment mining**, trend stage.
- **OutlierKit:** 3–5×, 5–10× and 10×+ bands, AI review of the first 15 s.
- **Satura:** an emerging-channel radar and a WebSub channel tracker.
- **Viewstats**, **ShortsMonkey MCP**.
- **youtube-outlier-finder:** finds small channels with Shorts at ≥10× their subscribers.
- **ig-radar-plugin:** a Claude Code plugin with an own-post postmortem.

Full list with links: [references.md](references.md).

## Added in round 3

| Feature | From | In viral-scout |
|---|---|---|
| **Comment mining**: questions and top comments under the hits | Trendhaus, Mysocial | `comments` (YouTube API commentThreads, or yt-dlp public comments); report section "What viewers ask" |
| **Topic-relative score** (× the niche median) | Mysocial | `vs_topic`, from data we already have |
| **Own-post postmortem**: your posts against your own usual | ig-radar-plugin | profile `own: {youtube: [...], urls: [...]}`, a "Your posts" tab |
| **Emerging creators** (small channel with a clear outlier) | Satura, youtube-outlier-finder | 🌱 `emerging` flag (≤50K followers and ≥3×) |
| **Age-matched baseline** (views/day vs the creator's views/day) | vidIQ | `vs_pace`, with the YouTube API key (2–3 units per creator) |
| **Trending hashtags** | TikTok Creative Center, Exolyt, Virlo | Apify trends actor (`APIFY_TRENDS_ACTOR`) and Instagram hashtag `top_media` (Graph API, 30 a week) |
| **Local competitors** | (none; asked for by the user) | `competitors` command: Google Places API (New), plus social links from each business's homepage |
| **Search** across everything collected | TubeLab (semantic), Sandcastles (library) | `search` (BM25 over titles, hooks, CTAs, transcripts), the Search page, the MCP `search` tool |
| **Setup page** for keys, with live tests | the paid tools' settings pages | dashboard `/setup` (local only; stored in `.env`; masked) |
| **New research** from a description | Virlo research agents | dashboard `/new`, `new` command, MCP `create_project` |

## Still not built (ranked)

1. **Semantic (embedding) search.** BM25 covers keyword search. Embeddings would need a local model.
2. **Scene-by-scene breakdown** (several frames per video). We read one thumbnail. Downloading whole videos is limited by platform terms, so this should stay with your own or licensed posts.
3. **YouTube WebSub push** for watched channels. Free, but needs a public callback URL, for example a Vercel route.
4. **Instagram own-post insights** through the Graph API Media Insights (own business account only).
5. **X / Threads coverage.** Low value for short-form video.

## Earlier backlog (now done)



1. **Trending sounds and hashtags.** TikTok Creative Center has no export, so this needs an Apify trends actor (paid). For Instagram, Graph API hashtag search (30 a week).
2. **Age-matched baseline** (vidIQ): compare views per day with the channel's median views per day at a similar age. It needs per-video dates in channel listings, which costs more requests.
3. **Local competitors:** use the official Google Places API to find nearby businesses in the same niche, then look up their public channels as watch-list candidates.
4. **Semantic search** over saved transcripts (TubeLab): an embeddings index of the swipe file.
