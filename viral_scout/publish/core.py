"""Pure publishing helpers (no network): settings, caption file, UTM links, posting slots, the ready-to-post queue."""
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Platforms with an official-API publisher in publish/node (the rest are always posted by hand).
API_PLATFORMS = ("instagram", "facebook", "youtube", "linkedin")
KNOWN = ("tiktok", "instagram", "youtube", "facebook", "threads", "x", "linkedin", "pinterest", "nextdoor")

# Standard env names the node publisher reads. A profile maps them to its own names (publish.tokens).
TOKEN_NAMES = {
    "instagram": ["INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID"],
    "facebook": ["FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_TOKEN"],
    "youtube": ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"],
    "linkedin": ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR"],
}

DEFAULTS = {
    "platforms": ["tiktok", "instagram", "youtube", "facebook"],
    "handles": {},
    "timezone": "America/Springfield",
    "slots": {"tiktok": "18:00", "instagram": "18:30", "youtube": "18:30", "facebook": "19:30"},
    "utm": {"medium": "social", "campaign": "{slug}", "sources": {}},
    "auto_post": {},
    # Films per post date and the time the n-th film of a date goes out on every auto platform (profile timezone).
    "per_day": 1,
    "times": ["18:30", "12:00", "08:00"],
    # owner: nothing is posted before the owner's ✅. auto: every finished film and post is approved when queued; the
    # owner can still stop one (🛑 in the queue row, or a 🛑 reply in the bot) until its time.
    "approval": "owner",
    "posts": {"enabled": False, "per_day": 1, "times": ["10:00", "15:00"], "platforms": ["linkedin", "facebook"]},
    # Comment challenges: a post with `challenge: KEYWORD` (or `mentions: 2`) in its caption header gets an answer
    # under every qualifying comment (reply_text, {link} = the post's reward link). dm: try a private reply first.
    "challenges": {"enabled": False, "dm": False, "days": 7, "reply_text": "Here you go: {link}",
                   "reply_text_instagram": "Sent! Link is in our bio too: {link}"},
    "env_file": "",
    "tokens": {},
    "youtube": {"category": "27", "language": "en", "privacy": "public"},
    "queue": "",
    "morning_pack": {"enabled": False, "hour": 9, "delivery": "none", "env_file": "",
                     "token_env": "TELEGRAM_BOT_TOKEN", "chat_env": "TELEGRAM_CHAT_ID"},
}


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def settings(cfg):
    """The profile's publish: block over the defaults, plus the queue path and the CTA link from studio:."""
    s = _merge(DEFAULTS, cfg.get("publish") or {})
    studio = cfg.get("studio") or {}
    if not s["queue"] and studio.get("vault_dir"):
        s["queue"] = str(Path(studio["vault_dir"]) / "05 Marketing" / "Video Studio" / "ready-to-post.md")
    s["link"] = s.get("link") or (studio.get("cta") or {}).get("link", "")
    if not s["env_file"]:
        from .. import config
        s["env_file"] = str(config.ROOT / "data" / "publish" / cfg["name"] / "keys.env")   # git-ignored, per business
    s["posts_queue"] = (s["posts"].get("queue") or (str(Path(studio["vault_dir"]) / "05 Marketing" / "Social" / "post-queue.md")
                                                    if studio.get("vault_dir") else ""))
    s["platforms"] = [p.lower() for p in s["platforms"]]
    if True in s["morning_pack"]:          # YAML 1.1 reads a bare `on:` key as True
        s["morning_pack"] = {k: v for k, v in s["morning_pack"].items() if k is not True} | {"enabled": bool(s["morning_pack"][True])}
    return s


def auto_post(s, platform):
    """True only when the profile opted in for this platform AND an API publisher exists for it."""
    return platform in API_PLATFORMS and s["auto_post"].get(platform) is True


