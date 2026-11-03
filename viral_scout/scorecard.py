"""Creative scorecard: 20 criteria rated 1–5 and a 100-point score, for any video (others' or your own draft).

The ratings come from the AI step (the /viral-scout skill reads title, hook, CTA, transcript, frames, comments and
numbers) and are stored per profile in data/scores/<profile>.json. This module validates them and computes totals.
It is a subjective creative assessment, not a prediction of views or sales: always read it next to real numbers.

  python -m viral_scout score set <profile> <post_id> < ratings.json     (from the skill)
  python -m viral_scout score show <profile> [<post_id>]
"""
import json
from datetime import datetime
from pathlib import Path

from . import config

# The 20 criteria (key, label, what to evaluate) and the 100-point group each feeds.
CRITERIA = [
    ("hook", "Hook", "Grabs attention in the first 1–3 seconds", "hook"),
    ("first_frame", "First-frame impact", "The opening visual stands out immediately", "hook"),
    ("audience", "Target audience", "Relevant to the intended viewer", "audience"),
    ("engagement", "Engagement", "Invites meaningful interaction", "audience"),
    ("retention", "Retention", "Keeps viewers watching", "retention"),
    ("watch_time", "Watch time", "Interesting enough to sustain attention", "retention"),
    ("pacing", "Pacing", "Every second serves a purpose", "retention"),
    ("storytelling", "Storytelling", "Clear progression from start to payoff", "retention"),
    ("pattern_interrupts", "Pattern interrupts", "Visual or narrative changes renew attention", "retention"),
    ("clarity", "Clarity", "The main message is understood quickly", "clarity"),
    ("value", "Value proposition", "The benefit to the viewer is obvious", "clarity"),
    ("emotion", "Emotional impact", "Curiosity, excitement, urgency, empathy…", "clarity"),
    ("credibility", "Credibility / proof", "Claims backed by demonstration, testimonial or evidence", "proof"),
    ("authenticity", "Authenticity", "Natural, credible, relatable", "proof"),
    ("cta", "CTA", "A clear, compelling next action", "cta"),
    ("conversion", "Conversion potential", "Can persuade the right audience to act", "cta"),
    ("visual", "Visual appeal", "Framing, lighting, graphics, editing", "production"),
    ("audio", "Audio quality", "Clear voice, appropriate sound", "production"),
    ("platform_fit", "Platform fit", "Adapted to the platform and how people use it", "platform"),
    ("shareability", "Shareability", "Worth sending to someone or saving", "platform"),
]
GROUPS = [  # (key, label, points)
    ("hook", "Hook and first frame", 15),
    ("audience", "Audience relevance", 15),
    ("retention", "Retention, storytelling and pacing", 15),
    ("clarity", "Clarity and value proposition", 15),
    ("proof", "Credibility and proof", 10),
    ("cta", "CTA and conversion readiness", 10),
    ("production", "Visual and audio production", 10),
    ("platform", "Platform-native execution", 5),
    ("compliance", "Accessibility and compliance", 5),
]
KEYS = {c[0] for c in CRITERIA}


def folder():
    p = config.ROOT / "data" / "scores"
    p.mkdir(parents=True, exist_ok=True)
    return p


def compute(card):
    """card: {"criteria": {key: {"score": 1-5, "why": str}}, "compliance": {"score": 1-5, "why": str}, ...}
    → adds group ratings (mean of their criteria), points, total /100, a verdict."""
    crit = card.get("criteria") or {}
    for k, v in list(crit.items()):
        if k not in KEYS:
            raise ValueError(f"unknown criterion {k}")
        s = v.get("score") if isinstance(v, dict) else v
        if not isinstance(s, (int, float)) or not 1 <= s <= 5:
            raise ValueError(f"{k}: score must be 1–5")
        crit[k] = {"score": round(float(s), 1), "why": (v.get("why", "") if isinstance(v, dict) else "")[:300]}
    groups, total, possible = {}, 0.0, 0
    for gk, label, pts in GROUPS:
        if gk == "compliance":
            c = card.get("compliance") or {}
            vals = [c["score"]] if isinstance(c, dict) and c.get("score") else []
        else:
            vals = [crit[k]["score"] for k, _, _, g in CRITERIA if g == gk and k in crit]
        if not vals:
            continue
        rating = sum(vals) / len(vals)
        points = rating / 5 * pts
        groups[gk] = {"label": label, "rating": round(rating, 1), "points": round(points, 1), "max": pts}
        total += points
        possible += pts
    score = round(total / possible * 100) if possible else None
    card["groups"] = groups
    card["total"] = score
    card["verdict"] = verdict(score)
    return card


def verdict(score):
    if score is None:
        return ""
    return ("Excellent" if score >= 85 else "Strong" if score >= 70 else "Promising, needs improvement" if score >= 55
            else "Needs work" if score >= 40 else "Weak")


def load(profile):
    f = folder() / f"{profile}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def save(profile, post_id, card, model="claude"):
    card = compute(dict(card))
    card.update(scored=datetime.now().isoformat(timespec="seconds"), model=model)
    data = load(profile)
    data[post_id] = card
    (folder() / f"{profile}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return card


def template():
    """What the skill fills in."""
    return {"criteria": {k: {"score": 3, "why": what} for k, _, what, _ in CRITERIA},
            "compliance": {"score": 3, "why": "accessible captions, accurate claims, rights to music/footage"},
            "summary": "one-sentence verdict", "fix_first": "the single change that would help most"}
