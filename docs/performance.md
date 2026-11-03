# Your performance (own videos and ads)

viral-scout's main pipeline reads **other creators' public numbers**: views, likes, comments. The numbers that explain *why* a video works or an ad pays (hook rate, watch time, retention curve, completion, shares and saves, CTR, CVR, CPA, CAC, ROAS) are private to the account that posted it. They can only be measured for **your own** videos and ads.

The own-performance module brings them in, legitimately: official APIs on your own accounts, or the exports you download yourself. Then it computes one KPI framework (sections A–E), compares every video with **your own medians**, names the biggest problem per video, runs the 5 tests and watches for creative fatigue.

```
python -m viral_scout perf <profile>                     # pull every configured source → report
python -m viral_scout perf <profile> --no-pull           # rebuild from stored data (no API calls)
python -m viral_scout perf import <profile> <file.csv> --source meta|tiktok|youtube|generic
python -m viral_scout perf auth youtube                  # one-time OAuth for YouTube Analytics
```

Output:
- `<output_dir>/<date>-performance.md`: the report (sources, unit economics, KPIs A–E, priorities, per-video tables, the 5 tests, retention curves, diagnostics, fatigue, caveats, skipped sources).
- `data/<profile>-perf-latest.json`: everything, for the dashboard, the MCP tools and other agents.
- `data/<profile>.sqlite`, tables `perf_records` (latest record per video/ad) and `perf_snapshots` (one row per video per run when its numbers change), for trends and fatigue.
- Dashboard: `/p/<profile>/performance` (**Your performance**).
- MCP: `perf_run` (start a job, poll `get_job`), `perf_results`, `perf_diagnose`.

Every source is optional. A missing key puts that source under **Skipped sources**; the run never fails over it.

## Sources

| Source | Keys | What it returns | Limits |
|---|---|---|---|
| Instagram Graph API, own media insights | `IG_GRAPH_TOKEN`, `IG_GRAPH_USER_ID` (the same as the watch list) | your reels: views, reach, likes, comments, shares, saved, total_interactions, ig_reels_avg_watch_time, ig_reels_video_view_total_time, reels_skip_rate, reposts; your comments' text for sentiment | token needs `instagram_manage_insights` (+ `instagram_manage_comments` for sentiment). No impressions for reels created after 2 Jul 2024; follows/profile_visits are feed/story only; no video length through the API |
| YouTube Analytics API | `YT_OAUTH_CLIENT_ID`, `YT_OAUTH_CLIENT_SECRET`, `YT_OAUTH_REFRESH_TOKEN` | per video: views, engagedViews, estimatedMinutesWatched, averageViewDuration, averageViewPercentage, likes, comments, shares, subscribersGained; retention curve (audienceWatchRatio + relativeRetentionPerformance by elapsedVideoTimeRatio) for the top 10; titles and lengths (Data API with the same token); comments for sentiment | no impressions / impressions CTR per video in the API: import a YouTube Studio CSV for those. Retention is one request per video. Data lags 1–2 days |
| Meta Marketing API, ad insights | `META_ADS_TOKEN`, `META_AD_ACCOUNT_ID` | per ad: impressions, reach, frequency, spend, cpm, cpc, ctr, clicks, inline link clicks and CTR, actions (3-second plays = `video_view`, link clicks, landing page views, leads, purchases), action_values (purchase value), cost_per_action_type, purchase_roas, video_play_actions, video_p25/50/75/100_watched_actions, ThruPlays, average watch time, 2-second continuous plays; creative id and thumbnail; daily rows for fatigue | token needs `ads_read`. If a field is rejected (renamed in a new API version) the pull retries without the video fields and says so |
| TikTok API for Business, integrated report | `TIKTOK_ADS_TOKEN`, `TIKTOK_ADVERTISER_ID` | per ad: spend, impressions, reach, frequency, clicks, ctr, cpc, cpm, conversion, cost_per_conversion, video_play_actions, video_watched_2s/6s, video_views_p25…p100, average_video_play, likes, comments, shares, follows, profile_visits, complete_payment, complete_payment_roas; daily rows | report period capped at 30 days. Rejected metrics → retried with the core set |
| CSV import | none | your Meta Ads Manager, TikTok Ads Manager or YouTube Studio export, or a generic file | see the mapping below |
| Business inputs | none | `economics:` in the profile: CAC, contribution margin, MER, max affordable CPA | |

