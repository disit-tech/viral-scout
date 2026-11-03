"""Your own Meta ad account: Marketing API ad insights (official; ads_read on your own ad account).

Needs META_ADS_TOKEN (a system-user or long-lived user token with ads_read) and META_AD_ACCOUNT_ID ("act_123…" or
just the number).

  GET /act_{id}/insights?level=ad&time_range=…              one row per ad for the period
  GET /act_{id}/insights?level=ad&time_increment=1          daily rows for fatigue (frequency vs CTR)
  GET /?ids=<ad ids>&fields=creative{id,name,thumbnail_url,video_id}

3-second video plays are the 'video_view' entry in `actions`; leads, purchases and landing page views are also
`actions` entries, purchase value is in `action_values`. If the API rejects a field (renamed or deprecated in a
newer version), we retry with a core set and say which fields were dropped.
"""
import json
import os
from datetime import date, timedelta

import requests

from .. import usage
from .schema import blank

API = "https://graph.facebook.com/v26.0"
CORE = ["ad_id", "ad_name", "adset_name", "campaign_name", "objective", "impressions", "reach", "frequency", "spend",
        "cpm", "cpc", "ctr", "clicks", "inline_link_clicks", "inline_link_click_ctr", "actions", "action_values",
        "cost_per_action_type", "purchase_roas", "date_start", "date_stop"]
VIDEO = ["video_play_actions", "video_p25_watched_actions", "video_p50_watched_actions", "video_p75_watched_actions",
         "video_p100_watched_actions", "video_thruplay_watched_actions", "video_avg_time_watched_actions",
         "video_continuous_2_sec_watched_actions"]
DAILY = ["ad_id", "date_start", "impressions", "reach", "frequency", "clicks", "inline_link_clicks", "spend"]

# First match wins, so the same event isn't counted twice under two names.
ACTIONS = {
    "views_3s": ["video_view"],
    "leads": ["lead", "onsite_conversion.lead_grouped", "offsite_conversion.fb_pixel_lead"],
    "purchases": ["omni_purchase", "purchase", "offsite_conversion.fb_pixel_purchase", "onsite_web_purchase"],
    "landing_page_views": ["omni_landing_page_view", "landing_page_view"],
    "link_clicks_action": ["link_click"],
    "follows": ["like", "onsite_conversion.follow"],
    "comments": ["comment"], "shares": ["post"], "saves": ["onsite_conversion.post_save"],
    "likes": ["post_reaction"],
}
REVENUE = ["omni_purchase", "purchase", "offsite_conversion.fb_pixel_purchase", "onsite_web_purchase"]


def available():
    return bool(os.environ.get("META_ADS_TOKEN") and os.environ.get("META_AD_ACCOUNT_ID"))


def account():
    a = os.environ.get("META_AD_ACCOUNT_ID", "")
    return a if a.startswith("act_") else f"act_{a}"


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def action(lst, types):
    """Value of the first action type present in a Meta actions list."""
    by = {a.get("action_type"): _num(a.get("value")) for a in (lst or [])}
    for t in types:
        if by.get(t) is not None:
            return by[t]
    return None


def _get(path, params, errors):
    usage.add("meta_ads_requests")
    try:
        r = requests.get(f"{API}/{path}", params={**params, "access_token": os.environ["META_ADS_TOKEN"]}, timeout=60)
        d = r.json()
    except (requests.RequestException, ValueError) as err:
        errors.append(f"meta ads {path}: {err}")
        return None
    if "error" in d:
        return {"_error": d["error"].get("message", "error")}
    return d


def insights(params, errors, max_pages=20):
    rows, after = [], None
    for _ in range(max_pages):
        p = dict(params, limit=200)
        if after:
            p["after"] = after
        d = _get(f"{account()}/insights", p, errors)
        if d is None or "_error" in d:
            return rows if rows else d
        rows += d.get("data") or []
        after = ((d.get("paging") or {}).get("cursors") or {}).get("after")
        if not (d.get("paging") or {}).get("next"):
            break
    return rows


