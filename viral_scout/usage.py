"""Usage counters per run (quota meter): YouTube API units, Apify results, page requests, captions, Whisper minutes,
and for the ads scout: meta_ad_library_requests, tiktok_research_requests, apify_items / apify_runs.

Own performance (viral_scout/perf) adds: ig_insights_requests, youtube_analytics_requests, meta_ads_requests,
tiktok_ads_requests (and youtube_api_units for videos.list / commentThreads with the OAuth token).

Profiles can set caps; the report warns at 80% (the way paid tools show a quota bar):
  budget: {youtube_api_units_per_day: 10000, apify_items_per_month: 500}
"""
import os
from collections import Counter

COUNTS = Counter()


def add(what, n=1):
    COUNTS[what] += n


def reset():
    COUNTS.clear()


def snapshot():
    return dict(COUNTS)


def warnings(cfg, today_units, month_apify):
    b = cfg.get("budget") or {}
    out = []
    cap = b.get("youtube_api_units_per_day", 10000)
    if cap and today_units >= 0.8 * cap:
        out.append(f"YouTube API: {today_units:,} of {cap:,} units used today ({today_units / cap:.0%}).")
    cap = b.get("apify_items_per_month")
    if cap and month_apify >= 0.8 * cap:
        out.append(f"Apify: {month_apify:,} of {cap:,} results this month ({month_apify / cap:.0%}).")
    return out


def apify_params():
    """Query params for an Apify actor run: the token plus a spend cap for that one run.

    APIFY_MAX_USD_PER_RUN (default 0.50; 0 = no cap) becomes Apify's maxTotalChargeUsd, so a run whose input
    turns out far bigger than intended stops at the cap instead of using up the month. It caps each run, not the
    total: one profile makes several runs (one per advertiser or keyword), so per_query still sets the total.
    """
    params = {"token": os.environ.get("APIFY_TOKEN", "")}
    try:
        cap = float(os.environ.get("APIFY_MAX_USD_PER_RUN", "0.5"))
    except ValueError:
        cap = 0.5
    if cap > 0:
        params["maxTotalChargeUsd"] = cap
    return params