**Out of scope:** Shopify, Stripe or your landing-page analytics. Revenue comes from what the ad platforms attribute (or CSV columns you add). Real MER needs your total revenue: put it in `economics.total_revenue`.

Usage is counted per run (`ig_insights_requests`, `youtube_analytics_requests`, `meta_ads_requests`, `tiktok_ads_requests`, `youtube_api_units`) and stored in the JSON.

### YouTube OAuth setup (once)

1. Google Cloud console → pick or create a project → **APIs & Services → Library**: enable **YouTube Analytics API** and **YouTube Data API v3**.
2. **OAuth consent screen**: External, add yourself as a test user (or publish it). Scopes are requested by the tool: `yt-analytics.readonly` and `youtube.readonly`.
3. **Credentials → Create credentials → OAuth client ID → Desktop app**. Copy the client ID and secret.
4. Save them (the secret goes through stdin):
   ```
   python -m viral_scout keys set YT_OAUTH_CLIENT_ID <client id>
   python -m viral_scout keys set YT_OAUTH_CLIENT_SECRET -
   ```
5. `python -m viral_scout perf auth youtube`. It prints Google's consent URL and opens it; sign in with the account that owns the channel. Google redirects to `http://127.0.0.1:<port>` where the tool is listening, and the refresh token is written to `.env` as `YT_OAUTH_REFRESH_TOKEN`. Use `--no-browser` to open the URL yourself, `--port N` for a fixed port.
6. Check it: `python -m viral_scout keys test YT_OAUTH_REFRESH_TOKEN`.

This is Google's installed-app flow with a loopback redirect and PKCE. The old copy-paste ("out-of-band") flow is no longer supported by Google. With the consent screen in "Testing", Google expires refresh tokens after 7 days; publish the app (it only reads your own data) to keep the token.

### Meta and TikTok tokens

- **Meta:** Meta for Developers → create an app (Business type) with the Marketing API product → Business Settings → System users → add a system user, assign your ad account with "View performance", generate a token with `ads_read`. `META_AD_ACCOUNT_ID` is `act_…` or just the number from Ads Manager.
- **TikTok:** TikTok for Business developers → create an app with the Reporting scope → authorize it on your advertiser account → exchange the auth code for a long-term access token. `TIKTOK_ADVERTISER_ID` is in Ads Manager's account info.
- **Instagram insights:** the existing Graph API token, with `instagram_manage_insights` added (and `instagram_manage_comments` for comment sentiment).

All keys appear on the dashboard's **Setup** page with a live test.

## CSV column mappings

Headers are matched case-insensitively, after removing a trailing currency code like `(USD)` or `(EUR)`. Unknown columns are ignored and listed. `Total` rows are skipped. Exports broken down by day (`Day`, `By Day`, `Date`) are summed into one record per ad, and the daily rows feed the fatigue check. The table lives in code at `viral_scout/perf/csvimport.py` (`COLUMNS`).

**Meta Ads Manager** (`--source meta`, kind paid)

