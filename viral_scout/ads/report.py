"""Ads report: Markdown for Obsidian (<output_dir>/<date>-ads-scout.md) + data/<profile>-ads-latest.json."""
import json
from datetime import datetime
from pathlib import Path

from ..report import cell, n

OFFER_NAMES = {
    "price": "price shown", "free_trial": "free trial / lesson", "free_quote": "free quote / consult",
    "free": "\"free\" claim", "discount": "discount / sale", "guarantee": "guarantee", "financing": "financing / $0 down",
    "incentive": "tax credit / rebate", "urgency": "urgency / scarcity", "social_proof": "social proof",
}
SOURCE_NAMES = {
    "meta_api": "Meta API", "tiktok_api": "TikTok API", "apify_meta": "Meta (Apify)",
    "apify_tiktok_top": "TikTok Top Ads (Apify)", "apify_google": "Google (Apify)",
}


def days(v):
    return "—" if v is None else f"{v:.0f} d"


def _offers(a):
    return ", ".join(OFFER_NAMES.get(o, o) for o in a.offers) or "—"


def _ad_table(ads):
    if not ads:
        return ["_Nothing here this run._", ""]
    out = ["| # | Ad (hook) | Advertiser | Running | Variants | Reach | Format | Platforms | Offer | Labels | Score |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, a in enumerate(ads, 1):
        hook = cell(a.hook or a.title or a.id, 60)
        link = f"[{hook}]({a.url})" if a.url else hook
        out.append(f"| {i} | {link}{' 🆕' if a.new else ''} | {cell(a.advertiser, 28)} | {days(a.days_running)} | "
                   f"{a.variants} | {n(a.reach)} | {a.format or '—'} | {cell(', '.join(a.platforms), 30) or '—'} | "
                   f"{cell(_offers(a), 40)} | {cell(' '.join(a.labels), 40)} | {a.ad_score:.0f} |")
    return out + [""]


def _card(a):
    out = [f"### {cell(a.advertiser, 50) or 'Unknown advertiser'}: {cell(a.hook or a.title or a.id, 80)}", ""]
    meta = [f"{days(a.days_running)} running" + (" (still running)" if a.is_active else " (stopped)"),
            f"{a.variants} variant{'s' if a.variants != 1 else ''}", a.format or "format unknown",
            ", ".join(a.platforms) or "", f"reach {n(a.reach)} ({a.reach_label})" if a.reach else "",
            SOURCE_NAMES.get(a.source, a.source), f"score {a.ad_score:.0f}"]
    out.append(" · ".join(m for m in meta if m) + (f" · {' '.join(a.labels)}" if a.labels else ""))
    out.append("")
    if a.image:
        out += [f"![creative|220]({a.image})", ""]
    if a.hook:
        out += [f"> **Hook:** {cell(a.hook, 300)}", ""]
    if a.offers:
        out += [f"> **Offer:** {_offers(a)}" + (f" ({'; '.join(cell(s, 40) for s in a.offer_text)})" if a.offer_text else ""), ""]
    bits = []
    if a.cta:
        bits.append(f"**CTA:** {cell(a.cta, 60)}")
    if a.landing_domain:
        bits.append(f"**Landing:** {a.landing_domain}")
    if a.start:
        bits.append(f"**Started:** {a.start:%Y-%m-%d}")
    if a.url:
        bits.append(f"[open in the library]({a.url})")
    if bits:
        out += [" · ".join(bits), ""]
    if a.body and a.body.strip() != a.hook.strip():
        t = a.body if len(a.body) <= 600 else a.body[:600] + "…"
        out += ["> [!quote]- Ad copy", "> " + t.replace("\n", "\n> "), ""]
    return out


def _one_per_group(ads):
    """Keep the best-scored ad of each variant group (ads arrive sorted by score)."""
    seen, out = set(), []
    for a in ads:
        g = a.group or a.key
        if g not in seen:
            seen.add(g)
            out.append(a)
    return out


def write(cfg, res):
    ads, adv = res["ads"], res["advertisers"]
    now = datetime.now()
    top = int((cfg.get("ads") or {}).get("top", 30))
    ranked = _one_per_group(ads)                      # variants of one creative → one row (best-scored)
    long_runners = [a for a in ranked if (a.days_running or 0) >= 30]
    new_tests = sorted([a for a in ads if "🆕 new test" in a.labels], key=lambda a: a.age_days or 0)
    lines = [
        "---", "type: ads-report", f"profile: {cfg['name']}", f"date: {now:%Y-%m-%d}", "tags: [viral-scout, ads]", "---", "",
        f"# Ads scout: {cfg['name']}, {now:%Y-%m-%d %H:%M}", "",
        f"{len(ads)} ads from {len(adv)} advertisers. Countries: {', '.join(res.get('countries') or [])}. "
        f"Sources that ran: {', '.join(sorted({SOURCE_NAMES.get(a.source, a.source) for a in ads})) or 'none'}.", "",
        "> [!info] How to read it",
        "> Nobody outside an advertiser sees spend or ROAS, so **these scores are proxies, not performance data**. "
        "An ad that keeps running for months is probably paying for itself; advertisers scale winners into many "
        "variants. **ad_score** (0–100) = 0.5 × longevity (ln-scaled, 120+ days = full) + 0.3 × variants "
        "(10+ = full) + 0.2 × still running + up to 0.15 × reach percentile where the source publishes reach. "
        "🏆 = running 30/60/90+ days · 🧬 = 3+ variants · 🆕 = new test (≤14 days) · ⏹ = stopped. "
        "Formulas: docs/ads-scout.md.", "",
        "> [!warning] Use them for angles, never copy them",
        "> Borrow the *angle* (the problem, the offer type, the format). Never reuse competitors' creatives, footage, "
        "copy or trademarks. Every claim in your own ads must be true and provable (FTC).", "",
    ]
    if res.get("coverage"):
        lines += ["## Coverage", ""] + [f"- {c}" for c in res["coverage"]] + [""]
    lines += ["## Advertisers", ""]
    if adv:
        lines += ["| Advertiser | Ads | Active | Longest | 30d+ | Max variants | Formats | Top offers | New (14 d) |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for r in adv[:40]:
            fm = ", ".join(f"{k} {v}" for k, v in r["formats"].items())
            of = ", ".join(OFFER_NAMES.get(k, k) for k in r["offers"]) or "—"
            burst = f"{r['launched_last_14d']}" + (" 🚀 burst" if r["launch_burst"] else "")
            lines.append(f"| {cell(r['advertiser'], 30)} | {r['ads']} | {r['active']} | {days(r['longest_days'])} | "
                         f"{r['long_runners']} | {r['max_variants']} | {cell(fm, 40)} | {cell(of, 50)} | {burst} |")
        lines.append("")
    else:
        lines += ["_No ads collected this run (see Skipped sources, and the lookup links below)._", ""]
    lines += ["## Winning ads (by ad_score)", "",
              "One row per creative; the Variants column counts its versions."] + [""] + _ad_table(ranked[:top])
    if res.get("offers"):
        lines += ["## Offers that keep running", "",
                  "How often each offer type appears, overall and in ads running 30+ days.", "",
                  "| Offer | Ads | In 30d+ ads |", "|---|---|---|"]
        lines += [f"| {OFFER_NAMES.get(o['offer'], o['offer'])} | {o['ads']} | {o['long_runners']} |" for o in res["offers"]]
        lines.append("")
    if long_runners:
        lines += ["## Hooks of the long-runners (30+ days)", ""]
        seen = set()
        for a in long_runners[:25]:
            h = (a.hook or a.title).strip()
            if h and h.lower() not in seen:
                seen.add(h.lower())
                lines.append(f"- “{cell(h, 160)}” · {cell(a.advertiser, 30)} · {days(a.days_running)}"
                             + (f" · {a.variants} variants" if a.variants > 1 else ""))
        lines.append("")
    if new_tests:
        lines += ["## New tests (started in the last 14 days)", "",
                  "What advertisers are trying right now. Watch which ones survive the next runs.", ""]
        lines += [f"- {cell(a.advertiser, 30)}: [{cell(a.hook or a.title or a.id, 100)}]({a.url}) · {a.format or '—'}"
                  for a in new_tests[:15]] + [""]
    if ads:
        lines += ["## Top ads in detail", ""]
        for a in ranked[: min(15, top)]:
            lines += _card(a)
    if res.get("lookup"):
        lines += ["## Look them up yourself", "",
                  "Public library pages to open in your browser (the tool doesn't fetch these pages).", ""]
        for r in res["lookup"]:
            lines.append(f"- **{cell(r['label'], 50)}** ({r['kind']}): " +
                         " · ".join(f"[{k}]({v})" for k, v in r["links"].items()))
        lines.append("")
    u = res.get("usage") or {}
    if u or res.get("budget"):
        lines += ["## Usage this run", "", " · ".join(f"{k.replace('_', ' ')}: {v:,}" for k, v in sorted(u.items()))
                  or "nothing counted", ""] + [f"- ⚠️ {w}" for w in res.get("budget") or []] + [""]
    if res["skipped"]:
        lines += ["## Skipped sources", ""] + [f"- {s}" for s in res["skipped"]] + [""]
    if res["errors"]:
        lines += ["## Errors", ""] + [f"- {cell(e, 240)}" for e in res["errors"][:30]] + [""]

    out_dir = Path((cfg.get("ads") or {}).get("output_dir") or cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / f"{now:%Y-%m-%d}-ads-scout.md"
    md.write_text("\n".join(lines), encoding="utf-8")

    data = Path(cfg["db"]).parent / f"{cfg['name']}-ads-latest.json"
    data.write_text(json.dumps({
        "profile": cfg["name"], "date": now.isoformat(), "report": str(md), "countries": res.get("countries"),
        "ads": [a.to_json() for a in ads], "advertisers": adv, "offers": res.get("offers", []),
        "coverage": res.get("coverage", []), "lookup": res.get("lookup", []), "skipped": res["skipped"],
        "errors": res["errors"], "usage": res.get("usage", {}), "budget": res.get("budget", []),
        "sources_requested": res.get("sources_requested", []),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(md), str(data)
