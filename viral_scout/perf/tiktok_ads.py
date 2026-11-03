"""Your own TikTok ad account: TikTok API for Business, integrated (synchronous) report.

Needs TIKTOK_ADS_TOKEN (a long-term access token from your TikTok for Business developer app, with Reporting
permission) and TIKTOK_ADVERTISER_ID.

  GET https://business-api.tiktok.com/open_api/v1.3/report/integrated/get/
      report_type=BASIC, data_level=AUCTION_AD, dimensions=["ad_id"] (+ "stat_time_day" for the daily rows)

Metric names follow TikTok's reporting docs (video_play_actions, video_watched_2s, video_watched_6s,
video_views_p25…p100, average_video_play, …). If TikTok rejects a metric we retry with the core set.
"""
import json
import os
from datetime import date, timedelta

import requests

from .. import usage
from .schema import blank

API = "https://business-api.tiktok.com/open_api/v1.3/report/integrated/get/"
CORE = ["ad_name", "campaign_name", "spend", "impressions", "reach", "frequency", "clicks", "ctr", "cpc", "cpm",
        "conversion", "cost_per_conversion", "conversion_rate"]
VIDEO = ["video_play_actions", "video_watched_2s", "video_watched_6s", "video_views_p25", "video_views_p50",
         "video_views_p75", "video_views_p100", "average_video_play", "average_video_play_per_user", "likes",
         "comments", "shares", "follows", "profile_visits", "complete_payment", "complete_payment_roas"]
DAILY = ["spend", "impressions", "reach", "frequency", "clicks"]


def available():
    return bool(os.environ.get("TIKTOK_ADS_TOKEN") and os.environ.get("TIKTOK_ADVERTISER_ID"))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def report(metrics, dims, start, end, errors, max_pages=20):
    rows, page = [], 1
    while page <= max_pages:
        usage.add("tiktok_ads_requests")
        params = {"advertiser_id": os.environ["TIKTOK_ADVERTISER_ID"], "report_type": "BASIC",
                  "data_level": "AUCTION_AD", "dimensions": json.dumps(dims), "metrics": json.dumps(metrics),
                  "start_date": start, "end_date": end, "page": page, "page_size": 200}
        try:
            d = requests.get(API, params=params, headers={"Access-Token": os.environ["TIKTOK_ADS_TOKEN"]},
                             timeout=60).json()
        except (requests.RequestException, ValueError) as err:
            errors.append(f"tiktok ads: {err}")
            return rows
        if d.get("code") != 0:
            return {"_error": d.get("message", "error")} if not rows else rows
        data = d.get("data") or {}
        rows += data.get("list") or []
        if page >= (data.get("page_info") or {}).get("total_page", 1):
            break
        page += 1
    return rows


def normalize(row):
    dm, m = row.get("dimensions") or {}, row.get("metrics") or {}
    r = blank("tiktok_ads", "paid", dm.get("ad_id"), platform="tiktok", title=m.get("ad_name") or dm.get("ad_id"),
              campaign=m.get("campaign_name"))
    g = lambda k: _num(m.get(k))
    r.update(spend=g("spend"), impressions=g("impressions"), reach=g("reach"), frequency=g("frequency"),
             clicks=g("clicks"), link_clicks=g("clicks"), conversions=g("conversion"),
             video_starts=g("video_play_actions"), views=g("video_play_actions"), views_2s=g("video_watched_2s"),
             views_6s=g("video_watched_6s"), p25=g("video_views_p25"), p50=g("video_views_p50"),
             p75=g("video_views_p75"), p100=g("video_views_p100"), avg_watch_time=g("average_video_play"),
             likes=g("likes"), comments=g("comments"), shares=g("shares"), follows=g("follows"),
             profile_visits=g("profile_visits"), purchases=g("complete_payment"))
    roas = g("complete_payment_roas")
    if roas is not None and r["spend"]:
        r["revenue"] = roas * r["spend"]
        r["notes"].append("Revenue = complete_payment_roas × spend (TikTok-attributed).")
    r["notes"].append("TikTok 'clicks' are destination clicks: used for CTR and link CTR alike.")
    return r


def pull(cfg, errors):
    days = min((cfg.get("perf") or {}).get("days", 28), 30)
    end = date.today() - timedelta(days=1)
    start = (end - timedelta(days=days - 1)).isoformat()
    rows = report(CORE + VIDEO, ["ad_id"], start, end.isoformat(), errors)
    if isinstance(rows, dict):
        errors.append(f"tiktok ads: full metric set rejected ({rows['_error'][:160]}); retried with core metrics")
        rows = report(CORE, ["ad_id"], start, end.isoformat(), errors)
        if isinstance(rows, dict):
            errors.append(f"tiktok ads report: {rows['_error']}")
            return []
    recs = {}
    for x in rows:
        r = normalize(x)
        r["date_start"], r["date_stop"] = start, end.isoformat()
        recs[r["key"]] = r
    daily = report(DAILY, ["ad_id", "stat_time_day"], start, end.isoformat(), errors)
    if isinstance(daily, list):
        for x in daily:
            dm, m = x.get("dimensions") or {}, x.get("metrics") or {}
            k = f"tiktok_ads:{dm.get('ad_id')}"
            if k in recs:
                recs[k]["daily"] = (recs[k]["daily"] or []) + [{
                    "date": (dm.get("stat_time_day") or "")[:10], "impressions": _num(m.get("impressions")),
                    "reach": _num(m.get("reach")), "frequency": _num(m.get("frequency")),
                    "clicks": _num(m.get("clicks")), "spend": _num(m.get("spend"))}]
    return list(recs.values())
