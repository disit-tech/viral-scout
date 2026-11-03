"""Export everything the web dashboard needs into web/data/ (git-ignored).

Per profile: the latest run (items, sections, scores, hooks), flags from the DB (saved, dismissed, tracked),
view history for charts, the AI ideas notes and the swipe notes. Plus index.json with one summary per profile.
"""
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import yaml

from . import config

WEB_DATA = config.ROOT / "web" / "data"


def _frontmatter(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, m.group(2)


def _jsonable(v):
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def _sections(items, top):
    """Same rules as report.sections, for runs written before sections were stored."""
    live = [i for i in items if not i["dismissed"]]
    disc = [i for i in live if not i["tracked"] and not i.get("watched")]
    key = lambda f: (lambda i: -(i.get(f) or 0))
    return {
        "by_day": [i["key"] for i in sorted([i for i in disc if i.get("per_day")], key=key("per_day"))[:top]],
        "outliers": [i["key"] for i in sorted([i for i in live if (i.get("outlier") or 0) >= 3 and not i["tracked"]],
                                              key=key("weighted"))[:top]],
        "rising": [i["key"] for i in sorted([i for i in live if i.get("rise_per_day")], key=key("rise_per_day"))[:top]],
        "seeds": [i["key"] for i in sorted([i for i in live if i["tracked"]], key=key("views"))],
    }


def profile(cfg):
    latest_path = Path(cfg["db"]).parent / f"{cfg['name']}-latest.json"
    if not latest_path.exists():
        return None
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    for it in latest["items"]:
        it.setdefault("key", f"{it['platform']}:{it['id']}")

    flags, history, runs = {}, {}, []
    if Path(cfg["db"]).exists():
        db = sqlite3.connect(cfg["db"])
        cols = {r[1] for r in db.execute("pragma table_info(items)")}
        want = [c for c in ("tracked", "dismissed", "saved", "alerted", "first_seen") if c in cols]
        for row in db.execute(f"select key, {', '.join(want)} from items"):
            flags[row[0]] = dict(zip(want, row[1:]))
        keys = {i["key"] for i in latest["items"]}
        for key, ts, views, likes in db.execute("select key, ts, views, likes from snapshots order by ts"):
            if key in keys:
                history.setdefault(key, []).append([ts, views if views is not None else likes])
        runs = [{"ts": r[0], **json.loads(r[1] or "{}")}
                for r in db.execute("select ts, summary from runs order by ts desc limit 30")]

    items = []
    for it in latest["items"]:
        it.setdefault("key", f"{it['platform']}:{it['id']}")
        f = flags.get(it["key"], {})
        it = dict(it, saved=bool(f.get("saved")), dismissed=bool(f.get("dismissed")),
                  tracked=bool(f.get("tracked")) or it.get("tracked", False), first_seen=f.get("first_seen"),
                  history=history.get(it["key"], [])[-30:])
        items.append(it)

    out_dir = Path(cfg["output_dir"])
    ideas = []
    for p in sorted(out_dir.glob("*-viral-ideas.md"), reverse=True)[:12]:
        fm, body = _frontmatter(p.read_text(encoding="utf-8"))
        ideas.append({"date": str(fm.get("date") or p.name[:10]), "file": p.name, "markdown": body})
    reports = [p.name[:10] for p in sorted(out_dir.glob("*-viral-scout.md"), reverse=True)[:30]]

    swipe_dir = Path(cfg.get("swipe_dir") or (out_dir / "swipe"))
    swipe = []
    for p in sorted(swipe_dir.glob("*.md")):
        fm, body = _frontmatter(p.read_text(encoding="utf-8"))
        if fm.get("type") != "swipe":
            continue
        swipe.append(_jsonable(dict(fm, file=p.name, body=body)))

    sections = latest.get("sections") or _sections(items, cfg["report"]["top"])
    return {
        "name": cfg["name"],
        "business": (cfg.get("business") or "").strip(),
        "date": latest.get("date"),
        "items": items,
        "sections": sections,
        "suggested_hashtags": latest.get("suggested_hashtags", []),
        "repeat_creators": latest.get("repeat_creators", []),
        "skipped": latest.get("skipped", []),
        "errors": latest.get("errors", []),
        "ideas": ideas,
        "reports": reports,
        "swipe": swipe,
        "runs": runs,
        "sources": {
            "keywords": len(cfg["discover"]["youtube"]["keywords"]),
            "hashtags": len(cfg["discover"]["youtube"]["hashtags"]),
            "watch": sum(len(v) for v in cfg["watch"].values()),
            "seeds": len(cfg["seeds"]),
        },
    }


def export_all(names=None, out=WEB_DATA):
    out.mkdir(parents=True, exist_ok=True)
    if not names:
        names = [p.stem for p in config.PROFILES.glob("*.yaml") if not p.stem.startswith("_")]
    index = []
    old = out / "index.json"
    if old.exists() and names:
        try:
            index = [p for p in json.loads(old.read_text(encoding="utf-8"))["profiles"] if p["name"] not in names]
        except (ValueError, KeyError):
            index = []
    done = []
    for name in sorted(names):
        cfg = config.load(name)
        data = profile(cfg)
        if not data:
            continue
        done.append(name)
        (out / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        live = [i for i in data["items"] if not i["dismissed"]]
        top = sorted([i for i in live if (i.get("outlier") or 0) >= 3], key=lambda i: -(i.get("weighted") or 0))[:4]
        index.append({
            "name": name, "date": data["date"], "business": data["business"][:220],
            "posts": len(live), "outliers": sum(1 for i in live if (i.get("outlier") or 0) >= 3),
            "mega": sum(1 for i in live if (i.get("outlier") or 0) >= 10),
            "new": sum(1 for i in live if i.get("new")), "saved": len(data["swipe"]), "ideas": len(data["ideas"]),
            "top": [{"title": i["title"], "thumbnail": i.get("thumbnail"), "outlier": i.get("outlier"),
                     "channel": i["channel"], "url": i["url"]} for i in top],
        })
    index.sort(key=lambda p: p["name"])
    (out / "index.json").write_text(json.dumps({"exported": datetime.now().isoformat(), "profiles": index},
                                               ensure_ascii=False), encoding="utf-8")
    return out, done
