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
    flag = (" 🆕" if it.key in new else "") + (" ⏳" if it.early else "")
    usual = x(it.outlier) + (f" {it.label}" if it.label else "")
    return (f"| {i} | [{cell(it.title) or it.id}]({it.url}){flag} | {creator} | {it.platform} | {reach_label} | "
            f"{n(it.per_day)} | {n(it.rise_per_day)} | {usual} | {pct(it.engagement)} | {age(it)} | "
            f"`{it.id}` |")


HEAD = ("| # | Post | Creator | Platform | Views | Per day | Rise/day | × usual | Engagement | Age | ID |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|")


def table(items, new):
    if not items:
        return "_Nothing here this run._\n"
    return HEAD + "\n" + "\n".join(row(i + 1, it, new) for i, it in enumerate(items)) + "\n"


def sections(items, tracked, watched, top):
    items = [i for i in items if not getattr(i, "dismissed", False)]
    disc = [i for i in items if i.key not in tracked and i.key not in watched]
    return {
        "own": sorted([i for i in items if i.own], key=lambda i: -(i.outlier or 0)),
        "by_day": sorted([i for i in disc if i.per_day], key=lambda i: i.per_day, reverse=True)[:top],
        "outliers": sorted([i for i in items if (i.outlier or 0) >= 3 and i.key not in tracked and not i.own],
                           key=lambda i: i.weighted, reverse=True)[:top],
        "rising": sorted([i for i in items if i.rise_per_day], key=lambda i: i.rise_per_day, reverse=True)[:top],
        "seeds": sorted([i for i in items if i.key in tracked], key=lambda i: i.reach or 0, reverse=True),
    }


def hooks(items, new, limit):
    """Hook + transcript excerpt for the strongest posts, as Obsidian callouts."""
    out = []
    for it in [i for i in items if i.hook or i.transcript][:limit]:
        out.append(f"### [{cell(it.title, 90) or it.id}]({it.url})")
        out.append(f"{cell(it.channel, 40)} · {it.platform} · {n(it.reach)} {'views' if it.views is not None else '♥'}"
                   f" · {n(it.per_day)}/day · {x(it.outlier)} usual {it.label}".rstrip()
                   + (" · 🆕" if it.key in new else "") + f" · `{it.id}`")
        out.append("")
        if it.thumbnail:
            out += [f"![thumbnail|180]({it.thumbnail})", ""]
        if it.hook:
            out.append(f"> **Hook:** {it.hook}")
            out.append("")
        if it.cta:
            out += [f"> **Ending / CTA:** {it.cta}", ""]
        extras = []
        if it.wpm:
            extras.append(f"{it.wpm} words/min")
        if it.creator_pct is not None:
            extras.append(f"beats {it.creator_pct:.0f}% of the creator's recent posts")
        if it.vs_pace:
            extras.append(f"{it.vs_pace:.1f}× the creator's usual views/day (age-matched)")
        if it.vs_topic:
            extras.append(f"{it.vs_topic:.1f}× the niche median views/day")
        if it.emerging:
            extras.append("emerging creator (<=50K followers)")
        if extras:
            out += ["_" + " · ".join(extras) + "_", ""]
        if it.transcript and it.transcript != it.hook:
            t = it.transcript if len(it.transcript) <= 700 else it.transcript[:700] + "…"
            out += ["> [!quote]- Transcript", "> " + t, ""]
    return out


def suggestions(cfg, items, limit=20):
    """Hashtags that keep appearing on hits but aren't in the profile: candidates to add."""
    import re
    from collections import Counter
    have = {h.lower().lstrip("#") for h in cfg["discover"]["youtube"]["hashtags"] + cfg["discover"]["tiktok"]["hashtags"]}
    c = Counter()
    for it in items:
        tags = {t.lower() for t in re.findall(r"#(\w+)", f"{it.title} {it.description}")}
        for t in tags - have - {"shorts", "short", "viral", "fyp", "foryou", "trending", "youtubeshorts", "reels"}:
            c[t] += 1
    return [f"#{t} ({k})" for t, k in c.most_common(limit) if k >= 2]


