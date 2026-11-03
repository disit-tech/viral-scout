"""Local competitors: nearby businesses in your niche (Google Places API, official) and their public social channels.

  python -m viral_scout competitors <profile> ["gutter cleaning"] [--near "Norridge, IL"]
Profile: local: {query: "gutter cleaning", near: "Norridge, IL", limit: 15}
For each business we open its own public homepage (one normal request, honest user agent) and collect links to
YouTube / Instagram / TikTok / Facebook. Result: a vault note with watch-list candidates.
"""
import os
import re
from datetime import date
from pathlib import Path

import requests

from . import usage

FIELDS = "places.displayName,places.formattedAddress,places.websiteUri,places.rating,places.userRatingCount,places.googleMapsUri"
SOCIAL = {
    "youtube": re.compile(r"https?://(?:www\.)?youtube\.com/(?:@[\w.-]+|channel/[\w-]+|c/[\w-]+|user/[\w-]+)", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/(?!p/|reel/|explore/)[\w.]+", re.I),
    "tiktok": re.compile(r"https?://(?:www\.)?tiktok\.com/@[\w.]+", re.I),
    "facebook": re.compile(r"https?://(?:www\.)?facebook\.com/(?!sharer|share|plugins|tr\?)[\w.-]+", re.I),
}
UA = "viral-scout/1.0 (+https://github.com/disit-tech/viral-scout) competitor-research"


def available():
    return bool(os.environ.get("GOOGLE_PLACES_API_KEY"))


def search(query, near=None, limit=15):
    r = requests.post("https://places.googleapis.com/v1/places:searchText",
                      headers={"X-Goog-Api-Key": os.environ["GOOGLE_PLACES_API_KEY"], "X-Goog-FieldMask": FIELDS},
                      json={"textQuery": f"{query} near {near}" if near else query, "pageSize": min(limit, 20)},
                      timeout=30)
    usage.add("places_requests")
    data = r.json()
    if not r.ok:
        raise RuntimeError(data.get("error", {}).get("message", r.text[:200]))
    return data.get("places", [])


def socials(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
        html = r.text if r.ok else ""
    except requests.RequestException:
        return {}
    out = {}
    for k, rx in SOCIAL.items():
        found = sorted({m.group(0).rstrip("/") for m in rx.finditer(html)})
        if found:
            out[k] = found[:3]
    return out


def competitors(cfg, query=None, near=None):
    local = cfg.get("local") or {}
    query, near = query or local.get("query"), near or local.get("near")
    if not query:
        raise ValueError("give a query (or set local.query in the profile)")
    places = search(query, near, local.get("limit", 15))
    rows = []
    for p in places:
        site = p.get("websiteUri")
        rows.append({"name": (p.get("displayName") or {}).get("text", ""), "address": p.get("formattedAddress", ""),
                     "rating": p.get("rating"), "reviews": p.get("userRatingCount"), "website": site,
                     "maps": p.get("googleMapsUri"), "socials": socials(site) if site else {}})
    out = Path(cfg["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    note = out / f"{date.today()}-local-competitors.md"
    lines = ["---", "type: local-competitors", f"profile: {cfg['name']}", f"date: {date.today()}", "---", "",
             f"# Local competitors: {query}" + (f" near {near}" if near else ""), "",
             "From the Google Places API; social links come from each business's own homepage.", "",
             "| Business | Rating | Website | YouTube | Instagram | TikTok | Facebook |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        s = r["socials"]
        link = lambda k: " ".join(f"[{u.split('/')[-1]}]({u})" for u in s.get(k, [])) or "—"
        site = f"[site]({r['website']})" if r["website"] else "—"
        lines.append(f"| [{r['name']}]({r['maps']}) | {r['rating'] or '—'} ({r['reviews'] or 0}) | {site} | "
                     f"{link('youtube')} | {link('instagram')} | {link('tiktok')} | {link('facebook')} |")
    yt = [u for r in rows for u in r["socials"].get("youtube", [])]
    ig = [u.rstrip("/").split("/")[-1] for r in rows for u in r["socials"].get("instagram", [])]
    lines += ["", "## Add to the watch list", "", "```yaml", "watch:",
              f"  youtube: {yt}", f"  instagram: {ig}", "```", ""]
    note.write_text("\n".join(lines), encoding="utf-8")
    return rows, note
