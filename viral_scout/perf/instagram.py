"""Your own Instagram reels: Instagram Graph API media insights (official; your own account only).

Needs IG_GRAPH_TOKEN (with instagram_basic + instagram_manage_insights + pages_read_engagement; add
instagram_manage_comments for comment sentiment) and IG_GRAPH_USER_ID.

  GET /{ig-user-id}/media                    own media, newest first
  GET /{ig-media-id}/insights?metric=...     per reel
  GET /{ig-media-id}/comments                own comments (text only, for the sentiment lexicon)

Reels metrics (checked Nov 2026, Graph API v26 docs): views, reach, likes, comments, shares, saved,
total_interactions, ig_reels_avg_watch_time (ms), ig_reels_video_view_total_time (ms), reels_skip_rate, reposts.
`impressions` and `plays` are deprecated for reels; `follows` / `profile_visits` are FEED/STORY only. If Meta
rejects a metric, we retry with smaller sets and note which ones were missing.
"""
import os

import requests

from .. import usage
from .schema import blank

API = "https://graph.facebook.com/v26.0"
FULL = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions", "ig_reels_avg_watch_time",
        "ig_reels_video_view_total_time", "reels_skip_rate", "reposts"]
FALLBACKS = [FULL,
             ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions",
              "ig_reels_avg_watch_time", "ig_reels_video_view_total_time"],
             ["reach", "likes", "comments", "shares", "saved"]]


def available():
    return bool(os.environ.get("IG_GRAPH_TOKEN") and os.environ.get("IG_GRAPH_USER_ID"))


def _get(path, params, errors):
    usage.add("ig_insights_requests")
    try:
        r = requests.get(f"{API}/{path}", params={**params, "access_token": os.environ["IG_GRAPH_TOKEN"]}, timeout=30)
        d = r.json()
    except (requests.RequestException, ValueError) as err:
        errors.append(f"instagram insights {path}: {err}")
        return None
    if "error" in d:
        return {"_error": d["error"].get("message", "error")}
    return d


def own_media(limit, errors):
    out, after = [], None
    while len(out) < limit:
        params = {"fields": "id,caption,media_type,media_product_type,permalink,timestamp,like_count,"
                            "comments_count,thumbnail_url", "limit": min(50, limit)}
        if after:
            params["after"] = after
        d = _get(f"{os.environ['IG_GRAPH_USER_ID']}/media", params, errors)
        if not d or "_error" in d:
            if d:
                errors.append(f"instagram own media: {d['_error']}")
            break
        out += d.get("data") or []
        after = ((d.get("paging") or {}).get("cursors") or {}).get("after")
        if not after or not (d.get("paging") or {}).get("next"):
            break
    return out[:limit]


def insights(media_id, sets, errors):
    """Try metric sets from fullest to smallest; returns (values, metrics used)."""
    for metrics in sets:
        d = _get(f"{media_id}/insights", {"metric": ",".join(metrics)}, errors)
        if d is None:
            return {}, []
        if "_error" not in d:
            vals = {}
            for m in d.get("data") or []:
                v = (m.get("values") or [{}])[0].get("value") if m.get("values") else m.get("total_value", {}).get("value")
                vals[m.get("name")] = v
            return vals, metrics
    errors.append(f"instagram insights {media_id}: {d['_error']}")
    return {}, []


def comments(media_id, errors, n=50):
    d = _get(f"{media_id}/comments", {"fields": "text", "limit": n}, errors)
    if not d or "_error" in d:
        return None
    return [c.get("text", "") for c in d.get("data") or []]


def pull(cfg, errors):
    pc = (cfg.get("perf") or {}).get("instagram") or {}
    media = own_media(pc.get("limit", 30), errors)
    reels = [m for m in media if m.get("media_product_type") == "REELS" or m.get("media_type") == "VIDEO"]
    sets, records, missing = list(FALLBACKS), [], set()
    for i, m in enumerate(reels):
        vals, used = insights(m["id"], sets, errors)
        if used and used != sets[0]:
            sets = [used] + [s for s in FALLBACKS if len(s) < len(used)]     # don't retry the bigger set every time
        missing |= set(FULL) - set(used)
        r = blank("instagram", "organic", m["id"], platform="instagram",
                  title=(m.get("caption") or "").split("\n")[0][:140], url=m.get("permalink"),
                  thumbnail=m.get("thumbnail_url"), published=m.get("timestamp"))
        ms = lambda k: vals[k] / 1000 if vals.get(k) is not None else None      # ms → s
        r.update(views=vals.get("views"), reach=vals.get("reach"),
                 likes=vals.get("likes", m.get("like_count")), comments=vals.get("comments", m.get("comments_count")),
                 shares=vals.get("shares"), saves=vals.get("saved"), total_interactions=vals.get("total_interactions"),
                 reposts=vals.get("reposts"), avg_watch_time=ms("ig_reels_avg_watch_time"),
                 total_watch_time=ms("ig_reels_video_view_total_time"), skip_rate_given=vals.get("reels_skip_rate"))
        if pc.get("comments", True) and i < pc.get("comment_posts", 10) and (m.get("comments_count") or 0) > 0:
            r["comment_texts"] = comments(m["id"], errors)
        r["notes"].append("Instagram doesn't return video length through the API, so avg % viewed needs a CSV "
                          "with durations.")
        records.append(r)
    if missing and reels:
        errors.append(f"instagram insights: not returned for this account/app: {', '.join(sorted(missing))}")
    return records