def write(cfg, res):
    items, new, top = res["items"], res["new"], cfg["report"]["top"]
    tracked, watched = res["tracked"], res["watched"]
    now = datetime.now()
    sec = sections(items, tracked, watched, top)
    by_day, outliers, rising, seeds = sec["by_day"], sec["outliers"], sec["rising"], sec["seeds"]

    lines = [
        "---", "type: report", f"profile: {cfg['name']}", f"date: {now:%Y-%m-%d}", "tags: [viral-scout]", "---", "",
        f"# Viral scout: {cfg['name']}, {now:%Y-%m-%d %H:%M}", "",
        f"{len(items)} posts checked. {len(new)} new since the last run. Sources: YouTube search and hashtags "
        f"({cfg['discover']['youtube']['window']}), {len(cfg['watch']['youtube'])} watched YouTube channels, "
        f"{len(seeds)} tracked links. yt-dlp {VERSION}.", "",
        "How to read it: **Per day** = views (or ♥ likes where views are hidden) divided by age. "
        "**Rise/day** = growth since our previous run, the best sign that something is taking off *now*. "
        "**× usual** = views compared with the creator's median post (or with their follower count). "
        "3× or more is an outlier: the format worked, not just the account (↑ 1.5×, ⚡ 3×, 🔥 10×). "
        "Outliers are ranked by ln(× usual) × ln(creator baseline), so one lucky post on a tiny channel doesn't top "
        "the list. ⏳ = under 6 hours old, numbers still settling.", "",
        f"Save one to the swipe file: `python -m viral_scout save {cfg['name']} <ID>`. "
        f"Hide it from future reports: `python -m viral_scout dismiss {cfg['name']} <ID>`.", "",
        "## Rising now (growth since the last run)", "",
        table(rising, new) if rising else "_Needs a second run to measure growth._\n",
        "## Fastest new posts on the topic (independent search)", "", table(by_day, new),
        "## Outliers: far above the creator's usual", "", table(outliers, new),
        "## Tracked links", "", table(seeds, new),
    ]
    if sec["own"]:
        lines += ["## Your posts vs your usual", "", table(sec["own"], new)]
    asks, seen_q = [], set()
    for it in outliers[:10] + by_day[:10]:
        for q in it.questions[:3]:
            if q not in seen_q:
                seen_q.add(q)
                asks.append(f"- \u201c{cell(q, 200)}\u201d on [{cell(it.title, 50)}]({it.url})")
    if asks:
        lines += ["## What viewers ask (from the comments)", "",
                  "Questions under the hits: ideas your audience already asked for.", ""] + asks[:20] + [""]
    strongest = []
    for it in rising[:5] + outliers[:8] + by_day[:8] + seeds:
        if it not in strongest:
            strongest.append(it)
    hk = hooks(strongest, new, cfg["report"].get("hooks", 20))
    if hk:
        lines += ["## Hooks: what the strongest posts say first", "",
                  "The first seconds decide whether people keep watching. YouTube text is the video's own captions; "
                  "Instagram/TikTok text is the post caption.", ""] + hk
    if res.get("trends"):
        lines += ["## Trending hashtags (TikTok, via Apify)", "", "| # | Hashtag | Views | Posts | On topic |",
                  "|---|---|---|---|---|"]
        lines += [f"| {t['rank']} | #{t['hashtag']} | {n(t['views'])} | {n(t['posts'])} | {'✅' if t['on_topic'] else ''} |"
                  for t in res["trends"][:30]] + [""]
    sug = suggestions(cfg, outliers + by_day + rising)
    if sug:
        lines += ["## Suggested hashtags (from this run's hits, not in the profile yet)", "", ", ".join(sug), ""]
    if res["repeat_creators"]:
        lines += ["## Creators who keep showing up (candidates for the watch list)", "",
                  ", ".join(res["repeat_creators"]), ""]
    u = res.get("usage") or {}
    if u or res.get("budget"):
        lines += ["## Usage this run", "",
                  " · ".join(f"{k.replace('_', ' ')}: {v:,}" for k, v in sorted(u.items())) or "nothing counted", ""]
        lines += [f"- ⚠️ {w}" for w in res.get("budget") or []] + [""]
    if res["skipped"]:
        lines += ["## Skipped sources", ""] + [f"- {s}" for s in res["skipped"]] + [""]
    if res["errors"]:
        lines += ["## Errors", ""] + [f"- {cell(e, 200)}" for e in res["errors"][:30]] + [""]

    out = Path(cfg["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    md = out / f"{now:%Y-%m-%d}-viral-scout.md"
    md.write_text("\n".join(lines), encoding="utf-8")

    def js(it):
        return {"key": it.key, "platform": it.platform, "id": it.id, "url": it.url, "title": it.title, "channel": it.channel,
                "channel_url": it.channel_url, "followers": it.followers, "views": it.views, "likes": it.likes,
                "comments": it.comments, "published": it.published.isoformat() if it.published else None,
                "per_day": it.per_day, "rise_per_day": it.rise_per_day, "outlier": it.outlier, "label": it.label,
                "weighted": it.weighted, "thumbnail": it.thumbnail, "duration": it.duration, "early": it.early,
                "channel_median": it.channel_median, "description": it.description[:500],
                "engagement": it.engagement, "found_by": it.found_by, "hook": it.hook,
                "transcript": it.transcript, "cta": it.cta, "wpm": it.wpm,
                "creator_pct": it.creator_pct, "frame": it.frame, "vs_pace": it.vs_pace,
                "vs_topic": it.vs_topic, "emerging": it.emerging, "own": it.own,
                "questions": it.questions, "top_comments": it.top_comments, "new": it.key in new,
                "tracked": it.key in tracked, "watched": it.key in watched}

    data = Path(cfg["db"]).parent / f"{cfg['name']}-latest.json"
    data.write_text(json.dumps({"date": now.isoformat(), "report": str(md), "items": [js(i) for i in items],
                                "sections": {k: [i.key for i in v] for k, v in sec.items()},
                                "suggested_hashtags": sug, "repeat_creators": res["repeat_creators"],
                                "skipped": res["skipped"], "errors": res["errors"],
                                "usage": res.get("usage", {}), "budget": res.get("budget", []),
                                "trends": res.get("trends", [])},
                               ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return str(md), str(data)