# ───────────── UTM ─────────────
def utm_link(url, platform, slug="", s=None):
    """url + utm_source=<platform> (or publish.utm.sources[platform]) + medium + campaign. Existing utm_* are kept."""
    if not url:
        return ""
    u = (s or DEFAULTS)["utm"]
    parts = urlsplit(url)
    q = dict(parse_qsl(parts.query))
    q.setdefault("utm_source", (u.get("sources") or {}).get(platform, platform))
    if u.get("medium"):
        q.setdefault("utm_medium", u["medium"])
    camp = (u.get("campaign") or "").replace("{slug}", slug).replace("{platform}", platform)
    if camp:
        q.setdefault("utm_campaign", camp)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


# ───────────── Caption file (same format as publish/node/lib.mjs) ─────────────
def parse_caption(text):
    """Header lines `ai:` / `title:`, a default caption, optional `## Instagram|Facebook|YouTube|TikTok…` overrides."""
    lines = text.lstrip("﻿").replace("\r", "").split("\n")
    meta, i = {}, 0
    while i < len(lines) and re.match(r"^(ai|title|photo|challenge|mentions|reward)\s*:", lines[i], re.I):
        k, _, v = lines[i].partition(":")
        meta[k.strip().lower()] = v.strip()
        i += 1
    parts, cur = {"base": []}, "base"
    for line in lines[i:]:
        h = re.match(r"^##\s*(%s)\s*$" % "|".join(KNOWN), line, re.I)
        if h:
            cur = h.group(1).lower()
            parts[cur] = []
        else:
            parts[cur].append(line)
    base = "\n".join(parts["base"]).strip()
    out = {"ai": bool(re.match(r"^(true|yes|1)$", meta.get("ai", ""), re.I)), "title": meta.get("title", ""),
           "photo": meta.get("photo", ""), "challenge": meta.get("challenge", "").strip().upper(),
           "mentions": int(meta.get("mentions") or 0) if str(meta.get("mentions") or "0").isdigit() else 0,
           "reward": meta.get("reward", "")}
    for p in KNOWN:
        out[p] = "\n".join(parts.get(p, [])).strip() or base
    return out


def hashtags(s):
    return re.findall(r"#(\w+)", s)


def youtube_title(caption, explicit=""):
    """≤ 100 characters, no < >, ends with #Shorts, cut at a word with "…" when too long."""
    first = explicit or next((l for l in caption.split("\n") if l.strip()), "")
    first = re.sub(r"\s+", " ", re.sub(r"[<>]", "", first)).strip()
    base = re.sub(r"\s*#shorts\b", "", first, flags=re.I).strip()
    tag, mx = " #Shorts", 100 - len(" #Shorts")
    if len(base) <= mx:
        return base + tag
    cut = base[: mx - 1]
    sp = cut.rfind(" ")
    cut = cut[:sp] if sp > 40 else cut
    return re.sub(r"[\s,.;:–-]+$", "", cut) + "…" + tag


def caption_problems(c):
    out = []
    if not c["instagram"]:
        out.append("instagram: empty caption")
    if len(c["instagram"]) > 2200:
        out.append(f"instagram: caption {len(c['instagram'])} > 2200 characters")
    if len(hashtags(c["instagram"])) > 30:
        out.append(f"instagram: {len(hashtags(c['instagram']))} hashtags > 30")
    if not c["youtube"]:
        out.append("youtube: empty caption")
    if len(c["youtube"].encode()) > 5000:
        out.append("youtube: description > 5000 bytes")
    return out


# ───────────── Queue: <vault>/05 Marketing/Video Studio/ready-to-post.md ─────────────
def read_queue(path):
    """Rows `| YYYY-MM-DD | title | `mp4` | script | status |` → dicts. Missing file → []."""
    p = Path(path) if path else None
    if not p or not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|", line):
            continue
        # Split on unescaped pipes outside wiki links only: Obsidian writes a link alias in a table as
        # `[[note\\|label]]`, but a hand-written `[[note|label]]` must not split the cell either.
        line = re.sub(r"\[\[[^\]]*\]\]", lambda m: m.group(0).replace("|", "\x1f"), line)
        c = [x.strip().replace("\x1f", "|") for x in re.split(r"(?<!\\)\|", line)]
        m = re.search(r"`([^`]+)`", c[3] if len(c) > 3 else "")
        rows.append({"date": c[1], "title": c[2] if len(c) > 2 else "", "video": m.group(1) if m else "",
                     "script": c[4] if len(c) > 4 else "", "status": c[5] if len(c) > 5 else ""})
    return rows


