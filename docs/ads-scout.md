# Ads scout

The organic side of viral-scout finds short videos that took off. The ads scout covers the paid side. It finds the ads in your niche that **keep running** (competitors and the category) and shows which hooks, offers and formats advertisers keep paying for. The `/viral-scout` skill then turns those into ad ideas for your business.

```
python -m viral_scout ads <profile>
  → <output_dir>/<date>-ads-scout.md        Obsidian report
  → data/<profile>-ads-latest.json          every ad with its scores
  → web/data/ads/<profile>.json             dashboard: /p/<profile>/ads
```

It uses the same YAML profile as the organic scout, with an `ads:` block ([profiles.md](profiles.md#ads-block)). Every source is optional. A missing key puts that source under **Skipped sources**, together with the key that unlocks it, and the run carries on.

## What you get

- **Advertisers:** ads found, how many still run, the longest run, how many run 30+ days, max variants, formats, top offers, and launches in the last 14 days (🚀 = 3 or more, a burst of new tests).
- **Winning ads:** every ad ranked by `ad_score`, with days running, variants, reach, format, platforms, offer and labels.
- **Offers that keep running:** each offer type, counted across all ads and across ads that ran 30+ days.
- **Hooks of the long-runners:** the first line of every ad that ran 30+ days.
- **New tests:** ads that started in the last 14 days. Re-run later to see which of them survive.
- **Top ads in detail:** creative image, hook, offer, CTA, landing domain, start date, a link to the public library and the full copy.
- **Look them up yourself:** links to the public Meta Ad Library, Google Ads Transparency Center and TikTok Creative Center pages for each advertiser, domain and keyword. The tool doesn't fetch these pages; they're for you to open.
- **Coverage, usage, skipped sources, errors.**

## Sources and real coverage

| Source (`ads.sources`) | Access | Key(s) | Coverage | Cost |
|---|---|---|---|---|
| `meta_api`: Meta Ad Library API (`ads_archive`) | official Graph API | `META_AD_LIBRARY_TOKEN` | **Ads that reached the EU**, plus political/issue ads anywhere. **US-only commercial ads are not in the API.** | free; rate-limited |
| `tiktok_api`: TikTok Commercial Content API (`/v2/research/adlib/ad/query/`) | official, by application | `TIKTOK_RESEARCH_CLIENT_KEY` + `TIKTOK_RESEARCH_CLIENT_SECRET` | **Ads shown in the EEA** (TikTok's API country list leaves out the UK and Switzerland). Gives media, first/last shown dates and reach, but **no ad copy**. | free after approval |
| `apify_meta`: Meta Ad Library via an Apify actor | paid provider | `APIFY_TOKEN` + `APIFY_ADS_ACTOR` | **Any country, including the US.** Whatever the public Ad Library shows: active and inactive ads, copy, dates, media, variant counts, no spend. | per ad (e.g. `apify~facebook-ads-scraper`, from $3.40 to $5.80 per 1,000 ads depending on the Apify plan, Nov 2026) |
| `apify_tiktok_top`: TikTok Creative Center Top Ads via an Apify actor | paid provider | `APIFY_TOKEN` + `APIFY_TIKTOK_ADS_ACTOR` | TikTok's own selection of top ads, by region/industry. Usually no start date, so longevity isn't scored. | depends on the actor |
| `apify_google`: Google Ads Transparency Center via an Apify actor | paid provider | `APIFY_TOKEN` + `APIFY_GOOGLE_ADS_ACTOR` | Search, YouTube and Display ads by advertiser/domain, with first/last shown dates. | depends on the actor |

### What "coverage" means for a US business

- **The free official route only shows EU ads.** If a profile's `countries` is `[US]`, the Meta API source is skipped with a coverage note rather than a key note: it would only return political ads. Set `ads.meta_countries: [DE, PL, ...]` to read what the same advertisers (or the category) run in Europe. That's useful for hooks and offers, though not for US pricing.
- On the official endpoint, Meta says that ads which "did not reach any location in the EU will only return if they are about social issues, elections or politics". Some ArchivedAd fields mention "UK & EU" targeting data, but UK-only commercial ads aren't promised by that sentence, so treat UK coverage as unconfirmed.
- **For US competitors, use `apify_meta`.** The actor reads the public Ad Library pages, which show all active and inactive ads in every country, so you aren't the one fetching them. Results depend on the actor, so fields are read loosely, and different actors give different fields.
- **TikTok** lists EEA ads only in its official API. US TikTok ads appear in Creative Center Top Ads (a curated selection), which has no public API, so the only route is an Apify actor.
- **Google:** the Transparency Center has no public API for US ads. Google provides API access to EEA ad data under the Transparency Center terms (not implemented here). For the US, use an Apify actor or the lookup links.

### Getting the keys

- **Meta Ad Library API:** confirm your identity and location for Meta (facebook.com/ID, which takes a few days), create a Meta for Developers app, then get a user access token in the Graph API Explorer and exchange it for a long-lived one. Put it in `META_AD_LIBRARY_TOKEN`. The default Graph version is `v26.0`; override it with `META_GRAPH_VERSION`. The ad snapshot URLs Meta returns contain your token, so the tool never writes them to the report or the dashboard export. It links to the public `facebook.com/ads/library/?id=<id>` page instead.
- **TikTok Commercial Content API:** apply on TikTok for Developers (research section). After approval, a research client is created. Put its key and secret in `TIKTOK_RESEARCH_CLIENT_KEY` / `TIKTOK_RESEARCH_CLIENT_SECRET`. The tool exchanges them for a 2-hour client token (`client_credentials`) on each run.
- **Apify:** `APIFY_TOKEN` (the same key the organic TikTok source uses), plus the actor id for each route: `APIFY_ADS_ACTOR`, `APIFY_TIKTOK_ADS_ACTOR`, `APIFY_GOOGLE_ADS_ACTOR`. Actor inputs differ, so the profile can pass `ads.apify_input`, `ads.tiktok_top_input` and `ads.google_input`, which are merged over the defaults. Check each actor's price per result before scheduling. Results are counted in the quota meter (`apify_items`, monthly cap `budget.apify_items_per_month`).

All of these appear on the dashboard **Setup** page (and `python -m viral_scout keys`), each with a cheap live test. The Meta test reads one ad ID, the TikTok test only fetches a client token, and the Apify actor test looks the actor up without running it.

## Scoring "winning" ads

Nobody outside the advertiser can see spend, conversions or ROAS. Everything below is a **proxy**. A long run usually means the ad pays for itself, but it can also be a brand campaign that runs regardless of results.

| Measure | Formula | Why |
|---|---|---|
| `days_running` | (stop date, or now while it runs) − start date. A stopped ad without a stop date counts as unknown, not long. | Advertisers stop ads that lose money. Practitioners use 14 to 60+ days as the threshold, and 30 days is the most common. |
| Longevity `L` | min(1, ln(1 + days) / ln(1 + 120)) | log scale: 7 d ≈ 0.43, 30 d ≈ 0.72, 120+ d = 1 |
| `variants` | size of the advertiser's creative group: ads that share their copy fingerprint (first ~25 words, without numbers/emoji/URLs) **or** their landing page (domain + path; bare homepages don't count), or the source's own count (Meta `collationCount`), whichever is larger | Advertisers scale winners by cloning them into variants |
| Variants `V` | min(1, ln(variants) / ln(10)) | 1 → 0, 3 → 0.48, 10+ → 1 |
| Activity `A` | 1 if still running; 0.5 if it stopped in the last 14 days; else 0 | what's working *now* |
| Reach `R` | the ad's percentile among this run's ads from the same source that publish reach (Meta EU reach, TikTok unique users seen, Creative Center views) | only where the platform publishes it |
| **`ad_score`** | round(100 × min(1, 0.5·L + 0.3·V + 0.2·A + 0.15·R)) | 0–100. Reach can only add, so ads from sources without reach aren't penalised |

**Labels:** 🏆 30d+ / 60d+ / 90d+ long-runner · 🧬 N variants (3 or more) · 📈 top reach (top 10%, when 10+ ads have reach) · 🆕 new test (running, started in the last 14 days) · ⏹ stopped. In the report, 🆕 next to a hook means the ad wasn't seen in the previous run.

**Advertiser launch bursts:** 3+ ads started in the last 14 days (🚀). A cluster of launches usually means a new campaign or a creative test.

### What's extracted from each ad

- **Hook:** the first line of the primary text (what people read before "See more"), cut at the first sentence and 18 words; else the headline.
- **Offer** (regex + keywords in English, Russian and Ukrainian, `viral_scout/ads/extract.py`):

| Tag | Examples it catches |
|---|---|
| `price` | $49, $19/lesson, 1200 грн/місяць, 99 EUR (not $0) |
| `free_trial` | free trial, first lesson free, бесплатный пробный урок, безкоштовне пробне заняття |
| `free_quote` | free quote / estimate / consultation / assessment, бесплатная консультация |
| `free` | any other "free" or "$0" claim: check it before you copy the angle |
| `discount` | 20% off, sale, promo code, скидка, знижка, акция |
| `guarantee` | money-back guarantee, risk-free, гарантия, повернемо гроші |
| `financing` | $0 down, monthly payments, 0% APR, loan / lease / PPA, рассрочка, розстрочка |
| `incentive` | tax credit, rebate, ITC, SREC, Illinois Shines |
| `urgency` | limited time, only 5 spots, ends Sunday, осталось, залишилось |
| `social_proof` | 4.9 stars, 2,000 homeowners, 500 студентов |

- **CTA:** the button text when the source gives it (Meta via Apify, Creative Center), else the first CTA phrase in the copy (book a free lesson, get a quote, sign up, call, learn more…).
- **Landing domain:** from the link URL (Facebook's `l.php` redirect is unwrapped) or Meta's link caption.
- **Format:** video / image / carousel / dco / text. The Meta API has no format field, so the tool runs one extra query per search with `media_type=VIDEO` (turn it off with `meta_video_pass: false`). Everything else is `image/other`, and multi-card ads are `carousel`.
- **Platforms:** Facebook, Instagram, Messenger, Audience Network, Threads (Meta), TikTok, Google surfaces.

## Ethics and rules

- **Legitimate sources only:** official APIs, or paid providers that handle the platform themselves. The ads scout never scrapes pages itself, never uses private or internal APIs, never spoofs headers, never logs in as you, and never gets around bot checks.
- **Why there's no built-in page scraper:** an earlier Playwright tool (`solarPanels/tools/ad-spy`) read the public Meta Ad Library page with a fixed browser user-agent and asked the user to log in when Facebook showed a login wall. Both break the rules above, so that approach was not carried over. Its useful ideas were: longest-running first, variants ("N ads use this creative"), newest ads as "what they're testing", and filtering keyword results down to the competitor's own pages. Those are now the scoring and the `advertisers[].match` option. The report's lookup links replace the scraper for manual checks.
- **Angles, not copies.** Use the ads to learn the problem, offer type and format that keep working. Never reuse competitors' creatives, footage, copy, music, logos or trademarks, and don't imitate their brand.
- **Truth in advertising (FTC):** every claim must be true and backed by evidence before the ad runs. A "free" offer tied to a purchase must disclose its terms clearly. ([FTC: Advertising FAQs for small business](https://www.ftc.gov/business-guidance/resources/advertising-faqs-guide-small-business))
- **Solar in Illinois:** Illinois Shines marketing rules apply to Approved Vendors and their marketing. Don't call a system "free" ("no free solar"), don't promise savings that the contract doesn't guarantee, and keep claims consistent with the program brochure and the current IPA consumer-protection documents. Check the current guidelines before publishing ([Illinois Shines resources](https://illinoisshines.com/brochures-and-other-resources/)). An ad that ran for 120 days isn't proof that it's compliant.

## Data

- `data/<profile>-ads-latest.json`: `ads[]` (every field above, including `ad_score`, `labels`, `offers`, `hook`, `cta`, `landing_domain`, `days_running`, `variants`), `advertisers[]`, `offers[]`, `coverage`, `lookup`, `skipped`, `errors`, `usage`.
- SQLite `data/<profile>.sqlite`, table `ads`: first/last seen per ad (that's what "new since the last run" uses). Ads runs are logged in `runs` with `kind: "ads"`, so Apify usage counts toward the monthly budget.
- Dashboard: `/p/<profile>/ads`, linked from the business page, read-only from `web/data/ads/<profile>.json`.
- MCP: `ads_run` (start a job, poll `get_job`) and `ads_results` (top ads, advertisers, offers, coverage, skipped sources; filter by advertiser or format).

## Code

| File | Role |
|---|---|
| `viral_scout/ads/model.py` | `Ad`, date/count/domain parsing, days running |
| `viral_scout/ads/extract.py` | hook, offer tags, CTA, format, copy fingerprint |
| `viral_scout/ads/score.py` | variant groups, reach percentiles, `ad_score`, labels, advertiser and offer summaries |
| `viral_scout/ads/sources.py` | Meta API, TikTok API, the three Apify routes, lookup links |
| `viral_scout/ads/run.py` | the run: sources → merge → score → history → report → export |
| `viral_scout/ads/report.py` | Markdown + JSON |
| `tests/test_ads.py` | offline checks: `python -m unittest discover -s tests -v` |

## Sources for the scoring

- Longevity as a profitability proxy, and its limits: [Winning Hunter: ad spend signals](https://winninghunter.com/blog/ad-spend-signals-competitor-profitability) (ads still live at day 21 were about 3× as likely to reach day 60; scores 14–45 days and 45+ days), [Superscale: how to use the Meta Ad Library](https://www.superscale.ai/learn/how-to-use-the-meta-ad-library) (variant counts as a budget signal), [Stackmatix: Meta Ads Library competitor research](https://www.stackmatix.com/blog/meta-ads-library-competitor-research) (a long run can also be brand spend). These are vendor write-ups and no independent test validates a specific day threshold, so the thresholds are heuristics.
- Field definitions: [Meta `ads_archive`](https://developers.facebook.com/docs/graph-api/reference/ads_archive/), [ArchivedAd fields](https://developers.facebook.com/docs/marketing-api/reference/archived-ad/), [TikTok Query Ads](https://developers.tiktok.com/doc/commercial-content-api-query-ads).

All links: [references.md](references.md#ads-scout).

## When you add keys: checklist

1. **US ads (recommended):** create an Apify account, then on the dashboard's **Setup** page save `APIFY_TOKEN` and `APIFY_ADS_ACTOR=apify~facebook-ads-scraper`, and click **Test**. That actor charges about $3.40–5.80 per 1,000 ads, depending on your Apify plan.
2. **Optional official EU sources:** `META_AD_LIBRARY_TOKEN` (Meta identity verification) and `TIKTOK_RESEARCH_CLIENT_KEY` / `_SECRET` (approval). These only cover ads shown in the EU.
3. Run one profile by hand: `python -m viral_scout ads nfSolarPanels`. Check the report: advertisers found, days running, hooks and offers. The field mapping follows the actor's documented output and is covered by tests (`tests/test_ads.py`, `ApifyFacebookAdsScraperShape`). If an actor version renames a field, adjust `viral_scout/ads/sources.py` → `_meta_apify_ad`.
4. Keep costs predictable: `ads.per_query` caps the ads fetched per advertiser or keyword (each one is a separate actor run), and `budget.apify_items_per_month` warns at 80%.
5. **Schedule:** `scripts/run-daily.ps1` runs the ads scout **weekly** (`-AdsDay Monday` by default; `Never` turns it off), before the AI step, so the ideas note covers ads too.
6. **Alerts:** if the profile has an `alerts:` block, competitor ads that just passed `ads.alert_days` (default 30) and are still running are sent to Telegram once each. `ads.alert_max` caps the count (default 3).
