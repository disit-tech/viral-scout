# References

Every external source viral-scout relies on, compares itself with, or cites. URLs were checked in November 2026. "Not re-checked" means the link was carried over from earlier research; "unverified" means the page didn't load for automated requests (typical for .gov sites) and was confirmed through search or secondary copies only.

## Competitors and similar tools

### Open source
| Tool | What it is | Link |
|---|---|---|
| viral-shorts MCP | YouTube Shorts discovery: VPH, engagement and a viral score (YouTube Data API) | https://github.com/Xeron2000/shorts (not re-checked) |
| viral_short_research_tool | YouTube keyword research: velocity, reach and engagement weights, GPT hook/body/CTA breakdown | https://github.com/wisnuhid7/viral_short_research_tool (not re-checked) |
| ViralMint | full pipeline: trends, outliers at 3–20×, Whisper, LLM breakdowns, clip rendering (AGPL) | https://github.com/openclaw-easy/ViralMint (not re-checked) |
| youtube-outlier-finder | finds small *channels* whose Shorts median is ≥10× their subscriber count | https://github.com/slaavass/youtube-outlier-finder |
| ig-radar-plugin | Claude Code plugin for Instagram Reels (Apify): 6-signal score, hook triggers, own-post postmortem | https://github.com/shafeela-bot/ig-radar-plugin |
| free-sort-feed-extension ("Outliers") | Chrome extension that sorts a profile you have open by views ÷ followers | https://github.com/RostyslavDzhohola/free-sort-feed-extension |
| instagram-viral-reels-research-skill | Reels research with frames and Whisper. It uses your logged-in session, which our rules don't allow | https://github.com/JSNGe/instagram-viral-reels-research-skill |
| mutube | checks a video against its previous 9 (work in progress) | https://pypi.org/project/mutube/ |

### Commercial
| Tool | Outlier / trend method | Link |
|---|---|---|
| 1of10 | views ÷ the channel's typical views; Shorts outliers, tracked channels, AI idea tools | https://1of10.com/features/shorts-outliers |
| vidIQ Outliers | views vs the channel average over a similar timeframe; bands <2×, 2–5×, 5–10×, >10× | https://vidiq.com/features/outliers/ · https://support.vidiq.com/en/articles/9660010-outliers |
| TubeLab | `zScore` + `averageViewsRatio`, semantic search, transcripts API | https://tubelab.net/docs/api/reference/search-outliers |
| Virlo | views ÷ the creator's median of up to 100 posts; 1.5×/3×/10× labels; ln(outlier)×ln(median) | https://www.virlo.ai · https://dev.virlo.ai/docs/satellite/video-outlier · https://dev.virlo.ai/docs/mcp |
| Sandcastles | "top 1%" outliers, transcripts, hook/story/format breakdowns, collections | https://sandcastles.ai (not re-checked) |
| Mysocial Outliers | views ÷ the creator's 25-post median; **topic median**; transcripts + **top comments**; MCP | https://mysocial.io/outliers |
| Trendhaus | TikTok "Post DNA" (transcript, on-screen text, pacing, CTA), hook library, **comment mining**, trend stage | https://trendhaus.ai/ · https://github.com/trendhaus-ai/tiktok-mcp |
| OutlierKit | YouTube outliers at 3–5×, 5–10×, 10×+; AI review of the first 15 s | https://outlierkit.com/ |
| Satura Creative Library | channel-baseline labels, emerging-channel radar, WebSub channel tracker | https://saturaai.com/creative-library |
| Viewstats | YouTube outlier colour bands, thumbnail search, alerts | https://www.viewstats.com/ |
| ShortsMonkey MCP | YouTube outliers and daily viral Shorts (method not documented) | https://www.shortsmonkey.com/en/youtube-mcp |
| Apify TikTok hook scraper | views ÷ followers ≥3×; hook (first 3.5 s) / body / CTA from captions; words per minute | https://apify.com/church_of_loujess/tiktok-viral-hook-script-scraper (not re-checked) |
| Apify DataScout YouTube Outlier Finder | views ÷ median of the last ~15 uploads. It uses YouTube's internal API, which our rules don't allow | https://apify.com/datascoutlab/youtube-outlier-finder |
| Foreplay | ad and creative swipe file | https://www.foreplay.co/ |
| omivibe | B2B lead generation and cold email (not a video tool; checked on request) | https://omivibe.com |

## Official APIs used (or available as optional sources)

