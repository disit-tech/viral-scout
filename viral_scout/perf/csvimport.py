"""CSV import (no keys): your own exports from Meta Ads Manager, TikTok Ads Manager, YouTube Studio, or a generic file.

  python -m viral_scout perf import <profile> <file.csv> --source meta|tiktok|youtube|generic

Headers are matched case-insensitively after removing a trailing currency code such as "(USD)", so
"Amount spent (EUR)" and "Amount spent (USD)" both map to spend. The full mapping is COLUMNS below and the table in
docs/performance.md. Unknown columns are ignored and listed. "Total" rows are skipped. Percent columns that
platforms export (CTR, avg % viewed) are only used when the counts behind them are missing.
"""
import csv
import hashlib
import io
import re

from .schema import FIELDS, VIEW_DEFINITIONS, blank

# normalized header → schema field. A few targets are pseudo-fields handled in parse_row:
#   _hours (watch time in hours), _yt_ctr (impressions CTR %), _roas (purchase ROAS), _result (generic results)
COLUMNS = {
    "meta": {
        "ad id": "id", "ad name": "title", "campaign name": "campaign", "reporting starts": "date_start",
        "reporting ends": "date_stop", "day": "date_start", "platform": "platform",
        "amount spent": "spend", "impressions": "impressions", "reach": "reach", "frequency": "frequency",
        "clicks (all)": "clicks", "link clicks": "link_clicks", "landing page views": "landing_page_views",
        "results": "_result", "leads": "leads", "purchases": "purchases", "website purchases": "purchases",
        "purchases conversion value": "revenue", "website purchases conversion value": "revenue",
        "purchase roas (return on ad spend)": "_roas", "website purchase roas (return on advertising spend)": "_roas",
        "3-second video plays": "views_3s", "2-second continuous video plays": "views_2s",
        "video plays": "video_starts", "video plays at 25%": "p25", "video plays at 50%": "p50",
        "video plays at 75%": "p75", "video plays at 100%": "p100", "thruplays": "thruplays",
        "video average play time": "avg_watch_time", "post reactions": "likes", "post comments": "comments",
        "post shares": "shares", "post saves": "saves", "page likes": "follows", "instagram follows": "follows",
        "instagram profile visits": "profile_visits", "video length": "duration",
    },
    "tiktok": {
        "ad id": "id", "ad name": "title", "campaign name": "campaign", "by day": "date_start", "date": "date_start",
        "cost": "spend", "total cost": "spend", "impressions": "impressions", "reach": "reach",
        "frequency": "frequency", "clicks (destination)": "link_clicks", "clicks": "link_clicks",
        "clicks (all)": "clicks", "conversions": "conversions", "results": "conversions",
        "video views": "video_starts", "2-second video views": "views_2s", "6-second video views": "views_6s",
        "video views at 25%": "p25", "video views at 50%": "p50", "video views at 75%": "p75",
        "video views at 100%": "p100", "average play time per video view": "avg_watch_time",
        "likes": "likes", "paid likes": "likes", "comments": "comments", "paid comments": "comments",
        "shares": "shares", "paid shares": "shares", "follows": "follows", "paid follows": "follows",
        "profile visits": "profile_visits", "paid profile visits": "profile_visits",
        "complete payment": "purchases", "total complete payment value": "revenue",
        "complete payment value": "revenue", "complete payment roas": "_roas", "leads": "leads",
        "form submissions": "leads", "video duration": "duration",
    },
    "youtube": {
        "content": "id", "video title": "title", "video publish time": "published", "duration": "duration",
        "views": "views", "engaged views": "engaged_views", "watch time (hours)": "_hours",
        "average view duration": "avg_watch_time", "average percentage viewed (%)": "avg_pct_viewed_given",
        "impressions": "impressions", "impressions click-through rate (%)": "_yt_ctr", "likes": "likes",
        "comments added": "comments", "shares": "shares", "subscribers gained": "follows",
        "stayed to watch (%)": "stayed_pct_given",
    },
}
GENERIC_ALIASES = {
    "ad id": "id", "video id": "id", "post id": "id", "name": "title", "ad name": "title", "caption": "title",
    "cost": "spend", "amount spent": "spend", "plays": "views", "video views": "views", "3s views": "views_3s",
    "3-second views": "views_3s", "2s views": "views_2s", "6s views": "views_6s", "saved": "saves",
    "avg watch time": "avg_watch_time", "average watch time": "avg_watch_time", "orders": "purchases",
    "conversion value": "revenue", "purchase value": "revenue", "link clicks": "link_clicks",
    "landing page views": "landing_page_views", "subscribers gained": "follows", "skip rate": "skip_rate_given",
    "date": "date_start", "publish date": "published", "length": "duration", "watch time (hours)": "_hours",
}
TEXT_FIELDS = {"id", "title", "campaign", "date_start", "date_stop", "published", "platform", "url", "kind"}
SUMMED = ("impressions", "reach", "spend", "clicks", "link_clicks", "views", "views_3s", "views_2s", "views_6s",
          "video_starts", "p25", "p50", "p75", "p100", "thruplays", "likes", "comments", "shares", "saves", "follows",
          "profile_visits", "landing_page_views", "conversions", "leads", "purchases", "revenue")
KINDS = {"meta": "paid", "tiktok": "paid", "youtube": "organic"}
PLATFORMS = {"meta": "facebook", "tiktok": "tiktok", "youtube": "youtube"}


def norm_header(h):
    h = (h or "").replace("﻿", "").replace("’", "'").strip().lower()
    h = re.sub(r"\s*\((?!all\))[a-z]{3}\)\s*$", "", h)   # trailing currency code: (usd), (eur); not "(all)"
    return re.sub(r"\s+", " ", h)


