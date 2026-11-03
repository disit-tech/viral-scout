"""Transcripts and hooks for the posts that make the report.

YouTube: the public caption track yt-dlp lists (json3). Instagram/TikTok: no public captions, so the post's
caption text stands in. The hook is what's said in the first few seconds, the part that decides whether people stay.
"""
import re

import requests

from .models import Item

HOOK_SECONDS = 4.0
HOOK_MAX_WORDS = 25
CTA_SECONDS = 5.0


def _clean(text):
    text = re.sub(r"\[(?:music|музыка|музика|applause)\]", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def split(segments, duration=None):
    """[(start_s, text)] → dict(transcript, hook, cta, wpm). Hook = first 4 s, CTA = last 5 s (Apify-style)."""
    segments = [(t, x) for t, x in segments if x and x.strip()]
    if not segments:
        return {"transcript": "", "hook": "", "cta": "", "wpm": None}
    full = _clean(" ".join(x for _, x in segments))
    hook = _clean(" ".join(x for t, x in segments if t < HOOK_SECONDS)) or _clean(segments[0][1])
    end = duration or segments[-1][0] + 2
    cta = _clean(" ".join(x for t, x in segments if t >= end - CTA_SECONDS)) if end > 2 * CTA_SECONDS else ""
    words = hook.split()
    if len(words) > HOOK_MAX_WORDS:
        hook = " ".join(words[:HOOK_MAX_WORDS]) + "…"
    span = max(end - segments[0][0], 1)
    wpm = round(len(full.split()) / span * 60) if span >= 5 else None
    return {"transcript": full[:4000], "hook": hook, "cta": cta[:300] if cta != hook else "", "wpm": wpm}


def from_json3(data, duration=None):
    """json3 caption events → split()."""
    segs = []
    for ev in data.get("events") or []:
        seg = "".join(s.get("utf8", "") for s in ev.get("segs") or [])
        if seg.strip():
            segs.append(((ev.get("tStartMs") or 0) / 1000, seg))
    return split(segs, duration)


def apply(item, parts):
    item.transcript, item.hook, item.cta, item.wpm = parts["transcript"], parts["hook"], parts["cta"], parts["wpm"]


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
                apply(item, from_json3(r.json(), item.duration))
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
