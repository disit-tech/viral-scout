"""YouTube via yt-dlp, no login and no API key.

discover(): keyword search filtered by upload date (+ Shorts length) and sorted by views, plus hashtag feeds.
watch():    a channel's latest Shorts/videos, with the channel median so outliers stand out.
enrich():   full numbers for one video (likes, comments, date, subscribers).
"""
import base64
import statistics
import time
from urllib.parse import quote_plus

from ..models import Item, parse_date
from ..ytdlp import extract

# YouTube search filter ("sp") is a small protobuf: sort=view count, upload date window, duration.
_UPLOAD = {"hour": 1, "today": 2, "week": 3, "month": 4, "year": 5}


def _sp(window="week", short=True):
    filt = bytes([0x08, _UPLOAD[window]]) + (bytes([0x18, 0x01]) if short else b"")
    raw = bytes([0x08, 0x03, 0x12, len(filt)]) + filt     # 08 03 = sort by view count
    return base64.urlsafe_b64encode(raw).decode()


def _item_from_entry(e, found_by):
    vid = e.get("id")
    if not vid or e.get("ie_key") not in (None, "Youtube") and "youtube" not in (e.get("url") or ""):
        return None
    url = e.get("webpage_url") or e.get("url") or f"https://www.youtube.com/watch?v={vid}"
    if "/shorts/" not in url and (e.get("duration") or 999) <= 180:
        url = f"https://www.youtube.com/shorts/{vid}"
    return Item(
        platform="youtube", id=vid, url=url, title=e.get("title") or "",
        channel=e.get("channel") or e.get("uploader") or "", channel_id=e.get("channel_id") or "",
        channel_url=e.get("channel_url") or e.get("uploader_url") or "",
        views=e.get("view_count"), duration=e.get("duration"),
        published=parse_date(e.get("timestamp") or e.get("upload_date")), found_by=[found_by],
    )


def _list(url, found_by, limit, errors):
    try:
        info = extract(url, flat=True, limit=limit)
    except RuntimeError as err:
        errors.append(f"{found_by}: {err}")
        return []
    out = []
    for e in (info or {}).get("entries") or []:
        it = _item_from_entry(e, found_by)
        if it:
            out.append(it)
    return out


def discover(keywords, hashtags, window="week", shorts=True, per_query=30, errors=None):
    errors = errors if errors is not None else []
    items = []
    sp = _sp(window, shorts)
    for kw in keywords:
        url = f"https://www.youtube.com/results?search_query={quote_plus(kw)}&sp={sp}"
        items += _list(url, f"youtube search: {kw}", per_query, errors)
        time.sleep(0.5)
    for tag in hashtags:
        tag = tag.lstrip("#").replace(" ", "").lower()
        url = f"https://www.youtube.com/hashtag/{quote_plus(tag)}" + ("/shorts" if shorts else "")
        items += _list(url, f"youtube #{tag}", per_query, errors)
        time.sleep(0.5)
    return items


def channel_recent(channel, limit=30, errors=None):
    """Latest Shorts (falls back to videos) of a channel: @handle, channel URL or channel id."""
    errors = errors if errors is not None else []
    base = channel
    if channel.startswith("@"):
        base = f"https://www.youtube.com/{channel}"
    elif channel.startswith("UC") and "/" not in channel:
        base = f"https://www.youtube.com/channel/{channel}"
    base = base.rstrip("/")
    for tab in ("shorts", "videos"):
        found = _list(f"{base}/{tab}", f"watch youtube {channel}", limit, [])
        if found:
            return found
    errors.append(f"watch youtube {channel}: no videos found")
    return []


def median_views(items):
    v = [i.views for i in items if i.views]
    return statistics.median(v) if len(v) >= 3 else None


BLOCKED = {"hit": False}      # set once YouTube asks to "confirm you're not a bot": stop opening videos this run


def enrich(item, errors=None):
    """Fill likes/comments/date/subscribers from the video page. Returns True on success."""
    errors = errors if errors is not None else []
    if BLOCKED["hit"]:
        return False
    try:
        info = extract(f"https://www.youtube.com/watch?v={item.id}")
    except RuntimeError as err:
        msg = str(err)
        if "not a bot" in msg or "429" in msg:
            BLOCKED["hit"] = True
            errors.append("youtube: bot check / rate limit hit, stopped opening videos for this run "
                          "(too many runs close together; it clears after a few hours)")
        else:
            errors.append(f"youtube {item.id}: {msg[:160]}")
        return False
    item.views = info.get("view_count") or item.views
    item.likes = info.get("like_count")
    item.comments = info.get("comment_count")
    item.followers = info.get("channel_follower_count")
    item.duration = info.get("duration") or item.duration
    item.published = parse_date(info.get("timestamp") or info.get("upload_date")) or item.published
    item.title = info.get("title") or item.title
    item.channel = info.get("channel") or item.channel
    item.channel_id = info.get("channel_id") or item.channel_id
    item.channel_url = info.get("channel_url") or item.channel_url
    item.description = (info.get("description") or "")[:2000]
    item.caption_url = caption_url(info)
    return True


def caption_url(info):
    """URL of the public json3 caption track in the video's own language (manual first, then auto).
    AI-dubbed videos list many "-orig" tracks, so the video's language goes first."""
    lang = (info.get("language") or "").split("-")[0].lower()
    prefs = [f"{lang}-orig", lang] if lang else []
    prefs += ["en-orig", "en", "ru-orig", "ru", "uk-orig", "uk", "es-orig", "es"]
    for tracks in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
        for k in [p for p in prefs if p in tracks] + sorted(k for k in tracks if k.endswith("-orig")):
            for t in tracks.get(k) or []:
                if t.get("ext") == "json3" and t.get("url"):
                    return t["url"]
    return ""
