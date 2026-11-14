"""Search demand: Google Trends per business, via Apify's Google Trends actor (Google's own Trends API is still
an application-gated alpha; unofficial libraries call Google's internal endpoints, which this project doesn't).

When does demand for each service rise, peak and fall in the business's area, which words do people search, and
what is rising right now. One Apify run per refresh (about $0.005 per term), cached for `every_days`.

  python -m viral_scout demand <profile> [--force]     # --force refetches even if the cache is fresh

Profile:
  demand:
    terms: [gutter cleaning, christmas light installation]   # one seasonal curve each (0-100, own scale)
    compare: [permanent lights, christmas light installation]  # up to 5 phrasings on one shared scale (wording)
    geo: US-IL-602        # Google Trends geo: US, US-IL (state) or a metro (US-IL-602 = Chicago DMA)
    time: today 5-y       # 5 years of weekly data: enough to see the seasons
    every_days: 7         # don't refetch more often (the weekly run calls it on the ads day)
    lead_weeks: 3         # "start posting by" = this many weeks before demand starts rising

Writes data/<profile>-demand.json (+ -demand-raw.json, the fetched rows), <output_dir>/<date>-search-demand.md
and web/data/demand/<profile>.json. Values are Google's 0-100 index (relative to the term's own peak), not volumes.
"""
import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from . import usage

ACTOR = "apify~google-trends-scraper"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _log(msg, quiet):
    if not quiet:
        print(msg, flush=True)
    else:
        from . import activity
        activity.note(msg)


def trends_url(terms, geo="", time_range="today 5-y"):
    q = ",".join(quote(t) for t in terms)
    return (f"https://trends.google.com/trends/explore?date={quote(time_range)}"
            + (f"&geo={quote(geo)}" if geo else "") + f"&q={q}")


# ---------- fetch (async Apify run: no 300 s limit) ----------

def _fetch(urls, errors, log):
    import requests
    token = os.environ.get("APIFY_TOKEN")
    actor = os.environ.get("APIFY_GOOGLE_TRENDS_ACTOR") or ACTOR
    params = usage.apify_params()
    payload = {"searchTerms": [], "startUrls": [{"url": u} for u in urls], "maxItems": len(urls), "isMultiple": False}
    try:
        r = requests.post(f"https://api.apify.com/v2/acts/{actor}/runs", params=params, json=payload, timeout=60)
        if r.status_code >= 400:
            errors.append(f"google trends: Apify HTTP {r.status_code} {r.text[:200]}")
            return []
        run = r.json()["data"]
        log(f"  Apify run {run['id']} started for {len(urls)} queries")
        deadline = time.time() + 900
        while run["status"] in ("READY", "RUNNING") and time.time() < deadline:
            time.sleep(5)
            run = requests.get(f"https://api.apify.com/v2/actor-runs/{run['id']}", params={"token": token},
                               timeout=30).json()["data"]
        if run["status"] != "SUCCEEDED":
            errors.append(f"google trends: Apify run {run['status']}")
        items = requests.get(f"https://api.apify.com/v2/datasets/{run['defaultDatasetId']}/items",
                             params={"token": token, "clean": "true"}, timeout=60).json()
    except (requests.RequestException, ValueError, KeyError) as err:
        errors.append(f"google trends: {err}"[:200])
        return []
    items = items if isinstance(items, list) else []
    usage.add("apify_items", len(items))
    usage.add("apify_runs")
    log(f"  {len(items)} results ({run.get('usageTotalUsd', 0):.3f} USD)" if isinstance(run.get("usageTotalUsd"), (int, float))
        else f"  {len(items)} results")
    return items


# ---------- analysis (pure functions, tested) ----------

def series(row, i=0):
    """[(date, value, has_data)] for the i-th term of a row, without the partial last week."""
    out = []
    for t in row.get("interestOverTime_timelineData") or []:
        if t.get("isPartial"):
            continue
        try:
            d = datetime.fromtimestamp(int(t["time"]), tz=timezone.utc).date()
            v = int((t.get("value") or [0])[i])
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        has = bool((t.get("hasData") or [True])[i]) if isinstance(t.get("hasData"), list) else True
        out.append((d, v, has))
    return out


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def _week(d):
    return min(52, d.isocalendar()[1])


