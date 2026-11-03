"""Markdown report (Obsidian-friendly) + JSON for other tools."""
import json
from datetime import datetime
from pathlib import Path

from .ytdlp import VERSION


def n(v):
    if v is None:
        return "—"
    v = float(v)
    for unit, d in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(v) >= d:
            return f"{v / d:.1f}{unit}".replace(".0", "")
    return f"{v:.0f}"


def x(v):
    return "—" if v is None else f"{v:.1f}×"


def pct(v):
    return "—" if v is None else f"{v * 100:.1f}%"


def age(it):
    a = it.age_days
    if a is None:
        return "—"
    return f"{a * 24:.0f} h" if a < 1 else f"{a:.0f} d"


def cell(s, width=70):
    s = (s or "").replace("|", "/").replace("\n", " ").replace("[", "(").replace("]", ")").strip()
    return s if len(s) <= width else s[: width - 1] + "…"


def row(i, it, new):
    reach_label = n(it.views) if it.views is not None else f"{n(it.likes)} ♥"
    creator = f"[{cell(it.channel, 30)}]({it.channel_url})" if it.channel_url else cell(it.channel, 30)
    flag = " 🆕" if it.key in new else ""
    return (f"| {i} | [{cell(it.title) or it.id}]({it.url}){flag} | {creator} | {it.platform} | {reach_label} | "
            f"{n(it.per_day)} | {n(it.rise_per_day)} | {x(it.outlier)} | {pct(it.engagement)} | {age(it)} | "
            f"{cell(', '.join(it.found_by), 40)} |")


HEAD = ("| # | Post | Creator | Platform | Views | Per day | Rise/day | × usual | Engagement | Age | Found by |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|")


def table(items, new):
    if not items:
        return "_Nothing here this run._\n"
    return HEAD + "\n" + "\n".join(row(i + 1, it, new) for i, it in enumerate(items)) + "\n"


def write(cfg, res):
    items, new, top = res["items"], res["new"], cfg["report"]["top"]
    tracked, watched = res["tracked"], res["watched"]
    now = datetime.now()
    disc = [i for i in items if i.key not in tracked and i.key not in watched]

    by_day = sorted([i for i in disc if i.per_day], key=lambda i: i.per_day, reverse=True)[:top]
    outliers = sorted([i for i in items if (i.outlier or 0) >= 3 and i.key not in tracked],
                      key=lambda i: i.outlier, reverse=True)[:top]
    rising = sorted([i for i in items if i.rise_per_day], key=lambda i: i.rise_per_day, reverse=True)[:top]
    seeds = sorted([i for i in items if i.key in tracked], key=lambda i: i.reach or 0, reverse=True)

    lines = [
        "---", "type: report", f"profile: {cfg['name']}", f"date: {now:%Y-%m-%d}", "tags: [viral-scout]", "---", "",
        f"# Viral scout: {cfg['name']}, {now:%Y-%m-%d %H:%M}", "",
        f"{len(items)} posts checked. {len(new)} new since the last run. Sources: YouTube search and hashtags "
        f"({cfg['discover']['youtube']['window']}), {len(cfg['watch']['youtube'])} watched YouTube channels, "
        f"{len(seeds)} tracked links. yt-dlp {VERSION}.", "",
        "How to read it: **Per day** = views (or ♥ likes where views are hidden) divided by age. "
        "**Rise/day** = growth since our previous run, the best sign that something is taking off *now*. "
        "**× usual** = views compared with the creator's median post (or with their follower count). "
        "3× or more is an outlier: the format worked, not just the account.", "",
        "## Rising now (growth since the last run)", "",
        table(rising, new) if rising else "_Needs a second run to measure growth._\n",
        "## Fastest new posts on the topic (independent search)", "", table(by_day, new),
        "## Outliers: far above the creator's usual", "", table(outliers, new),
        "## Tracked links", "", table(seeds, new),
    ]
    if res["repeat_creators"]:
        lines += ["## Creators who keep showing up (candidates for the watch list)", "",
                  ", ".join(res["repeat_creators"]), ""]
    if res["skipped"]:
        lines += ["## Skipped sources", ""] + [f"- {s}" for s in res["skipped"]] + [""]
    if res["errors"]:
        lines += ["## Errors", ""] + [f"- {cell(e, 200)}" for e in res["errors"][:30]] + [""]

    out = Path(cfg["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    md = out / f"{now:%Y-%m-%d}-viral-scout.md"
    md.write_text("\n".join(lines), encoding="utf-8")

    def js(it):
        return {"platform": it.platform, "id": it.id, "url": it.url, "title": it.title, "channel": it.channel,
                "channel_url": it.channel_url, "followers": it.followers, "views": it.views, "likes": it.likes,
                "comments": it.comments, "published": it.published.isoformat() if it.published else None,
                "per_day": it.per_day, "rise_per_day": it.rise_per_day, "outlier": it.outlier,
                "engagement": it.engagement, "found_by": it.found_by, "new": it.key in new,
                "tracked": it.key in tracked, "watched": it.key in watched}

    data = Path(cfg["db"]).parent / f"{cfg['name']}-latest.json"
    data.write_text(json.dumps({"date": now.isoformat(), "items": [js(i) for i in items],
                                "skipped": res["skipped"], "errors": res["errors"]}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return str(md), str(data)
