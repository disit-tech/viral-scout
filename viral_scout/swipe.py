"""Swipe file: one Obsidian note per saved post, plus a Bases view to work through them by status."""
import re
from datetime import datetime
from pathlib import Path

from .report import n, x

BASE = """filters:
  and:
    - 'type == "swipe"'
    - 'profile == "{profile}"'
properties:
  formula.views_k:
    displayName: "Views (K)"
formulas:
  views_k: 'if(views, (views / 1000).round(1), "")'
views:
  - type: table
    name: Swipe file
    groupBy:
      property: status
      direction: ASC
    order:
      - file.name
      - status
      - format
      - platform
      - creator
      - formula.views_k
      - outlier
      - hook
      - saved
  - type: cards
    name: Cards
    image: note.thumbnail
    order:
      - file.name
      - status
      - hook
"""

STATUSES = "idea → scripted → filmed → posted (or skip)"


def slug(text, max_len=60):
    s = re.sub(r"#\S+", "", text or "")
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE).strip().lower()
    s = re.sub(r"[\s_-]+", "-", s)
    return s[:max_len].strip("-") or "post"


def _yaml(v):
    if v is None:
        return '""'
    if isinstance(v, (int, float)):
        return str(round(v, 2) if isinstance(v, float) else v)
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def write(cfg, item, note=""):
    folder = Path(cfg.get("swipe_dir") or (Path(cfg["output_dir"]) / "swipe"))
    folder.mkdir(parents=True, exist_ok=True)
    base = folder / "swipe.base"
    if not base.exists():
        base.write_text(BASE.format(profile=cfg["name"]), encoding="utf-8")
    path = folder / f"{slug(item.title or item.id)}-{item.id[-6:]}.md"
    existing = list(folder.glob(f"*-{item.id[-6:]}.md"))
    if existing:
        # Never overwrite a note someone may have edited; only add a transcript that was missing.
        path = existing[0]
        text = path.read_text(encoding="utf-8")
        if item.transcript and "## Transcript" not in text:
            if item.hook:
                text = re.sub(r'^hook: ""$', f"hook: {_yaml(item.hook)}", text, count=1, flags=re.M)
            text = text.rstrip() + "\n\n## Transcript\n\n" + item.transcript + "\n"
            path.write_text(text, encoding="utf-8")
        return path
    fm = {
        "type": "swipe", "profile": cfg["name"], "status": "idea", "format": "", "platform": item.platform,
        "url": item.url, "post_id": item.id, "creator": item.channel, "creator_url": item.channel_url,
        "views": item.views, "likes": item.likes, "comments": item.comments, "followers": item.followers,
        "outlier": round(item.outlier, 1) if item.outlier else None, "per_day": round(item.per_day) if item.per_day else None,
        "published": item.published.date().isoformat() if item.published else None,
        "saved": datetime.now().date().isoformat(), "hook": item.hook, "thumbnail": item.thumbnail,
    }
    lines = ["---"] + [f"{k}: {_yaml(v)}" for k, v in fm.items()] + ["tags: [swipe]", "---", ""]
    lines += [f"# {item.title or item.id}", "",
              f"[{item.platform} post]({item.url}) by [{item.channel}]({item.channel_url}) · "
              f"{n(item.reach)} {'views' if item.views is not None else '♥'} · {n(item.per_day)}/day · "
              f"{x(item.outlier)} usual {item.label}".rstrip(), ""]
    if item.thumbnail:
        lines += [f"![thumbnail|240]({item.thumbnail})", ""]
    if item.hook:
        lines += [f"> **Hook:** {item.hook}", ""]
    lines += ["## Why it works", "", note or "_Format, hook type, structure, why people watch to the end._", "",
              "## Our version", "", "_How we'd film this for our audience._", "",
              f"Status: {STATUSES}. Change `status` above.", ""]
    if item.transcript:
        lines += ["## Transcript", "", item.transcript, ""]
    elif item.description:
        lines += ["## Caption", "", item.description, ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
