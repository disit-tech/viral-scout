"""Diagnostics: the biggest problem per video/ad, the 5 tests, creative fatigue, organic vs paid priorities.

Benchmarks are the ACCOUNT'S OWN medians (same kind: organic vs paid; same length band for retention KPIs), never
universal benchmarks. Thresholds: "low" = under 75% of the benchmark; for costs, "high" = over 133% of it.

Rules, in funnel order (each needs the step before it to be fine, so the problem is located, not just listed):
  low_reach        low views/reach                         → distribution, topic relevance, budget/CPM
  low_hook         low hook rate                           → first 1–3 seconds
  low_retention    hook fine, retention low                → the middle: pacing, payoff, length, drop-offs
  low_engagement   retention fine, engagement low          → no reason to comment/save/share, no CTA
  low_ctr          engagement fine, CTR low                → CTA, offer clarity, link placement
  low_cvr          CTR fine, conversion low                → post-click: landing page, speed, offer, pricing,
                                                             checkout friction, message match, traffic quality
  high_cpa         conversions fine, CPA high              → CPM/CPC, audience, bidding, frequency
  weak_profit      ROAS fine, profit weak                  → margins, attribution, incrementality
  fatigue          frequency rising while CTR falls        → refresh the creative
The biggest problem = the finding with the highest weight × severity, where weights follow the priorities of
the record's kind (organic vs paid) and the profile's goal (sales, leads, awareness).
"""
from . import kpis as K

LOW, HIGH_COST = 0.75, 1.33
MIN_N = 3          # a median over fewer videos isn't a benchmark

PRIORITIES = {
    "organic": [
        ("Retention", "avg % viewed and completion: the main distribution signal on every short-video feed"),
        ("Watch time", "average seconds watched; rewatches count on TikTok/Instagram"),
        ("Shares and saves", "the strongest 'this was worth it' signals; better than likes"),
        ("Audience relevance", "reach beyond followers; the right people, not just more people"),
        ("Follower conversion", "follows ÷ reach: did the video make people want more from you?"),
        ("Meaningful engagement", "specific comments and questions, not emoji; feed them back into ideas"),
    ],
    "paid": {
        "sales": [
            ("CPA / CAC", "against your max affordable CPA, not against the platform's averages"),
            ("Contribution margin / ROAS", "revenue × margin − spend; break-even ROAS = 1 ÷ gross margin"),
            ("CVR", "post-click: landing page, offer, checkout"),
            ("CTR", "link CTR: does the creative make the right people click?"),
            ("Hook rate and retention", "cheap attention lowers CPM and CPC"),
            ("CPM / CPC", "auction cost; watch it rise with frequency"),
        ],
        "leads": [
            ("CPL and lead quality", "CPL × lead-to-customer rate = the CAC you actually pay"),
            ("CAC vs LTV", "LTV:CAC 3:1 or better"),
            ("CVR on the form", "fields, friction, message match"),
            ("CTR", "link CTR"),
            ("Hook rate and retention", ""),
            ("CPM / CPC", ""),
        ],
        "awareness": [
            ("CPM and reach", "cost per thousand people actually reached"),
            ("Hook rate", "3-second views ÷ impressions"),
            ("ThruPlay / completion", "did the message land?"),
            ("Frequency", "2–3 per week is plenty for most audiences before fatigue"),
            ("Engagement and follows", "cheap secondary signal"),
            ("Brand lift", "only measurable with a platform lift study"),
        ],
    },
}

WEIGHTS = {
    "organic": {"low_retention": 1.0, "low_reach": 0.9, "low_hook": 0.85, "low_engagement": 0.8,
                "low_follow": 0.7, "low_ctr": 0.4, "low_cvr": 0.3},
    "sales": {"weak_profit": 1.0, "high_cpa": 0.95, "low_cvr": 0.85, "fatigue": 0.8, "low_ctr": 0.75,
              "low_hook": 0.65, "low_retention": 0.6, "low_reach": 0.5, "low_engagement": 0.3},
    "leads": {"high_cpa": 1.0, "low_cvr": 0.85, "fatigue": 0.8, "low_ctr": 0.75, "low_hook": 0.65,
              "low_retention": 0.6, "low_reach": 0.5, "weak_profit": 0.4, "low_engagement": 0.3},
    "awareness": {"low_reach": 1.0, "low_hook": 0.9, "low_retention": 0.85, "fatigue": 0.8,
                  "low_engagement": 0.5, "low_ctr": 0.3},
}

