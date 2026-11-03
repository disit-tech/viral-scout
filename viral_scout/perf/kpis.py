"""Every own-performance KPI, with its formula and its denominator.

compute(record, economics) returns {kpi_id: {"value", "num", "den", "denominator"}} for every KPI the record has
the inputs for. The denominator actually used is recorded with each value, because platforms define the inputs
differently (see PLATFORM_DIFFERENCES) and some KPIs fall back to a second-best denominator.

Groups:
  A Attention   impressions, reach, frequency, views, hook rate, 2-s / 6-s view rate, start rate, CPM
  B Retention   avg watch time, avg % viewed, 25/50/75/100 % view rates, completion, ThruPlay rate,
                retention curve, rewatch/loop, drop-off points
  C Engagement  engagement, like/comment/share/save rate, follower conversion, profile visit rate, sentiment
  D Traffic     CTR, link CTR, CPC, CPC (link), CPV, landing page views, LPV rate
  E Conversion  conversions, CVR, CPA, CPL, CAC, AOV, ROAS, contribution margin, LTV:CAC; MER at account level
All rates are percentages (×100). Money is in the ad account's currency.
"""
import re
import statistics

GROUPS = {"A": "Attention", "B": "Retention", "C": "Engagement", "D": "Traffic", "E": "Conversion & profit"}

PLATFORM_DIFFERENCES = [
    ("3-second view (Meta)", "the 'video_view' action: at least 3 s played, or the whole video if shorter. Our hook "
     "rate uses it: 3-s views ÷ impressions."),
    ("2-second continuous view (Meta / TikTok)", "Meta: 2 continuous seconds with ≥50% of the video on screen. TikTok "
     "'video_watched_2s': ≥2 s in one impression session, replays excluded. Stricter than a start, looser than 3 s."),
    ("6-second view (TikTok)", "≥6 s in one impression session (or a shorter video played in full, or an engagement "
     "in the first 6 s)."),
    ("ThruPlay (Meta)", "played to completion, or at least 15 s for longer videos. Not the same as a 100% view."),
    ("Engaged view (YouTube)", "engagedViews; for Shorts it keeps the pre-2025 counting, while 'views' now counts "
     "every start and replay."),
    ("Instagram views", "every start, replays included, no minimum time. Instagram reports no impressions for reels "
     "created after 2 Jul 2024, so reach is the denominator and the hook proxy is 100 − reels_skip_rate."),
    ("YouTube 'Stayed to watch'", "Shorts only: share of feed views that weren't swiped away. Used as the hook proxy "
     "for YouTube Studio imports."),
    ("Average play time", "TikTok and Instagram include replays, so it can exceed the video length; YouTube's "
     "averageViewDuration excludes looping clips (since Dec 2021)."),
    ("Conversions", "platform-attributed with that platform's window (Meta default 7-day click / 1-day view). Two "
     "platforms can claim the same sale; compare with your own sales data (MER)."),
]


def _f(v):
    return None if v is None else float(v)


def ratio(num, den, scale=1.0):
    """num ÷ den × scale, or None when either side is missing or den is 0."""
    if num is None or den in (None, 0):
        return None
    return float(num) / float(den) * scale


def starts(r):
    """Plays started: video_starts if reported, else the platform's views."""
    return r.get("video_starts") or r.get("views")


def engagements(r):
    """Interactions: Instagram's total_interactions if given, else likes + comments + shares + saves."""
    if r.get("total_interactions") is not None:
        return r["total_interactions"]
    parts = [r.get(k) for k in ("likes", "comments", "shares", "saves")]
    return None if all(p is None for p in parts) else sum(p or 0 for p in parts)


def acquisitions(r):
    """Attributed acquisitions for CPA: purchases, else the platform's conversions, else leads."""
    for k in ("purchases", "conversions", "leads"):
        if r.get(k):
            return r[k], k
    return None, None


def revenue(r, econ):
    """Attributed revenue, else purchases × the profile's avg_order_value (estimated)."""
    if r.get("revenue") is not None:
        return r["revenue"], "attributed revenue"
    if r.get("purchases") and econ.get("avg_order_value"):
        return r["purchases"] * econ["avg_order_value"], "purchases × profile AOV (estimate)"
    return None, None


