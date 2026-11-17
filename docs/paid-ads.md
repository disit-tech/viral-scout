# Paid ads (your own ad accounts)

Each business's own ad accounts on Meta (Facebook and Instagram), Google Ads and TikTok Ads, in one place: what's running, what it spends this month against a hard monthly cap, what each result costs, and Claude building and launching campaigns from a brief. Competitors' ads are a different feature: the [ads scout](ads-scout.md).

| | Where |
|---|---|
| Dashboard | business page → **Paid ads** tile and tab (`/p/<profile>/paid`) |
| Claude Code | `/ads <profile> [request]` (skill in `.claude/skills/ads/`) |
| CLI | `python -m viral_scout paid <profile> pull \| status \| cap \| pause \| resume \| budget \| log \| ask \| enforce` |
| Data | `data/paid/<profile>.json` (last read), `data/paid/<profile>-log.jsonl` (every change), `web/data/paid/<profile>.json` (dashboard) |

## Two ways in

Claude and the dashboard reach the accounts differently, because the dashboard can't use Claude's connectors:

| Platform | Claude (build, launch, read) | Dashboard and CLI (numbers, pause, resume, budget) |
|---|---|---|
| Meta | official **Meta Ads MCP** (`meta-ads`, hosted at `https://mcp.facebook.com/ads`, open beta): read, create, update, pause | Marketing API with `META_ADS_TOKEN` (`ads_read` + `ads_management`) |
| Google Ads | official **google-ads-mcp** (`googleads/google-ads-mcp`, runs locally): read-only reports; changes through the `paid` CLI | official Google Ads API (REST v26) with OAuth: campaigns, budgets, spend, conversions; pause / resume / daily budget |
| TikTok | TikTok's hosted **Ads MCP** (`tiktok-ads`, `https://business-api.tiktok.com/open_mcp/tt-ads-mcp-layer`): TikTok has a doc page for it; its tools and write access are only described by third parties so far | TikTok API for Business with `TIKTOK_ADS_TOKEN` |
| Site analytics | Google's official **GA4 MCP** (`analytics-mcp`, read-only): sessions and key events by source / campaign, to judge ads by leads | — |

### Connect Meta (Claude)

Registered at user scope: `claude mcp add --transport http --scope user meta-ads https://mcp.facebook.com/ads`. Then in Claude Code type `/mcp`, pick `meta-ads` and log in with the Facebook account that manages the ad accounts. Meta rolls the connector out to ad accounts in waves: an account outside the rollout gets every request refused, and the skill says so and stops.

### Connect Google Ads

1. Google Cloud console (the same project as YouTube Analytics is fine): enable the **Google Ads API**, create an OAuth client ID of type **Desktop app**, and publish the consent screen (**In production**; in Testing the refresh token dies after 7 days).
2. Setup page → `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET` (they fall back to the YouTube Analytics client).
3. `python -m viral_scout paid auth google` → sign in with the Google account that manages the businesses' Google Ads accounts → `GOOGLE_ADS_REFRESH_TOKEN` lands in `.env`.
4. Only if needed: `GOOGLE_ADS_LOGIN_CUSTOMER_ID` (you reach the accounts through a manager account) and `GOOGLE_ADS_DEVELOPER_TOKEN` (Google Ads → Tools → API Center). Google's REST auth page now lists only `Authorization` and `login-customer-id`; older guides require the developer token, so it's sent whenever it's set. **Test** on the Setup page lists the accounts the login reaches.
5. The customer id (`123-456-7890`) goes into each business's Paid ads page.

For Claude, Google's own read-only server (`googleads/google-ads-mcp`, runs on this PC) can be added as `google-ads` (`claude mcp add --scope user google-ads …`, see its README). It isn't required: the skill reads Google through `paid <profile> status` too. Creating a Google campaign isn't automated (Google's connector can't, and unofficial write servers aren't used): the skill gives the exact setup to enter in Google Ads.

### Connect TikTok (Claude)

Registered: `claude mcp add --transport http --scope user tiktok-ads https://business-api.tiktok.com/open_mcp/tt-ads-mcp-layer` (the "layer" server, about 40 tools; TikTok also lists a "flat" one with about 400). In Claude Code `/mcp` → `tiktok-ads` → sign in with the TikTok for Business account (authorization lasts about 30 days, per third-party docs). If the sign-in fails, the address is wrong or not open yet: remove it with `claude mcp remove tiktok-ads --scope user`.

