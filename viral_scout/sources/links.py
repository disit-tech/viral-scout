"""Single posts by URL (any platform yt-dlp supports): the seeds people send you, and re-checks for velocity."""
import re

from ..models import Item, parse_date
from ..ytdlp import extract


def platform_of(url):
    u = url.lower()
    if "instagram.com" in u:
        return "instagram"
    if "tiktok.com" in u:
        return "tiktok"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    return "other"


def clean_url(url):
    """Drop tracking query strings (utm_source, igsh, srtk...)."""
    return re.sub(r"\?.*$", "", url.strip()) if platform_of(url) in ("instagram", "tiktok") else url.strip()


def _title(info):
    """Instagram titles are just "Video by <user>"; the caption's first line says more."""
    t = (info.get("title") or "").strip()
    desc = (info.get("description") or "").strip()
    if desc and (not t or t.lower().startswith("video by")):
        t = desc
    return t.splitlines()[0][:140] if t else ""


def fetch(url, found_by="seed", errors=None):
    errors = errors if errors is not None else []
    url = clean_url(url)
    try:
        info = extract(url)
    except RuntimeError as err:
        errors.append(f"{url}: {err}")
        return None
    plat = platform_of(url)
    handle = info.get("channel") or info.get("uploader_id") or ""
    if plat == "instagram" and handle:
        channel_url = f"https://www.instagram.com/{handle}/"
    else:
        channel_url = info.get("channel_url") or info.get("uploader_url") or ""
    return Item(
        platform=plat, id=str(info.get("id")), url=info.get("webpage_url") or url,
        title=_title(info),
        channel=("@" + handle) if plat in ("instagram", "tiktok") and handle else (info.get("channel") or info.get("uploader") or ""),
        channel_url=channel_url, channel_id=info.get("channel_id") or "",
        followers=info.get("channel_follower_count"),
        views=info.get("view_count"), likes=info.get("like_count"), comments=info.get("comment_count"),
        duration=info.get("duration"), published=parse_date(info.get("timestamp") or info.get("upload_date")),
        found_by=[found_by],
        description=(info.get("description") or "")[:2000],
        caption_url=_caption(info),
    )


def _caption(info):
    from .youtube import caption_url
    return caption_url(info)
