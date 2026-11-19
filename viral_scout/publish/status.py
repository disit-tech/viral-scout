"""What the dashboard's Posting page shows: `python -m viral_scout publish <profile> status --json`, and the row
buttons: `publish <profile> row stop|resume <file>` (the 🛑 / ✅ cell of a queue row). Key VALUES never leave here,
only whether each one is set."""
import json
from datetime import date, timedelta
from pathlib import Path

from . import auto, connect, core

KEYS = {
    "instagram": ["INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID"],
    "facebook": ["FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_TOKEN"],
    "youtube": ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"],
    "linkedin": ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR"],
    "tiktok": ["TIKTOK_POST_REFRESH_TOKEN"],
    "threads": ["THREADS_ACCESS_TOKEN", "THREADS_USER_ID"],
}
CONNECT = {"instagram": "meta", "facebook": "meta", "youtube": "google", "linkedin": "linkedin", "tiktok": "tiktok", "threads": "threads"}


def _log(cfg, name):
    f = auto.data_dir(cfg) / name
    out = []
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def build(cfg, now=None):
    from ..jobs import settings as jobs_settings
    s, J = core.settings(cfg), jobs_settings.settings(cfg)
    now = now or core.now_in(s["timezone"]).replace(tzinfo=None)
    env = connect.keys_for(cfg)
    done = auto.published(cfg)
    auto_on = [p for p in s["platforms"] if core.auto_post(s, p)]
    since = now.date() - timedelta(days=3)

    def row_out(rows, r, times, plats, key, kind):
        why = auto.due(s, rows, r, now, times, int(s.get("late_days", 1)))
        file = r.get("video") or r.get("file") or ""
        k = Path(file).name if file else ""
        cap = auto.caption_for(file) if kind == "film" and file else (Path(file) if file and Path(file).exists() else None)
        state = ("posted" if core.posted(r) else "stopped" if core.stopped(r) else
                 "due now" if why is None else "waiting for approval" if why == "waiting for approval" else
                 "missed" if why == "missed" else "scheduled")
        return {"kind": kind, "date": r["date"], "time": core.post_time(s, rows, r, times), "title": r["title"], "file": file,
                "status": r.get("status", ""), "state": state, "approved": core.approved(r) or s["approval"] == "auto",
                "caption": bool(cap), "platforms": {p: (p, k) in done for p in plats}}

    films = core.read_queue(s["queue"])
    film_rows = [row_out(films, r, s["times"], auto_on, "video", "film") for r in films if r["date"] >= str(since)]
    ps = s["posts"]
    post_plats = [p for p in ps.get("platforms") or [] if p in ("facebook", "linkedin", "threads")]
    posts = core.read_posts(s["posts_queue"])
    post_rows = [row_out(posts, r, ps.get("times") or ["10:00"], post_plats, "file", "post") for r in posts if r["date"] >= str(since)]
    keys = {p: {"connected": all(env.get(k) for k in names), "missing": [k for k in names if not env.get(k)], "connect": CONNECT[p]}
            for p, names in KEYS.items()}
    # The shared app keys each Connect button needs first (names → set or not; values never leave here).
    prereqs = {k: bool(env.get(k)) for k in ("META_APP_ID", "META_APP_SECRET", "META_USER_TOKEN", "LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET",
                                          "TIKTOK_POST_CLIENT_KEY", "TIKTOK_POST_CLIENT_SECRET")}
    prereqs["GOOGLE_CLIENT"] = bool((env.get("YOUTUBE_CLIENT_ID") or env.get("YT_OAUTH_CLIENT_ID")) and
                                    (env.get("YOUTUBE_CLIENT_SECRET") or env.get("YT_OAUTH_CLIENT_SECRET")))
    if env.get("LINKEDIN_TOKEN_EXPIRES"):
        keys["linkedin"]["expires"] = env["LINKEDIN_TOKEN_EXPIRES"]
    replied = auto.data_dir(cfg) / "replied.json"
    return {
        "profile": cfg["name"], "timezone": s["timezone"], "now": now.isoformat(timespec="minutes"),
        "settings": {"approval": s["approval"], "per_day": s["per_day"], "times": s["times"][: max(1, int(s["per_day"]))],
                     "platforms": s["platforms"], "auto_post": {p: core.auto_post(s, p) for p in KEYS},
                     "posts": {k: ps.get(k) for k in ("enabled", "per_day", "times", "platforms")},
                     "challenges": {k: s["challenges"].get(k) for k in ("enabled", "dm", "reply_text", "reply_text_instagram")},
                     "film_job": bool(J["film"]["enabled"]), "posts_job": bool(J["posts"]["enabled"])},
        "queue": s["queue"], "posts_queue": s["posts_queue"],
        "prereqs": prereqs, "handles": s["handles"] or {},
        "films": film_rows, "posts": post_rows, "keys": keys, "warnings": connect.expiring(cfg, now.date()),
        "published": list(reversed(_log(cfg, "published.jsonl")))[:30],
        "challenges": {"replied": len(json.loads(replied.read_text(encoding="utf-8"))) if replied.exists() else 0,
                       "active": len([e for e in _log(cfg, "challenges.jsonl") if e.get("time", "") >= str(date.today() - timedelta(days=int(s["challenges"].get("days", 7))))])},
    }


def set_row(cfg, action, file):
    """stop → 🛑 stopped (dashboard); resume → ✅ auto (approval auto) or ✅ approved. Returns the new status."""
    s = core.settings(cfg)
    for path, rows, field in ((s["queue"], core.read_queue(s["queue"]), "video"), (s["posts_queue"], core.read_posts(s["posts_queue"]), "file")):
        r = next((x for x in rows if x.get(field) == file), None)
        if not r:
            continue
        if core.posted(r):
            raise ValueError("already posted")
        new = "🛑 stopped (dashboard)" if action == "stop" else ("✅ auto" if s["approval"] == "auto" else "✅ approved (dashboard)")
        auto.set_status(path, file, new)
        return new
    raise ValueError("no queued film or post with that file")
