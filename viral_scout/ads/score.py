"""Which ads are "winning": proxies only (nobody outside the advertiser sees spend or ROAS).

  longevity  L = min(1, ln(1 + days running) / ln(1 + 120))      120+ days → 1.0; 30 d ≈ 0.72; 7 d ≈ 0.43
  variants   V = min(1, ln(variants) / ln(10))                     1 → 0, 3 → 0.48, 10+ → 1.0
  activity   A = 1 if still running; 0.5 if it stopped in the last 14 days; else 0
  reach      R = percentile of the ad's reach among this run's ads from the same source (0–1), when published
  ad_score = round(100 × min(1, 0.5·L + 0.3·V + 0.2·A + 0.15·R))   (R only adds; ads without reach aren't penalised)

Variants: ads from the same advertiser that share their copy fingerprint (first ~25 words) or their landing page
(domain + path) are one creative group; variants = max(group size, the source's own count, e.g. Meta collationCount).

Labels: 🏆 90d+ / 🏆 60d+ / 🏆 30d+ long-runner · 🧬 N variants (≥3) · 📈 top reach (top 10%, ≥10 ads with reach)
        · 🆕 new test (running, started ≤14 days ago) · ⏹ stopped
"""
import math
from collections import Counter, defaultdict
from datetime import timedelta
from urllib.parse import urlparse

from . import extract
from .model import Ad, now, unwrap

LONG_RUNNER_DAYS = (90, 60, 30)
NEW_DAYS = 14


def enrich(ads):
    """Fill hook, offers and CTA from the copy."""
    for a in ads:
        a.hook = a.hook or extract.hook(a.title, a.body)
        a.offers, a.offer_text = extract.offers(a.text())
        a.cta = extract.cta(a.cta_text, a.text())
    return ads


def _landing_key(a: Ad):
    u = unwrap(a.link_url)
    if not u:
        return ""
    try:
        p = urlparse(u if "://" in u else "https://" + u)
    except ValueError:
        return ""
    path = (p.path or "/").rstrip("/") or "/"
    return f"{a.landing_domain}{path}" if a.landing_domain else ""


def group_variants(ads):
    """Union-find over (advertiser, copy fingerprint) and (advertiser, landing page)."""
    parent = list(range(len(ads)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    seen = {}
    for i, a in enumerate(ads):
        who = (a.advertiser or a.advertiser_id or "?").lower()
        keys = []
        fp = extract.normalize_copy(a.body or a.title)
        if len(fp.split()) >= 4:
            keys.append(("copy", who, fp))
        lk = _landing_key(a)
        if lk and not lk.endswith("/"):
            keys.append(("land", who, lk))          # a bare homepage is shared by unrelated ads, so it doesn't count
        for k in keys:
            if k in seen:
                parent[find(i)] = find(seen[k])
            else:
                seen[k] = i
    groups = defaultdict(list)
    for i in range(len(ads)):
        groups[find(i)].append(i)
    for root, members in groups.items():
        gid = f"g{root}"
        for i in members:
            ads[i].group = gid
            ads[i].variants = max(len(members), ads[i].variants_reported or 1)
    return ads


def _percentiles(ads):
    by_src = defaultdict(list)
    for a in ads:
        if a.reach:
            by_src[a.source].append(a.reach)
    for a in ads:
        vals = by_src.get(a.source)
        if a.reach and vals and len(vals) >= 2:
            a.reach_pct = sum(1 for v in vals if v < a.reach) / (len(vals) - 1)
        elif a.reach and vals:
            a.reach_pct = 0.5
    return {s: len(v) for s, v in by_src.items()}


def components(a: Ad):
    days = a.days_running
    L = min(1.0, math.log1p(days) / math.log1p(120)) if days is not None else 0.0
    V = min(1.0, math.log(a.variants) / math.log(10)) if a.variants and a.variants > 1 else 0.0
    if a.is_active:
        A = 1.0
    elif a.stop and (now() - a.stop) <= timedelta(days=14):
        A = 0.5
    else:
        A = 0.0
    R = a.reach_pct or 0.0
    return L, V, A, R


def score(ads):
    """Group variants, compute reach percentiles, ad_score and labels. Returns ads sorted best first."""
    group_variants(ads)
    reach_n = _percentiles(ads)
    for a in ads:
        L, V, A, R = components(a)
        a.ad_score = round(100 * min(1.0, 0.5 * L + 0.3 * V + 0.2 * A + 0.15 * R), 1)
        labels = []
        d = a.days_running
        for t in LONG_RUNNER_DAYS:
            if d is not None and d >= t:
                labels.append(f"🏆 {t}d+ long-runner")
                break
        if a.variants >= 3:
            labels.append(f"🧬 {a.variants} variants")
        if a.reach_pct is not None and a.reach_pct >= 0.9 and reach_n.get(a.source, 0) >= 10:
            labels.append("📈 top reach")
        if a.is_active and a.age_days is not None and a.age_days <= NEW_DAYS:
            labels.append("🆕 new test")
        if not a.is_active:
            labels.append("⏹ stopped")
        a.labels = labels
    ads.sort(key=lambda a: (-a.ad_score, -(a.days_running or 0)))
    return ads


def advertisers(ads):
    """One summary row per advertiser: ads, active, longest run, max variants, formats, offers, recent launches."""
    by = defaultdict(list)
    for a in ads:
        by[a.advertiser or a.advertiser_id or "?"].append(a)
    rows = []
    cutoff = now() - timedelta(days=NEW_DAYS)
    for name, group in by.items():
        days = [a.days_running for a in group if a.days_running is not None]
        recent = [a for a in group if a.start and a.start >= cutoff]
        offers = Counter(o for a in group for o in a.offers)
        rows.append({
            "advertiser": name,
            "ads": len(group),
            "active": sum(1 for a in group if a.is_active),
            "longest_days": round(max(days), 1) if days else None,
            "long_runners": sum(1 for d in days if d >= 30),
            "max_variants": max(a.variants for a in group),
            "groups": len({a.group for a in group}),
            "formats": dict(Counter(a.format or "unknown" for a in group)),
            "platforms": sorted({p for a in group for p in a.platforms}),
            "offers": dict(offers.most_common(6)),
            "launched_last_14d": len(recent),
            "launch_burst": len(recent) >= 3,
            "domains": sorted({a.landing_domain for a in group if a.landing_domain})[:5],
            "sources": sorted({a.source for a in group}),
            "best_score": max(a.ad_score for a in group),
        })
    rows.sort(key=lambda r: (-r["best_score"], -r["ads"]))
    return rows


def offer_summary(ads):
    """How often each offer type appears overall and among long-runners (≥30 days)."""
    allc = Counter(o for a in ads for o in a.offers)
    longc = Counter(o for a in ads if (a.days_running or 0) >= 30 for o in a.offers)
    return [{"offer": o, "ads": n, "long_runners": longc.get(o, 0)} for o, n in allc.most_common()]
