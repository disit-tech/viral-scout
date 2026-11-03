"""Tests for own performance: KPIs, diagnostics, CSV import, and a no-keys run.

  python -m pytest tests            (if pytest is installed)
  python tests/test_perf.py         (no dependencies: runs every test_ function)
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from viral_scout.perf import csvimport, diagnose as D, kpis as K  # noqa: E402
from viral_scout.perf.run import analyze  # noqa: E402
from viral_scout.perf.schema import blank  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"


def approx(a, b, tol=1e-4):
    return a is not None and abs(a - b) <= tol * max(1, abs(b))


def paid(id_, **kw):
    r = blank("test", "paid", id_, platform="facebook")
    r.update(kw)
    return r


def organic(id_, **kw):
    r = blank("test", "organic", id_, platform="instagram")
    r.update(kw)
    return r


# ---- kpis.py -------------------------------------------------------------------------------------------------
def test_attention_and_traffic_formulas():
    r = paid("a", impressions=10_000, reach=4_000, views_3s=3_000, views_2s=3_500, video_starts=9_000, spend=200,
             clicks=150, link_clicks=100, landing_page_views=80)
    k = K.compute(r)
    assert approx(k["hook_rate"]["value"], 30.0)                      # 3s ÷ impressions × 100
    assert "impressions" in k["hook_rate"]["denominator"]
    assert approx(k["view_rate_2s"]["value"], 35.0)
    assert approx(k["start_rate"]["value"], 90.0)
    assert approx(k["cpm"]["value"], 20.0)                            # 200 ÷ 10,000 × 1000
    assert approx(k["frequency"]["value"], 2.5)
    assert approx(k["ctr"]["value"], 1.5)
    assert approx(k["link_ctr"]["value"], 1.0)
    assert approx(k["cpc"]["value"], 200 / 150)
    assert approx(k["cpc_link"]["value"], 2.0)
    assert approx(k["lpv_rate"]["value"], 80.0)


def test_retention_formulas():
    r = paid("b", video_starts=1000, p25=600, p50=400, p75=250, p100=100, avg_watch_time=9, duration=30,
             impressions=2000, thruplays=300)
    k = K.compute(r)
    assert approx(k["avg_pct_viewed"]["value"], 30.0)                 # 9 ÷ 30 × 100
    assert approx(k["completion_rate"]["value"], 10.0)                # 100 ÷ 1000 × 100
    assert approx(k["p50_rate"]["value"], 40.0)
    assert approx(k["thruplay_rate"]["value"], 15.0)
    c = K.curve(r)
    assert c["source"] == "quartiles"
    assert c["points"][0] == [0.0, 100.0]
    assert c["drops"][0]["from"] == 0.0 and approx(c["drops"][0]["drop"], 40.0)   # biggest drop: start → 25%
    assert c["drops"][0]["seconds"] == [0.0, 7.5]
    assert "biggest drops" in K.curve_summary(c)


def test_avg_pct_falls_back_to_platform_value():
    r = organic("c", avg_pct_viewed_given=42.0)
    assert approx(K.compute(r)["avg_pct_viewed"]["value"], 42.0)


def test_youtube_curve_resampled_and_rewatch():
    pts = [[i / 100, (1.2 if i < 5 else 1.0 - i / 200), 0.5] for i in range(101)]
    r = organic("yt", platform="youtube", retention=pts, duration=20)
    c = K.curve(r)
    assert c["source"] == "retention" and len(c["points"]) == 11
    assert c["peak"] > 100
    assert approx(K.compute(r)["rewatch"]["value"], 20.0)


def test_engagement_formulas_and_fallback_denominator():
    r = organic("d", views=10_000, reach=8_000, likes=500, comments=50, shares=100, saves=150, follows=40,
                profile_visits=200)
    k = K.compute(r)
    assert approx(k["engagement_rate"]["value"], 8.0)                 # 800 ÷ 10,000
    assert approx(k["share_rate"]["value"], 1.0)
    assert approx(k["save_rate"]["value"], 1.5)
    assert approx(k["follower_conversion"]["value"], 0.5)             # 40 ÷ reach 8,000
    assert k["follower_conversion"]["denominator"] == "reach"
    assert approx(k["profile_visit_rate"]["value"], 2.5)
    r2 = organic("e", reach=1000, likes=50)
    assert "reach" in K.compute(r2)["like_rate"]["denominator"]


def test_hook_proxies():
    assert approx(K.compute(organic("f", skip_rate_given=35.0))["hook_rate"]["value"], 65.0)
    k = K.compute(organic("g", stayed_pct_given=70.0))["hook_rate"]
    assert approx(k["value"], 70.0) and k["denominator"].endswith("proxy)")


def test_conversion_and_profit():
    econ = {"avg_order_value": 100, "gross_margin": 0.4, "ltv": 400, "lead_to_customer_rate": 0.2}
    r = paid("h", spend=1000, link_clicks=500, landing_page_views=400, purchases=20, revenue=2400, leads=50)
    k = K.compute(r, econ)
    assert approx(k["cvr"]["value"], 5.0)                             # 20 ÷ 400 LPV
    assert "landing page views" in k["cvr"]["denominator"]
    assert approx(k["cpa"]["value"], 50.0)
    assert approx(k["cpl"]["value"], 20.0)
    assert approx(k["cac"]["value"], 50.0)
    assert approx(k["aov"]["value"], 120.0)
    assert approx(k["roas"]["value"], 2.4)
    assert approx(k["contribution_margin"]["value"], 2400 * 0.4 - 1000)   # −40: ROAS 2.4 but losing money
    assert approx(k["ltv_cac"]["value"], 8.0)
    # Revenue estimated from AOV when not reported
    k2 = K.compute(paid("i", spend=500, purchases=10), econ)
    assert approx(k2["roas"]["value"], 2.0) and "estimate" in k2["roas"]["denominator"]
    # Lead-gen CAC
    k3 = K.compute(paid("j", spend=300, leads=30), econ)
    assert approx(k3["cac"]["value"], 50.0)                           # 300 ÷ (30 × 0.2)


def test_unit_economics_and_mer():
    ue = K.unit_economics({"avg_order_value": 100, "gross_margin": 0.4, "ltv": 400, "lead_to_customer_rate": 0.2,
                           "monthly_revenue_per_customer": 50, "payback_months": 6, "target_cpa": 35})
    assert approx(ue["max_cpa_first_order"]["value"], 40)
    assert approx(ue["break_even_roas"]["value"], 2.5)
    assert approx(ue["max_cac_lifetime"]["value"], 160)
    assert approx(ue["max_cpl"]["value"], 32)
    assert approx(ue["max_cac_payback"]["value"], 120)
    m = K.mer({"total_revenue": 50_000, "total_marketing_spend": 10_000}, [])
    assert approx(m["value"], 5.0)
    m2 = K.mer({}, [paid("k", spend=100, revenue=300), paid("l", spend=100, revenue=100)])
    assert approx(m2["value"], 2.0) and "proxy" in m2["basis"]


def test_sentiment():
    s = K.sentiment(["love this, so helpful", "boring and useless", "thanks!"])
    assert s[1] == 3 and s[2] == 2 and approx(s[0], 20.0)
    assert K.sentiment(["ok"]) is None


def test_missing_inputs_give_no_kpi():
    k = K.compute(blank("test", "paid", "z"))
    assert k == {}


# ---- diagnose.py ---------------------------------------------------------------------------------------------
def _account():
    """Four ads: a control, a weak hook, a hook that doesn't hold, and one that clicks but doesn't convert."""
    base = dict(impressions=100_000, video_starts=90_000, spend=1000, duration=20)
    return [
        paid("ok", views_3s=30_000, p25=27_000, p50=18_000, p75=9_000, p100=4_500, link_clicks=1500,
             landing_page_views=1200, purchases=60, revenue=6000, likes=800, comments=40, shares=60, saves=30,
             **base),
        paid("weak_hook", views_3s=10_000, p25=9_000, p50=6_000, p75=3_000, p100=1_500, link_clicks=1400,
             landing_page_views=1100, purchases=50, revenue=5000, likes=750, comments=40, shares=60, saves=30, **base),
        paid("no_hold", views_3s=31_000, p25=12_000, p50=5_000, p75=2_000, p100=900, link_clicks=1500,
             landing_page_views=1150, purchases=55, revenue=5500, likes=780, comments=40, shares=55, saves=30, **base),
        paid("no_convert", views_3s=29_000, p25=26_000, p50=17_000, p75=8_500, p100=4_200, link_clicks=1600,
             landing_page_views=1300, purchases=10, revenue=1000, likes=820, comments=45, shares=65, saves=35, **base),
    ]


def test_diagnose_finds_the_right_stage():
    rows, meds, _ = analyze(_account(), {}, "sales")
    by = {r["id"]: r for r in rows}
    assert by["weak_hook"]["diagnosis"]["problem"]["rule"] == "low_hook"
    assert by["no_hold"]["diagnosis"]["problem"]["rule"] == "low_retention"
    assert any("Drop-off" in x for x in by["no_hold"]["diagnosis"]["problem"]["investigate"])
    p = by["no_convert"]["diagnosis"]["problem"]
    assert p["rule"] in ("low_cvr", "high_cpa")
    assert any(f["rule"] == "low_cvr" for f in by["no_convert"]["diagnosis"]["findings"])
    assert any("Landing page" in x for x in next(f for f in by["no_convert"]["diagnosis"]["findings"]
                                                 if f["rule"] == "low_cvr")["investigate"])
    assert by["ok"]["diagnosis"]["problem"] is None
    assert any("Attribution" in c for c in by["ok"]["diagnosis"]["caveats"])


def test_weak_profit_and_target_cpa():
    econ = {"gross_margin": 0.3, "target_cpa": 30}
    recs = _account()
    rows, meds, _ = analyze(recs, econ, "sales")
    by = {r["id"]: r for r in rows}
    # ROAS 6× with 30% margin → break-even 3.33×, profitable; CPA 16.7 < 30
    assert all(f["rule"] != "weak_profit" for f in by["ok"]["diagnosis"]["findings"])
    # no_convert: CPA 100 > target 30
    assert any(f["rule"] == "high_cpa" or f["rule"] == "low_cvr" for f in by["no_convert"]["diagnosis"]["findings"])
    # A 2.5× ROAS ad at 30% margin loses money even though "2.5× sounds fine"
    r = paid("roas_trap", spend=1000, revenue=2500, purchases=25, link_clicks=1000, landing_page_views=900,
             impressions=100_000)
    rows, meds, _ = analyze(recs + [r], econ, "sales")
    trap = next(x for x in rows if x["id"] == "roas_trap")
    assert any(f["rule"] == "weak_profit" for f in trap["diagnosis"]["findings"])
    assert any("4× ROAS" in c for c in trap["diagnosis"]["caveats"])


def test_five_tests():
    rows, meds, _ = analyze(_account(), {"avg_order_value": 100, "gross_margin": 0.4}, "sales")
    by = {r["id"]: {t["test"]: t for t in r["tests"]} for r in rows}
    assert by["weak_hook"]["Attention"]["status"] == "fail"
    assert by["ok"]["Attention"]["status"] == "pass"
    assert by["no_hold"]["Retention"]["status"] == "fail"
    assert by["ok"]["Business impact"]["metric"] == "contribution_margin"
    assert by["ok"]["Business impact"]["status"] == "pass"
    assert by["no_convert"]["Business impact"]["status"] == "fail"
    assert [t for t in by["ok"]] == ["Attention", "Retention", "Engagement", "Action", "Business impact"]


def test_like_for_like_bands():
    recs = [organic(f"s{i}", views=1000, p100=800, duration=7) for i in range(3)] + \
           [organic(f"l{i}", views=1000, p100=200, duration=45) for i in range(3)]
    rows, meds, _ = analyze(recs, {}, "sales")
    long_one = next(r for r in rows if r["id"] == "l0")
    t = next(t for t in long_one["tests"] if t["test"] == "Retention")
    assert t["status"] == "pass" and "30–60s" in t["basis"]   # vs other 45-s videos


def test_fatigue():
    series = [(f"2026-10-0{i}", 1.2 + i * 0.25, 1.5 - i * 0.15) for i in range(1, 8)]
    f = D.fatigue(series)
    assert f["detected"]
    assert not D.fatigue([(str(i), 2.0, 1.0) for i in range(8)])["detected"]
    assert D.fatigue(series[:3]) is None


def test_organic_priorities_and_awareness_variant():
    pr = D.priorities("awareness")
    assert pr["organic"][0]["what"] == "Retention"
    assert pr["paid"][0]["what"].startswith("CPM")
    assert D.priorities("leads")["paid"][0]["what"].startswith("CPL")


# ---- CSV import ----------------------------------------------------------------------------------------------
def test_meta_csv():
    recs, unknown = csvimport.read(str(FIX / "meta_ads_export.csv"), "meta")
    assert len(recs) == 3                                     # Totals row skipped
    a = next(r for r in recs if r["id"] == "120201")
    assert a["kind"] == "paid" and a["platform"] == "facebook" and a["source"] == "csv:meta"
    assert a["spend"] == 1000 and a["impressions"] == 100_000 and a["views_3s"] == 30_000
    assert a["views"] == 30_000 and a["avg_watch_time"] == 6 and a["revenue"] == 6000
    assert a["conversions"] == 60 and a["p100"] == 4500 and a["date_start"] == "2026-10-01"
    k = K.compute(a)
    assert approx(k["hook_rate"]["value"], 30.0) and approx(k["roas"]["value"], 6.0)
    assert unknown == []


def test_tiktok_csv_daily_rows_merge_and_fatigue():
    recs, unknown = csvimport.read(str(FIX / "tiktok_ads_export.csv"), "tiktok")
    assert len(recs) == 1
    r = recs[0]
    assert r["id"] == "1800001" and r["spend"] == 300 and r["impressions"] == 60_000 and len(r["daily"]) == 6
    assert r["views_2s"] == sum([4000, 3900, 3800, 3700, 3600, 3500])
    assert r["date_start"] == "2026-10-01" and r["date_stop"] == "2026-10-06"
    k = K.compute(r)
    assert approx(k["view_rate_2s"]["value"], 22500 / 60000 * 100)
    f = D.fatigue(D.daily_series(r))
    assert f["detected"], f


def test_youtube_csv():
    recs, _ = csvimport.read(str(FIX / "youtube_studio_export.csv"), "youtube")
    assert len(recs) == 3                                     # Total row skipped
    v = next(r for r in recs if r["id"] == "abc123XYZ01")
    assert v["kind"] == "organic" and v["platform"] == "youtube"
    assert v["avg_watch_time"] == 8 and v["duration"] == 28 and v["clicks"] == 6000
    assert approx(v["total_watch_time"], 70 * 3600)
    k = K.compute(v)
    assert approx(k["avg_pct_viewed"]["value"], 8 / 28 * 100)
    assert approx(k["hook_rate"]["value"], 72.5)
    assert approx(k["ctr"]["value"], 4.0)


def test_generic_csv_and_value_parsing():
    text = "id,title,kind,impressions,views_3s,spend,purchases,revenue\nx1,My ad,paid,\"1,000\",250,$50.00,2,\"€120,50\"\n"
    recs, _ = csvimport.read(text, "generic")
    assert recs[0]["impressions"] == 1000 and recs[0]["spend"] == 50 and approx(recs[0]["revenue"], 120.5)
    assert csvimport.parse_value("12.5%") == 12.5 and csvimport.parse_value("1:02:03") == 3723
    assert csvimport.parse_value("--") is None
    assert csvimport.norm_header("Amount spent (EUR)") == "amount spent"


# ---- API payload normalizers (shapes from the platforms' docs) ----------------------------------------------
def test_meta_api_row():
    from viral_scout.perf.meta_ads import normalize
    row = {"ad_id": "9", "ad_name": "Hook A", "impressions": "10000", "reach": "4000", "frequency": "2.5",
           "spend": "200.5", "clicks": "150", "inline_link_clicks": "100", "date_start": "2026-10-01",
           "actions": [{"action_type": "video_view", "value": "3000"}, {"action_type": "landing_page_view", "value": "80"},
                       {"action_type": "omni_purchase", "value": "4"}, {"action_type": "purchase", "value": "4"}],
           "action_values": [{"action_type": "omni_purchase", "value": "480"}],
           "video_p100_watched_actions": [{"action_type": "video_view", "value": "500"}],
           "video_play_actions": [{"action_type": "video_view", "value": "9000"}],
           "video_thruplay_watched_actions": [{"action_type": "video_view", "value": "1200"}]}
    r = normalize(row)
    assert r["views_3s"] == 3000 and r["views"] == 3000 and r["purchases"] == 4 and r["revenue"] == 480
    assert r["landing_page_views"] == 80 and r["p100"] == 500 and r["thruplays"] == 1200 and r["video_starts"] == 9000
    k = K.compute(r)
    assert approx(k["hook_rate"]["value"], 30.0) and approx(k["cvr"]["value"], 5.0)


def test_tiktok_api_row():
    from viral_scout.perf.tiktok_ads import normalize
    row = {"dimensions": {"ad_id": "77"}, "metrics": {"ad_name": "POV", "spend": "50.00", "impressions": "10000",
           "clicks": "150", "conversion": "5", "video_play_actions": "9000", "video_watched_2s": "4000",
           "video_views_p100": "800", "average_video_play": "4.5", "complete_payment_roas": "2.0"}}
    r = normalize(row)
    assert r["id"] == "77" and r["views_2s"] == 4000 and r["revenue"] == 100
    k = K.compute(r)
    assert approx(k["view_rate_2s"]["value"], 40.0) and approx(k["completion_rate"]["value"], 800 / 9000 * 100)


# ---- end to end: no keys --------------------------------------------------------------------------------------
def test_cli_without_keys_lists_skipped_sources():
    from viral_scout import config
    from viral_scout.perf.run import build, import_csv
    for k in ("IG_GRAPH_TOKEN", "IG_GRAPH_USER_ID", "YT_OAUTH_CLIENT_ID", "YT_OAUTH_CLIENT_SECRET",
              "YT_OAUTH_REFRESH_TOKEN", "META_ADS_TOKEN", "META_AD_ACCOUNT_ID", "TIKTOK_ADS_TOKEN",
              "TIKTOK_ADVERTISER_ID"):
        os.environ.pop(k, None)
    with tempfile.TemporaryDirectory() as tmp:
        prof = Path(tmp) / "perftest.yaml"
        prof.write_text(f"name: perftest\noutput_dir: {tmp}/out\ndb: {tmp}/perftest.sqlite\n"
                        "economics: {avg_order_value: 100, gross_margin: 0.4, ltv: 300}\n", encoding="utf-8")
        cfg = config.load(str(prof))
        cfg["db"] = f"{tmp}/perftest.sqlite"
        import viral_scout.export as ex
        old = ex.WEB_DATA
        ex.WEB_DATA = Path(tmp) / "web"
        try:
            data, (md, js) = build(cfg)
            assert len(data["sources"]["skipped"]) == 4
            text = Path(md).read_text(encoding="utf-8")
            assert "## Skipped sources" in text and "META_ADS_TOKEN" in text and "perf auth youtube" in text
            import_csv(cfg, str(FIX / "meta_ads_export.csv"), "meta")
            data, (md, js) = build(cfg, do_pull=False)
            assert len(data["records"]) == 3
            text = Path(md).read_text(encoding="utf-8")
            for h in ("## KPIs", "## The 5 tests", "## Retention curves", "## Diagnostics", "## Priorities"):
                assert h in text, h
            assert json.loads(Path(js).read_text(encoding="utf-8"))["unit_economics"]["break_even_roas"]
        finally:
            ex.WEB_DATA = old


if __name__ == "__main__":
    fails = 0
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        try:
            fn()
            print(f"ok   {name}")
        except Exception as err:          # noqa: BLE001
            fails += 1
            import traceback
            print(f"FAIL {name}: {type(err).__name__}: {err}")
            traceback.print_exc()
    print(f"\n{len(tests) - fails}/{len(tests)} passed")
    sys.exit(1 if fails else 0)
