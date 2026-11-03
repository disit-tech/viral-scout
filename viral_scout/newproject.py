"""Start research on a new project/business from a description and a few keywords.

  python -m viral_scout new <name> --business "..." --keywords "k1; k2" [--hashtags "a b"] [--languages "k1=ru"]
         [--vault-project <folder>] [--research]
Writes profiles/<name>.yaml (git-ignored) with hashtags, a topic filter and spam excludes derived from the keywords.
--research makes a throwaway quick-research profile (prefix research-) that reports into reports/.
"""
import re
from pathlib import Path

import yaml

from . import config

BASE_EXCLUDE = [
    "minecraft|roblox|fortnite|gaming|\\bgame\\b|anime|cartoon|for kids|nursery",
    "🔴|\\blive:|24/7",
    "crypto|bitcoin|forex",
]
GENERIC = set("how to the a an and of for in on with best top tips tip easy quick new vs your you my what why is are "
              "do does 2025 2026 guide ideas idea video shorts at to by from before after about this that".split())


def slug(s):
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE).strip().lower()
    return re.sub(r"[\s_]+", "-", s)[:50] or "project"


def derive_hashtags(keywords, limit=14):
    tags = []
    for kw in keywords:
        words = [w for w in re.findall(r"[\w']+", kw.lower(), re.UNICODE) if w not in GENERIC]
        if not words:
            continue
        joined = "".join(words)
        if len(words) <= 2 and 3 <= len(joined) <= 24 and joined not in tags:   # "doggrooming", not 4-word blobs
            tags.append(joined)
        for w in words:
            if len(w) >= 5 and w not in tags:
                tags.append(w)
    return tags[:limit]


def derive_must_match(keywords):
    words = []
    for kw in keywords:
        for w in re.findall(r"[\w']+", kw.lower(), re.UNICODE):
            if w in GENERIC or len(w) < 3:
                continue
            stem = w[:max(4, len(w) - 2)] if len(w) > 6 else w      # "cleaning" → "cleani" matches "clean*"
            if stem not in words:
                words.append(stem)
    return "|".join(re.escape(w) for w in words[:30])


def create(name, business, keywords, hashtags=None, languages=None, vault_project=None, research=False,
           window="month", region=None):
    name = ("research-" if research and not name.startswith("research-") else "") + slug(name)
    path = config.PROFILES / f"{name}.yaml"
    if path.exists():
        raise FileExistsError(f"profile {name} already exists")
    keywords = [k.strip() for k in keywords if k.strip()]
    tags = [h.lstrip("#").strip() for h in (hashtags or []) if h.strip()] or derive_hashtags(keywords)
    vault = None
    if vault_project and not research:
        vault = f"${{OBSIDIAN_VAULT}}/projects/{vault_project}/05 Marketing/viral"
    prof = {
        "name": name,
        "business": business.strip(),
        "discover": {
            "youtube": {"window": window, "shorts": True, "per_query": 30, "keywords": keywords,
                        "languages": languages or {}, "hashtags": tags, **({"region": region} if region else {})},
            "tiktok": {"keywords": keywords[:3], "hashtags": tags[:3]},
        },
        "watch": {"youtube": [], "instagram": [], "tiktok": []},
        "seeds": [],
        "filters": {"min_views": 5000, "max_age_days": 60, "must_match": derive_must_match(keywords),
                    "exclude": BASE_EXCLUDE},
        "enrich_top": 60,
        "recheck": {"max_age_days": 30, "limit": 60},
        "report": {"top": 25, "hooks": 20, "transcripts": 30},
        "transcribe": {"whisper": True, "model": "base", "max_per_run": 6, "max_seconds": 180},
        "budget": {"youtube_api_units_per_day": 10000, "apify_items_per_month": 0},
    }
    if vault:
        prof["output_dir"] = vault
        prof["swipe_dir"] = vault + "/swipe"
    header = (f"# {'Quick research' if research else 'Project'} profile created by `viral_scout new`. "
              "Tune keywords, hashtags, must_match and exclude after the first run (docs/profiles.md).\n")
    path.write_text(header + yaml.safe_dump(prof, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
    return name, path


def parse_list(s):
    return [x.strip() for x in re.split(r"[;\n]|,(?=\s*[^\d])", s or "") if x.strip()]


def parse_languages(s):
    out = {}
    for part in parse_list(s):
        if "=" in part:
            k, v = part.rsplit("=", 1)
            out[k.strip()] = v.strip()
    return out