def parse_value(v):
    """'1,234' → 1234; '$5.20' → 5.2; '12.5%' → 12.5; '0:00:23' → 23 (seconds); '' / '-' → None."""
    if v is None:
        return None
    s = str(v).strip().replace(" ", "")
    if s in ("", "-", "--", "—", "N/A", "n/a"):
        return None
    if re.fullmatch(r"\d+:\d{2}(:\d{2})?(\.\d+)?", s):
        parts = [float(p) for p in s.split(":")]
        return sum(p * 60 ** i for i, p in enumerate(reversed(parts)))
    s = re.sub(r"[^\d.,\-eE]", "", s)
    if s.count(",") and s.count("."):
        s = s.replace(",", "")
    elif s.count(",") == 1 and len(s.split(",")[1]) != 3:
        s = s.replace(",", ".")                                # decimal comma: 1,5
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def mapping(source):
    if source == "generic":
        m = {f: f for f in FIELDS}
        m.update(GENERIC_ALIASES)
        return m
    return COLUMNS[source]


def parse_row(row, source, cols):
    vals = {}
    for raw, v in row.items():
        f = cols.get(norm_header(raw))
        if not f:
            continue
        if f in TEXT_FIELDS:
            if v not in (None, "") and f not in vals:
                vals[f] = str(v).strip()
        else:
            x = parse_value(v)
            if x is not None and vals.get(f) is None:
                vals[f] = x
    if not any(vals.get(k) for k in ("id", "title")) or str(vals.get("id", vals.get("title", ""))).lower() == "total":
        return None
    kind = (vals.pop("kind", None) or KINDS.get(source) or ("paid" if vals.get("spend") else "organic")).lower()
    platform = (vals.pop("platform", None) or PLATFORMS.get(source) or "other").lower()
    if source == "meta" and platform not in ("facebook", "instagram", "messenger", "audience_network"):
        platform = "facebook"
    rid = vals.pop("id", None) or hashlib.sha1(vals.get("title", "").encode()).hexdigest()[:12]
    if vals.get("date_start") and source in ("meta", "tiktok") and any(norm_header(h) in ("day", "by day", "date") for h in row):
        rid = f"{rid}@{vals['date_start']}"
    r = blank(f"csv:{source}", kind, rid, platform=platform)
    hours, ctr, roas, result = vals.pop("_hours", None), vals.pop("_yt_ctr", None), vals.pop("_roas", None), \
        vals.pop("_result", None)
    r.update({k: v for k, v in vals.items() if k in FIELDS})
    if hours is not None:
        r["total_watch_time"] = hours * 3600
    if ctr is not None and r.get("impressions"):
        r["clicks"] = round(r["impressions"] * ctr / 100)
        r["notes"].append("Clicks = impressions × impressions CTR (YouTube thumbnail clicks).")
    if r.get("revenue") is None and roas is not None and r.get("spend"):
        r["revenue"] = roas * r["spend"]
    if result is not None and r.get("conversions") is None:
        r["conversions"] = result
    if source == "meta":
        r["views"] = r.get("views_3s") or r.get("views")
        if r.get("conversions") is None:
            r["conversions"] = r.get("purchases") or r.get("leads")
    if source == "tiktok" and r.get("views") is None:
        r["views"] = r.get("video_starts")
    if r.get("view_definition") is None:
        r["view_definition"] = VIEW_DEFINITIONS.get(platform)
    return r


def read(text_or_path, source):
    """Parse a CSV (path or text) → (records, unknown headers)."""
    if source not in ("meta", "tiktok", "youtube", "generic"):
        raise ValueError("source must be meta, tiktok, youtube or generic")
    if "\n" in str(text_or_path):
        text = str(text_or_path)
    else:
        with open(text_or_path, encoding="utf-8-sig", newline="") as fh:
            text = fh.read()
    text = text.lstrip("﻿")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    cols = mapping(source)
    unknown = [h for h in (reader.fieldnames or []) if norm_header(h) not in cols]
    recs = [r for r in (parse_row(row, source, cols) for row in reader) if r]
    # Daily rows of one ad (export broken down by day) → one record with a daily series.
    merged = {}
    for r in recs:
        base = r["key"].split("@")[0]
        if "@" not in r["key"]:
            merged[base] = r
            continue
        m = merged.setdefault(base, dict(r, key=base, id=r["id"].split("@")[0], daily=[], notes=list(r["notes"])))
        m["daily"].append({"date": r["date_start"], "impressions": r.get("impressions"), "reach": r.get("reach"),
                           "frequency": r.get("frequency"), "clicks": r.get("clicks"),
                           "link_clicks": r.get("link_clicks"), "spend": r.get("spend")})
        m.setdefault("_rows", []).append(r)
    out = []
    for m in merged.values():
        rows = m.pop("_rows", None)
        if rows:
            for k in SUMMED:
                vals = [x.get(k) for x in rows if x.get(k) is not None]
                m[k] = sum(vals) if vals else None
            w = [(x["avg_watch_time"], x.get("video_starts") or x.get("views") or 0) for x in rows
                 if x.get("avg_watch_time") is not None]
            tw = sum(n for _, n in w)
            m["avg_watch_time"] = sum(a * n for a, n in w) / tw if tw else None
            dates = sorted(x["date_start"] for x in rows if x.get("date_start"))
            m["date_start"], m["date_stop"] = (dates[0], dates[-1]) if dates else (None, None)
            m["frequency"] = None              # daily frequency can't be summed; recomputed from impressions ÷ reach
            m["notes"].append("Summed from daily rows; reach is summed across days, so it over-counts people.")
        out.append(m)
    return out, unknown
