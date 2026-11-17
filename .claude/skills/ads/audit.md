# Ad account audit (read-only): `/ads <profile> audit`

Condensed for small local and B2B service businesses from the control catalogs of
[claude-ads](https://github.com/AgriciDaniel/claude-ads) (`ads/references/{meta,google,tiktok}-audit.md` and
`conversion-tracking.md`, MIT License, Copyright (c) AgriciDaniel). Check IDs are theirs, so findings can be
compared with a full claude-ads run.

## Rules

- **Read only.** An audit changes nothing. Fixes are proposals; pausing or budget changes go through the normal
  `/ads` steps (cap check, log) and only when the owner asks.
- **Evidence or `unknown`.** Every check is `pass`, `fail`, `unknown` (the evidence isn't available) or `n/a`
  (doesn't apply to this business, goal or campaign type). Never guess a pass. Say what evidence would settle an
  `unknown`.
- **No universal thresholds.** Judge against the business's own numbers (`perf_results` medians,
  `economics.target_cpa`), its goal and its sample size (fewer than about 50 results or 7 days: too early to judge
  a campaign). Benchmarks from blogs are context, never a fail on their own.
- **Not adopting a beta or new feature is never a fail.** List those separately as optional opportunities.
- **Separate the layers:** what the data shows → what it probably means (confidence) → what to do (priority,
  effort, how to tell it worked).

## Evidence sources (in this order)

1. `python -m viral_scout paid <profile> status` (all three platforms, this month, the cap).
2. The connectors: `meta-ads` (Meta), `tiktok-ads` (TikTok), `google-ads` if added, `analytics-mcp` (GA4 on the
   business's site: sessions and key events by source / medium / campaign).
3. MCP `viral-scout` → `perf_results` (CTR, CPA, hook rate, fatigue from the ad insights).
4. The business's site repo for tags (Pixel, Google tag, TikTok pixel, server-side events), if the owner names it.

## 1. Measurement first (if this fails, nothing else can be judged)

| ID | Check | Evidence |
|---|---|---|
| M01 / G-CT3 / T01 | Pixel / Google tag / TikTok pixel on the landing pages | events received in the platform, or the site code |
| M02 / G43 / T02 | Server-side events (Meta Conversions API, Google enhanced conversions, TikTok Events API) where the site can send them | platform event source, site code |
| M03 / G-CT1 | No double counting: browser and server copies share the dedup id; one lead = one conversion | event counts vs real leads |
| M07 / G42 / G47 | The optimization event is the real business outcome (lead, call, booking), not a page view; micro events are secondary | conversion action settings |
| G46 / M35 | Attribution and conversion windows fit the sales cycle | account settings |
| G-CT2 | GA4 linked and receiving the ads' traffic (UTMs) | `analytics-mcp` report by campaign |
| M39 | Every ad URL has `utm_source / utm_medium=paid / utm_campaign` | ad URLs |
| — | Reconcile: platform leads vs GA4 key events vs leads actually received (CRM, inbox, calls) for the same dates | all three; never add platforms' conversions together |

## 2. Meta

| ID | Check |
|---|---|
| M18 | Objective matches the goal (leads → Leads/Sales objective with the lead event, not Traffic or Engagement) |
| M11 / M16 | Not fragmented: few campaigns and ad sets, each with enough budget to exit learning |
| M13 / M14 | Learning phase: ad sets stuck in "learning limited"; frequent edits resetting learning |
| M-ST1 / M-ST2 | Budget adequate for the goal's cost per result; budgets actually spent |
| M12 / M17 | Campaign vs ad-set budget used on purpose; budget goes to what works |
| M25 / M26 / M27 | Several formats and concepts per ad set; 9:16 video for Reels and Stories |
| M28 / M-CR1 / M-CR2 | Fatigue: rising frequency with falling CTR; creatives refreshed |
| M29 | Hook rate (3-second plays ÷ impressions) against the business's own median |
| M30 / M31 | Social proof and native-looking (UGC-style) creatives present |
| M19 / M23 | Audiences don't overlap; current customers and recent leads excluded |
| M20 / M21 / M24 | Custom and lookalike audiences fresh and built from good sources (customer list, leads) |
| M33 / M34 | Placements: Advantage+ placements or a reason not to; placement results reviewed |
| M36 / M37 | Bid strategy fits (lowest cost while learning; cost cap only with enough data); frequency watched |
| M40 | A test is running (one variable at a time) |
| — | Special ad category declared when housing, employment, credit or financing applies |

## 3. Google Ads

| ID | Check |
|---|---|
| G11 / G12 | Location targeting = the service area ("people in", not "interested in"); Search partners and Display network off unless chosen |
| G10 | Ad schedule matches the hours calls can be answered |
| G13 / G14 / G15 / G16 | Search terms reviewed recently; negatives in place; spend on irrelevant searches |
| G17 / G18 | Broad match only with smart bidding and good conversion data |
| G-WS1 / G-KW1 | Keywords that spend without converting; keywords with no impressions |
| G20 / G21 / G24 | Quality Score and its parts; landing page experience |
| G26 / G27 / G28 / G29 | At least one responsive search ad per ad group with enough headlines and descriptions; Ad Strength |
| G50 / G51 / G52 / G54 / G55 | Sitelinks, callouts, structured snippets, call extension (local services: essential), lead forms where useful |
| G05 / G07 | Brand vs non-brand separated; Search and Performance Max not competing for the same searches |
| G36 / G37 / G39 | Smart bidding fits the data volume; target CPA realistic against `economics.target_cpa`; budget-limited campaigns |
| G59 / G60 | Landing page fast on mobile and matches the ad |
| — | Local services: Local Services Ads and the Google Business Profile considered (outside this API; mention, don't score) |

## 4. TikTok

| ID | Check |
|---|---|
| T01 / T02 | Pixel and Events API (with `ttclid`) |
| T03 / T12 / T13 | Simple structure; budget enough per ad group to learn |
| T06 / T07 / T25 | 9:16, native-looking, text and CTA inside the safe zone |
| T08 / T09 | Hook in the first seconds; creative fatigue |
| T10 | Spark Ads (boosting the business's own organic posts) considered |
| T22 / T23 / T24 | Caption keywords, licensed sound, CTA button |
| T17 / T18 / T19 | CTR, CPA and completion rate against the business's own numbers |

## 5. Across platforms

- Budget split follows cost per result, not habit; the month's projection vs the cap (`paid status`).
- One landing page per offer; the ad's promise matches the page; the form or phone number works on mobile.
- Compliance: the profile's `studio.compliance` note; no unprovable claims; AI-made creatives labelled.

## Output

1. A short summary for the owner: the 3 most important fixes first (measurement before creative before budget),
   each with why, effort and how to tell it worked.
2. The table of checks with status and evidence.
3. Optional opportunities (new features, betas), unscored.
4. Save to the vault: `<vault>/projects/<project>/05 Marketing/ads/<date>-ad-audit.md`.
