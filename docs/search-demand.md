# Search demand (Google Trends)

When does demand for each service rise, peak and fall where the business works, what are people starting to
search for, and which words do they use. viral-scout finds *what content works*; this part adds *when* and
*with which words*, so posts and ads go out before demand peaks.

```
python -m viral_scout demand <profile>          # cached: refetches at most every demand.every_days (default 7)
python -m viral_scout demand <profile> --force  # refetch now
```

The weekly run (`scripts/run-daily.ps1`, on the ads day) calls it for every profile with a `demand:` block.
Dashboard: `/p/<profile>/demand` (linked from the ads page). Vault: `<output_dir>/<date>-search-demand.md`.
MCP: `demand_results(profile, term?)` (free, reads the stored data).

## Profile

```yaml
demand:
  terms: [gutter cleaning, christmas light installation, handyman]   # one seasonal curve each
  compare: [permanent lights, christmas light installation, holiday light installation]  # up to 5, one shared scale
  geo: US-IL-602      # US, a state (US-IL) or a metro (DMA code: US-IL-602 = Chicago)
  time: today 5-y     # 5 years of weekly data
  every_days: 7
  lead_weeks: 3       # "start posting by" = this many weeks before demand starts rising
```

Pick terms the way customers would type them, without the city (the geo already limits the area). Niche terms
in one metro often have weeks at zero: the page marks them *few searches here* and only shows their season
shape. A state-level geo gives steadier numbers.

## What you get

| | How it's computed |
|---|---|
| **The average year** | 5 years of weekly values averaged by week of the year, smoothed over 5 weeks, as an index (1.0 = the term's yearly average) |
| **Seasons** (up to 2 per term) | A peak at least 15% above the yearly average, 8+ weeks from another peak. It starts after the last week below average and ends at the last week above it. Gutter cleaning in Chicago, for example, has a June and an October season. |
| **Start posting by** | The next season start minus `lead_weeks` |
| **In season now** | Today falls between a season's start and end |
| **Now vs last year** | Last 4 complete weeks vs the same weeks a year earlier |
| **Now vs normal** | Last 4 weeks vs what this time of year usually looks like (hidden off-season and for thin data, where the ratio is noise) |
| **2-year trend** | The last 52 weeks vs the 52 before |
| **Rising buyer searches** | Google's rising related queries that sound like someone about to hire (near me, cost, how much, company, installation, reviews...). The rest (games, shows, brands) are listed separately as likely noise. |
| **Which words people use** | The `compare` terms on one shared scale: each one's share of the searches over the last 12 months |

Values are Google's 0–100 index (each term against its own peak), **not search volumes**. For absolute volumes
to size an ad budget, Google Ads Keyword Planner is the better tool.

## Access and cost

Google's official Trends API is still an application-gated alpha (announced July 2025, no general availability
yet), and the popular unofficial Python libraries call Google's internal endpoints, which this project doesn't do.
So the data comes from Apify's own **Google Trends Scraper** (`apify~google-trends-scraper`, override with
`APIFY_GOOGLE_TRENDS_ACTOR`), using `APIFY_TOKEN`:

- one async Apify run per refresh (no 300 s sync limit), one Google Trends URL per term plus one for `compare`
- about **$0.005 per term** on the Starter plan (Nov 2026): 8 terms + a comparison ≈ $0.045 a week
- the per-run spend cap (`APIFY_MAX_USD_PER_RUN`) applies, like every Apify call
- the fetched rows are kept in `data/<profile>-demand-raw.json`; re-running inside `every_days` only re-analyzes them (free)

When Google opens its API, the fetch step is the only part to change.
