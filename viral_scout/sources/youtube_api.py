"""YouTube Data API v3 search: the reliable way to find Shorts by keyword (yt-dlp can't read Shorts search results).

  YOUTUBE_API_KEY  a free key from Google Cloud (APIs & Services → enable "YouTube Data API v3" → Credentials).
Quota: 10,000 units/day free. One keyword = 100 (search) + 1 (video stats) + 1 (channel stats) ≈ 102 units.
"""
import os
from datetime import datetime, timedelta, timezone

import requests

from ..models import Item

API = "https://www.googleapis.com/youtube/v3"
WINDOW_DAYS = {"hour": 1 / 24, "today": 1, "week": 7, "month": 30, "year": 365}


def available():
    return bool(os.environ.get("YOUTUBE_API_KEY"))


def _get(path, params, errors, label):
    params = dict(params, key=os.environ["YOUTUBE_API_KEY"])
    try:
        r = requests.get(f"{API}/{path}", params=params, timeout=30)
        data = r.json()
    except (requests.RequestException, ValueError) as err:
        errors.append(f"{label}: {err}")
        return {}
    if "error" in data:
        errors.append(f"{label}: {data['error'].get('message')}")
        return {}
    return data


def _seconds(iso):
    """PT1M5S → 65."""
    import re
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def discover(keywords, window="week", shorts=True, per_query=30, languages=None, region=None, errors=None):
    errors = errors if errors is not None else []
    after = (datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS.get(window, 7))).strftime("%Y-%m-%dT%H:%M:%SZ")
    found = {}   # video id -> found_by
    for kw in keywords:
        params = {"part": "snippet", "q": kw, "type": "video", "order": "viewCount", "publishedAfter": after,
                  "maxResults": min(per_query, 50)}
        if shorts:
            params["videoDuration"] = "short"     # under 4 minutes
        if region:
            params["regionCode"] = region
        lang = (languages or {}).get(kw) if isinstance(languages, dict) else None
        if lang:
            params["relevanceLanguage"] = lang
        data = _get("search", params, errors, f"youtube api search: {kw}")
        for r in data.get("items") or []:
            vid = (r.get("id") or {}).get("videoId")
            if vid:
                found.setdefault(vid, []).append(f"youtube api: {kw}")
    return _videos(found, errors)


def _videos(found, errors):
    items, ids = [], list(found)
    for i in range(0, len(ids), 50):
        data = _get("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(ids[i:i + 50])},
                    errors, "youtube api videos")
        for v in data.get("items") or []:
            sn, st = v.get("snippet") or {}, v.get("statistics") or {}
            dur = _seconds((v.get("contentDetails") or {}).get("duration"))
            vid = v["id"]
            items.append(Item(
                platform="youtube", id=vid,
                url=f"https://www.youtube.com/shorts/{vid}" if dur and dur <= 180 else f"https://www.youtube.com/watch?v={vid}",
                title=sn.get("title") or "", channel=sn.get("channelTitle") or "", channel_id=sn.get("channelId") or "",
                channel_url=f"https://www.youtube.com/channel/{sn.get('channelId')}",
                views=int(st["viewCount"]) if "viewCount" in st else None,
                likes=int(st["likeCount"]) if "likeCount" in st else None,
                comments=int(st["commentCount"]) if "commentCount" in st else None,
                duration=dur,
                published=datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00")) if sn.get("publishedAt") else None,
                found_by=found[vid],
            ))
    # Subscribers, one call per 50 channels.
    chans = list({i.channel_id for i in items if i.channel_id})
    subs = {}
    for i in range(0, len(chans), 50):
        data = _get("channels", {"part": "statistics", "id": ",".join(chans[i:i + 50])}, errors, "youtube api channels")
        for c in data.get("items") or []:
            sc = (c.get("statistics") or {}).get("subscriberCount")
            if sc is not None:
                subs[c["id"]] = int(sc)
    for it in items:
        it.followers = subs.get(it.channel_id)
    return items
