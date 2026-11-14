# Dashboard

A Next.js app in `web/` that shows every business profile: outliers, fastest posts, rising posts and tracked links as cards (thumbnail, labels, metrics, growth sparkline, hook, transcript), plus the AI ideas notes, a swipe-file board and source health.

It runs in two modes:

| | Local (your PC) | Published (Vercel, free Hobby plan) |
|---|---|---|
| Start | `cd web && npm install && npm run dev` → http://localhost:3210 | `scripts/publish.ps1` |
| Data | `web/data/*.json`, refreshed after every run | a snapshot uploaded with each deploy |
| Save / Track / Dismiss / swipe status | run the Python CLI and update the vault | read-only; the buttons copy the CLI command |
| Login | none (unless `SITE_PASSWORD` is set) | password (`SITE_PASSWORD`); locked if it's missing |

Nothing runs in the cloud. Collection stays on your PC (home IP, yt-dlp, the scheduled task). Vercel only hosts the pages.

## Data flow

```
python -m viral_scout run <profile>      → data/<profile>-latest.json + SQLite
   └─ export (automatic after each run)  → web/data/<profile>.json, web/data/index.json
python -m viral_scout export [profiles]  → the same, by hand
scripts/publish.ps1                      → export + vercel deploy --prod (uploads web/ incl. data/)
```

`web/data/` is git-ignored, so the public repo never contains business data. The deploy uploads it straight from your PC: `web/.vercelignore` deliberately doesn't exclude it.

## Publish to Vercel

One-time setup:
```powershell
npx vercel login                       # once per PC
scripts/publish.ps1 -SetPassword       # links project "viral-scout", asks for a password, deploys
```

Afterwards:
```powershell
scripts/publish.ps1                    # export + production deploy
scripts/publish.ps1 -Preview           # preview URL instead
```

To publish automatically after the scheduled run, pass `-Publish` to `scripts/schedule.ps1`: it adds a `viral-scout publish` task after the last profile, on the same weekly day. Or add `pwsh -File scripts/publish.ps1` to your own task after `run-daily.ps1`.

**Free plan notes:**
- Vercel Hobby is meant for personal, non-commercial use. If the dashboard becomes a client deliverable, move it to Pro.
- Vercel's own "Password Protection" is a paid feature, so this app has its own login: an HMAC-signed cookie, valid 30 days. It runs in `src/proxy.ts`, Next 16's replacement for middleware.
- Every page is pre-rendered at build time. The only server code that runs is the login check, which fits comfortably in the free limits.

## Pages

