"""Trending hashtags (what Creative Center, Exolyt and Virlo show) through legitimate sources only.

1. TikTok trends via an Apify actor of your choice (paid):  APIFY_TOKEN + APIFY_TRENDS_ACTOR
   Profile: trends: {apify_input: {...actor input, e.g. country/period...}}
2. Instagram hashtag top posts via the official Graph API (free, business account): IG_GRAPH_TOKEN + IG_GRAPH_USER_ID
   Profile: trends: {instagram_hashtags: [tag1, tag2]}. Meta allows 30 unique hashtags per 7 days; we count them.
"""
import os
import re
from datetime import datetime, timedelta, timezone

import requests

from . import usage
from .models import Item

GRAPH = "https://graph.facebook.com/v21.0"


def tiktok_trends(cfg, errors):
    """Rows: {hashtag, views, posts, rank, on_topic}. Field names vary per actor, so we read them loosely."""
    actor, token = os.environ.get("APIFY_TRENDS_ACTOR"), os.environ.get("APIFY_TOKEN")
    if not (actor and token):
        return None
    payload = (cfg.get("trends") or {}).get("apify_input") or {}
    try:
        r = requests.post(f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items",
                          params={"token": token}, json=payload, timeout=300)
        if not r.ok:
            errors.append(f"trends (Apify {actor}): HTTP {r.status_code} {r.text[:150]}")
            return []
        rows = r.json() if isinstance(r.json(), list) else []
    except (requests.RequestException, ValueError) as err:
        errors.append(f"trends (Apify): {err}")
        return []
    usage.add("apify_items", len(rows))
    must = re.compile(cfg["filters"]["must_match"], re.I) if cfg["filters"].get("must_match") else None
    out = []
    for i, row in enumerate(rows):
        tag = row.get("hashtag") or row.get("hashtagName") or row.get("name") or row.get("title") or ""
        if not tag:
            continue
        views = row.get("videoViews") or row.get("views") or row.get("viewCount")
        posts = row.get("publishCnt") or row.get("posts") or row.get("videoCount")
        out.append({"hashtag": str(tag).lstrip("#"), "views": views, "posts": posts,
                    "rank": row.get("rank") or i + 1, "on_topic": bool(must and must.search(str(tag)))})
    return out


def _weekly_tags(store):
    store.db.execute("create table if not exists ig_hashtags (tag text, ts text)")
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    return {r[0] for r in store.db.execute("select distinct tag from ig_hashtags where ts>=?", (since,))}


def instagram_top(cfg, store, errors):
    tok, uid = os.environ.get("IG_GRAPH_TOKEN"), os.environ.get("IG_GRAPH_USER_ID")
    tags = [t.lstrip("#").lower() for t in (cfg.get("trends") or {}).get("instagram_hashtags") or []]
    if not (tok and uid and tags):
        return None
    used = _weekly_tags(store)
    items = []
    for tag in tags:
        if tag not in used and len(used) >= 30:
            errors.append(f"instagram #{tag}: skipped, 30 hashtags in 7 days used (Meta limit)")
            continue
        try:
            r = requests.get(f"{GRAPH}/ig_hashtag_search", params={"user_id": uid, "q": tag, "access_token": tok},
                             timeout=30).json()
            hid = (r.get("data") or [{}])[0].get("id")
            if not hid:
                errors.append(f"instagram #{tag}: {r.get('error', {}).get('message', 'no id')}")
                continue
            if tag not in used:
                store.db.execute("insert into ig_hashtags values (?,?)", (tag, datetime.now(timezone.utc).isoformat()))
                used.add(tag)
            m = requests.get(f"{GRAPH}/{hid}/top_media", params={
                "user_id": uid, "access_token": tok, "limit": 30,
                "fields": "id,caption,like_count,comments_count,media_type,media_product_type,permalink,timestamp"},
                timeout=30).json()
        except (requests.RequestException, ValueError) as err:
            errors.append(f"instagram #{tag}: {err}")
            continue
        for x in m.get("data") or []:
            if x.get("media_type") != "VIDEO" and x.get("media_product_type") != "REELS":
                continue
            ts = x.get("timestamp")
            items.append(Item(platform="instagram", id=x["id"], url=x.get("permalink", ""),
                              title=(x.get("caption") or "").split("\n")[0][:140], likes=x.get("like_count"),
                              comments=x.get("comments_count"),
                              published=datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z") if ts else None,
                              found_by=[f"instagram #{tag} top"]))
    store.commit()
    return items