INVESTIGATE = {
    "low_reach": {
        "organic": ["Topic/audience relevance: is this something your audience searches for or sends to friends?",
                    "Cover and first frame: would it stop a scroll with the sound off?",
                    "Posting time and gaps between posts", "Reach beyond followers (was it shown to non-followers?)"],
        "paid": ["Budget and audience size (too small an audience caps delivery)",
                 "CPM against your median: competition, narrow targeting, seasonality",
                 "Learning phase / delivery limited / ad partially rejected"],
    },
    "low_hook": ["First 1–3 s: motion, a face, or the payoff shown first",
                 "On-screen text that states the promise in the first second",
                 "Is it obvious who it's for? Name the viewer or their situation",
                 "Cut logos, intros and 'hey guys' before the hook",
                 "Test 3 new openings on the same body (one variable)"],
    "low_retention": ["Does the body deliver the hook's promise, quickly? Delayed payoff loses people",
                      "Pacing: a cut or new visual every 1–3 s, no dead air",
                      "Length: try a version 20–30% shorter",
                      "Look at what happens at the drop-off points"],
    "low_engagement": ["Give a reason to comment: a specific question or a clear opinion",
                       "Give a reason to save: steps, a checklist, numbers",
                       "Give a reason to share: relatable, or useful to send to one person",
                       "Ask for one action in the last seconds"],
    "low_follow": ["Is it clear what else they'll get by following (series, format, promise)?",
                   "Profile: name, bio and pinned posts match the video's promise"],
    "low_ctr": ["CTA: say it and show it, once, near the end (and early for ads)",
                "Is the offer clear inside the video, not only in the caption?",
                "Link or button placement and wording",
                "Entertaining but not selling: tie the content to the problem you solve"],
    "low_cvr": ["Landing page message match: same promise, same visual, same offer as the ad",
                "Page speed on mobile (LPV rate shows lost clicks)",
                "Offer and pricing: is the price, guarantee or first step clear?",
                "Checkout or form friction: fields, account creation, payment options",
                "Traffic quality: accidental clicks, wrong audience, placements",
                "Tracking: is the pixel/conversions API firing on the thank-you page?"],
    "high_cpa": ["CPM against your median: audience saturation, seasonality, competition",
                 "CPC: the creative's CTR", "Optimization event and bid strategy",
                 "Frequency: same people seeing it again and again",
                 "Compare with your max affordable CPA, not with platform averages"],
    "weak_profit": ["Gross margin: below break-even ROAS every attributed sale loses money",
                    "Attribution: platform-claimed sales vs your own orders (view-through, two platforms "
                    "claiming one sale)",
                    "Incrementality: would these buyers have bought anyway? (holdout or geo test)",
                    "Discounts, refunds and returns lowering real revenue",
                    "First-order loss can be fine if LTV covers it: check LTV:CAC"],
    "fatigue": ["Refresh the hook and first frame, keep the body that works",
                "Widen the audience or exclude recent viewers/converters",
                "Rotate in a new variation before the old one dies"],
}

TITLES = {
    "low_reach": "Low views / reach", "low_hook": "Low hook rate", "low_retention": "Good hook, weak retention",
    "low_engagement": "Watched, but little engagement", "low_follow": "Watched, but few follows",
    "low_ctr": "Engaging, but few clicks", "low_cvr": "Clicks, but few conversions (post-click problem)",
    "high_cpa": "Converts, but CPA is too high", "weak_profit": "Good ROAS, weak profit",
    "fatigue": "Creative fatigue",
}


def _val(row, kid):
    k = row["kpis"].get(kid)
    return k["value"] if k else None


def compare(row, meds, kid):
    """(value, benchmark, ratio value÷benchmark, basis) or None."""
    v = _val(row, kid)
    if v is None:
        return None
    if meds.get("n", {}).get(kid, 0) < MIN_N:
        return None
    b, basis = K.benchmark(meds, kid, row.get("duration"))
    if not b:
        return None
    return v, b, v / b, basis


