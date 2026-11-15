"""The profile's `ideas:` block (and the shared `studio:` block) with defaults, plus the API credentials.

Credentials never live in the profile: `ideas.api.env_file` names a KEY=VALUE file (e.g. the solar site's
.env.local) and `url_env` / `secret_env` name the variables in it. A real environment variable wins, like ideas.mjs.
"""
import copy
import os
import re
from datetime import date
from pathlib import Path

from .. import config

SLUG = re.compile(r"^[a-z][a-z0-9-]{1,30}$")

# The idea fields and limits the API accepts (solar site/src/app/api/ideas/route.ts, `Idea`).
FIELDS = {"title": 200, "rubric": 80, "hookType": 40, "hook": 300, "angle": 600, "fact": 600, "source": 400,
          "visual": 600, "cta": 200, "why": 300}
REQUIRED = ("title", "hook")
BATCH_MAX = 60
IDEAS_MAX = 20
# lib/idea-bot.ts PLATFORMS: the only keys the API takes in `platforms`.
PLATFORMS = ["facebook", "fb_groups", "instagram", "tiktok", "youtube", "nextdoor", "google", "linkedin", "threads",
             "yelp", "email", "print"]
# lib/idea-bot.ts STAGE keys (the skill normally sets making, draft or posted).
STAGES = ["script", "script_ok", "making", "draft", "posted", "pack", "pack_sent"]

# Market data files viral-scout writes into output_dir (newest by the date the name starts with).
MARKET_TYPES = ["viral-scout", "viral-ideas", "ads-scout", "ads-ideas", "search-demand"]

DEFAULTS = {
    "project": "",
    "api": {"env_file": "", "url_env": "IDEAS_SITE_URL", "secret_env": "IDEAS_API_SECRET",
            "default_url": "http://localhost:3000",
            # The studio bot service (service/), for `ideas <p> status`; defaults to the ideas API's own URL.
            "service_url_env": "STUDIO_SERVICE_URL"},
    "header": "",
    "rubrics": [],
    "score": {"criteria": ["Hook", "Clarity", "Proof", "Call-out", "Fit"], "threshold": 38},
    "experiment_share": 0.2,
    "sources": [],
    "tracker": "",
    "taste_note": "",
    "market_data": {"dir": "", "min_share": 0.5, "max_age_days": 14},
    "packs": {"enabled": False, "platforms": [], "limits": {}, "banned_words": []},
    "blog": False,
    "batch_dir": "",
    "daily": {"count": 5, "at": "08:15", "add_dirs": []},
}


class IdeasError(Exception):
    pass


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def ideas_cfg(cfg):
    """The resolved `ideas:` block. Raises IdeasError when the profile has none or its project slug is unsafe."""
    raw = cfg.get("ideas")
    if not isinstance(raw, dict):
        raise IdeasError(f"profile {cfg.get('name')} has no ideas: block (see docs/ideas.md)")
    ic = _merge(copy.deepcopy(DEFAULTS), copy.deepcopy(raw))   # never share (or mutate) the defaults
    slug = str(ic.get("project") or "")
    if not SLUG.match(slug):
        raise IdeasError(f"profile {cfg.get('name')}: ideas.project must be a slug like solar, homes or agency "
                         f"(got {slug!r})")
    ic["project"] = slug
    ic["taste_note"] = ic["taste_note"] or cfg.get("taste_note") or ""
    ic["market_data"]["dir"] = ic["market_data"]["dir"] or cfg.get("output_dir") or ""
    ic["batch_dir"] = ic["batch_dir"] or str(config.ROOT / "data" / "ideas" / cfg["name"])
    return ic


def studio_cfg(cfg):
    return cfg.get("studio") if isinstance(cfg.get("studio"), dict) else {}


def resolve(cfg, path):
    """A note path from the profile → absolute. Relative paths are taken from studio.vault_dir, else the vault root."""
    if not path:
        return ""
    p = Path(path)
    if p.is_absolute() or "${" in path:
        return str(p)
    base = studio_cfg(cfg).get("vault_dir") or os.environ.get("OBSIDIAN_VAULT", "")
    return str(Path(base) / p) if base else str(p)


def read_env_file(path):
    """KEY=VALUE lines (# comments, optional quotes), like ideas.mjs reads site/.env.local."""
    out = {}
    p = Path(path) if path else None
    if not p or not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = re.sub(r'^"|"$', "", v.strip())
    return out


def credentials(ic, environ=None, service=False):
    """→ (base_url, secret). The secret is required. service=True: the bot service's URL (status) instead."""
    environ = os.environ if environ is None else environ
    api = ic["api"]
    file_env = read_env_file(api.get("env_file"))

    def get(k):
        return environ.get(k) or file_env.get(k) if k else None

    base = (get(api.get("url_env")) or api.get("default_url") or "http://localhost:3000").rstrip("/")
    if service:
        base = (get(api.get("service_url_env")) or base).rstrip("/")
    secret = get(api.get("secret_env"))
    if not secret:
        where = api.get("env_file") or "the environment"
        raise IdeasError(f"{api.get('secret_env')} is not set in {where} (ideas.api in the profile)")
    return base, secret


def _dated(name):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", name)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def market_files(ic, today=None):
    """Newest market-data report per type in the profile's output_dir: {type: {file, date, age_days, fresh}}."""
    today = today or date.today()
    folder = Path(ic["market_data"]["dir"]) if ic["market_data"]["dir"] else None
    out = {}
    if not folder or not folder.is_dir():
        return out
    for kind in MARKET_TYPES:
        best = None
        for f in folder.glob(f"*-{kind}.md"):
            d = _dated(f.name)
            if d and (best is None or d > best[0]):
                best = (d, f)
        if best:
            age = (today - best[0]).days
            out[kind] = {"file": str(best[1]), "date": best[0].isoformat(), "age_days": age,
                         "fresh": age <= ic["market_data"]["max_age_days"]}
    return out