def new_customers(r, econ):
    """Customers for CAC: purchases (each assumed a new customer), else leads × lead_to_customer_rate."""
    if r.get("purchases"):
        return r["purchases"], "purchases (assumes each is a new customer)"
    if r.get("leads") and econ.get("lead_to_customer_rate"):
        return r["leads"] * econ["lead_to_customer_rate"], "leads × lead_to_customer_rate"
    return None, None


def visits(r):
    """Eligible visits for CVR: landing page views, else link clicks, else all clicks."""
    for k, label in (("landing_page_views", "landing page views"), ("link_clicks", "link clicks"),
                     ("clicks", "clicks (all)")):
        if r.get(k):
            return r[k], label
    return None, None


# ---- sentiment (simple lexicon; English + a few Russian/Ukrainian/Spanish words) -----------------------------
POS = set("""love loved lovely great awesome amazing helpful useful thanks thank thx perfect best nice cool good
excellent brilliant beautiful clear finally wow fantastic recommend legend gem fire super genius informative
спасибо класс круто супер отлично полезно люблю дякую чудово корисно gracias genial excelente""".split())
NEG = set("""hate bad worst boring useless wrong scam fake terrible awful annoying stupid clickbait trash dislike
misleading cringe expensive rip ripoff disappointed slow confusing lies lie spam плохо ужас развод фигня
скучно погано жах malo horrible estafa""".split())


def sentiment(texts):
    """(score −100..100, positive hits, negative hits) from a word lexicon, or None if no sentiment words."""
    if not texts:
        return None
    pos = neg = 0
    for t in texts:
        words = re.findall(r"[\w']+", (t or "").lower())
        pos += sum(w in POS for w in words) + (t or "").count("❤") + (t or "").count("🔥")
        neg += sum(w in NEG for w in words)
    if pos + neg == 0:
        return None
    return (pos - neg) / (pos + neg) * 100, pos, neg


# ---- KPI definitions ------------------------------------------------------------------------------------------
def _val(v, den_label=None, num=None, den=None):
    return None if v is None else (v, num, den, den_label)


def _k_hook(r, e):
    v = ratio(r.get("views_3s"), r.get("impressions"), 100)
    if v is not None:
        return v, r["views_3s"], r["impressions"], "impressions (3-second views ÷ impressions)"
    if r.get("skip_rate_given") is not None:
        return 100 - r["skip_rate_given"], None, None, "plays (100 − Instagram reels_skip_rate; proxy)"
    if r.get("stayed_pct_given") is not None:
        return r["stayed_pct_given"], None, None, "Shorts feed views (YouTube 'Stayed to watch'; proxy)"
    return None


def _k_awt(r, e):
    if r.get("avg_watch_time") is not None:
        return r["avg_watch_time"], None, None, "plays (as reported)"
    v = ratio(r.get("total_watch_time"), starts(r))
    return _val(v, "plays (total watch time ÷ plays)", r.get("total_watch_time"), starts(r))


def _k_pct(r, e):
    awt = _k_awt(r, e)
    if awt and r.get("duration"):
        return awt[0] / r["duration"] * 100, awt[0], r["duration"], "video length (avg watch time ÷ duration)"
    if r.get("avg_pct_viewed_given") is not None:
        return r["avg_pct_viewed_given"], None, None, "video length (as reported by the platform)"
    return None


def _k_quart(field):
    def f(r, e):
        s = starts(r)
        return _val(ratio(r.get(field), s, 100), "plays started", r.get(field), s)
    return f


def _k_rate(field, den_field="views"):
    def f(r, e):
        den = r.get(den_field)
        label = den_field
        if not den and den_field == "views":
            den, label = r.get("reach"), "reach (no views reported)"
        return _val(ratio(r.get(field), den, 100), label, r.get(field), den)
    return f


def _k_eng(r, e):
    n = engagements(r)
    den, label = r.get("views"), "views"
    if not den:
        den, label = r.get("reach"), "reach (no views reported)"
    return _val(ratio(n, den, 100), label, n, den)


def _k_follow(r, e):
    den, label = r.get("reach"), "reach"
    if not den:
        den, label = r.get("views"), "views (no reach reported)"
    return _val(ratio(r.get("follows"), den, 100), label, r.get("follows"), den)


def _k_profile(r, e):
    den, label = r.get("reach"), "reach"
    if not den:
        den, label = r.get("views"), "views (no reach reported)"
    return _val(ratio(r.get("profile_visits"), den, 100), label, r.get("profile_visits"), den)


