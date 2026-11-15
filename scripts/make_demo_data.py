"""Sanitized demo copy of the dashboard data (for screenshots and the public demo).

  python scripts/make_demo_data.py web/data web/data-demo
Generic profile names and descriptions, public YouTube posts only, no business strategy, places, local paths or
real profile names. Edit DEMO below to map your profiles to demo names. Then: scripts/publish-demo.ps1
"""
import json, re, sys
from pathlib import Path
src = Path(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
DEMO = {
  "englishSchool": ("language-school", "Online English school for adult beginners. Short selfie-style lessons filmed on a phone: everyday phrases, pronunciation, plain-vs-native English, with humour."),
  "northForge": ("home-services", "Local home-services company: gutters, holiday lights, handyman repairs. Videos filmed on real jobs: before/after, quick homeowner tips, seasonal reveals."),
}
SCRUB = [(r"native-language/native-language", "native-language"), (r"Daisy🇺🇸", "Daisy"),(r"Norridge|Park Ridge|Niles|Des Plaines|Harwood Heights|Chicago|Illinois|\bIL\b|60706", "our area"),
         (r"Northforge", "the company"), (r"Ukrainian|Russian|UA/RU|UA / RU|Ukrainian- and Russian-speaking", "native-language"),
         (r"\(UA / RU\)|\(UA/RU\)", "")]
def scrub(s):
    for a, b in SCRUB: s = re.sub(a, b, s)
    return s
# ---- ads + search demand (2026-11-14): anonymized, text and numbers only ----
# Advertisers become "Competitor A, B, …"; their names and domains are scrubbed out of the copy; no creatives
# (images, video), ad-library links, landing URLs or AI extras. Demand: no area, no Trends links, no related
# searches that name a brand or a place.
AD_KEEP = ["key", "source", "id", "advertiser", "body", "title", "link_caption", "landing_domain", "cta_text", "format",
           "platforms", "countries", "start", "stop", "active", "days_running", "reach", "reach_label", "likes", "variants",
           "group", "hook", "offers", "offer_text", "cta", "ad_score", "labels", "found_by", "new", "first_seen", "last_seen"]
BRANDS_EXTRA = r"ned stevens|leaf ?filter|leafguard|gutter ?helmet|feldco|andersen|angi\b|angie'?s|home ?advisor|thumbtack|"                r"mr\.? ?handyman|ace handyman|window genie|christmas decor|brothers that just do gutters|4 ?ever|"                r"home genius|clean pro|leaf blaster|lowe'?s|home depot|menards|costco|ace hardware|sam'?s club|amazon|walmart|yelp|nextdoor|taskrabbit"
PHONE = r"\(?\b\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b"


def letters(n):
    out = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def demo_ads(real, name, biz):
    f = src / "ads" / f"{real}.json"
    if not f.exists():
        return None
    a = json.loads(f.read_text(encoding="utf-8"))
    counts = {}
    for ad in a["ads"]:
        counts[ad.get("advertiser") or ""] = counts.get(ad.get("advertiser") or "", 0) + 1
    names = [n for n, _ in sorted(counts.items(), key=lambda x: -x[1]) if n]
    amap = {n: f"Competitor {letters(i)}" for i, n in enumerate(names)}
    doms = {}
    for ad in a["ads"]:
        d = (ad.get("landing_domain") or "").lower()
        if d and ad.get("advertiser") in amap:
            doms.setdefault(d, amap[ad["advertiser"]].split()[-1].lower())
    full = sorted((n for n in names if len(n) >= 3), key=len, reverse=True)   # whole names only: single words
    area = re.compile(r"(?:north ?west )?chicago(?:land)?|illinois|northwest suburbs|north shore|norridge|park ridge|des plaines|"  # like
                      r"harwood heights|niles|evanston|skokie|schaumburg|naperville|elmhurst|oak park|60706", re.I)  # "Lights"

    def clean(t):                                                             # are too common to replace
        if not isinstance(t, str):
            return t
        t = re.sub(r"https?://\S+|www\.\S+", "", t)
        t = re.sub(r"\b[\w-]+(?:\.[\w-]+)*\.(?:com|net|org|co|us|io|biz)\b",
                   lambda m: f"competitor-{doms[m.group(0).lower()]}.example" if m.group(0).lower() in doms else "example.com",
                   t, flags=re.I)
        for n in full:
            t = re.sub(rf"(?<!\w){re.escape(n)}(?!\w)", amap[n], t, flags=re.I)
        t = re.sub(BRANDS_EXTRA, "the company", t, flags=re.I)
        t = re.sub(PHONE, "(555) 010-0000", t)
        t = area.sub("our area", t)
        return scrub(t)

    ads = []
    for ad in a["ads"]:
        x = {k: ad[k] for k in AD_KEEP if k in ad}
        x["advertiser"] = amap.get(ad.get("advertiser") or "", "Unknown advertiser")
        for k in ("body", "title", "link_caption", "cta_text", "hook", "cta"):
            if k in x:
                x[k] = clean(x[k])
        x["offer_text"] = [clean(o) for o in x.get("offer_text") or []]
        d = (ad.get("landing_domain") or "").lower()
        x["landing_domain"] = f"competitor-{doms[d]}.example" if d in doms else ("" if d else "")
        x["found_by"] = [clean(fb) for fb in x.get("found_by") or []]
        x["url"], x["image"], x["video"] = "", "", ""
        x["id"] = f"demo{len(ads) + 1:04d}"             # real ids would lead straight back to the ad in the library
        x["key"] = f"{x['source']}:{x['id']}"
        ads.append(x)
    advs = []
    for r in a["advertisers"]:
        r = dict(r, advertiser=amap.get(r["advertiser"], "Unknown advertiser"),
                 domains=[f"competitor-{doms[d.lower()]}.example" for d in r.get("domains") or [] if d.lower() in doms])
        advs.append(r)
    return {"profile": name, "business": biz, "date": a["date"], "countries": a.get("countries", []), "ads": ads,
            "advertisers": advs, "offers": a.get("offers", []), "coverage": [clean(c) for c in a.get("coverage", [])],
            "lookup": [], "skipped": [clean(x) for x in a.get("skipped", [])], "errors": [], "usage": {}, "budget": [],
            "reports": []}


def demo_demand(real, name):
    f = src / "demand" / f"{real}.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    bad = re.compile(BRANDS_EXTRA + r"|chicago|illinois|\bil\b|norridge|park ridge|niles|des plaines|evanston|naperville|"
                     r"schaumburg|arlington|elmhurst|oak park|skokie", re.I)
    for t in d.get("terms", []):
        t.pop("trends_url", None)
        rel = t.get("related") or {}
        for k in ("rising", "top", "rising_topics"):
            rel[k] = [q for q in rel.get(k) or [] if not bad.search(str(q.get("query") or q.get("title") or ""))]
        rel["places"] = []
    if d.get("compare"):
        d["compare"].pop("trends_url", None)
    d.update(profile=name, geo="local metro", errors=[], skipped=[], usage={})
    text = re.sub(r"US-[A-Z]{2}(?:-\d+)?", "the state", json.dumps(d, ensure_ascii=False))
    text = re.sub(r"(?i)chicago(?:land)?|illinois", "our area", text)
    return json.loads(text)