| API | Used for | Docs |
|---|---|---|
| YouTube Data API v3: search.list | keyword search for Shorts (100 units) | https://developers.google.com/youtube/v3/docs/search/list |
| YouTube Data API v3: videos.list | stats, durations (1 unit) | https://developers.google.com/youtube/v3/docs/videos/list |
| YouTube Data API v3: channels.list | subscribers, uploads playlist (1 unit) | https://developers.google.com/youtube/v3/docs/channels/list |
| YouTube Data API v3: commentThreads.list | comment mining (1 unit) | https://developers.google.com/youtube/v3/docs/commentThreads/list |
| YouTube quota costs | budget meter | https://developers.google.com/youtube/v3/determine_quota_cost |
| YouTube push notifications (WebSub) | possible future channel alerts | https://developers.google.com/youtube/v3/guides/push_notifications |
| Instagram Graph API: Business Discovery | Instagram watch list | https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/business_discovery |
| Instagram Graph API: Hashtag Search | hashtag ids (30 unique per 7 days) | https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-hashtag-search |
| Instagram Graph API: hashtag top_media | top posts for a hashtag | https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-hashtag/top-media |
| Instagram Graph API: Media Insights | own reels' insights ([Your performance](performance.md)) | https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/insights |
| Google Places API (New): Text Search | local competitors | https://developers.google.com/maps/documentation/places/web-service/text-search |
| Places API billing | cost of local competitor runs | https://developers.google.com/maps/documentation/places/web-service/usage-and-billing |
| Apify: run actor sync, get dataset items | TikTok and trends through actors | https://docs.apify.com/api/v2/act-run-sync-get-dataset-items-post |
| Apify TikTok scraper (default actor) | TikTok discovery and watch list | https://apify.com/clockworks/tiktok-scraper |
| TikTok Creative Center | trend reference (no public API or export) | https://ads.tiktok.com/help/article/how-to-use-trends · https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en |
| Telegram Bot API | alerts (`sendMessage`, `getMe`, `getUpdates`) | https://core.telegram.org/bots/api#sendmessage |
| Google Trends API (alpha, by application) | not used | https://developers.google.com/search/blog/2025/07/trends-api |

## Own performance APIs

Used by [Your performance](performance.md) on your own accounts only. Checked November 2026 (pages loaded and, where noted, read).

| API | Used for | Docs |
|---|---|---|
| Instagram Graph API: IG Media Insights | reels metrics (views, reach, saved, shares, ig_reels_avg_watch_time, ig_reels_video_view_total_time, reels_skip_rate, reposts, total_interactions); `impressions` deprecated for media after 2 Jul 2024; follows/profile_visits feed/story only (read, v26.0) | https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/insights |
| Instagram Graph API: IG User media | listing your own media | https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media |
| YouTube Analytics API: metrics | views, engagedViews, estimatedMinutesWatched, averageViewDuration, averageViewPercentage, shares, subscribersGained, audienceWatchRatio, relativeRetentionPerformance (read) | https://developers.google.com/youtube/analytics/metrics |
| YouTube Analytics API: channel reports | audience retention report: `elapsedVideoTimeRatio`, one video per request (read) | https://developers.google.com/youtube/analytics/channel_reports |
| YouTube Analytics API: reports.query | the report endpoint | https://developers.google.com/youtube/analytics/reference/reports/query |
| Google OAuth for installed apps | loopback redirect, PKCE, out-of-band flow removed (read) | https://developers.google.com/identity/protocols/oauth2/native-app · https://developers.google.com/youtube/reporting/guides/authorization/installed-apps |
| Meta Marketing API: Insights | `/{object}/insights`, v26.0 (read) | https://developers.facebook.com/documentation/ads-commerce/marketing-api/insights |
| Meta Marketing API: Ad insights reference | field list (actions, action_values, video_p25…p100_watched_actions, video_thruplay_watched_actions, purchase_roas). The page renders with JavaScript, so the field names come from Meta's reference as known and partner mappings, not read in full (partly unverified) | https://developers.facebook.com/documentation/ads-commerce/marketing-api/reference/adgroup/insights |
| TikTok API for Business | integrated report `/open_api/v1.3/report/integrated/get/` and metric names (portal renders with JavaScript; partly unverified) | https://business-api.tiktok.com/portal/docs · https://business-api.tiktok.com/portal/docs?id=1751443956638721 |
| TikTok Ads help: video play metrics | definitions of video views, 2-s/6-s views, 25–100% views, average play time (read) | https://ads.tiktok.com/help/article/video-play |
| YouTube Shorts view counting (31 Mar 2025) | "views" counts every start/replay; engaged views keep the old count | YouTube Help / Creator Insider announcement (not re-checked) |

## Libraries and frameworks