### Connect Google Analytics (Claude, read-only)

Google's server (`analytics-mcp`, PyPI, Apache 2.0) is installed in its own environment at `~/.local/mcp/analytics-mcp` and registered at user scope with `GOOGLE_APPLICATION_CREDENTIALS` (gcloud's default credentials file) and `GOOGLE_CLOUD_PROJECT`. One-time: enable the Google Analytics Admin API and Data API in that Cloud project, then sign in with the Google account that can see the sites' GA4 properties:

```
gcloud auth application-default login --scopes https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/cloud-platform
```

### Audit

`/ads <profile> audit` runs a read-only checklist (`.claude/skills/ads/audit.md`, condensed from the MIT-licensed claude-ads control catalogs): measurement first (pixels, server-side events, no double counting, the real lead event, UTMs, platform vs GA4 vs real leads), then Meta, Google and TikTok structure, creative, audiences, bidding and budget. Every check is pass / fail / unknown / n/a with its evidence; the 3 most important fixes come first; the result goes to the vault.

### Keys for the dashboard

`META_ADS_TOKEN` and `TIKTOK_ADS_TOKEN` in `.env` (Setup page, filter "paid ads"). One token sees every business's account; the account ids live per business in the profile, never as a shared default, so one business can't show or spend on another's account.

## The `paid:` block

```yaml
paid:
  monthly_cap_usd: 300          # hard limit per calendar month, all platforms; 0 = nothing may start
  platforms: [meta, google, tiktok]
  accounts: {meta: act_123, google: "123-456-7890", tiktok: "7000000000000000000"}
  brief:                        # what Claude starts from
    goal: leads                 # leads | sales | traffic | awareness | messages | calls
    daily_budget_usd: 20
    geo: "Chicago metro, 25 mi around 60601"
    audience: "homeowners 35-65"
    offer: "free outage checklist"
    landing: https://example.com/checklist
    notes: "never mention prices"
```

Edit it on the Paid ads page (**Brief, cap and accounts**). Meta and TikTok ids fall back to `perf.meta_ad_account_id` / `perf.tiktok_advertiser_id`.

## The cap

The projected month = spend so far + every running campaign's daily budget for the days left (today included) + what remains of lifetime budgets + the new or changed budget. Above `monthly_cap_usd` → refused. It's checked by:

- `paid <profile> cap <daily>`: the skill runs it before any launch; exit code 3 means refused.
- `paid <profile> resume|budget …` and the dashboard's Resume and Budget buttons (fresh numbers each time).
- The **backstop** after every dashboard **Build campaign with Claude** run (`paid <profile> ask`): it reads the accounts again and, if the month is over the cap or can't be totalled, pauses every campaign created during the run, newest first, and logs `auto-pause`. `paid <profile> enforce` does the same for today's campaigns by hand.

It also refuses when no cap is set, when an account isn't in USD (the cap is USD), and when a listed account can't be read (its spend is unknown), for example a Google account id without the Google keys. A Google shared budget is counted once for all its campaigns. Pausing is always allowed. Scheduled jobs never spend (publish-and-jobs.md, safety rules).

As a second backstop outside viral-scout, set an account spending limit in each platform's billing settings.

## Change log

Every launch, pause, resume, budget change, refusal and auto-pause is a line in `data/paid/<profile>-log.jsonl` with when, who (`dashboard`, `claude`, `cli`, `backstop`), platform, campaign and amount. The page shows the latest 50. Claude records launches made through the Meta connector with `paid <profile> log launch "…" --platform meta --campaign <id> --amount <daily> --by claude`.

## Build campaign with Claude

The button (or `paid <profile> ask "<extra>"`) runs Claude Code headless on your subscription with the `/ads` skill. It may only read files and the web, use the `meta-ads` and `google-ads` connectors and the viral-scout MCP's read tools, and run `python -m viral_scout paid <profile> …`. It reads the account, competitors' long-running ads, search demand and your own results, plans one campaign, checks the cap, builds it paused, reads it back, starts it and logs it. Its log is in `data/logs/paid/`, and the run shows on the Activity page.