def season(points):
    """Seasonal index per week of year (1..52, mean = 1), smoothed over 5 weeks, plus per-month index."""
    by_week = {w: [] for w in range(1, 53)}
    by_month = {m: [] for m in range(1, 13)}
    for d, v, _ in points:
        by_week[_week(d)].append(v)
        by_month[d.month].append(v)
    overall = _mean(v for _, v, _ in points) or 1.0
    raw = [(_mean(by_week[w]) / overall) if by_week[w] else None for w in range(1, 53)]
    filled = [x if x is not None else 1.0 for x in raw]
    smooth = [_mean(filled[(i + k) % 52] for k in range(-2, 3)) for i in range(52)]
    months = [round(_mean(by_month[m]) / overall, 2) if by_month[m] else None for m in range(1, 13)]
    return [round(x, 3) for x in smooth], months


def _week_start(year, week):
    return date.fromisocalendar(year, week, 1)


def _next_date(week, today):
    d = _week_start(today.year, week)
    return d if d >= today - timedelta(days=6) else _week_start(today.year + 1, week)


def _prev_date(week, today):
    d = _week_start(today.year, week)
    return d if d <= today else _week_start(today.year - 1, week)


def _in_span(w, a, b):
    """Is week w inside the cyclic span a..b (weeks 1..52)?"""
    return a <= w <= b if a <= b else (w >= a or w <= b)


def seasons(idx, min_peak=1.15, min_gap=8):
    """Up to 2 seasons on the cyclic weekly index: each local peak at least 15% above the yearly average, 8+ weeks
    apart. A season starts after the last week below average before the peak and ends at the last week above it."""
    n = len(idx)
    peaks = [w for w in range(n) if idx[w] >= min_peak and idx[w] >= idx[(w - 1) % n] and idx[w] >= idx[(w + 1) % n]]
    peaks.sort(key=lambda w: -idx[w])
    kept = []
    for w in peaks:
        if all(min((w - k) % n, (k - w) % n) >= min_gap for k in kept):
            kept.append(w)
    out, spans = [], set()
    for p in kept[:3]:
        rise = next(((p - b) % n for b in range(1, n) if idx[(p - b) % n] < 1.0), None)
        fall = next(((p + f) % n for f in range(1, n) if idx[(p + f) % n] < 1.0), None)
        if rise is None or fall is None:
            continue
        span = ((rise + 1) % n + 1, (fall - 1) % n + 1)
        if span in spans:                              # two peaks inside one long season
            continue
        spans.add(span)
        out.append({"rise_week": span[0], "peak_week": p + 1, "end_week": span[1], "height": round(idx[p], 2)})
    return sorted(out, key=lambda x: -x["height"])[:2]


def _season_dates(s, today, lead_weeks):
    """Anchor a season at its current occurrence (if we're in it) or the next one."""
    w = _week(today)
    inside = _in_span(w, s["rise_week"], s["end_week"])
    rise = _prev_date(s["rise_week"], today) if inside else _next_date(s["rise_week"], today)
    peak = rise + timedelta(weeks=(s["peak_week"] - s["rise_week"]) % 52)
    end = rise + timedelta(weeks=(s["end_week"] - s["rise_week"]) % 52, days=6)
    nxt = _next_date(s["rise_week"], today + timedelta(days=7)) if inside else rise
    return {**s, "in_season": inside, "rise_date": rise.isoformat(), "peak_date": peak.isoformat(),
            "end_date": end.isoformat(), "start_by": (nxt - timedelta(weeks=lead_weeks)).isoformat(),
            "next_rise": nxt.isoformat(), "label": MONTHS[peak.month - 1] + " peak"}