def _first(row, meds, kids):
    for kid in kids:
        c = compare(row, meds, kid)
        if c:
            return kid, c
    return None, None


ATTN = ["hook_rate", "view_rate_2s", "view_rate_6s"]
REACH = ["views", "reach", "impressions"]
RET = ["avg_pct_viewed", "completion_rate", "p50_rate", "thruplay_rate", "avg_watch_time"]
ENG = ["engagement_rate", "share_rate", "save_rate"]
CTR = ["link_ctr", "ctr"]


def _fmt(kid, v):
    unit = K.KPI_BY_ID[kid][3] if kid in K.KPI_BY_ID else ""
    if unit == "pct":
        return f"{v:.1f}%"
    if unit == "money":
        return f"{v:,.2f}"
    if unit == "x":
        return f"{v:.2f}×"
    if unit == "seconds":
        return f"{v:.1f} s"
    return f"{v:,.0f}"


def _ev(kid, c):
    label = K.KPI_BY_ID[kid][2] if kid in K.KPI_BY_ID else kid
    return f"{label} {_fmt(kid, c[0])} vs {_fmt(kid, c[1])} ({c[3]})"


def _low(c):
    return c is not None and c[2] < LOW


def _ok(c):
    return c is not None and c[2] >= 0.9


def fatigue(series, min_points=6):
    """series: [(date, frequency, ctr%)] oldest first. Fatigue = frequency up ≥15% while CTR down ≥20%
    (last third vs first third)."""
    pts = [p for p in series if p[1] is not None and p[2] is not None]
    if len(pts) < min_points:
        return None
    t = max(2, len(pts) // 3)
    f0, f1 = sum(p[1] for p in pts[:t]) / t, sum(p[1] for p in pts[-t:]) / t
    c0, c1 = sum(p[2] for p in pts[:t]) / t, sum(p[2] for p in pts[-t:]) / t
    rising, falling = f0 and f1 >= f0 * 1.15, c0 and c1 <= c0 * 0.8
    return {"detected": bool(rising and falling), "frequency": [round(f0, 2), round(f1, 2)],
            "ctr": [round(c0, 2), round(c1, 2)], "points": len(pts), "from": pts[0][0], "to": pts[-1][0]}


def daily_series(r):
    """(date, frequency, ctr%) per day from a record's daily rows."""
    out = []
    for d in sorted(r.get("daily") or [], key=lambda x: x.get("date") or ""):
        imp = d.get("impressions")
        clicks = d.get("link_clicks") if d.get("link_clicks") is not None else d.get("clicks")
        freq = d.get("frequency")
        if freq is None and imp and d.get("reach"):
            freq = imp / d["reach"]
        out.append((d.get("date"), freq, K.ratio(clicks, imp, 100) if imp and imp >= 50 else None))
    return out


def diagnose(row, meds, econ=None, goal="sales", fatigue_info=None):
    """row: record + {"kpis": {...}}. Returns {"problem", "findings", "caveats"}."""
    econ = econ or {}
    kind = row.get("kind") or "organic"
    wkey = "organic" if kind == "organic" else (goal if goal in WEIGHTS else "sales")
    weights = WEIGHTS[wkey]
    ue = K.unit_economics(econ)
    found = []

    def add(rule, sev, evidence, extra=None):
        inv = INVESTIGATE[rule]
        if isinstance(inv, dict):
            inv = inv["organic" if kind == "organic" else "paid"]
        sev = max(0.0, min(1.0, sev))
        found.append({"rule": rule, "title": TITLES[rule], "severity": round(sev, 2),
                      "score": round(sev * weights.get(rule, 0.2), 3), "evidence": evidence,
                      "investigate": list(inv) + (extra or [])})

    reach_k, reach_c = _first(row, meds, REACH)
    attn_k, attn_c = _first(row, meds, ATTN)
    ret_k, ret_c = _first(row, meds, RET)
    eng_k, eng_c = _first(row, meds, ENG)
    ctr_k, ctr_c = _first(row, meds, CTR)
    cvr_c = compare(row, meds, "cvr")

    if _low(reach_c):
        add("low_reach", 1 - reach_c[2], _ev(reach_k, reach_c))
    if _low(attn_c):
        add("low_hook", 1 - attn_c[2], _ev(attn_k, attn_c))
    if _low(ret_c) and (attn_c is None or not _low(attn_c)):
        c = K.curve(row)
        extra = []
        if c and c["drops"]:
            extra = [f"Drop-off: {K.curve_summary(c)}"]
        add("low_retention", 1 - ret_c[2], _ev(ret_k, ret_c), extra)
    if _low(eng_c) and (ret_c is None or not _low(ret_c)):
        add("low_engagement", 1 - eng_c[2], _ev(eng_k, eng_c))
    if kind == "organic":
        fc = compare(row, meds, "follower_conversion")
        if _low(fc) and (ret_c is None or not _low(ret_c)):
            add("low_follow", 1 - fc[2], _ev("follower_conversion", fc))
    if _low(ctr_c) and (eng_c is None or not _low(eng_c)) and goal != "awareness":
        add("low_ctr", 1 - ctr_c[2], _ev(ctr_k, ctr_c))
    if _low(cvr_c) and (ctr_c is None or not _low(ctr_c)):
        lpv = row["kpis"].get("lpv_rate")
        extra = [f"LPV rate {lpv['value']:.0f}% of link clicks reached the page"] if lpv else []
        add("low_cvr", 1 - cvr_c[2], _ev("cvr", cvr_c), extra)

    # CPA / CPL against the business's own limits first, the account median second.
    cost_kid = "cpl" if goal == "leads" and _val(row, "cpl") is not None else "cpa"
    cost = _val(row, cost_kid)
    if cost is not None and kind == "paid" and (cvr_c is None or not _low(cvr_c)):
        limit, basis = None, None
        if cost_kid == "cpa":
            for key in ("target_cpa", "max_cpa_first_order"):
                if key in ue:
                    limit, basis = ue[key]["value"], key.replace("_", " ")
                    break
        elif "max_cpl" in ue:
            limit, basis = ue["max_cpl"]["value"], "max CPL from LTV"
        if limit:
            if cost > limit:
                add("high_cpa", 1 - limit / cost, f"{K.KPI_BY_ID[cost_kid][2]} {cost:,.2f} vs {limit:,.2f} ({basis})")
        else:
            c = compare(row, meds, cost_kid)
            if c and c[2] > HIGH_COST:
                add("high_cpa", 1 - 1 / c[2], _ev(cost_kid, c))

    roas, cm = _val(row, "roas"), _val(row, "contribution_margin")
    if roas is not None and kind == "paid":
        be = ue.get("break_even_roas", {}).get("value")
        rc = compare(row, meds, "roas")
        roas_good = roas >= 2 or (rc is not None and rc[2] >= 1)
        if roas_good and ((cm is not None and cm < 0) or (be and roas < be)):
            sev = 1.0 if cm is not None and cm < 0 else 1 - roas / be
            ev = f"ROAS {roas:.2f}×" + (f" vs break-even {be:.2f}×" if be else "") + \
                 (f"; contribution margin {cm:,.2f}" if cm is not None else "")
            add("weak_profit", max(sev, 0.5), ev)

    if fatigue_info and fatigue_info.get("detected"):
        f = fatigue_info
        add("fatigue", min(1.0, 1 - f["ctr"][1] / f["ctr"][0] + 0.3) if f["ctr"][0] else 0.6,
            f"frequency {f['frequency'][0]} → {f['frequency'][1]}, CTR {f['ctr'][0]}% → {f['ctr'][1]}% "
            f"({f['from']} … {f['to']})")

    found.sort(key=lambda x: -x["score"])
    return {"problem": found[0] if found else None, "findings": found, "caveats": caveats(row, meds, econ)}


def caveats(row, meds, econ):
    out = []
    k = row["kpis"]
    if row.get("kind") == "paid" and any(x in k for x in ("cpa", "roas", "cvr", "conversions")):
        out.append("Attribution: conversions are what the platform claims within its window (view-through "
                   "included); two platforms can claim one sale. Check against your own orders.")
    if "roas" in k:
        gm = (econ or {}).get("gross_margin")
        be = f" Break-even ROAS here is {1 / gm:.2f}×." if gm else " Set economics.gross_margin to see break-even."
        out.append("A 4× ROAS is not automatically profitable: profit = revenue × margin − spend − other costs." + be)
    b = K.duration_band(row.get("duration"))
    if any(x in k for x in K.DURATION_DEPENDENT) and not (b and meds.get("bands", {}).get(b)):
        out.append("Like-for-like: retention is compared with videos of mixed lengths (fewer than 3 in this length "
                   "band). Don't compare a 7-s video with a 45-s one on completion.")
    if (k.get("hook_rate", {}).get("denominator") or "").endswith("proxy)"):
        out.append("Hook rate is a platform proxy here (skip rate / stayed to watch), not 3-s views ÷ impressions.")
    vol = row.get("impressions") or row.get("views") or 0
    if vol and vol < 1000:
        out.append(f"Small sample ({vol:,} {'impressions' if row.get('impressions') else 'views'}): early signal "
                   "only. Rates swing a lot under ~1,000.")
    return out


def _test(name, row, meds, kids, cost=False):
    for kid in kids:
        c = compare(row, meds, kid)
        if not c:
            continue
        r = c[2]
        if cost:
            status = "pass" if r <= 1.0 else "warn" if r <= HIGH_COST else "fail"
        else:
            status = "pass" if r >= 1.0 else "warn" if r >= LOW else "fail"
        return {"test": name, "status": status, "metric": kid, "value": c[0], "benchmark": c[1], "basis": c[3]}
    return {"test": name, "status": "n/a", "metric": None, "value": None, "benchmark": None,
            "basis": "no data (or fewer than 3 comparable videos)"}


def five_tests(row, meds, econ=None, goal="sales"):
    """Attention, Retention, Engagement, Action, Business impact: pass / warn / fail vs the account's medians."""
    econ = econ or {}
    paid = row.get("kind") == "paid"
    out = [
        _test("Attention", row, meds, ATTN + REACH),
        _test("Retention", row, meds, RET),
        _test("Engagement", row, meds, ENG),
        _test("Action", row, meds, CTR if paid else ["follower_conversion", "profile_visit_rate", "ctr"]),
    ]
    ue = K.unit_economics(econ)
    biz = None
    if paid:
        cm = _val(row, "contribution_margin")
        cpa = _val(row, "cpl" if goal == "leads" else "cpa")
        limit = (ue.get("max_cpl") if goal == "leads" else ue.get("target_cpa") or ue.get("max_cpa_first_order"))
        if cm is not None:
            biz = {"test": "Business impact", "status": "pass" if cm > 0 else "fail", "metric": "contribution_margin",
                   "value": cm, "benchmark": 0, "basis": "contribution margin above zero"}
        elif cpa is not None and limit:
            r = cpa / limit["value"]
            biz = {"test": "Business impact", "status": "pass" if r <= 1 else "warn" if r <= 1.25 else "fail",
                   "metric": "cpl" if goal == "leads" else "cpa", "value": cpa, "benchmark": limit["value"],
                   "basis": "your target / max affordable"}
        elif _val(row, "roas") is not None and "break_even_roas" in ue:
            roas, be = _val(row, "roas"), ue["break_even_roas"]["value"]
            biz = {"test": "Business impact", "status": "pass" if roas >= be * 1.2 else "warn" if roas >= be else "fail",
                   "metric": "roas", "value": roas, "benchmark": be, "basis": "break-even ROAS (+20% for pass)"}
        else:
            biz = _test("Business impact", row, meds, ["cpa", "cpl", "cac"], cost=True)
            if biz["status"] == "n/a":
                biz = _test("Business impact", row, meds, ["roas"])
    else:
        biz = _test("Business impact", row, meds, ["cvr", "follower_conversion"])
        if biz["metric"] == "follower_conversion":
            biz["basis"] += " (follows as the organic business signal)"
    out.append(biz)
    return out


def priorities(goal="sales"):
    paid = PRIORITIES["paid"].get(goal) or PRIORITIES["paid"]["sales"]
    return {"organic": [{"what": a, "why": b} for a, b in PRIORITIES["organic"]],
            "paid": [{"what": a, "why": b} for a, b in paid], "goal": goal}