def _k_sent(r, e):
    s = sentiment(r.get("comment_texts"))
    return None if s is None else (s[0], s[1], s[1] + s[2], "comments with a sentiment word (pos − neg) ÷ (pos + neg)")


def _k_cvr(r, e):
    n, what = acquisitions(r)
    den, label = visits(r)
    return _val(ratio(n, den, 100), f"{label} ({what} ÷ visits)" if label else None, n, den)


def _k_cpa(r, e):
    n, what = acquisitions(r)
    return _val(ratio(r.get("spend"), n), f"attributed {what}" if what else None, r.get("spend"), n)


def _k_cac(r, e):
    n, label = new_customers(r, e)
    return _val(ratio(r.get("spend"), n), label, r.get("spend"), n)


def _k_aov(r, e):
    rev, label = r.get("revenue"), "orders (attributed revenue ÷ purchases)"
    v = ratio(rev, r.get("purchases"))
    return _val(v, label, rev, r.get("purchases"))


def _k_roas(r, e):
    rev, label = revenue(r, e)
    return _val(ratio(rev, r.get("spend")), f"spend ({label} ÷ spend)" if label else None, rev, r.get("spend"))


def _k_contrib(r, e):
    rev, label = revenue(r, e)
    gm = e.get("gross_margin")
    if rev is None or gm is None or r.get("spend") is None:
        return None
    return rev * gm - r["spend"], rev * gm, r["spend"], f"({label}) × gross margin − spend"


def _k_ltvcac(r, e):
    cac = _k_cac(r, e)
    if not cac or not e.get("ltv"):
        return None
    return e["ltv"] / cac[0], e["ltv"], cac[0], "CAC (profile LTV ÷ CAC)"


def _k_rewatch(r, e):
    c = curve(r)
    if not c or c["source"] != "retention" or c["peak"] <= 100:
        return None
    return c["peak"] - 100, None, None, "viewers at video start (peak audience watch ratio − 100%)"


def _k_freq(r, e):
    if r.get("frequency") is not None:
        return r["frequency"], None, None, "reach (as reported)"
    return _val(ratio(r.get("impressions"), r.get("reach")), "reach", r.get("impressions"), r.get("reach"))


def _k_count(field, label="count"):
    return lambda r, e: _val(_f(r.get(field)), label)


def _k_div(num, den, scale, label):
    return lambda r, e: _val(ratio(r.get(num), r.get(den), scale), label, r.get(num), r.get(den))