index = []
for real, (name, biz) in DEMO.items():
    d = json.loads((src / f"{real}.json").read_text(encoding="utf-8"))
    d["name"], d["business"] = name, biz
    d["items"] = [i for i in d["items"] if not i["tracked"] and i["platform"] == "youtube"]   # public YouTube only
    keys = {i["key"] for i in d["items"]}
    d["sections"] = {k: [x for x in v if x in keys] for k, v in d["sections"].items()}
    d["sections"]["seeds"] = []
    for i in d["items"]:
        i["saved"] = False
    # ideas: keep only the generic parts (patterns + breakdown)
    ideas = []
    for n in d["ideas"]:
        md = n["markdown"]
        md = re.split(r"\n## Ideas", md)[0]
        md = scrub(md).replace(real, name)
        md = re.sub(r"\[\[[^\]]+\]\]", "the run report", md)
        ideas.append({**n, "markdown": md + "\n\n## Ideas\n\n_Five ideas adapted to the business are written here by the AI step (kept private in this demo)._\n"})
    d["ideas"] = ideas
    d["swipe"] = [{**s, "profile": name, "creator": s.get("creator"), "body": re.sub(r"## Our version[\s\S]*", "", s.get("body", ""))} for s in d["swipe"] if s.get("platform") == "youtube"]
    d["skipped"] = [scrub(s) for s in d["skipped"]]; d["errors"] = []
    d["runs"] = [{"ts": r["ts"], "items": r.get("items"), "errors": 0} for r in d["runs"][:5]]
    for s in d["swipe"]:
        s["profile"] = name
        s.pop("creator_url", None)
    for i in d["items"]:
        i["frame"] = ""
    ads = demo_ads(real, name, biz)
    if ads:
        (out / "ads").mkdir(exist_ok=True)
        (out / "ads" / f"{name}.json").write_text(json.dumps(ads, ensure_ascii=False), encoding="utf-8")
        d["ads_summary"] = {"date": ads["date"], "ads": len(ads["ads"]), "advertisers": len(ads["advertisers"])}
    else:
        d["ads_summary"] = None
    dem = demo_demand(real, name)
    if dem:
        (out / "demand").mkdir(exist_ok=True)
        (out / "demand" / f"{name}.json").write_text(json.dumps(dem, ensure_ascii=False), encoding="utf-8")
    d["display_name"] = None
    d["budget"] = []
    (out / f"{name}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    live = d["items"]
    top = sorted([i for i in live if (i.get("outlier") or 0) >= 3], key=lambda i: -(i.get("weighted") or 0))[:4]
    index.append({"name": name, "date": d["date"], "business": biz, "posts": len(live),
      "outliers": sum(1 for i in live if (i.get("outlier") or 0) >= 3), "mega": sum(1 for i in live if (i.get("outlier") or 0) >= 10),
      "new": 0, "saved": len(d["swipe"]), "ideas": len(d["ideas"]),
      "ads": len(ads["ads"]) if ads else None, "demand": bool(dem),
      "top": [{"title": i["title"], "thumbnail": i.get("thumbnail"), "outlier": i.get("outlier"), "channel": i["channel"], "url": i["url"]} for i in top]})
(out / "index.json").write_text(json.dumps({"exported": json.loads((src / "index.json").read_text(encoding="utf-8"))["exported"], "profiles": index}, ensure_ascii=False), encoding="utf-8")
print("demo:", [p["name"] for p in index], [p["posts"] for p in index])