| Column | Field |
|---|---|
| Ad ID / Ad name / Campaign name | id / title / campaign |
| Reporting starts / Reporting ends / Day | date_start / date_stop / daily rows |
| Amount spent | spend |
| Impressions / Reach / Frequency | impressions / reach / frequency |
| Clicks (all) / Link clicks / Landing page views | clicks / link_clicks / landing_page_views |
| Results / Leads / Purchases / Website purchases | conversions / leads / purchases |
| Purchases conversion value / Website purchases conversion value | revenue |
| Purchase ROAS (return on ad spend) | revenue = ROAS × spend, when no value column |
| 3-second video plays / 2-second continuous video plays / Video plays | views_3s (also "views") / views_2s / video_starts |
| Video plays at 25% / 50% / 75% / 100% / ThruPlays | p25 / p50 / p75 / p100 / thruplays |
| Video average play time | avg_watch_time (h:mm:ss or seconds) |
| Post reactions / comments / shares / saves | likes / comments / shares / saves |
| Page likes / Instagram follows / Instagram profile visits | follows / follows / profile_visits |

**TikTok Ads Manager** (`--source tiktok`, kind paid)

| Column | Field |
|---|---|
| Ad ID / Ad name / Campaign name / By Day, Date | id / title / campaign / daily rows |
| Cost, Total cost | spend |
| Impressions / Reach / Frequency | impressions / reach / frequency |
| Clicks (destination), Clicks / Clicks (all) | link_clicks / clicks |
| Conversions, Results / Leads, Form submissions | conversions / leads |
| Video views | video_starts (also "views") |
| 2-second / 6-second video views | views_2s / views_6s |
| Video views at 25% / 50% / 75% / 100% | p25 / p50 / p75 / p100 |
| Average play time per video view | avg_watch_time |
| Likes / Comments / Shares / Follows / Profile visits (and the "Paid …" variants) | likes / comments / shares / follows / profile_visits |
| Complete payment / Total complete payment value / Complete payment ROAS | purchases / revenue / revenue = ROAS × spend |

**YouTube Studio** (Advanced mode → Export → Table data, `--source youtube`, kind organic)

| Column | Field |
|---|---|
| Content / Video title / Video publish time / Duration | id / title / published / duration |
| Views / Engaged views | views / engaged_views |
| Watch time (hours) | total_watch_time (× 3600) |
| Average view duration | avg_watch_time |
| Average percentage viewed (%) | avg % viewed as reported (used when the length is missing) |
| Impressions / Impressions click-through rate (%) | impressions / clicks = impressions × CTR |
| Likes / Comments added / Shares / Subscribers gained | likes / comments / shares / follows |
| Stayed to watch (%) | Shorts hook proxy |

**Generic** (`--source generic`): any field name from `viral_scout/perf/schema.py` (`impressions`, `views_3s`, `spend`, `purchases`, `revenue`, `duration`, `kind`, `platform`, …) plus common aliases (`cost`, `plays`, `orders`, `conversion value`, `saved`, `skip rate`). Rows with `spend` are paid unless `kind` says otherwise.

## KPIs

All rates are percentages. Every value in the JSON carries its numerator, denominator and the **denominator actually used** (`denominator`), because some KPIs fall back to a second-best denominator. Account totals are Σ numerators ÷ Σ denominators over the records that have both, so a TikTok ad without 3-second views doesn't dilute the hook rate.

### A. Attention

| KPI | Formula | Denominator | Notes |
|---|---|---|---|
| Impressions | times shown | | |
| Reach | unique accounts | | summed across ads it over-counts people |
| Frequency | impressions ÷ reach | reach | as reported when available |
| Views | platform view count | | definitions differ (below) |
| Hook rate | 3-second views ÷ impressions × 100 | impressions | Instagram: 100 − reels_skip_rate; YouTube Shorts CSV: "Stayed to watch". Both are proxies and labelled as such |
| 2-s view rate | 2-second views ÷ impressions × 100 | impressions | Meta 2-s continuous, TikTok video_watched_2s |
| 6-s view rate | 6-second views ÷ impressions × 100 | impressions | TikTok |
| Video start rate | video starts ÷ impressions × 100 | impressions | autoplay feeds sit near 100% |
| CPM | spend ÷ impressions × 1000 | impressions | |

### B. Retention