def posted(row):
    return bool(re.search(r"posted|📤|опубл", row.get("status", ""), re.I))


def approved(row):
    return bool(re.search(r"✅|approved|схвал|\bauto\b", row.get("status", ""), re.I)) and not stopped(row)


def stopped(row):
    return bool(re.search(r"🛑|\bstop", row.get("status", ""), re.I))


def post_time(s, rows, row, times=None):
    """HH:MM for `row`: the n-th row of its date (queue order) takes times[n] (the last time when there are more)."""
    times = times or s["times"]
    same = [r for r in rows if r["date"] == row["date"]]
    n = next((i for i, r in enumerate(same) if r is row), 0)
    return times[min(n, len(times) - 1)] if times else "18:30"


def slug_of(row):
    v = row.get("video") or ""
    if v:
        film = Path(v).parent.parent if Path(v).parent.name == "out" else Path(v).parent
        return film.name
    return re.sub(r"[^a-z0-9]+", "-", row.get("title", "").lower()).strip("-")[:60]


def plan(cfg, start=None, days=7):
    """Every queued, unposted film from `start` for `days` days → one entry per platform: slot, link, auto/manual."""
    s = settings(cfg)
    start = start or date.today()
    end = start + timedelta(days=days)
    out = []
    for row in read_queue(s["queue"]):
        try:
            d = date.fromisoformat(row["date"])
        except ValueError:
            continue
        if not (start <= d < end) or posted(row):
            continue
        slug = slug_of(row)
        posts = []
        rows_all = read_queue(s["queue"])
        mine = next((r for r in rows_all if r == row), row)
        for p in s["platforms"]:
            at = post_time(s, rows_all, mine) if auto_post(s, p) else s["slots"].get(p, "")
            posts.append({"platform": p, "handle": s["handles"].get(p, ""), "at": f"{row['date']} {at}".strip(),
                          "link": utm_link(s["link"], p, slug, s), "mode": "auto" if auto_post(s, p) else "manual"})
        out.append({**row, "slug": slug, "approved": approved(row), "posts": posts})
    return out


def free_dates(cfg, start=None, horizon=14):
    """Dates from `start` (default tomorrow) on with no queued film: where the film job puts the next one."""
    s = settings(cfg)
    count = {}
    for r in read_queue(s["queue"]):
        count[r["date"]] = count.get(r["date"], 0) + 1
    d = start or (date.today() + timedelta(days=1))
    per = max(1, int(s["per_day"]))
    return [str(d + timedelta(days=i)) for i in range(horizon) if count.get(str(d + timedelta(days=i)), 0) < per]


# ───────────── Text / photo posts: <vault>/05 Marketing/Social/post-queue.md ─────────────
def read_posts(path):
    """Rows `| YYYY-MM-DD | title | `post.md` | status |` → dicts (post = caption file, optional `photo:` header)."""
    p = Path(path) if path else None
    if not p or not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|", line):
            continue
        c = [x.strip() for x in line.split("|")]
        m = re.search(r"`([^`]+)`", c[3] if len(c) > 3 else "")
        rows.append({"date": c[1], "title": c[2] if len(c) > 2 else "", "file": m.group(1) if m else "",
                     "status": c[4] if len(c) > 4 else ""})
    return rows


def chunks(text, mx=3900):
    """Split on paragraph breaks into Telegram-sized messages (limit 4096)."""
    out, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        add = ("\n\n" if cur else "") + para
        if cur and len(cur) + len(add) > mx:
            out.append(cur)
            cur = para
        else:
            cur += add
    if cur.strip():
        out.append(cur)
    res = []
    for c in out:
        res.extend([c[i:i + mx] for i in range(0, len(c), mx)] if len(c) > mx else [c])
    return res


def now_in(tz):
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(tz))
    except Exception:
        return datetime.now()
