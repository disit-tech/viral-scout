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
| Google Ads | official **google-ads-mcp** (`googleads/google-ads-mcp`, runs locally): read-only reports | not read yet; the page links the account |
| TikTok | no official MCP: the `paid` CLI | TikTok API for Business with `TIKTOK_ADS_TOKEN` |

### Connect Meta (Claude)

Registered at user scope: `claude mcp add --transport http --scope user meta-ads https://mcp.facebook.com/ads`. Then in Claude Code type `/mcp`, pick `meta-ads` and log in with the Facebook account that manages the ad accounts. Meta rolls the connector out to ad accounts in waves: an account outside the rollout gets every request refused, and the skill says so and stops.

### Connect Google Ads (Claude, read-only)

Google's server runs on this PC and needs a Google Cloud project with the Google Ads API enabled and an OAuth login for the account that manages the Google Ads accounts. Follow the repo's README (`googleads/google-ads-mcp`), then register it as `google-ads` (`claude mcp add --scope user google-ads …`). It can't create campaigns or change budgets: the skill gives the exact clicks for Google Ads instead.

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

It also refuses when no cap is set, when an account isn't in USD (the cap is USD), and when a listed account can't be read (its spend is unknown). Google Ads isn't read by the dashboard yet, so a business with a Google account listed can't start new spend through the cap check until it is. Pausing is always allowed. Scheduled jobs never spend (publish-and-jobs.md, safety rules).

As a second backstop outside viral-scout, set an account spending limit in each platform's billing settings.

## Change log

Every launch, pause, resume, budget change, refusal and auto-pause is a line in `data/paid/<profile>-log.jsonl` with when, who (`dashboard`, `claude`, `cli`, `backstop`), platform, campaign and amount. The page shows the latest 50. Claude records launches made through the Meta connector with `paid <profile> log launch "…" --platform meta --campaign <id> --amount <daily> --by claude`.

## Build campaign with Claude

The button (or `paid <profile> ask "<extra>"`) runs Claude Code headless on your subscription with the `/ads` skill. It may only read files and the web, use the `meta-ads` and `google-ads` connectors and the viral-scout MCP's read tools, and run `python -m viral_scout paid <profile> …`. It reads the account, competitors' long-running ads, search demand and your own results, plans one campaign, checks the cap, builds it paused, reads it back, starts it and logs it. Its log is in `data/logs/paid/`, and the run shows on the Activity page.
