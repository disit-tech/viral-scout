"""Export everything the web dashboard needs into web/data/ (git-ignored).

Per profile: the latest run (items, sections, scores, hooks), flags from the DB (saved, dismissed, tracked),
view history for charts, the AI ideas notes and the swipe notes. Plus index.json with one summary per profile.
Ads scout data goes to web/data/ads/<profile>.json (a sub-folder, so it never shows up as a profile).
Own performance (viral_scout/perf) goes to web/data/perf/<profile>.json, separate from the run data.
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
        "own": [i["key"] for i in live if i.get("own")],
    }


def profile(cfg):
    latest_path = Path(cfg["db"]).parent / f"{cfg['name']}-latest.json"
    # A business created without a run ("Create only") still gets its pages: empty, date null ("never"), and the
    # setup hints say what's needed before the first run.
    latest = json.loads(latest_path.read_text(encoding="utf-8")) if latest_path.exists() else {"items": [], "date": None}
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
                for r in db.execute("select ts, summary from runs order by ts desc limit 60")]
        runs = [r for r in runs if r.get("kind") != "ads"][:30]      # ads runs have their own page

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
    from . import scorecard
    scores = scorecard.load(cfg["name"])
    for it in items:
        if it["id"] in scores:
            it["scorecard"] = scores[it["id"]]
    checks = []
    cdir = config.ROOT / "data" / "checks" / cfg["name"]
    if cdir.exists():
        for f in sorted(cdir.glob("*/check.json"), reverse=True)[:30]:
            c = json.loads(f.read_text(encoding="utf-8"))
            c.pop("file", None)                      # local path stays local
            c["frames"] = []                         # images aren't exported
            c["scorecard"] = scores.get(f"check:{c['slug']}")
            checks.append(c)
    ads_path = Path(cfg["db"]).parent / f"{cfg['name']}-ads-latest.json"
    ads_summary = None
    if ads_path.exists():
        try:
            a = json.loads(ads_path.read_text(encoding="utf-8"))
            ads_summary = {"date": a.get("date"), "ads": len(a.get("ads") or []),
                           "advertisers": len(a.get("advertisers") or [])}
        except ValueError:
            pass
    return {
        "ads_summary": ads_summary,
        "name": cfg["name"],
        "display_name": (cfg.get("display_name") or "").strip() or None,
        "business": (cfg.get("business") or "").strip(),
        "setup": _setup(cfg),
        "date": latest.get("date"),
        "items": items,
        "sections": sections,
        "checks": checks,
        "suggested_hashtags": latest.get("suggested_hashtags", []),
        "repeat_creators": latest.get("repeat_creators", []),
        "skipped": latest.get("skipped", []),
        "usage": latest.get("usage", {}),
        "budget": latest.get("budget", []),
        "trends": latest.get("trends", []),
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


def _features(cfg):
    """One line per feature for the business card on the Businesses page (numbers only, from files on disk)."""
    base, n = Path(cfg["db"]).parent, cfg["name"]

    def read(f):
        try:
            return json.loads((base / f).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    out = {}
    a = read(f"{n}-ads-latest.json")
    if a:
        ads = a.get("ads") or []
        out["ads"] = {"ads": len(ads), "running": sum(1 for x in ads if x.get("active")),
                      "long": sum(1 for x in ads if x.get("active") and (x.get("days_running") or 0) >= 30),
                      "advertisers": len(a.get("advertisers") or []), "date": a.get("date")}
    d = read(f"{n}-demand.json")
    if d:
        cal = d.get("calendar") or []
        today = datetime.now().date().isoformat()
        nxt = sorted((c for c in cal if not c.get("in_season") and (c.get("start_by") or "") >= today),
                     key=lambda c: c.get("start_by") or "")
        out["demand"] = {"in_season": [c["term"] for c in cal if c.get("in_season")][:3], "terms": len(d.get("terms") or []),
                         "next": {"term": nxt[0]["term"], "start_by": nxt[0]["start_by"]} if nxt else None,
                         "date": d.get("fetched") or d.get("date")}
    pf = read(f"{n}-perf-latest.json")
    if pf and pf.get("records"):
        out["perf"] = {"records": len(pf.get("records") or []), "date": pf.get("date")}
    from .paid import core as paid
    ps = paid.settings(cfg)
    if ps["cap"] > 0 or ps["accounts"]:
        snap = paid.load(cfg)
        spent, future, _ = paid.committed(snap)
        running = sum(1 for acc in ((snap or {}).get("platforms") or {}).values() for c in (acc.get("campaigns") or []) if c.get("running"))
        out["paid"] = {"cap": ps["cap"], "spent": spent, "projected": round(spent + future, 2), "running": running}
    return out


def _setup(cfg):
    """What each section is configured with (counts only), for the business overview."""
    ads, dem, loc = cfg.get("ads") or {}, cfg.get("demand") or {}, cfg.get("local") or {}
    own = cfg.get("own") or {}
    return {
        "ads": {"advertisers": len(ads.get("advertisers") or []), "keywords": len(ads.get("keywords") or []),
                "domains": len(ads.get("domains") or []), "countries": ads.get("countries") or []} if ads else None,
        "demand": {"terms": len(dem.get("terms") or []), "geo": dem.get("geo")} if dem else None,
        "local": bool(loc.get("query")),
        "perf": bool((cfg.get("perf") or {}).get("meta_ad_account_id")),
        "own": len(own.get("youtube") or []) + len(own.get("urls") or []),
        "tiktok": len(cfg["discover"]["tiktok"]["keywords"]) + len(cfg["discover"]["tiktok"]["hashtags"])
        + len(cfg["watch"]["tiktok"]),
    }


def ads_data(cfg):
    """The latest ads run for the dashboard, or None. Meta snapshot URLs carry the access token, so they never leave."""
    p = Path(cfg["db"]).parent / f"{cfg['name']}-ads-latest.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    for a in d.get("ads") or []:
        a.pop("snapshot_url", None)
    try:                                   # first/last time viral-scout saw each ad (the ad page's history)
        import sqlite3
        db = sqlite3.connect(cfg["db"])
        seen = {k: (f, l) for k, f, l in db.execute("select key, first_seen, last_seen from ads")}
        db.close()
        for a in d.get("ads") or []:
            if a["key"] in seen:
                a["first_seen"], a["last_seen"] = seen[a["key"]]
    except sqlite3.Error:
        pass
    from .ads import extra                 # transcripts, AI breakdowns, swipe notes (data/<p>-ads-extra.json)
    more = extra.load(cfg)
    for a in d.get("ads") or []:
        for k, v in (more.get(a["key"]) or {}).items():
            a[k] = v
    d.pop("report", None)
    d["business"] = (cfg.get("business") or "").strip()
    reports = sorted(Path((cfg.get("ads") or {}).get("output_dir") or cfg["output_dir"]).glob("*-ads-scout.md"), reverse=True)
    d["reports"] = [r.name[:10] for r in reports[:30]]
    return d


def export_ads(cfg, out=WEB_DATA):
    d = ads_data(cfg)
    if not d:
        return None
    (out / "ads").mkdir(parents=True, exist_ok=True)
    f = out / "ads" / f"{cfg['name']}.json"
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return f


def export_demand(cfg, out=WEB_DATA):
    """Search demand (Google Trends) for the dashboard: data/<profile>-demand.json as it is."""
    from .demand import paths
    p = paths(cfg)[0]
    if not p.exists():
        return None
    (out / "demand").mkdir(parents=True, exist_ok=True)
    f = out / "demand" / f"{cfg['name']}.json"
    f.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    return f


def export_all(names=None, out=WEB_DATA):
    out.mkdir(parents=True, exist_ok=True)
    every = not names
    if every:
        names = [p.stem for p in config.PROFILES.glob("*.yaml") if not p.stem.startswith("_")]
    index = []
    old = out / "index.json"
    if old.exists() and not every:                 # a partial export keeps the others' entries, if they still exist
        try:
            index = [p for p in json.loads(old.read_text(encoding="utf-8"))["profiles"]
                     if p["name"] not in names and (config.PROFILES / f"{p['name']}.yaml").exists()]
        except (ValueError, KeyError):
            index = []
    done = []
    for name in sorted(names):
        cfg = config.load(name)
        export_ads(cfg, out)
        has_demand = bool(export_demand(cfg, out))
        data = profile(cfg)
        if not data:
            continue
        if name.startswith("example-") and not data["items"]:   # the repo's sample profiles show only once they've run
            continue
        done.append(name)
        (out / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        live = [i for i in data["items"] if not i["dismissed"]]
        top = sorted([i for i in live if (i.get("outlier") or 0) >= 3], key=lambda i: -(i.get("weighted") or 0))[:4]
        index.append({
            "name": name, "display_name": data.get("display_name"), "date": data["date"], "business": data["business"][:220],
            "posts": len(live), "outliers": sum(1 for i in live if (i.get("outlier") or 0) >= 3),
            "mega": sum(1 for i in live if (i.get("outlier") or 0) >= 10),
            "new": sum(1 for i in live if i.get("new")), "saved": len(data["swipe"]), "ideas": len(data["ideas"]),
            "ads": (data.get("ads_summary") or {}).get("ads"), "demand": has_demand,
            "features": _features(cfg),
            "top": [{"title": i["title"], "thumbnail": i.get("thumbnail"), "outlier": i.get("outlier"),
                     "channel": i["channel"], "url": i["url"]} for i in top],
        })
    perf_done = set(export_perf(names, out)[1])
    from .paid.cli import export as export_paid   # the Paid ads page reads the last pull; exporting never calls an API
    for p in index:
        try:
            export_paid(config.load(p["name"]), out)
            p["paid"] = True
        except Exception:  # noqa: BLE001 (the page shows "not pulled yet")
            pass
    for p in index:
        if p["name"] in perf_done:
            p["perf"] = True
    index.sort(key=lambda p: p["name"])
    from .keys import KEYS                 # the key catalog for the published Setup page: names and help, never values
    (out / "keys.json").write_text(json.dumps(KEYS, ensure_ascii=False), encoding="utf-8")
    (out / "index.json").write_text(json.dumps({"exported": datetime.now().isoformat(), "profiles": index},
                                               ensure_ascii=False), encoding="utf-8")
    return out, done


def perf_profile(cfg):
    """Own-performance data for the dashboard (data/<profile>-perf-latest.json), or None."""
    p = Path(cfg["db"]).parent / f"{cfg['name']}-perf-latest.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    for r in data.get("records", []):
        r.pop("comment_texts", None)            # own comments stay local; the page only needs the sentiment score
    return data


def export_perf(names=None, out=WEB_DATA):
    """web/data/perf/<profile>.json for the "Your performance" page. Returns (folder, exported names)."""
    folder = out / "perf"
    if not names:
        names = [p.stem for p in config.PROFILES.glob("*.yaml") if not p.stem.startswith("_")]
    done = []
    for name in sorted(names):
        try:
            data = perf_profile(config.load(name))
        except FileNotFoundError:
            continue
        if not data:
            continue
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        done.append(name)
    return folder, done