def analyze_term(term, row, today=None, lead_weeks=3, i=0):
    today = today or date.today()
    pts = series(row, i)
    if len(pts) < 60:
        return {"term": term, "status": "no data", "note": "Google Trends returned too little data for this term."}
    vals = [v for _, v, _ in pts]
    zero_share = sum(1 for v in vals if v == 0) / len(vals)
    low = zero_share > 0.35
    idx, months = season(pts)
    strength = round(max(idx) - min(idx), 2)
    shape = "strong season" if strength >= 0.8 else "mild season" if strength >= 0.35 else "steady all year"
    found = [_season_dates(x, today, lead_weeks) for x in seasons(idx)] if shape != "steady all year" else []
    if low:
        found = found[:1]                              # thin data: a second peak is usually noise
    main = found[0] if found else None
    last4 = pts[-4:]
    yago = [p for p in pts if timedelta(days=358) <= (last4[-1][0] - p[0]) <= timedelta(days=386)]
    now_mean = _mean(v for _, v, _ in last4)
    yago_mean = _mean(v for _, v, _ in yago[-4:]) if yago else None
    norm = _mean(idx[_week(d) - 1] for d, _, _ in last4) * _mean(vals)
    last52, prev52 = vals[-52:], vals[-104:-52]
    out = {
        "term": term, "status": "ok", "weeks": len(pts), "low_volume": low, "zero_share": round(zero_share, 2),
        "shape": shape, "strength": strength, "season_index": idx, "month_index": months, "seasons": found,
        "peak_week": main["peak_week"] if main else max(range(52), key=lambda k: idx[k]) + 1,
        "low_week": min(range(52), key=lambda k: idx[k]) + 1,
        "in_season": any(x["in_season"] for x in found),
        "now": round(now_mean, 1),
        # With many zero weeks the week-to-week numbers are noise; the seasonal shape (5 years averaged) still holds.
        "vs_last_year_pct": None if low else (round((now_mean / yago_mean - 1) * 100) if yago_mean else None),
        # Off-season the expected level can be a few index points: a ratio on that is noise.
        "vs_normal_pct": None if low or norm < 8 else round((now_mean / norm - 1) * 100),
        "trend_pct": round((_mean(last52) / _mean(prev52) - 1) * 100) if prev52 and _mean(prev52) else None,
        "series": [[d.isoformat(), v] for d, v, _ in pts],
    }
    if low:
        out["note"] = (f"Few searches in this area ({round(zero_share * 100)}% of weeks at zero): the season shape is "
                       "usable, week-to-week changes aren't. A wider geo (e.g. US-IL) gives steadier numbers.")
    if main:
        out.update({k: main[k] for k in ("rise_date", "peak_date", "end_date", "start_by")},
                   rise_week=main["rise_week"], weeks_to_peak=max(0, (date.fromisoformat(main["peak_date"]) - today).days // 7))
    return out


# Searches from people about to buy a service (what a local business can act on), vs everything else.
_BUYER = re.compile(r"\b(near me|cost|costs|price|prices|pricing|how much|quote|estimate|service|services|company|companies|"
                    r"contractor|contractors|installer|installers|install|installation|hire|local|cheap|affordable|best|"
                    r"reviews?|professional|repair|replacement|chicago|illinois)\b", re.I)


def related(row, n=15):
    def pick(key, field="query"):
        out = []
        for q in (row.get(key) or [])[:n]:
            text = q.get(field) if field == "query" else (q.get("topic") or {}).get("title")
            if text:
                out.append({"query": text, "value": q.get("formattedValue") or q.get("value"),
                            "buyer": bool(_BUYER.search(text))})
        return out
    cities = []
    for c in row.get("interestByCity") or row.get("interestByMetro") or []:
        v = c.get("value")
        v = v[0] if isinstance(v, list) and v else v
        if isinstance(v, (int, float)) and v > 0:
            cities.append({"name": c.get("geoName"), "value": v})
    cities.sort(key=lambda c: -c["value"])
    rising = pick("relatedQueries_rising")
    return {"rising": sorted(rising, key=lambda q: not q["buyer"]), "top": pick("relatedQueries_top"),
            "rising_topics": pick("relatedTopics_rising", "topic"), "places": cities[:12]}


def compare(terms, row, months=12):
    """Up to 5 phrasings on one scale: average of the last `months` months, and each one's share."""
    avgs = []
    for i, t in enumerate(terms):
        pts = series(row, i)[-months * 4:]
        avgs.append((t, _mean(v for _, v, _ in pts)))
    total = sum(a for _, a in avgs) or 1.0
    top = max((a for _, a in avgs), default=0) or 1.0
    return [{"term": t, "avg": round(a, 1), "share_pct": round(a / total * 100), "vs_top": round(a / top, 2)}
            for t, a in sorted(avgs, key=lambda x: -x[1])]


def _week_label(w, today=None):
    d = _next_date(w, today or date.today())
    return d.strftime("%b %d").replace(" 0", " ")


# ---------- run ----------

def paths(cfg):
    base = Path(cfg["db"]).parent
    return base / f"{cfg['name']}-demand.json", base / f"{cfg['name']}-demand-raw.json"


def scout_demand(cfg, force=False, quiet=False):
    usage.reset()
    dcfg = cfg.get("demand") or {}
    terms = [str(t).strip() for t in dcfg.get("terms") or [] if str(t).strip()][:20]
    cmp_terms = [str(t).strip() for t in dcfg.get("compare") or [] if str(t).strip()][:5]
    out_json, raw_json = paths(cfg)
    errors, skipped = [], []
    if not terms:
        skipped.append("Search demand: the profile has no demand.terms (see docs/search-demand.md).")
        return {"skipped": skipped, "terms": [], "errors": []}, None
    if not os.environ.get("APIFY_TOKEN"):
        skipped.append("Search demand: needs APIFY_TOKEN (Apify's Google Trends actor, about $0.005 per term).")
        return {"skipped": skipped, "terms": [], "errors": []}, None
    geo, time_range = dcfg.get("geo", "US"), dcfg.get("time", "today 5-y")
    every = float(dcfg.get("every_days", 7))
    urls = [trends_url([t], geo, time_range) for t in terms] + ([trends_url(cmp_terms, geo, time_range)] if len(cmp_terms) > 1 else [])

    raw = None
    if raw_json.exists() and not force:
        cached = json.loads(raw_json.read_text(encoding="utf-8"))
        age = (datetime.now() - datetime.fromisoformat(cached["fetched"])).total_seconds() / 86400
        if age < every and cached.get("urls") == urls:
            raw = cached
            _log(f"demand: cached Google Trends data from {cached['fetched'][:16]} ({age:.1f} days old, refresh every "
                 f"{every:g}); nothing fetched", quiet)
    if raw is None:
        _log(f"demand: Google Trends via Apify, {len(urls)} queries, geo {geo or 'worldwide'}, {time_range}", quiet)
        items = _fetch(urls, errors, lambda m: _log(m, quiet))
        if not items:
            if raw_json.exists():
                raw = json.loads(raw_json.read_text(encoding="utf-8"))
                errors.append("google trends: no new data; showing the last fetch")
            else:
                return {"skipped": skipped, "terms": [], "errors": errors}, None
        else:
            raw = {"fetched": datetime.now().isoformat(timespec="seconds"), "urls": urls, "items": items}
            raw_json.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    by_url = {it.get("inputUrlOrTerm"): it for it in raw["items"]}
    lead = int(dcfg.get("lead_weeks", 3))
    rows = []
    for t, u in zip(terms, urls):
        it = by_url.get(u)
        if not it:
            rows.append({"term": t, "status": "no data", "note": "No result for this term in the last fetch."})
            continue
        a = analyze_term(t, it, lead_weeks=lead)
        a["related"] = related(it)
        a["trends_url"] = u
        rows.append(a)
    comparison = None
    if len(cmp_terms) > 1 and by_url.get(urls[-1]):
        comparison = {"terms": cmp_terms, "rows": compare(cmp_terms, by_url[urls[-1]]), "trends_url": urls[-1]}
    result = {
        "profile": cfg["name"], "date": datetime.now().isoformat(timespec="seconds"), "fetched": raw["fetched"],
        "geo": geo, "time": time_range, "lead_weeks": lead, "terms": rows, "compare": comparison,
        "calendar": calendar(rows), "errors": errors, "skipped": skipped, "usage": usage.snapshot(),
    }
    out_json.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    md = write_report(cfg, result)
    try:
        from .export import export_demand
        export_demand(cfg)
    except Exception as err:  # noqa: BLE001
        _log(f"export for the dashboard failed: {err}", quiet)
    return result, (md, out_json)


def calendar(rows):
    """One row per season: what's in season now, then what to prepare next (by start-by date)."""
    cal = []
    for r in rows:
        if r.get("status") != "ok":
            continue
        for x in r.get("seasons") or []:
            cal.append({"term": r["term"], "label": x["label"], "start_by": x["start_by"], "rise": x["rise_date"],
                        "peak": x["peak_date"], "end": x["end_date"], "in_season": x["in_season"],
                        "next_rise": x["next_rise"], "shape": r["shape"], "low_volume": r["low_volume"]})
    return sorted(cal, key=lambda c: (not c["in_season"], c["end"] if c["in_season"] else c["start_by"]))


def _pct(v):
    return "—" if v is None else f"{v:+d}%"


def write_report(cfg, res):
    folder = Path(cfg["output_dir"])
    folder.mkdir(parents=True, exist_ok=True)
    md = folder / f"{datetime.now():%Y-%m-%d}-search-demand.md"
    L = ["---", "type: search-demand", f"profile: {cfg['name']}", f"date: {datetime.now():%Y-%m-%d}",
         f"geo: {res['geo']}", "tags: [viral-scout, search-demand]", "---", "",
         f"# Search demand: {cfg['name']}", "",
         f"Google Trends, {res['geo'] or 'worldwide'}, {res['time']}, fetched {res['fetched'][:10]}. Values are Google's "
         "0–100 index (each term against its own peak), not search volumes.", ""]
    if res["calendar"]:
        L += ["## Calendar: what to prepare next", "",
              f"Start posting and advertising about {res['lead_weeks']} weeks before demand starts rising.", "",
              "| Term | Season | Now | Start posting by | Demand rises | Peak | Ends |", "|---|---|---|---|---|---|---|"]
        for c in res["calendar"]:
            now = f"**in season** until {c['end']}" if c["in_season"] else "—"
            L.append(f"| {c['term']} | {c['label']} | {now} | **{c['start_by']}**{' (next year)' if c['in_season'] else ''} | "
                     f"{c['rise']} | {c['peak']} | {c['end']} |")
        L.append("")
    L += ["## Per term", "", "| Term | Shape | Peak | Now vs last year | Now vs normal for the season | 2-year trend | Note |",
          "|---|---|---|---|---|---|---|"]
    for r in res["terms"]:
        if r.get("status") != "ok":
            L.append(f"| {r['term']} | no data | | | | | {r.get('note', '')} |")
            continue
        peaks = ", ".join(x["label"] for x in r.get("seasons") or []) or _week_label(r["peak_week"])
        L.append(f"| {r['term']} | {r['shape']} | {peaks} | {_pct(r['vs_last_year_pct'])} | "
                 f"{_pct(r['vs_normal_pct'])} | {_pct(r['trend_pct'])} | {'few searches here: shape only' if r['low_volume'] else ''} |")
    L.append("")
    buyer = [(r["term"], q) for r in res["terms"] if r.get("status") == "ok"
             for q in (r.get("related") or {}).get("rising", []) if q.get("buyer")]
    other = [(r["term"], q) for r in res["terms"] if r.get("status") == "ok"
             for q in (r.get("related") or {}).get("rising", []) if not q.get("buyer")]
    if buyer:
        L += ["## Rising buyer searches (video and ad ideas, new keywords)", "",
              "Searches growing fastest that sound like someone about to hire (near me, cost, company, installation...).", ""]
        for t, q in buyer[:24]:
            L.append(f"- **{q['query']}** ({q['value']}) · from \"{t}\"")
        L.append("")
    if other:
        L += ["## Other rising searches (often noise: games, shows, brands)", "",
              ", ".join(f"{q['query']} ({q['value']})" for _, q in other[:30]), ""]
    if res.get("compare"):
        L += ["## Which words people use", "", "| Phrasing | Share of searches (last 12 months) | vs the most searched |", "|---|---|---|"]
        for c in res["compare"]["rows"]:
            L.append(f"| {c['term']} | {c['share_pct']}% | {c['vs_top']:.2f}× |")
        L.append("")
    if res["errors"]:
        L += ["## Errors", ""] + [f"- {e}" for e in res["errors"]] + [""]
    md.write_text("\n".join(L), encoding="utf-8")
    return md


def cli(cfg, force=False, quiet=False):
    res, out = scout_demand(cfg, force=force, quiet=quiet)
    for s in res.get("skipped") or []:
        print("skipped:", s)
    for e in res.get("errors") or []:
        print("error:", e)
    if out:
        ok = [r for r in res["terms"] if r.get("status") == "ok"]
        now = [c for c in res["calendar"] if c["in_season"]]
        nxt = [c for c in res["calendar"] if not c["in_season"]][:3]
        print(f"report: {out[0]}\ndata:   {out[1]}\nterms: {len(ok)} of {len(res['terms'])} with data\n"
              f"in season now: {', '.join(c['term'] + ' (until ' + c['end'] + ')' for c in now) or 'nothing'}\n"
              f"next to prepare: {', '.join(c['term'] + ' ' + c['label'] + ': start by ' + c['start_by'] for c in nxt) or '—'}")
    return 0 if out or res.get("skipped") else 1
