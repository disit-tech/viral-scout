"""Local copies of thumbnails / first frames for the posts in the report.

Many Shorts and reels put the hook on screen as text ("CRISPS vs FRIES vs CHIPS"), not in speech. The /viral-scout
skill reads these images with Claude's vision to pull out on-screen text and the visual format; no OCR install needed.
Instagram/TikTok thumbnail URLs expire, so a local copy is the only way to look at them later.
"""
from pathlib import Path

import requests

from . import config


def folder(cfg):
    p = config.ROOT / "data" / "frames" / cfg["name"]
    p.mkdir(parents=True, exist_ok=True)
    return p


def fetch(cfg, item, errors):
    if item.frame and Path(item.frame).exists():
        return item.frame
    url = item.thumbnail
    if not url:
        return ""
    if item.platform == "youtube":
        url = f"https://i.ytimg.com/vi/{item.id}/hq720.jpg"   # larger, still public; falls back below
    path = folder(cfg) / f"{item.platform}-{item.id}.jpg"
    if not path.exists():
        for u in (url, item.thumbnail):
            try:
                r = requests.get(u, timeout=20)
                if r.ok and r.headers.get("content-type", "").startswith("image"):
                    path.write_bytes(r.content)
                    break
            except requests.RequestException as err:
                errors.append(f"frame {item.key}: {err}")
    item.frame = str(path) if path.exists() else ""
    return item.frame