# id, group, label, unit, better, formula, fn, note
KPIS = [
    ("impressions", "A", "Impressions", "count", "high", "times shown", _k_count("impressions"), ""),
    ("reach", "A", "Reach", "count", "high", "unique accounts reached", _k_count("reach"), ""),
    ("frequency", "A", "Frequency", "x", None, "impressions ÷ reach", _k_freq, "rising frequency + falling CTR = fatigue"),
    ("views", "A", "Views", "count", "high", "platform view count", _k_count("views", "platform definition"),
     "definitions differ per platform"),
    ("hook_rate", "A", "Hook rate", "pct", "high", "3-second views ÷ impressions × 100", _k_hook,
     "Instagram: 100 − skip rate; YouTube Shorts: 'Stayed to watch' (proxies, not comparable across platforms)"),
    ("view_rate_2s", "A", "2-s view rate", "pct", "high", "2-second views ÷ impressions × 100",
     _k_div("views_2s", "impressions", 100, "impressions"), "TikTok/Meta 2-s continuous"),
    ("view_rate_6s", "A", "6-s view rate", "pct", "high", "6-second views ÷ impressions × 100",
     _k_div("views_6s", "impressions", 100, "impressions"), "TikTok"),
    ("start_rate", "A", "Video start rate", "pct", "high", "video starts ÷ impressions × 100",
     _k_div("video_starts", "impressions", 100, "impressions"), "autoplay feeds sit near 100%"),
    ("cpm", "A", "CPM", "money", "low", "spend ÷ impressions × 1000", _k_div("spend", "impressions", 1000, "impressions"), ""),
    ("avg_watch_time", "B", "Avg watch time", "seconds", "high", "total watch time ÷ plays", _k_awt,
     "TikTok/Instagram include replays"),
    ("avg_pct_viewed", "B", "Avg % viewed", "pct", "high", "avg watch time ÷ duration × 100", _k_pct,
     "compare only videos of similar length"),
    ("p25_rate", "B", "25% view rate", "pct", "high", "25% views ÷ starts × 100", _k_quart("p25"), ""),
    ("p50_rate", "B", "50% view rate", "pct", "high", "50% views ÷ starts × 100", _k_quart("p50"), ""),
    ("p75_rate", "B", "75% view rate", "pct", "high", "75% views ÷ starts × 100", _k_quart("p75"), ""),
    ("completion_rate", "B", "Completion rate", "pct", "high", "completed (100%) views ÷ starts × 100",
     _k_quart("p100"), "a 7-s video completes far more often than a 45-s one: compare like with like"),
    ("thruplay_rate", "B", "ThruPlay rate", "pct", "high", "ThruPlays ÷ impressions × 100",
     _k_div("thruplays", "impressions", 100, "impressions"), "Meta: completed or ≥15 s"),
    ("rewatch", "B", "Rewatch / loop", "pct", "high", "peak audience watch ratio − 100%", _k_rewatch,
     "YouTube retention above 100% means segments were rewatched"),
    ("engagement_rate", "C", "Engagement rate", "pct", "high", "(likes + comments + shares + saves) ÷ views × 100",
     _k_eng, "Instagram: total_interactions when reported"),
    ("like_rate", "C", "Like rate", "pct", "high", "likes ÷ views × 100", _k_rate("likes"), ""),
    ("comment_rate", "C", "Comment rate", "pct", "high", "comments ÷ views × 100", _k_rate("comments"), ""),
    ("share_rate", "C", "Share rate", "pct", "high", "shares ÷ views × 100", _k_rate("shares"), "strongest organic signal"),
    ("save_rate", "C", "Save rate", "pct", "high", "saves ÷ views × 100", _k_rate("saves"), ""),
    ("follower_conversion", "C", "Follower conversion", "pct", "high", "follows ÷ reach × 100", _k_follow, ""),
    ("profile_visit_rate", "C", "Profile visit rate", "pct", "high", "profile visits ÷ reach × 100", _k_profile, ""),
    ("sentiment", "C", "Comment sentiment", "score", "high", "(positive − negative) ÷ (positive + negative) × 100",
     _k_sent, "simple word lexicon on your own comments; a hint, not a measurement"),
    ("ctr", "D", "CTR (all)", "pct", "high", "clicks ÷ impressions × 100", _k_div("clicks", "impressions", 100, "impressions"), ""),
    ("link_ctr", "D", "Link CTR", "pct", "high", "link clicks ÷ impressions × 100",
     _k_div("link_clicks", "impressions", 100, "impressions"), ""),
    ("cpc", "D", "CPC (all)", "money", "low", "spend ÷ clicks", _k_div("spend", "clicks", 1, "clicks (all)"), ""),
    ("cpc_link", "D", "CPC (link)", "money", "low", "spend ÷ link clicks", _k_div("spend", "link_clicks", 1, "link clicks"), ""),
    ("cpv", "D", "CPV", "money", "low", "spend ÷ views", _k_div("spend", "views", 1, "views (platform definition)"),
     "Meta: per 3-s view"),
    ("landing_page_views", "D", "Landing page views", "count", "high", "landing page loads after a click",
     _k_count("landing_page_views"), "Meta pixel/SDK needed"),
    ("lpv_rate", "D", "LPV rate", "pct", "high", "landing page views ÷ link clicks × 100",
     _k_div("landing_page_views", "link_clicks", 100, "link clicks"), "low = slow page or accidental clicks"),
    ("conversions", "E", "Conversions", "count", "high", "attributed results", _k_count("conversions", "platform-attributed"), ""),
    ("cvr", "E", "CVR", "pct", "high", "conversions ÷ eligible visits × 100", _k_cvr, "visits = LPV, else link clicks"),
    ("cpa", "E", "CPA", "money", "low", "spend ÷ attributed acquisitions", _k_cpa, ""),
    ("cpl", "E", "CPL", "money", "low", "spend ÷ leads", _k_div("spend", "leads", 1, "leads"), ""),
    ("cac", "E", "CAC", "money", "low", "spend ÷ new customers", _k_cac, "leads × lead_to_customer_rate for lead-gen"),
    ("aov", "E", "AOV", "money", "high", "revenue ÷ orders", _k_aov, ""),
    ("roas", "E", "ROAS", "x", "high", "attributed revenue ÷ spend", _k_roas,
     "4× ROAS is not profit: break-even ROAS = 1 ÷ gross margin"),
    ("contribution_margin", "E", "Contribution margin", "money", "high", "revenue × gross margin − spend", _k_contrib,
     "needs economics.gross_margin"),
    ("ltv_cac", "E", "LTV:CAC", "x", "high", "LTV ÷ CAC", _k_ltvcac, "needs economics.ltv; 3:1 is a common floor"),
]
KPI_BY_ID = {k[0]: k for k in KPIS}
COST_KPIS = {k[0] for k in KPIS if k[4] == "low"}
DURATION_DEPENDENT = {"avg_watch_time", "avg_pct_viewed", "p25_rate", "p50_rate", "p75_rate", "completion_rate",
                      "thruplay_rate"}