| KPI | Formula | Denominator | Notes |
|---|---|---|---|
| Avg watch time | total watch time ÷ plays | plays | as reported when available; TikTok/Instagram include replays |
| Avg % viewed | avg watch time ÷ duration × 100 | video length | falls back to the platform's own % |
| 25/50/75% view rate | n% views ÷ starts × 100 | plays started | starts = video_starts, else views |
| Completion rate | completed (100%) views ÷ starts × 100 | plays started | |
| ThruPlay rate | ThruPlays ÷ impressions × 100 | impressions | Meta |
| Retention curve | % of the starting audience still watching at each point | | YouTube audienceWatchRatio; else built from the quartile counts (+ the 3-s point when the length is known) |
| Rewatch / loop | peak audience watch ratio − 100% | starting audience | only YouTube shows it (curve above 100%) |
| Drop-off points | the largest falls between neighbouring curve points (resampled to every 10%) | | shown in seconds when the length is known |

### C. Engagement

| KPI | Formula | Denominator | Notes |
|---|---|---|---|
| Engagement rate | (likes + comments + shares + saves) ÷ views × 100 | views (reach if no views) | Instagram's total_interactions when reported |
| Like / comment / share / save rate | each ÷ views × 100 | views (reach if no views) | shares and saves are the strongest signals |
| Follower conversion | follows ÷ reach × 100 | reach (views if no reach) | YouTube: subscribersGained |
| Profile visit rate | profile visits ÷ reach × 100 | reach | |
| Comment sentiment | (positive − negative) ÷ (positive + negative) × 100 | comments with a sentiment word | small word lexicon on your own comments; skipped when there are none. A hint, not a measurement |

### D. Traffic

| KPI | Formula | Denominator |
|---|---|---|
| CTR (all) | clicks ÷ impressions × 100 | impressions |
| Link CTR | link clicks ÷ impressions × 100 | impressions |
| CPC (all) / CPC (link) | spend ÷ clicks / spend ÷ link clicks | clicks / link clicks |
| CPV | spend ÷ views | views as the platform defines them (Meta: 3-s plays) |
| Landing page views | page loads after a click (Meta pixel) | |
| LPV rate | landing page views ÷ link clicks × 100 | link clicks |

### E. Conversion and profit

| KPI | Formula | Denominator / source |
|---|---|---|
| Conversions | platform-attributed results | |
| CVR | conversions ÷ eligible visits × 100 | landing page views, else link clicks, else clicks |
| CPA | spend ÷ attributed acquisitions | purchases, else conversions, else leads |
| CPL | spend ÷ leads | |
| CAC | spend ÷ new customers | purchases (each assumed new), or leads × `lead_to_customer_rate` |
| AOV | revenue ÷ orders | |
| ROAS | attributed revenue ÷ spend | revenue, else purchases × `avg_order_value` (marked as an estimate) |
| MER | total revenue ÷ total marketing spend | `economics.total_revenue ÷ total_marketing_spend`; without them a blended ROAS proxy, labelled |
| Contribution margin | revenue × gross margin − spend | needs `gross_margin` |
| LTV:CAC | LTV ÷ CAC | needs `ltv` |

### Max affordable CAC from unit economics

| Limit | Formula | Meaning |
|---|---|---|
| Max CPA, first order | AOV × gross margin | break-even on the first purchase |
| Break-even ROAS | 1 ÷ gross margin | below it every attributed sale loses money (40% margin → 2.5×) |
| Max CAC, lifetime | LTV × gross margin | break-even over the customer's life |
| Target CAC (3:1) | LTV × gross margin ÷ 3 | room for overheads and profit |
| Max CPL | LTV × gross margin × lead-to-customer rate | what a lead is worth at break-even |
| Max CAC, payback | monthly revenue per customer × gross margin × payback months | CAC recovered within your payback window |

Example: AOV 100, margin 40%, LTV 400, 20% of leads buy → max first-order CPA 40, break-even ROAS 2.5×, lifetime CAC limit 160, target CAC 53, max CPL 32.