| | Link |
|---|---|
| yt-dlp (public pages, captions, comments, audio) | https://github.com/yt-dlp/yt-dlp |
| faster-whisper (local transcripts) | https://github.com/SYSTRAN/faster-whisper |
| Model Context Protocol Python SDK | https://github.com/modelcontextprotocol/python-sdk |
| MCP specification | https://modelcontextprotocol.io/specification |
| Next.js 16 (dashboard), `proxy.ts` | https://nextjs.org/blog/next-16 · https://nextjs.org/docs/app/api-reference/file-conventions/proxy |
| Tailwind CSS v4 | https://tailwindcss.com/blog/tailwindcss-v4 · https://tailwindcss.com/docs |
| marked (Markdown → HTML for ideas notes) | https://marked.js.org/ · https://github.com/markedjs/marked |
| cobalt (media downloader, used for the screenshots/research) | https://github.com/imputnet/cobalt |
| BM25 ranking (search) | https://en.wikipedia.org/wiki/Okapi_BM25 |

## Platform terms and policies

| | Link |
|---|---|
| YouTube API Services Terms of Service | https://developers.google.com/youtube/terms/api-services-terms-of-service |
| YouTube API Developer Policies | https://developers.google.com/youtube/terms/developer-policies |
| Meta Platform Terms | https://developers.facebook.com/terms/ |
| TikTok Terms of Service (US / rest of world) | https://www.tiktok.com/legal/page/us/terms-of-service/en · https://www.tiktok.com/legal/page/row/terms-of-service/en |
| Vercel Hobby plan (personal, non-commercial) | https://vercel.com/docs/plans/hobby |
| Vercel fair use | https://vercel.com/docs/limits/fair-use-guidelines |

Our rule, from these terms: public pages via yt-dlp, official APIs, or paid providers only. No private APIs, no spoofed headers, no logging in with someone's account behind their back, and other creators' footage is never reused.

## Originality and duplicate detection

The full write-up, with every source, is [originality-and-duplicate-detection.md](originality-and-duplicate-detection.md). Key sources:
- Meta Rights Manager and Audible Magic: https://transparency.meta.com/reports/intellectual-property/protecting-intellectual-property-rights/
- Instagram on reposts, watermarks and aggregators: https://creators.instagram.com/blog/tips-for-improving-your-reach
- Facebook unoriginal content (2025): https://creators.facebook.com/blog/combating-unoriginal-content
- YouTube Content ID: https://support.google.com/youtube/answer/2797370 · reused content policy: https://support.google.com/youtube/answer/1311392
- TikTok integrity and authenticity: https://www.tiktok.com/community-guidelines/en/integrity-authenticity · copyright policy: https://www.tiktok.com/legal/page/global/copyright-policy/en
- PDQ / TMK+PDQF: https://github.com/facebook/ThreatExchange/tree/main/pdq · https://about.fb.com/news/2019/08/open-source-photo-video-matching/
- Shazam fingerprinting (Wang 2003): https://www.princeton.edu/~cuff/ele201/files/Wang03-shazam.pdf
- Meta copy-detection challenges: https://arxiv.org/abs/2106.09672 · https://arxiv.org/abs/2306.09489
- Remix / Duet / Stitch / Shorts remix: https://help.instagram.com/139004934231412 · https://support.tiktok.com/en/using-tiktok/creating-videos/duets · https://support.google.com/youtube/answer/10623810
- US Copyright Office Fair Use Index: https://www.copyright.gov/fair-use/

## Scoring references

| Idea | Source |
|---|---|
| Views ÷ the creator's **median** (not mean); 1.5×/3×/10× labels; ln(outlier) × ln(median) | Virlo: https://dev.virlo.ai/docs/satellite/video-outlier |
| Age-matched baseline ("similar timeframe") | vidIQ: https://support.vidiq.com/en/articles/9660010-outliers |
| z-score and average-views ratio | TubeLab: https://tubelab.net/docs/api/reference/search-outliers |
| Topic-relative score (views ÷ topic median) | Mysocial: https://mysocial.io/outliers |
| Hook = first ~3.5 s of captions; CTA; words per minute | Apify hook scraper (above) |
| VPH thresholds, a confidence penalty for very new videos | viral-shorts MCP, viral_short_research_tool (above) |

## Facts cited in idea notes

| Fact | Source |
|---|---|
| Food in a power outage: fridge about 4 h closed; full freezer about 48 h, half-full about 24 h | FoodSafety.gov chart: https://www.foodsafety.gov/food-safety-charts/food-safety-during-power-outage (unverified, 403 to bots) · USDA FSIS: https://www.fsis.usda.gov/food-safety/safe-food-handling-and-preparation/emergencies/food-safety-during-power-outage (unverified) |
| Generators: never indoors or in a garage; keep them 20+ ft from doors, windows and vents (carbon monoxide) | CDC: https://www.cdc.gov/natural-disasters/psa-toolkit/prevent-carbon-monoxide-poisoning.html · https://www.cdc.gov/carbon-monoxide/factsheets/generator-safety-fact-sheet.html |

Always show the source on screen when a video states one of these numbers, and check that the page still says it before posting.
