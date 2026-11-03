"""Instagram accounts through the official Instagram Graph API (Business Discovery).

Needs a Facebook app and an Instagram Business/Creator account of your own:
  IG_GRAPH_TOKEN   long-lived access token with instagram_basic + pages_read_engagement
  IG_GRAPH_USER_ID your Instagram business account id
Business Discovery returns another professional account's followers and recent media with likes and comments.
It does not return view counts, so likes are the reach signal. Personal (non-professional) accounts can't be read.
Without the token this source is skipped. We never call Instagram's private web API.
"""
import os
import statistics
from datetime import datetime

import requests

from ..models import Item

API = "https://graph.facebook.com/v21.0"


def available():
    return bool(os.environ.get("IG_GRAPH_TOKEN") and os.environ.get("IG_GRAPH_USER_ID"))


def watch(username, limit=25, errors=None):
    errors = errors if errors is not None else []
    username = username.lstrip("@")
    fields = (f"business_discovery.username({username})"
              f"{{username,followers_count,media.limit({limit})"
              f"{{id,permalink,caption,like_count,comments_count,timestamp,media_type,media_product_type}}}}")
    try:
        r = requests.get(f"{API}/{os.environ['IG_GRAPH_USER_ID']}",
                         params={"fields": fields, "access_token": os.environ["IG_GRAPH_TOKEN"]}, timeout=30)
        data = r.json()
    except (requests.RequestException, ValueError) as err:
        errors.append(f"watch instagram @{username}: {err}")
        return []
    if "error" in data:
        errors.append(f"watch instagram @{username}: {data['error'].get('message')}")
        return []
    bd = data.get("business_discovery") or {}
    out = []
    for m in (bd.get("media") or {}).get("data") or []:
        if m.get("media_type") != "VIDEO" and m.get("media_product_type") != "REELS":
            continue
        ts = m.get("timestamp")
        out.append(Item(
            platform="instagram", id=m["id"], url=m.get("permalink", ""),
            title=(m.get("caption") or "").split("\n")[0][:140],
            channel="@" + username, channel_url=f"https://www.instagram.com/{username}/",
            followers=bd.get("followers_count"), likes=m.get("like_count"), comments=m.get("comments_count"),
            published=datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z") if ts else None,
            found_by=[f"watch instagram @{username}"],
        ))
    likes = [i.likes for i in out if i.likes]
    med = statistics.median(likes) if len(likes) >= 3 else None
    for i in out:   # no views on Instagram: compare likes with the account's median likes
        i.channel_median = med
    return out