def definitions():
    """KPI metadata for reports and the dashboard tooltips."""
    out = [{"id": k[0], "group": k[1], "label": k[2], "unit": k[3], "better": k[4], "formula": k[5], "note": k[7]}
           for k in KPIS]
    out.append({"id": "mer", "group": "E", "label": "MER", "unit": "x", "better": "high",
                "formula": "total revenue ÷ total marketing spend", "note": "account level only"})
    out.append({"id": "drop_offs", "group": "B", "label": "Drop-off points", "unit": "pct", "better": None,
                "formula": "largest falls between neighbouring points of the retention curve", "note": ""})
    return out


def compute(r, econ=None):
    econ = econ or {}
    out = {}
    for kid, *_rest in KPIS:
        fn = KPI_BY_ID[kid][6]
        try:
            res = fn(r, econ)
        except (TypeError, ZeroDivisionError, ValueError):
            res = None
        if res is None or res[0] is None:
            continue
        v, num, den, label = res
        out[kid] = {"value": round(float(v), 4), "num": num, "den": den, "denominator": label}
    return out


# ---- retention curve -------------------------------------------------------------------------------------------
def curve(r):
    """Retention curve as [[elapsed 0–1, % of starting audience still watching]], with the largest drops.

    From YouTube's audienceWatchRatio (100 points) when present, else built from the 25/50/75/100% view counts
    (plus the 3-second point when the duration is known). Returns None when neither exists.
    """
    pts, source = [], None
    if r.get("retention"):
        pts = sorted((float(p[0]), float(p[1]) * 100) for p in r["retention"] if p and p[1] is not None)
        source = "retention"
    else:
        s = starts(r)
        if s and any(r.get(q) is not None for q in ("p25", "p50", "p75", "p100")):
            pts = [(0.0, 100.0)]
            if r.get("views_3s") and r.get("duration") and r.get("video_starts"):
                x = 3 / r["duration"]
                if 0 < x < 0.25:
                    pts.append((x, min(100.0, r["views_3s"] / r["video_starts"] * 100)))
            for x, q in ((0.25, "p25"), (0.5, "p50"), (0.75, "p75"), (1.0, "p100")):
                if r.get(q) is not None:
                    pts.append((x, r[q] / s * 100))
            source = "quartiles"
    if len(pts) < 2:
        return None
    # Resample dense curves to every 10% so drops aren't 1-point noise.
    if len(pts) > 15:
        grid = [i / 10 for i in range(11)]
        pts = [min(pts, key=lambda p: abs(p[0] - g)) for g in grid]
        pts = [(g, p[1]) for g, p in zip(grid, pts)]
    drops = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if y0 - y1 > 0:
            d = {"from": round(x0, 3), "to": round(x1, 3), "drop": round(y0 - y1, 1)}
            if r.get("duration"):
                d["seconds"] = [round(x0 * r["duration"], 1), round(x1 * r["duration"], 1)]
            drops.append(d)
    drops.sort(key=lambda d: -d["drop"])
    return {"source": source, "points": [[round(x, 3), round(y, 1)] for x, y in pts], "drops": drops[:3],
            "peak": round(max(y for _, y in pts), 1), "end": round(pts[-1][1], 1)}


