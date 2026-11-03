"""TikTok through an Apify actor (paid per result; TikTok blocks plain scraping and yt-dlp's profile/tag lists).

  APIFY_TOKEN        your Apify API token
  APIFY_TIKTOK_ACTOR actor id, default clockworks~tiktok-scraper
Without the token this source is skipped. Single TikTok links still work through yt-dlp as seeds.
"""
import os
import statistics

import requests

from ..models import Item, parse_date

DEFAULT_ACTOR = "clockworks~tiktok-scraper"


def available():
    return bool(os.environ.get("APIFY_TOKEN"))


def _run(payload, label, errors):
    actor = os.environ.get("APIFY_TIKTOK_ACTOR", DEFAULT_ACTOR)
    url = f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
    try:
        r = requests.post(url, params={"token": os.environ["APIFY_TOKEN"]}, json=payload, timeout=300)
        if r.status_code >= 400:
            errors.append(f"{label}: Apify HTTP {r.status_code} {r.text[:200]}")
            return []
        return r.json()
    except (requests.RequestException, ValueError) as err:
        errors.append(f"{label}: {err}")
        return []


def _item(d, found_by):
    author = d.get("authorMeta") or {}
    handle = author.get("name") or ""
    return Item(
        platform="tiktok", id=str(d.get("id")), url=d.get("webVideoUrl") or "",
        title=(d.get("text") or "").split("\n")[0][:140],
        channel="@" + handle if handle else "", channel_url=f"https://www.tiktok.com/@{handle}" if handle else "",
        followers=author.get("fans"), views=d.get("playCount"), likes=d.get("diggCount"),
        comments=d.get("commentCount"), duration=(d.get("videoMeta") or {}).get("duration"),
        published=parse_date(d.get("createTimeISO") and int(_iso(d["createTimeISO"])) or d.get("createTime")),
        found_by=[found_by],
    )


def _iso(s):
    from datetime import datetime
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def discover(hashtags, keywords, per_query=30, errors=None):
    errors = errors if errors is not None else []
    out = []
    if hashtags:
        for d in _run({"hashtags": [h.lstrip("#") for h in hashtags], "resultsPerPage": per_query,
                       "shouldDownloadVideos": False, "shouldDownloadCovers": False}, "tiktok hashtags", errors):
            out.append(_item(d, "tiktok #" + ",".join(h.lstrip("#") for h in hashtags)[:60]))
    if keywords:
        for d in _run({"searchQueries": keywords, "resultsPerPage": per_query, "searchSection": "/video",
                       "shouldDownloadVideos": False, "shouldDownloadCovers": False}, "tiktok search", errors):
            out.append(_item(d, "tiktok search"))
    return out


def watch(usernames, limit=30, errors=None):
    errors = errors if errors is not None else []
    if not usernames:
        return []
    rows = _run({"profiles": [u.lstrip("@") for u in usernames], "resultsPerPage": limit,
                 "shouldDownloadVideos": False, "shouldDownloadCovers": False}, "watch tiktok", errors)
    items = [_item(d, "watch tiktok " + ((d.get("authorMeta") or {}).get("name") or "")) for d in rows]
    by = {}
    for i in items:
        by.setdefault(i.channel, []).append(i)
    for group in by.values():
        v = [i.views for i in group if i.views]
        med = statistics.median(v) if len(v) >= 3 else None
        for i in group:
            i.channel_median = med
    return items