### Platform definitions differ

| Term | Definition |
|---|---|
| 3-second view (Meta) | the `video_view` action: ≥3 s played (or the whole video if shorter). Our hook rate uses it |
| 2-second continuous view | Meta: 2 continuous seconds with ≥50% on screen. TikTok `video_watched_2s`: ≥2 s within one impression session, replays excluded |
| 6-second view (TikTok) | ≥6 s in one impression session, or a shorter video played in full, or an engagement in the first 6 s |
| ThruPlay (Meta) | played to completion, or ≥15 s for longer videos. Not the same as a 100% view |
| YouTube views vs engaged views | since 31 Mar 2025 Shorts "views" count every start and replay; `engagedViews` keeps the older, stricter count. Long-form views need real watching |
| Instagram views | every start, replays included. No impressions for new reels, so reach is the denominator and the hook proxy is 100 − skip rate |
| Average play time | TikTok and Instagram include replays (can exceed the length); YouTube's averageViewDuration excludes looping clips since Dec 2021 |
| Conversions | attributed by each platform with its own window (Meta default 7-day click / 1-day view); two platforms can claim one sale |

Never compare hook rates across platforms. Compare a TikTok ad with TikTok ads, a Meta ad with Meta ads. The tool does this: medians are per platform when there are at least 3 videos on it, else per kind.

## Diagnostics

Benchmarks are **your account's medians**: same kind (organic or paid), same platform when it has 3+ records, and for retention KPIs the same length band (<15 s, 15–30 s, 30–60 s, 60 s+) when the band has 3+ videos. "Low" = under 75% of the benchmark; for costs, "high" = over 133%. A median over fewer than 3 videos isn't used.

| Symptom | Rule | Investigate |
|---|---|---|
| Low views / reach | views (or reach) < 75% of the median | organic: topic relevance, cover and first frame, posting time, reach beyond followers. Paid: budget and audience size, CPM, learning phase, rejections |
| Low hook rate | hook (or 2-s) rate low | first 1–3 s: motion, face or payoff first; on-screen promise; who it's for; cut intros; test 3 openings on the same body |
| High hook, low retention | hook fine, avg % viewed / completion / 50% rate low | does the body deliver the promise fast; pacing; a version 20–30% shorter; what happens at the drop-off points |
| High retention, low engagement | retention fine, engagement / share / save rate low | a reason to comment, save, share; one ask in the last seconds |
| High engagement, low CTR | engagement fine, link CTR low | CTA said and shown; offer clear inside the video; link placement; tie the content to your product |
| High CTR, low conversion | CTR fine, CVR low | post-click: landing page message match, mobile speed (LPV rate), offer and pricing, checkout/form friction, traffic quality, tracking |
| Good conversions, high CPA | CPA above `target_cpa` / max CPA, or 133% of the median | CPM, CPC, optimization event and bidding, frequency, audience |
| High ROAS, weak profit | ROAS ≥2× or above median, but contribution margin < 0 or ROAS < break-even | margin, attribution (view-through, double counting), incrementality (holdout/geo test), discounts and returns, LTV |
| Creative fatigue | frequency up ≥15% while CTR down ≥20% (last third vs first third of ≥6 daily rows, or ≥3 snapshots) | refresh the hook and first frame, widen the audience, rotate a new variation in |

The **biggest problem** is the finding with the highest weight × severity. Weights follow the priorities below, so a paid sales ad with a weak hook but a fine CPA isn't flagged first for its hook. Every diagnosis also lists caveats: attribution, "4× ROAS isn't profit" with your break-even ROAS, like-for-like length, hook proxies, small samples (<1,000 impressions or views).

### The 5 tests

Per video, against your medians: ✅ at or above, ⚠️ within 25% below, ❌ more than 25% below (for costs the other way round), · not measurable.

