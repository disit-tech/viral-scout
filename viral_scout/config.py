"""Profiles: one YAML per business in profiles/. ${ENV_VARS} are expanded in strings."""
import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "profiles"

DEFAULTS = {
    "discover": {"youtube": {"keywords": [], "hashtags": [], "window": "week", "shorts": True, "per_query": 30},
                 "tiktok": {"keywords": [], "hashtags": [], "per_query": 30}},
    "watch": {"youtube": [], "instagram": [], "tiktok": []},
    "seeds": [],
    "filters": {"min_views": 5000, "exclude": [], "must_match": "", "max_age_days": 60},
    "enrich_top": 40,
    "recheck": {"max_age_days": 30, "limit": 60},
    "report": {"top": 25},
}


def _expand(v):
    if isinstance(v, str):
        return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), v)
    if isinstance(v, list):
        return [_expand(x) for x in v]
    if isinstance(v, dict):
        return {k: _expand(x) for k, x in v.items()}
    return v


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def load_env():
    """Read KEY=VALUE lines from .env in the repo root (git-ignored) without overriding real env vars."""
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)\s*$", line)
        if m and m.group(1) not in os.environ:
            os.environ[m.group(1)] = m.group(2).strip().strip('"')


def load(name_or_path):
    p = Path(name_or_path)
    if not p.suffix:
        p = PROFILES / f"{name_or_path}.yaml"
    cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    cfg = _expand(_merge(DEFAULTS, cfg))
    cfg.setdefault("name", p.stem)
    cfg["_path"] = str(p)
    data = ROOT / "data"
    data.mkdir(exist_ok=True)
    cfg.setdefault("db", str(data / f"{cfg['name']}.sqlite"))
    cfg.setdefault("output_dir", str(ROOT / "reports" / cfg["name"]))
    return cfg
