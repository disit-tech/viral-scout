"""What still needs setting up, per feature, with where to fix each item: the dashboard's setup checklists.

  python -m viral_scout setup-check [profile]      JSON: {global: [...], profiles: {name: {display, sections: [...]}}}

Every item is {id, label, done, optional, detail, fix}. fix tells the dashboard where the shortcut goes:
  {"kind": "key", "name": "YOUTUBE_API_KEY", "use": "videos"}  → /setup?use=videos#key-YOUTUBE_API_KEY
  {"kind": "field", "path": "demand.terms"}                    → /p/<profile>/settings#f-demand.terms
  {"kind": "page", "href": "/schedule"}                        → that page
  {"kind": "command", "text": "python -m viral_scout …"}       → copy button
  {"kind": "doc", "href": "/docs/paid-ads"}                    → the docs page
Cheap checks only (env vars, the profile, files, programs on PATH), so it runs on every page load. Nothing here
calls an API; the Setup page's Test buttons do that.
"""
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

from . import config


def _env(name):
    return bool(os.environ.get(name))


def _item(id, label, done, fix=None, detail="", optional=False):
    return {"id": id, "label": label, "done": bool(done), "optional": optional, "detail": detail, "fix": fix}


def _key(name, use):
    return {"kind": "key", "name": name, "use": use}


def _field(path):
    return {"kind": "field", "path": path}


def _cmd(text):
    return {"kind": "command", "text": text}


def _claude():
    return shutil.which("claude") or shutil.which("claude.cmd")


def _ytdlp():
    d = os.environ.get("VIRAL_SCOUT_YTDLP")
    return bool(d and Path(d, "yt_dlp").is_dir()) or importlib.util.find_spec("yt_dlp") is not None


def tools():
    """Programs a single page needs (Check a video: FFmpeg). Each feature's own needs are in its section."""
    return [
        _item("claude", "Claude Code CLI", _claude(), _cmd("npm install -g @anthropic-ai/claude-code"), _claude() or "not on PATH"),
        _item("ffmpeg", "FFmpeg (reads the video file)", shutil.which("ffmpeg"), _cmd("winget install Gyan.FFmpeg"),
              shutil.which("ffmpeg") or "not on PATH"),
    ]


def _vault():
    v = os.environ.get("OBSIDIAN_VAULT", "")
    return v if v and Path(v).is_dir() else ""


def _latest(cfg, suffix=""):
    base = Path(cfg["db"]).parent
    if suffix == "-demand":                       # demand keeps one file, not a -latest copy
        return (base / f"{cfg['name']}-demand.json").exists()
    return (base / f"{cfg['name']}{suffix}-latest.json").exists()


