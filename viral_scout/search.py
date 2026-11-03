"""Search everything ever collected (all runs, all profiles): titles, hooks, CTAs, transcripts, captions, creators.

BM25 ranking in pure Python, no extra install. Works in any language the text is in (Cyrillic included).
  python -m viral_scout search "polite rude phrases" [--profile englishSchool] [--limit 20]
"""
import math
import re
import sqlite3
from collections import Counter
from pathlib import Path

from . import config

TOKEN = re.compile(r"[\w']+", re.UNICODE)
STOP = set("a an and are as at be but by for from has have i if in is it its of on or so that the this to was we with "
           "you your my me our they them he she his her not no do does did can just how what why when who will "
           "и в во не на что как это я ты он она мы вы они с со а но по за из у к о от до же ли бы так все вот "
           "і та що як це не на з до у в за по від ми ви вони він вона".split())


def tokens(text):
    return [t for t in (m.group(0).lower() for m in TOKEN.finditer(text or "")) if t not in STOP and len(t) > 1]


def _docs(profiles):
    for name in profiles:
        cfg = config.load(name)
        if not Path(cfg["db"]).exists():
            continue
        db = sqlite3.connect(cfg["db"])
        cols = {r[1] for r in db.execute("pragma table_info(items)")}
        want = [c for c in ("hook", "cta", "transcript", "description", "dismissed", "saved") if c in cols]
        q = f"select key, platform, id, url, title, channel, {', '.join(want)} from items"
        for row in db.execute(q):
            rec = dict(zip(["key", "platform", "id", "url", "title", "channel", *want], row))
            if rec.get("dismissed"):
                continue
            latest = db.execute("select views, likes from snapshots where key=? order by ts desc limit 1",
                                (rec["key"],)).fetchone()
            rec["views"], rec["likes"] = latest if latest else (None, None)
            rec["profile"] = name
            # Title and hook count double: they are what the post is about.
            rec["_text"] = " ".join([rec.get("title") or ""] * 2 + [rec.get("hook") or ""] * 2 +
                                    [rec.get("cta") or "", rec.get("transcript") or "",
                                     (rec.get("description") or "")[:1500], rec.get("channel") or ""])
            yield rec


def search(query, profiles=None, limit=20):
    if not profiles:
        profiles = [p.stem for p in config.PROFILES.glob("*.yaml") if not p.stem.startswith("_")]
    docs = list(_docs(profiles))
    q = tokens(query)
    if not q or not docs:
        return []
    toks = [Counter(tokens(d["_text"])) for d in docs]
    lens = [sum(t.values()) for t in toks]
    avg = sum(lens) / len(lens) or 1
    df = Counter(w for t in toks for w in set(t) if w in q)
    n, k1, b = len(docs), 1.5, 0.75
    scored = []
    for d, t, ln in zip(docs, toks, lens):
        s = 0.0
        for w in q:
            f = t.get(w, 0)
            if not f:
                continue
            idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
            s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * ln / avg))
        if s > 0:
            phrase = query.lower() in d["_text"].lower()
            scored.append((s * (1.5 if phrase else 1.0), d))
    scored.sort(key=lambda x: -x[0])
    out = []
    for s, d in scored[:limit]:
        text = d.get("transcript") or d.get("description") or ""
        out.append({k: d.get(k) for k in ("profile", "platform", "id", "url", "title", "channel", "views", "likes",
                                           "hook", "cta", "saved")}
                   | {"score": round(s, 2), "snippet": snippet(text, q)})
    return out


def snippet(text, q, width=160):
    low = (text or "").lower()
    pos = min((low.find(w) for w in q if low.find(w) >= 0), default=-1)
    if pos < 0:
        return (text or "")[:width]
    start = max(0, pos - width // 3)
    return ("…" if start else "") + text[start:start + width].replace("\n", " ") + "…"