| Test | Measured by (first available) |
|---|---|
| Attention | hook rate → 2-s / 6-s view rate → views / reach / impressions |
| Retention | avg % viewed → completion → 50% rate → ThruPlay rate → avg watch time (length band) |
| Engagement | engagement rate → share rate → save rate |
| Action | paid: link CTR → CTR. Organic: follower conversion → profile visit rate → CTR |
| Business impact | paid: contribution margin > 0 → CPA (CPL for lead-gen) vs your target/max → ROAS vs break-even (+20% to pass) → CPA vs median. Organic: CVR → follower conversion |

### Organic vs paid priorities

| Organic | Paid, sales | Paid, leads | Paid, awareness |
|---|---|---|---|
| 1. Retention (avg % viewed, completion) | CPA / CAC vs max affordable | CPL and lead quality | CPM and reach |
| 2. Watch time | contribution margin / ROAS | CAC vs LTV | hook rate |
| 3. Shares and saves | CVR | CVR on the form | ThruPlay / completion |
| 4. Audience relevance | CTR | CTR | frequency |
| 5. Follower conversion | hook and retention | hook and retention | engagement and follows |
| 6. Meaningful engagement | CPM / CPC | CPM / CPC | brand lift (platform study) |

Set the goal in the profile (`perf.goal: sales | leads | awareness`). Without it: `leads` when the economics block has a lead-to-customer rate and no AOV, else `sales`.

## Testing process

1. **One goal per test.** Decide the one number that decides the winner (hook rate for an opening test, CPA for an offer test) before you launch.
2. **Variations of one variable.** Same body, three hooks. Or same video, two offers. Change two things and you won't know which one worked.
3. **Fair comparisons.** Same audience, budget, placement and dates; similar lengths for retention; same platform for hook rates.
4. **Early vs final signals.** Hook rate and CTR settle after about 1,000 impressions per variation. CVR and CPA need volume: aim for ~50 conversions per variation before calling it, or use a cheaper proxy (landing page views, add to cart) and confirm later.
5. **Watch fatigue.** A winner decays: frequency climbs, CTR falls, CPA rises. The report flags it; refresh the hook first.
6. **Scale validated winners.** Raise budget gradually (about 20–30% every few days), keep the loser paused rather than deleted, and keep the winner as the control for the next test.

## What marketers forget

- **The offer.** A better video won't save a weak offer. If CTR is high and CVR is low, test the offer before the creative.
- **The landing page.** Message match, mobile speed, one clear action. LPV rate under ~70% of link clicks usually means a slow page or accidental clicks.
- **Profitability.** ROAS is revenue, not profit. Know your break-even ROAS (1 ÷ gross margin) and your max CPA before you look at the dashboard.
- **Attribution.** Platforms claim conversions within their windows, including view-through. Add up what every platform claims and compare with your real orders. MER (total revenue ÷ total marketing spend) is the honest top-line number.
- **Audience quality.** Cheap clicks from the wrong people inflate CTR and kill CVR. Check placements, geography and lead quality, not only volume.

## Profile blocks

```yaml
economics:                    # your unit economics (all optional)
  avg_order_value: 120
  gross_margin: 0.6           # 0–1
  ltv: 480                    # revenue per customer over their lifetime
  lead_to_customer_rate: 0.2  # for lead-gen
  target_cpa: 40
  payback_months: 3
  monthly_revenue_per_customer: 60    # optional, for the payback CAC limit
  total_revenue: 25000        # optional, for real MER over the same period
  total_marketing_spend: 6000
perf:
  goal: sales                 # sales | leads | awareness
  days: 28                    # API lookback
  sources: [instagram, youtube, meta_ads, tiktok_ads]   # default: all with keys
  instagram: {limit: 30, comments: true, comment_posts: 10}
  youtube: {limit: 50, retention_videos: 10, comments: true, comment_posts: 10}
```

## Verified API references (November 2026)

See [references](references.md#own-performance-apis) for the doc pages each source was built from.