def sections(cfg):
    n = cfg["name"]
    d = cfg.get("discover") or {}
    yt, tt = d.get("youtube") or {}, d.get("tiktok") or {}
    w = cfg.get("watch") or {}
    own = cfg.get("own") or {}
    ads, dem, loc = cfg.get("ads") or {}, cfg.get("demand") or {}, cfg.get("local") or {}
    perf = cfg.get("perf") or {}
    out = []

    out.append({"id": "business", "title": "Business", "href": f"/p/{n}/settings#business", "items": [
        _item("business", "Business description", (cfg.get("business") or "").strip(), _field("business"),
              "every idea, breakdown and campaign is adapted to it"),
        _item("vault", "Obsidian vault folder (reports, idea notes, swipe file)", _vault(), _key("OBSIDIAN_VAULT", "tools"),
              _vault()),
        _item("display_name", "Display name", cfg.get("display_name"), _field("display_name"), optional=True),
    ]})

    has_yt = bool(yt.get("keywords") or yt.get("hashtags") or w.get("youtube"))
    has_tt = bool(tt.get("keywords") or tt.get("hashtags") or w.get("tiktok"))
    vid = [
        _item("ytdlp", "yt-dlp (reads public posts)", _ytdlp(), _key("VIRAL_SCOUT_YTDLP", "tools"),
              "" if _ytdlp() else "pip install yt-dlp, or point VIRAL_SCOUT_YTDLP at a clone"),
        _item("search", "Something to search (YouTube keywords, hashtags or creators)", has_yt or has_tt,
              _field("discover.youtube.keywords")),
        _item("yt_key", "YouTube Data API key (keyword search)", _env("YOUTUBE_API_KEY"), _key("YOUTUBE_API_KEY", "videos"),
              "free; hashtag feeds and creators work without it", optional=not yt.get("keywords")),
    ]
    if has_tt:
        vid.append(_item("apify_tt", "Apify token (TikTok, paid per result)", _env("APIFY_TOKEN"), _key("APIFY_TOKEN", "videos")))
    if w.get("instagram"):
        vid.append(_item("ig", "Instagram Graph API (Instagram watch list)", _env("IG_GRAPH_TOKEN") and _env("IG_GRAPH_USER_ID"),
                         _key("IG_GRAPH_TOKEN", "videos")))
    vid += [
        _item("own", "Your own channels (your posts vs your usual)", own.get("youtube") or own.get("urls"),
              _field("own.youtube"), optional=True),
        _item("run", "First videos run", _latest(cfg), _cmd(f"python -m viral_scout run {n} --free"),
              "or the overview's Run YouTube now button"),
    ]
    out.append({"id": "videos", "title": "Videos", "href": f"/p/{n}/videos", "items": vid})

    a = [
        _item("targets", "Competitors or keyword searches", ads.get("advertisers") or ads.get("keywords") or ads.get("domains"),
              _field("ads.advertisers")),
        _item("countries", "Countries", ads.get("countries"), _field("ads.countries"), optional=True),
        _item("apify", "Apify token (US ads, paid per ad)", _env("APIFY_TOKEN"), _key("APIFY_TOKEN", "ads")),
        _item("meta_actor", "Facebook / Instagram ads actor", _env("APIFY_ADS_ACTOR"), _key("APIFY_ADS_ACTOR", "ads")),
        _item("google_actor", "Google ads actor (competitor domains)", _env("APIFY_GOOGLE_ADS_ACTOR"),
              _key("APIFY_GOOGLE_ADS_ACTOR", "ads"), optional=not ads.get("domains")),
        _item("tiktok_actor", "TikTok top ads actor", _env("APIFY_TIKTOK_ADS_ACTOR"), _key("APIFY_TIKTOK_ADS_ACTOR", "ads"), optional=True),
        _item("eu", "Meta Ad Library API (EU ads, free)", _env("META_AD_LIBRARY_TOKEN"), _key("META_AD_LIBRARY_TOKEN", "ads"), optional=True),
        _item("run", "First ads run", _latest(cfg, "-ads"), _cmd(f"python -m viral_scout ads {n}"), "weekly on Mondays once scheduled"),
    ]
    out.append({"id": "ads", "title": "Ads (competitors)", "href": f"/p/{n}/ads", "items": a})

    out.append({"id": "demand", "title": "Search demand", "href": f"/p/{n}/demand", "items": [
        _item("terms", "Services to track", dem.get("terms"), _field("demand.terms")),
        _item("geo", "Area (Google Trends geo)", dem.get("geo"), _field("demand.geo")),
        _item("apify", "Apify token (about $0.005 per term)", _env("APIFY_TOKEN"), _key("APIFY_TOKEN", "demand")),
        _item("run", "First search demand run", _latest(cfg, "-demand"), _cmd(f"python -m viral_scout demand {n}")),
    ]})

    yt_ok = all(_env(k) for k in ("YT_OAUTH_CLIENT_ID", "YT_OAUTH_CLIENT_SECRET", "YT_OAUTH_REFRESH_TOKEN"))
    p = [
        _item("ig", "Instagram insights (your account)", _env("IG_GRAPH_TOKEN") and _env("IG_GRAPH_USER_ID"),
              _key("IG_GRAPH_TOKEN", "performance"), optional=True),
        _item("yt_client", "YouTube Analytics: OAuth client", _env("YT_OAUTH_CLIENT_ID") and _env("YT_OAUTH_CLIENT_SECRET"),
              _key("YT_OAUTH_CLIENT_ID", "performance"), optional=True),
        _item("yt_login", "YouTube Analytics: sign in", _env("YT_OAUTH_REFRESH_TOKEN"), _cmd("python -m viral_scout perf auth youtube"),
              optional=True),
        _item("meta", "Meta ads insights", _env("META_ADS_TOKEN") and perf.get("meta_ad_account_id"),
              _key("META_ADS_TOKEN", "performance") if not _env("META_ADS_TOKEN") else _field("perf.meta_ad_account_id"),
              optional=True),
        _item("tiktok", "TikTok ads insights", _env("TIKTOK_ADS_TOKEN"), _key("TIKTOK_ADS_TOKEN", "performance"), optional=True),
    ]
    any_src = any(i["done"] for i in p) or yt_ok
    p.insert(0, _item("source", "At least one source (an account above, or a CSV export)", any_src or _latest(cfg, "-perf"),
                      _cmd(f"python -m viral_scout perf import {n} export.csv --source meta|tiktok|youtube|generic"),
                      "connect one account below, or import an export"))
    p.append(_item("run", "First performance pull", _latest(cfg, "-perf"), _cmd(f"python -m viral_scout perf {n}")))
    out.append({"id": "performance", "title": "Your performance", "href": f"/p/{n}/performance", "items": p})

    out.append({"id": "local", "title": "Local competitors", "href": f"/p/{n}/settings#perf", "optional": True, "items": [
        _item("query", "What to search nearby", loc.get("query"), _field("local.query")),
        _item("near", "Near (city, ST)", loc.get("near"), _field("local.near")),
        _item("places", "Google Places API key", _env("GOOGLE_PLACES_API_KEY"), _key("GOOGLE_PLACES_API_KEY", "local")),
    ]})

    ideas = cfg.get("ideas") if isinstance(cfg.get("ideas"), dict) else None
    studio = cfg.get("studio") if isinstance(cfg.get("studio"), dict) else {}
    instr = studio.get("instructions")
    i = [
        _item("block", "Idea generator set up", ideas, {"kind": "page", "href": "/schedule"},
              "Schedule page → Idea generator → Set up"),
        _item("service", "Bot service address", _env("STUDIO_SERVICE_URL") or _env("IDEAS_SITE_URL"), _key("STUDIO_SERVICE_URL", "ideas")),
        _item("secret", "Ideas API secret", _env("IDEAS_API_SECRET"), _key("IDEAS_API_SECRET", "ideas")),
        _item("claude", "Claude Code CLI", _claude(), _cmd("npm install -g @anthropic-ai/claude-code")),
        _item("instructions", "Studio instructions note (the business's rules for ideas and videos)",
              instr and Path(str(instr)).exists(), {"kind": "doc", "href": "/docs/studio"}, str(instr or ""), optional=True),
        _item("bots", "Telegram bots connected", None, {"kind": "page", "href": "/bots"}, "check on the Bots page", optional=True),
    ]
    out.append({"id": "ideas", "title": "Ideas & Telegram", "href": "/ideas", "items": i})

    from .paid import core as paid
    s = paid.settings(cfg)
    b = s["brief"]
    out.append({"id": "paid", "title": "Paid ads", "href": f"/p/{n}/paid", "optional": True, "items": [
        _item("cap", "Monthly cap", s["cap"] > 0, {"kind": "page", "href": f"/p/{n}/paid#brief-cap"}),
        _item("brief", "Brief (goal, budget, area, audience)", all(b.get(k) for k in ("goal", "daily_budget_usd", "geo", "audience")),
              {"kind": "page", "href": f"/p/{n}/paid#brief"}),
        _item("account", "At least one ad account id", s["accounts"], {"kind": "page", "href": f"/p/{n}/paid#brief"}),
        _item("key", "A dashboard key (Meta, Google or TikTok)",
              _env("META_ADS_TOKEN") or _env("TIKTOK_ADS_TOKEN") or _env("GOOGLE_ADS_REFRESH_TOKEN"), _key("META_ADS_TOKEN", "paid")),
    ]})

    out.append({"id": "alerts", "title": "Telegram alerts", "href": "/setup?use=alerts", "optional": True, "items": [
        _item("tg", "Telegram bot + chat for outlier alerts", _env("TELEGRAM_BOT_TOKEN") and _env("TELEGRAM_CHAT_ID"),
              _key("TELEGRAM_BOT_TOKEN", "alerts")),
    ]})

    for sec in out:   # a section is done when every required item is
        req = [x for x in sec["items"] if not x["optional"]]
        sec["open"] = sum(1 for x in req if not x["done"])
        sec["total"] = len(req)
    return out


def check(name=None):
    config.load_env()
    every = [p.stem for p in sorted(config.PROFILES.glob("*.yaml")) if not p.stem.startswith("_")]
    names = [name] if name else every
    profiles = {}
    for nm in names:
        try:
            cfg = config.load(nm)
        except Exception as err:  # noqa: BLE001 (a broken profile shows as one item)
            profiles[nm] = {"display": nm, "error": str(err)[:200], "sections": []}
            continue
        studio = cfg.get("studio") if isinstance(cfg.get("studio"), dict) else {}
        profiles[nm] = {"display": cfg.get("display_name") or studio.get("brand") or nm, "sections": sections(cfg)}
    g = tools()
    g.insert(0, _item("profiles", "At least one business", bool(every), {"kind": "page", "href": "/new"},
                      f"{len(every)} set up" if every else "describe the business and its first run starts"))
    return {"global": g, "profiles": profiles}


def cli(argv):
    print(json.dumps(check(argv[0] if argv else None), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(cli(sys.argv[1:]))