def normalize(row, source="meta_ads"):
    """One Meta insights row → a normalized record."""
    acts = row.get("actions")
    r = blank(source, "paid", row.get("ad_id"), platform="facebook", title=row.get("ad_name") or row.get("ad_id"),
              campaign=row.get("campaign_name"), date_start=row.get("date_start"), date_stop=row.get("date_stop"))
    link = _num(row.get("inline_link_clicks"))
    r.update(impressions=_num(row.get("impressions")), reach=_num(row.get("reach")),
             frequency=_num(row.get("frequency")), spend=_num(row.get("spend")), clicks=_num(row.get("clicks")),
             link_clicks=link if link is not None else action(acts, ACTIONS["link_clicks_action"]),
             views_3s=action(acts, ACTIONS["views_3s"]), leads=action(acts, ACTIONS["leads"]),
             purchases=action(acts, ACTIONS["purchases"]),
             landing_page_views=action(acts, ACTIONS["landing_page_views"]),
             follows=action(acts, ACTIONS["follows"]), comments=action(acts, ACTIONS["comments"]),
             shares=action(acts, ACTIONS["shares"]), saves=action(acts, ACTIONS["saves"]),
             likes=action(acts, ACTIONS["likes"]), revenue=action(row.get("action_values"), REVENUE),
             video_starts=action(row.get("video_play_actions"), ["video_view"]),
             p25=action(row.get("video_p25_watched_actions"), ["video_view"]),
             p50=action(row.get("video_p50_watched_actions"), ["video_view"]),
             p75=action(row.get("video_p75_watched_actions"), ["video_view"]),
             p100=action(row.get("video_p100_watched_actions"), ["video_view"]),
             thruplays=action(row.get("video_thruplay_watched_actions"), ["video_view"]),
             avg_watch_time=action(row.get("video_avg_time_watched_actions"), ["video_view"]),
             views_2s=action(row.get("video_continuous_2_sec_watched_actions"), ["video_view"]))
    r["views"] = r["views_3s"]
    r["conversions"] = r["purchases"] or r["leads"]
    if r["revenue"] is None and row.get("purchase_roas") and r["spend"]:
        roas = action(row["purchase_roas"], REVENUE)
        r["revenue"] = roas * r["spend"] if roas is not None else None
    return r


def pull(cfg, errors):
    days = (cfg.get("perf") or {}).get("days", 28)
    until = date.today() - timedelta(days=1)
    tr = json.dumps({"since": (until - timedelta(days=days - 1)).isoformat(), "until": until.isoformat()})
    base = {"level": "ad", "time_range": tr}
    rows = insights({**base, "fields": ",".join(CORE + VIDEO)}, errors)
    if isinstance(rows, dict):           # a field was rejected: core fields only
        errors.append(f"meta ads: full field set rejected ({rows['_error'][:160]}); retried without video fields")
        rows = insights({**base, "fields": ",".join(CORE)}, errors)
        if isinstance(rows, dict):
            errors.append(f"meta ads insights: {rows['_error']}")
            return []
    rows = rows or []
    recs = {r["key"]: r for r in (normalize(x) for x in rows)}
    daily = insights({**base, "time_increment": 1, "fields": ",".join(DAILY)}, errors)
    if isinstance(daily, list):
        for d in daily:
            k = f"meta_ads:{d.get('ad_id')}"
            if k in recs:
                recs[k]["daily"] = (recs[k]["daily"] or []) + [{
                    "date": d.get("date_start"), "impressions": _num(d.get("impressions")), "reach": _num(d.get("reach")),
                    "frequency": _num(d.get("frequency")), "clicks": _num(d.get("clicks")),
                    "link_clicks": _num(d.get("inline_link_clicks")), "spend": _num(d.get("spend"))}]
    ids = [r["id"] for r in recs.values()]
    for i in range(0, len(ids), 50):
        d = _get("", {"ids": ",".join(ids[i:i + 50]), "fields": "creative{id,name,thumbnail_url,video_id}"}, errors)
        if not d or "_error" in d:
            continue
        for ad_id, v in d.items():
            c = (v or {}).get("creative") or {}
            r = recs.get(f"meta_ads:{ad_id}")
            if r:
                r["creative_id"], r["thumbnail"] = c.get("id"), c.get("thumbnail_url")
                if c.get("video_id"):
                    vd = _get(c["video_id"], {"fields": "length"}, [])
                    if vd and "_error" not in vd and vd.get("length"):
                        r["duration"] = _num(vd["length"])
    return list(recs.values())