def curve_summary(c, duration=None):
    """One line: where viewers drop."""
    if not c:
        return ""
    keep = {x: y for x, y in c["points"]}
    parts = [f"{int(x * 100)}%: {keep[x]:.0f}%" for x in (0.25, 0.5, 0.75, 1.0) if x in keep]
    head = "Still watching at " + ", ".join(parts) if parts else ""
    drops = []
    for d in c["drops"]:
        span = f"{d['seconds'][0]:g}–{d['seconds'][1]:g} s" if d.get("seconds") else f"{d['from']:.0%}–{d['to']:.0%}"
        drops.append(f"{span} (−{d['drop']:.0f} pts)")
    tail = ("; biggest drops: " + ", ".join(drops)) if drops else ""
    loop = "; rewatched (curve above 100%)" if c["peak"] > 100 else ""
    return (head + tail + loop).strip("; ")


# ---- aggregation, medians, unit economics ------------------------------------------------------------------------
SUMMABLE = ["impressions", "reach", "views", "video_starts", "views_2s", "views_3s", "views_6s", "thruplays",
            "engaged_views", "p25", "p50", "p75", "p100", "total_watch_time", "likes", "comments", "shares", "saves",
            "reposts", "follows", "profile_visits", "total_interactions", "clicks", "link_clicks",
            "landing_page_views", "spend", "conversions", "leads", "purchases", "revenue"]


def aggregate(records):
    """Sum counts across records (reach is summed too, so it over-counts unique people; frequency left out)."""
    tot = {}
    for k in SUMMABLE:
        vals = [r.get(k) for r in records if r.get(k) is not None]
        tot[k] = sum(vals) if vals else None
    # total_interactions only for records that have it would mix definitions; recompute from parts.
    tot["total_interactions"] = None
    if tot.get("total_watch_time") is None:
        tw = [r["avg_watch_time"] * starts(r) for r in records if r.get("avg_watch_time") and starts(r)]
        tot["total_watch_time"] = sum(tw) if tw else None
    return tot


def account_kpis(rows, econ=None):
    """Account-level KPIs from per-record KPIs: Σ numerators ÷ Σ denominators over the records that have BOTH, so a
    record without 3-second views doesn't dilute the hook rate. Counts and contribution margin are summed;
    proxies without counts (Instagram skip rate, platform-given %) and sentiment are left to the medians."""
    econ = econ or {}
    out = {}
    for kid, _g, _l, unit, *_ in KPIS:
        have = [r["kpis"][kid] for r in rows if kid in r["kpis"]]
        if not have:
            continue
        labels = sorted({h["denominator"] or "" for h in have})
        label = labels[0] if len(labels) == 1 else "mixed: " + "; ".join(labels)
        if unit == "count" or kid == "contribution_margin":
            out[kid] = {"value": round(sum(h["value"] for h in have), 4), "num": None, "den": None,
                        "denominator": "sum over records", "n": len(have)}
            continue
        pairs = [h for h in have if h["num"] is not None and h["den"] not in (None, 0) and h["num"] != 0]
        if kid in ("sentiment", "rewatch", "ltv_cac") or not pairs:
            continue
        scale = pairs[0]["value"] * pairs[0]["den"] / pairs[0]["num"]
        n, d = sum(h["num"] for h in pairs), sum(h["den"] for h in pairs)
        if d:
            out[kid] = {"value": round(n / d * scale, 4), "num": n, "den": d, "denominator": label, "n": len(pairs)}
    if "cac" in out and econ.get("ltv"):
        out["ltv_cac"] = {"value": round(econ["ltv"] / out["cac"]["value"], 4), "num": econ["ltv"],
                          "den": out["cac"]["value"], "denominator": "account CAC", "n": out["cac"]["n"]}
    return out


def duration_band(d):
    if not d:
        return None
    return "<15s" if d < 15 else "15–30s" if d < 30 else "30–60s" if d < 60 else "60s+"


def medians(rows):
    """rows: [{"kpis": {...}, "duration": s}] → {"all": {kpi: median}, "bands": {band: {kpi: median}}, "n": {...}}."""
    out, n, bands = {}, {}, {}
    for kid in [k[0] for k in KPIS]:
        vals = [row["kpis"][kid]["value"] for row in rows if kid in row["kpis"]]
        if vals:
            out[kid], n[kid] = statistics.median(vals), len(vals)
    for b in ("<15s", "15–30s", "30–60s", "60s+"):
        sub = [row for row in rows if duration_band(row.get("duration")) == b]
        bm = {}
        for kid in DURATION_DEPENDENT:
            vals = [row["kpis"][kid]["value"] for row in sub if kid in row["kpis"]]
            if len(vals) >= 3:
                bm[kid] = statistics.median(vals)
        if bm:
            bands[b] = bm
    return {"all": out, "n": n, "bands": bands}