- `/search`: searches titles, hooks, endings, transcripts and captions. Locally it covers the full history of every business through the Python CLI; the published site searches the latest runs in the browser.
- `/new`: **New research**. Pick **Quick research** (a one-off `research-…` profile, reports go to the repo's `reports/`) or **New project** (reports go to an Obsidian project folder you pick). Describe the business or topic and add search phrases. Hashtags, the topic filter and the spam rules are derived for you, and the first run starts in the background while the page shows its progress. Local only.
- `/activity` (**Activity** in the nav, with a pulsing dot while something runs; local only): what is running on this PC right now. Every `run`, `ads` and `perf` command writes a live log to `data/activity/` (also the progress lines `--quiet` hides), whoever started it: the CLI, the weekly task, an AI agent or the dashboard. Per run: status, elapsed time, time since the last output, a progress bar for ads runs (searches done of planned, per source: Facebook/Instagram, TikTok, Google), the ads found so far and the live log (follow mode). Above it, Apify: spend this cycle against the plan limit, the cap per run, and every actor run of the last 6 hours with its status, duration and cost, linked to the Apify console. Refreshes every 3 s; reading Apify's run list is free. CLI: `python -m viral_scout activity`.
- `/setup`: every API key with what it unlocks, its cost, how to get it and a docs link. Paste, **Save** and **Test** it. Keys go into `.env` on your PC through stdin (never on the command line). Secrets are always shown masked. Actor ids and settings are shown in full. Local only; the published site never manages keys. The **Ads: Apify actors** group names the actor each route is built for, and **Spend controls** holds `APIFY_MAX_USD_PER_RUN` (the cap per Apify run) and `VIRAL_SCOUT_MCP_PAID` (whether MCP clients may start paid runs). **Test** on an actor only looks it up, so nothing runs or bills. **Test** on `APIFY_TOKEN` shows the plan and this cycle's spend against its limit (for example `$3.35 of $19 used this cycle (resets 2026-12-13)`), and fails once the limit is reached, because then every Apify run is blocked.

- `/p/<profile>/performance`: **Your performance**. Your own videos and ads: KPI cards grouped A–E (hover for formula and denominator), an organic / paid toggle, the 5 tests per video, a retention curve with drop-off markers, the diagnosis, priorities, unit economics and CSV import steps. Read-only; data from `web/data/perf/<profile>.json`. See [performance.md](performance.md).
- `/`: one card per business, with posts, outliers, 🔥 mega, saved, and the top thumbnails.
- `/p/<profile>` has these tabs:
  - **Outliers**, **Fastest**, **Rising now**, **Tracked**: card grids with search, a platform filter and "hide saved".
  - **Ideas**: the `<date>-viral-ideas.md` notes written by the `/viral-scout` skill, rendered as HTML.
  - **Swipe file**: a board with idea → scripted → filmed → posted → skip columns. Changing a card's status locally edits the note's `status:` in the vault.
  - **Sources**: skipped sources, suggested hashtags, creators who keep showing up, errors and recent runs.
- `/p/<profile>/ads` (the **Ads** button on the business page): the ads scout ([ads-scout.md](ads-scout.md)). Three views: **Cards**, a **Table** (click a column header to sort, click a row for the full copy, where it was found and the library link) and **Groups** (group by advertiser, platform, placement, offer, format, CTA, landing domain, the search that found it, running time, start month or label; each group shows its ads, running count, 30d+ count, longest run and best score, and expands to its top ads). Filters: platform chips (Facebook/Instagram, Google, TikTok) with counts, running or stopped, minimum days running (7/30/60/90+), competitor searches vs keyword/category searches, new since the last run, format, offer, advertiser and text search. The advertiser table follows the filters, sorts by any column, has a search box, lists the platforms each advertiser runs on, and **hide** removes an advertiser from the view (for example Angi's ads that recruit contractors). Filters, view and sort live in the URL, so a link reopens the same view. **CSV** downloads what's shown. Cards load 60 at a time. Below: offers that keep running (click one to filter), coverage (including what the noise filter dropped), skipped sources and lookup links. Read-only, from `web/data/ads/<profile>.json`, which `python -m viral_scout ads|export` writes. Meta snapshot URLs, which carry the access token, are never exported.
- `/p/<profile>/a/<ad>`: **one ad in detail** (click any ad card, table row or group card). The creative (image, video while the signed link lasts, or a text ad laid out as in search results). **Why it's worth studying**: days running against the 21/30/60/90-day marks, compared with the advertiser's median run, variants, score rank, new this week, and whether a competitor or keyword search found it. **Numbers**. **Copy breakdown**: the part people see before "See more" (about 125 characters on Facebook/Instagram, 90 for a Google description) in bold, the hook and whether it fits, the problem it names, offer, money/free, proof (reviews, years, warranty, licence), urgency, CTA, voice and length. **Variants**: the other versions in the same group. **The advertiser's playbook**: their ads in this run on a start→stop timeline (hover a bar, click to open it, or switch to a table), median and longest run, offer, platform and format mix. **Same angle elsewhere**: other advertisers with overlapping copy or the same offer. **History**: first and last time viral-scout saw it. Links to the ad library, the landing page and the lookup pages. All of it is computed from the collected data, with no AI and no extra cost. A **★ worth studying** badge (still running after 30+ days, 60+ days in total, or 3+ variants) marks the ads to open first, with a filter for it on the ads page.

## Security

- Local actions only accept requests whose host is `localhost` or `127.0.0.1`. The Python CLI is called with fixed arguments, never through a shell.
- On Vercel (`VERCEL` is set) actions are switched off, and the API answers 403.
- Pages send `X-Robots-Tag: noindex` and set `robots: noindex`.
