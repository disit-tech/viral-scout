---
name: ads
description: Run a business's own paid ads (Meta Facebook/Instagram, Google Ads, TikTok Ads) from viral-scout - read the ad accounts, review what's running and what each result costs, plan a campaign from a brief (goal, budget, area, audience), check it against the business's monthly cap, then build and launch it through Meta's official ads connector, and pause or rebudget campaigns. Use when the user asks to launch, set up, check, pause, scale or fix ads or a campaign, asks what their ads cost or return, or names a goal, budget, geo or audience for ads. Args - /ads <profile> [brief or request].
---

# Ads (your own ad accounts)

Repo: `D:\repo\viral-scout`. Run from there with `PYTHONIOENCODING=utf-8`. Docs: `docs/paid-ads.md`.
Competitors' ads are the ads scout (`/viral-scout <profile> ads`); this skill is the business's OWN accounts.

**This spends real money.** Every euro or dollar comes from the owner's ad account. The rules below are not optional.

## Hard rules

1. **The cap.** Before you launch, resume or raise anything, run
   `python -m viral_scout paid <profile> cap <daily_usd>` (or `--lifetime <usd>` for a lifetime budget).
   Exit code 3 / "REFUSED" → do not create or start it. Say why (the numbers it printed) and stop.
   No cap set (0) → nothing may start: ask the owner to set one on the dashboard's Paid ads page.
2. **Build paused, then start.** Create the campaign, ad sets and ads PAUSED, read them back, check the targeting,
   budget, schedule, landing URL and copy, and only then set them ACTIVE. One campaign per request unless the
   owner asked for more.
3. **Record it.** After launching (or changing) anything through a connector, run
   `python -m viral_scout paid <profile> log launch "<campaign name>: <goal>, $<daily>/day, <geo>, <audience>" --platform meta --campaign <id> --amount <daily> --by claude`
   then `python -m viral_scout paid <profile> pull`. Use `log change`, `log pause` the same way.
4. **Pausing is always fine.** `python -m viral_scout paid <profile> pause <meta|tiktok> <campaign_id> --by claude`.
   Resume / budget changes: `paid <profile> resume|budget …` (they run the cap check themselves).
5. **Unattended means no spend.** In a scheduled job, only read and report.
6. **Ads rules.** Meta special ad categories (housing, employment, credit/financing, social issues): declare them
   when they apply and accept the targeting limits. No claims we can't prove ("#1", "best", savings promises,
   fake urgency), no before/after where banned, FTC endorsement rules. The business's compliance note (profile
   `studio.compliance`) wins over anything here. Never copy a competitor's wording, brand or creative.
7. **Ask when the brief is thin.** Missing goal, daily budget, area or audience → ask (in a live session) or stop
   and say what's missing (headless). Never guess the budget.

## Steps

1. **State.** `python -m viral_scout paid <profile> status` (pull first if the snapshot is older than a day):
   the cap, spent, projected month, what's running, cost per result. The brief is in `profiles/<profile>.yaml`
   under `paid.brief`; the owner's request overrides it.
2. **Context** (read, don't run paid tools): MCP `viral-scout` → `ads_results` (competitors' long-running angles,
   offers, hooks), `demand_results` (what people search now, start-posting-by dates), `perf_results` (own ads:
   CTR, CPA, fatigue). The business: `profiles/<profile>.yaml` (`business`, `studio`) and its vault notes.
3. **Read the account** through the connector (Meta: the `meta-ads` MCP; Google: the `google-ads` MCP, read-only;
   TikTok: the `paid` CLI). Pixel / conversion event set up? Existing audiences? Past winners?
4. **Plan** in a few lines: objective → optimization event, budget and schedule, geo (radius / zips / metro),
   audience (broad + the brief's signals; exclusions such as current customers), placements, 2–3 creatives with
   hook / primary text (first 125 characters carry it) / headline ≤ 40 / CTA / landing URL with UTM
   (`utm_source=facebook&utm_medium=paid&utm_campaign=<slug>`), what success looks like (target cost per result
   from `economics.target_cpa` if set), and when to judge it (not before ~50 results or 7 days).
5. **Cap check** (rule 1). Refused → stop and report.
6. **Build** paused (rule 2), read back, start, **log** (rule 3), **pull**.
7. **Report** to the owner: what runs, budget, projected month vs cap, what to watch, when to look again. Write a
   short note to the vault: `<vault>/projects/<project>/05 Marketing/ads/<date>-<slug>.md` (plan, ids, budget, the
   check output).

## Platforms

- **Meta** (`meta-ads` MCP, official, hosted at mcp.facebook.com/ads): read, create, update, pause. If every call
  fails with a rollout/permission error, the account isn't in Meta's rollout yet: say so and stop.
- **Google Ads** (`google-ads` MCP, official, read-only): reports, keywords, search terms. Changes: tell the owner
  exactly what to click in Google Ads; don't use unofficial write servers.
- **TikTok Ads**: no official MCP. Read with `paid <profile> status`; pause / resume / budget with the `paid` CLI.
  Creating TikTok campaigns: give the owner the exact setup to enter in TikTok Ads Manager.