PLATFORM_NAMES = {"youtube": "YouTube", "instagram": "Instagram", "facebook": "Meta", "tiktok": "TikTok"}


def scoped_medians(kind_meds, platform_meds, platform, min_n=3):
    """Like for like: per KPI, the same platform's median when it has ≥min_n videos, else all videos of the kind.
    Platforms define views, clicks and conversions differently, so same-platform medians are fairer."""
    out = {"all": dict(kind_meds["all"]), "n": dict(kind_meds["n"]), "bands": {}, "scope": {}}
    pm = platform_meds or {"all": {}, "n": {}, "bands": {}}
    for kid, n in pm["n"].items():
        if n >= min_n:
            out["all"][kid], out["n"][kid] = pm["all"][kid], n
            out["scope"][kid] = PLATFORM_NAMES.get(platform, platform)
    for b in set(kind_meds["bands"]) | set(pm["bands"]):
        out["bands"][b] = dict(kind_meds["bands"].get(b, {}))
        out["bands"][b].update(pm["bands"].get(b, {}))
    return out


def benchmark(meds, kid, duration):
    """The fair comparison value: the same-length band median for duration-dependent KPIs, else the account median
    (same platform when there are enough videos)."""
    b = duration_band(duration)
    scope = meds.get("scope", {}).get(kid)
    if kid in DURATION_DEPENDENT and b and kid in meds.get("bands", {}).get(b, {}):
        return meds["bands"][b][kid], f"median of your {b} videos"
    if kid in meds.get("all", {}):
        note = (f"{scope} median" if scope else "account median") +             (" (mixed lengths)" if kid in DURATION_DEPENDENT else "")
        return meds["all"][kid], note
    return None, None


def unit_economics(econ):
    """Max affordable CPA / CAC / CPL and break-even ROAS from the profile's economics block."""
    e = econ or {}
    out = {}
    aov, gm, ltv, l2c = e.get("avg_order_value"), e.get("gross_margin"), e.get("ltv"), e.get("lead_to_customer_rate")
    if aov and gm:
        out["max_cpa_first_order"] = {"value": aov * gm, "formula": "AOV × gross margin",
                                      "note": "break-even on the first order"}
    if gm:
        out["break_even_roas"] = {"value": 1 / gm, "formula": "1 ÷ gross margin",
                                  "note": "below this ROAS each attributed sale loses money"}
    if ltv and gm:
        out["max_cac_lifetime"] = {"value": ltv * gm, "formula": "LTV × gross margin",
                                   "note": "break-even over the customer's lifetime"}
        out["target_cac_3to1"] = {"value": ltv * gm / 3, "formula": "LTV × gross margin ÷ 3",
                                  "note": "leaves room for overhead and profit"}
        if l2c:
            out["max_cpl"] = {"value": ltv * gm * l2c, "formula": "LTV × gross margin × lead-to-customer rate",
                              "note": "the most a lead is worth at break-even"}
    if e.get("monthly_revenue_per_customer") and gm and e.get("payback_months"):
        out["max_cac_payback"] = {"value": e["monthly_revenue_per_customer"] * gm * e["payback_months"],
                                  "formula": "monthly revenue per customer × gross margin × payback months",
                                  "note": f"CAC recovered within {e['payback_months']} months"}
    if e.get("target_cpa"):
        out["target_cpa"] = {"value": e["target_cpa"], "formula": "from the profile", "note": ""}
    return out


def mer(econ, paid_records):
    """MER = total revenue ÷ total marketing spend. Uses economics.total_revenue / total_marketing_spend when given;
    otherwise a blended ROAS over all ads (attributed revenue ÷ ad spend), labelled as such."""
    e = econ or {}
    if e.get("total_revenue") and e.get("total_marketing_spend"):
        return {"value": e["total_revenue"] / e["total_marketing_spend"], "basis": "economics.total_revenue ÷ "
                "economics.total_marketing_spend (all channels: the honest number)"}
    rev = sum(r["revenue"] for r in paid_records if r.get("revenue") is not None)
    spend = sum(r["spend"] for r in paid_records if r.get("spend"))
    if rev and spend:
        return {"value": rev / spend, "basis": "blended ROAS proxy (attributed revenue ÷ ad spend across ads). Set "
                "economics.total_revenue and total_marketing_spend for real MER."}
    return None
