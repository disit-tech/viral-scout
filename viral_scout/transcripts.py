"""Transcripts and hooks for the posts that make the report.

YouTube: the public caption track yt-dlp lists (json3). Instagram/TikTok: no public captions, so the post's
caption text stands in. The hook is what's said in the first few seconds, the part that decides whether people stay.
"""
import re

import requests

from .models import Item

HOOK_SECONDS = 4.0
HOOK_MAX_WORDS = 25


def _clean(text):
    text = re.sub(r"\[(?:music|музыка|музика|applause)\]", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def from_json3(data):
    """json3 caption events → (full transcript, hook)."""
    words_hook, parts = [], []
    for ev in data.get("events") or []:
        start = (ev.get("tStartMs") or 0) / 1000
        seg = "".join(s.get("utf8", "") for s in ev.get("segs") or [])
        if not seg.strip():
            continue
        parts.append(seg)
        if start < HOOK_SECONDS:
            words_hook.append(seg)
    full = _clean(" ".join(parts))
    hook = _clean(" ".join(words_hook)) or full
    hook_words = hook.split()
    if len(hook_words) > HOOK_MAX_WORDS:
        hook = " ".join(hook_words[:HOOK_MAX_WORDS]) + "…"
    return full, hook


class RateLimited(Exception):
    """YouTube said 429: stop fetching captions for this run, try again next run."""


def fill(item: Item, errors=None, captions=True):
    errors = errors if errors is not None else []
    if item.transcript:
        return
    if item.caption_url and captions:
        try:
            r = requests.get(item.caption_url, timeout=30)
            if r.status_code == 429:
                raise RateLimited()
            if r.ok:
                item.transcript, item.hook = from_json3(r.json())
                item.transcript = item.transcript[:4000]
                if item.transcript:
                    return
        except (requests.RequestException, ValueError) as err:
            errors.append(f"captions {item.key}: {err}")
    # No captions: the first line of the caption/description is the next best thing.
    if not item.hook:
        for line in (item.description or "").splitlines():
            words = re.sub(r"#\S+", "", line).strip()
            if len(words) >= 8:                      # skip hashtag-only and empty lines
                item.hook = _clean(words)[:200]
                break
