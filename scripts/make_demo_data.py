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
    (out / f"{name}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    live = d["items"]
    top = sorted([i for i in live if (i.get("outlier") or 0) >= 3], key=lambda i: -(i.get("weighted") or 0))[:4]
    index.append({"name": name, "date": d["date"], "business": biz, "posts": len(live),
      "outliers": sum(1 for i in live if (i.get("outlier") or 0) >= 3), "mega": sum(1 for i in live if (i.get("outlier") or 0) >= 10),
      "new": 0, "saved": len(d["swipe"]), "ideas": len(d["ideas"]),
      "top": [{"title": i["title"], "thumbnail": i.get("thumbnail"), "outlier": i.get("outlier"), "channel": i["channel"], "url": i["url"]} for i in top]})
(out / "index.json").write_text(json.dumps({"exported": json.loads((src / "index.json").read_text(encoding="utf-8"))["exported"], "profiles": index}, ensure_ascii=False), encoding="utf-8")
print("demo:", [p["name"] for p in index], [p["posts"] for p in index])
