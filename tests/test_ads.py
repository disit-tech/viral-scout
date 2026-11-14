"""Ads scout checks that need no keys or network: parsing, offer/CTA extraction, variants, scoring, report.

  python -m unittest discover -s tests -v
"""
import json
import math
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from viral_scout.ads import extract, score, sources  # noqa: E402
from viral_scout.ads.model import Ad, domain, now, parse_count, parse_when  # noqa: E402


def days_ago(d):
    return now() - timedelta(days=d)


class Parsing(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(parse_when("2026-03-01T08:00:00+0000").year, 2026)
        self.assertEqual(parse_when("20260701").month, 7)
        self.assertEqual(parse_when(20260701).day, 1)                 # TikTok YYYYMMDD as a number
        self.assertEqual(parse_when(1767225600).year, 2026)           # unix seconds
        self.assertEqual(parse_when(1767225600000).year, 2026)        # unix ms
        self.assertEqual(parse_when("Jan 5, 2026").day, 5)
        self.assertIsNone(parse_when("soon"))

    def test_counts(self):
        self.assertEqual(parse_count("11K"), 11000)
        self.assertEqual(parse_count("1.2M"), 1200000)
        self.assertEqual(parse_count("100K+"), 100000)
        self.assertEqual(parse_count("12,345"), 12345)
        self.assertEqual(parse_count({"lower_bound": "1000", "upper_bound": "1999"}), 1499)
        self.assertIsNone(parse_count(None))

    def test_domain(self):
        self.assertEqual(domain("https://www.Sunrun.com/go?x=1"), "sunrun.com")
        self.assertEqual(domain("SUNRUN.COM"), "sunrun.com")
        self.assertEqual(domain("l.facebook.com/l.php?u=https%3A%2F%2Fwww.example.org%2Fa"), "example.org")
        self.assertEqual(domain("Learn more"), "")


class Extraction(unittest.TestCase):
    def test_offers_en(self):
        tags, snips = extract.offers("Get a FREE quote today! $0 down financing, 30% federal tax credit. "
                                     "Limited time offer. Rated 4.9 stars by 2,000 homeowners.")
        for t in ("free_quote", "financing", "incentive", "urgency", "social_proof"):
            self.assertIn(t, tags)
        self.assertNotIn("free", tags)            # a specific free offer replaces the generic tag
        self.assertTrue(snips)

    def test_offers_price_and_trial(self):
        tags, _ = extract.offers("Your first lesson is free, then $19/lesson. Money-back guarantee.")
        self.assertIn("free_trial", tags)
        self.assertIn("price", tags)
        self.assertIn("guarantee", tags)

    def test_offers_ru_uk(self):
        tags, _ = extract.offers("Бесплатный пробный урок! Скидка 20% до пятницы. Осталось 5 мест.")
        self.assertIn("free_trial", tags)
        self.assertIn("discount", tags)
        self.assertIn("urgency", tags)
        tags, _ = extract.offers("Безкоштовне пробне заняття. Знижка -30%. Розстрочка без переплат. 1200 грн/місяць")
        self.assertIn("free_trial", tags)
        self.assertIn("discount", tags)
        self.assertIn("financing", tags)
        self.assertIn("price", tags)

    def test_hook(self):
        self.assertEqual(extract.hook("Title", "🔥\nStop paying ComEd for blackouts. Here's how batteries work."),
                         "Stop paying ComEd for blackouts.")
        self.assertEqual(extract.hook("Book a free class", ""), "Book a free class")

    def test_cta(self):
        self.assertEqual(extract.cta("LEARN_MORE", ""), "Learn more")
        self.assertEqual(extract.cta("", "Запишитесь на пробный урок сегодня"), "Book a free lesson")
        self.assertEqual(extract.cta("", "Get your free quote in 2 minutes"), "Get a quote")

    def test_format(self):
        self.assertEqual(extract.norm_format("VIDEO"), "video")
        self.assertEqual(extract.norm_format("DCO"), "dco")
        self.assertEqual(extract.norm_format("", cards=3), "carousel")
        self.assertEqual(extract.norm_format("", has_images=1), "image")


def sample_ads():
    copy = "Power outage again? Keep your lights on with a home battery. Free quote, $0 down."
    return [
        Ad(source="meta_api", id="1", advertiser="SunCo", body=copy, link_url="https://sunco.com/battery",
           start=days_ago(120), platforms=["facebook", "instagram"], reach=50000),
        Ad(source="meta_api", id="2", advertiser="SunCo", body=copy + " 🔋", link_url="https://sunco.com/battery?v=2",
           start=days_ago(95), platforms=["facebook"], reach=20000),
        Ad(source="meta_api", id="3", advertiser="SunCo", body="Different words entirely here for testing purposes now",
           link_url="https://sunco.com/battery", start=days_ago(40), reach=1000),
        Ad(source="meta_api", id="4", advertiser="SunCo", body="Brand new test about electric bills going up again",
           start=days_ago(3)),
        Ad(source="meta_api", id="5", advertiser="OtherSolar", body="Solar is free! Sign up now.",
           start=days_ago(200), stop=days_ago(150)),
        Ad(source="apify_meta", id="6", advertiser="OtherSolar", body="Huge sale on panels", start=days_ago(10),
           variants_reported=8),
    ]


class Scoring(unittest.TestCase):
    def setUp(self):
        self.ads = score.score(score.enrich(sample_ads()))
        self.by = {a.id: a for a in self.ads}

    def test_variants_grouping(self):
        # 1 and 2 share copy; 3 shares the landing page path with 1 → one group of 3.
        self.assertEqual(self.by["1"].group, self.by["2"].group)
        self.assertEqual(self.by["1"].group, self.by["3"].group)
        self.assertEqual(self.by["1"].variants, 3)
        self.assertEqual(self.by["4"].variants, 1)
        self.assertEqual(self.by["6"].variants, 8)             # source's own collation count wins

    def test_longevity_and_labels(self):
        self.assertIn("🏆 90d+ long-runner", self.by["1"].labels)
        self.assertIn("🏆 30d+ long-runner", self.by["3"].labels)
        self.assertIn("🆕 new test", self.by["4"].labels)
        self.assertIn("⏹ stopped", self.by["5"].labels)
        self.assertAlmostEqual(self.by["5"].days_running, 50, delta=0.1)
        self.assertIn("🧬 3 variants", self.by["1"].labels)

    def test_score_order_and_range(self):
        self.assertEqual(self.ads[0].id, "1")
        for a in self.ads:
            self.assertGreaterEqual(a.ad_score, 0)
            self.assertLessEqual(a.ad_score, 100)
        self.assertGreater(self.by["1"].ad_score, self.by["4"].ad_score)
        self.assertGreater(self.by["3"].ad_score, self.by["5"].ad_score)   # running beats stopped

    def test_formula(self):
        import math
        # 120 days, 3 variants, active, best reach among 3 → 0.5*1 + 0.3*ln3/ln10 + 0.2 + 0.15*1 ≈ 99.3
        self.assertAlmostEqual(self.by["1"].ad_score, round(100 * (0.5 + 0.3 * math.log(3) / math.log(10) + 0.2 + 0.15), 1),
                               delta=0.1)
        # 3 days, 1 variant, active, no reach → 0.5*ln4/ln121 + 0.2
        self.assertAlmostEqual(self.by["4"].ad_score, round(100 * (0.5 * math.log(4) / math.log(121) + 0.2), 1), delta=0.2)

    def test_offers_filled(self):
        self.assertIn("free_quote", self.by["1"].offers)
        self.assertIn("free", self.by["5"].offers)        # "Solar is free!" is flagged for a compliance check

    def test_advertiser_summary(self):
        rows = {r["advertiser"]: r for r in score.advertisers(self.ads)}
        self.assertEqual(rows["SunCo"]["ads"], 4)
        self.assertEqual(rows["SunCo"]["long_runners"], 3)
        self.assertEqual(rows["SunCo"]["launched_last_14d"], 1)


class SourceMapping(unittest.TestCase):
    def test_meta_api_row(self):
        row = {"id": "123", "page_id": "9", "page_name": "SunCo", "ad_delivery_start_time": "2026-06-01T07:00:00+0000",
               "ad_creative_bodies": ["Keep the lights on."], "ad_creative_link_titles": ["Free quote"],
               "ad_creative_link_captions": ["SUNCO.COM"], "publisher_platforms": ["FACEBOOK", "INSTAGRAM"],
               "eu_total_reach": 4200, "ad_snapshot_url": "https://www.facebook.com/ads/archive/render_ad/?id=123&access_token=SECRET"}
        ad = sources._meta_ad(row, "meta keyword solar", ["DE"])
        self.assertEqual(ad.landing_domain, "sunco.com")
        self.assertEqual(ad.platforms, ["facebook", "instagram"])
        self.assertEqual(ad.reach, 4200)
        self.assertNotIn("SECRET", json.dumps(ad.to_json()))   # the token in snapshot URLs never reaches the JSON

    def test_tiktok_row(self):
        row = {"ad": {"id": 77, "first_shown_date": 20260701, "last_shown_date": 20260810, "status": "inactive",
                      "videos": [{"url": "https://v.example/x.mp4"}], "image_urls": [], "reach": {"unique_users_seen": "11K"}},
               "advertiser": {"buisness_id": 5, "business_name": "EnglishCo", "paid_by": "EnglishCo"}}
        ad = sources._tiktok_ad(row, "tiktok keyword english")
        self.assertEqual(ad.format, "video")
        self.assertEqual(ad.reach, 11000)
        self.assertEqual(ad.advertiser_id, "5")
        self.assertAlmostEqual(ad.days_running, 40, delta=0.1)
        self.assertFalse(ad.is_active)

    def test_apify_meta_row_loose(self):
        row = {"adArchiveID": "555", "pageName": "SunCo", "isActive": True, "startDate": 1767225600,
               "collationCount": 4, "publisherPlatform": ["FACEBOOK"],
               "snapshot": {"body": {"text": "Free estimate this week only."}, "title": "SunCo Solar",
                            "linkUrl": "https://sunco.com/offer", "ctaText": "Get quote", "displayFormat": "VIDEO",
                            "videos": [{"videoPreviewImageUrl": "https://img.example/p.jpg"}]}}
        ad = sources._meta_apify_ad(row, "apify meta advertiser SunCo", "US")
        self.assertEqual((ad.id, ad.format, ad.variants_reported, ad.image), ("555", "video", 4, "https://img.example/p.jpg"))
        self.assertTrue(ad.is_active)
        self.assertEqual(ad.url, "https://www.facebook.com/ads/library/?id=555")

    def test_meta_countries(self):
        self.assertEqual(sources.meta_countries({"countries": ["US"]}), [])
        self.assertEqual(sources.meta_countries({"countries": ["US", "pl"]}), ["PL"])
        self.assertEqual(sources.meta_countries({"countries": ["US"], "meta_countries": ["de"]}), ["DE"])

    def test_lookup_links(self):
        rows = sources.lookup_links({"countries": ["US"], "advertisers": ["Sunrun", {"name": "X", "page_id": "42",
                                                                                     "domain": "x.com"}],
                                     "keywords": ["home battery"], "domains": ["sunrun.com"]})
        self.assertEqual(len(rows), 4)
        self.assertIn("view_all_page_id=42", rows[1]["links"]["Meta Ad Library"])
        self.assertIn("q=home+battery", rows[3]["links"]["Meta Ad Library"])


class RunWithoutKeys(unittest.TestCase):
    def test_skipped_sources_listed(self):
        for k in ("META_AD_LIBRARY_TOKEN", "TIKTOK_RESEARCH_CLIENT_KEY", "APIFY_TOKEN", "APIFY_ADS_ACTOR"):
            os.environ.pop(k, None)
        from viral_scout.ads import run as ads_run
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {"name": "t", "db": str(Path(tmp) / "t.sqlite"), "output_dir": tmp,
                   "ads": {"advertisers": ["SunCo"], "keywords": ["home battery"], "countries": ["US"]}}
            import viral_scout.export as ex
            orig = ex.export_ads
            ex.export_ads = lambda cfg, out=None: None           # don't touch web/data from a test
            try:
                res, (md, js) = ads_run.scout_ads(cfg, quiet=True)
            finally:
                ex.export_ads = orig
            self.assertEqual(res["ads"], [])
            self.assertEqual(len(res["skipped"]), 5)
            text = Path(md).read_text(encoding="utf-8")
            self.assertIn("## Skipped sources", text)
            self.assertIn("META_AD_LIBRARY_TOKEN", text)
            self.assertIn("## Look them up yourself", text)
            self.assertTrue(json.loads(Path(js).read_text(encoding="utf-8"))["skipped"])

    def test_meta_api_us_only_is_a_coverage_skip(self):
        # With a token but only US in countries, the official API would return political ads only: skip, no request.
        os.environ["META_AD_LIBRARY_TOKEN"] = "dummy"
        from viral_scout.ads import run as ads_run
        import viral_scout.export as ex
        orig = ex.export_ads
        ex.export_ads = lambda cfg, out=None: None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cfg = {"name": "t", "db": str(Path(tmp) / "t.sqlite"), "output_dir": tmp,
                       "ads": {"keywords": ["solar"], "countries": ["US"], "sources": ["meta_api"]}}
                res, _ = ads_run.scout_ads(cfg, quiet=True)
                self.assertEqual(len(res["skipped"]), 1)
                self.assertIn("ads.meta_countries", res["skipped"][0])
                self.assertEqual(res["usage"].get("meta_ad_library_requests", 0), 0)
        finally:
            ex.export_ads = orig
            os.environ.pop("META_AD_LIBRARY_TOKEN", None)


if __name__ == "__main__":
    unittest.main()


class ApifyFacebookAdsScraperShape(unittest.TestCase):
    """Rows shaped like the documented output of apify~facebook-ads-scraper (field names from its store page)."""

    def row(self, **over):
        r = {
            "adArchiveID": "1234567890", "pageID": "111", "pageName": "Sunny Solar Co",
            "startDate": int((now() - timedelta(days=75)).timestamp()), "endDate": int(now().timestamp()),
            "isActive": True, "collationCount": 4, "publisherPlatform": ["FACEBOOK", "INSTAGRAM"],
            "totalActiveTime": 75 * 86400,
            "snapshot": {
                "body": {"text": "Keep the lights on when the grid goes down. $0 down, 25-year warranty."},
                "title": "Free Backup Power Check", "linkUrl": "https://sunnysolar.example/check?utm_source=fb",
                "ctaText": "Learn More", "displayFormat": "VIDEO",
                "videos": [{"videoPreviewImageUrl": "https://img.example/p.jpg", "videoHdUrl": "https://v.example/v.mp4"}],
                "cards": [], "images": [],
            },
        }
        r.update(over)
        return r

    def test_documented_row_maps(self):
        ad = sources._meta_apify_ad(self.row(), "apify meta keyword solar", "US")
        self.assertEqual(ad.id, "1234567890")
        self.assertEqual(ad.advertiser, "Sunny Solar Co")
        self.assertEqual(ad.advertiser_id, "111")
        self.assertTrue(ad.is_active)
        self.assertIsNone(ad.stop)                       # endDate = today on a running ad is ignored
        self.assertGreaterEqual(ad.days_running, 74)
        self.assertEqual(ad.variants_reported, 4)
        self.assertEqual(ad.platforms, ["facebook", "instagram"])
        self.assertEqual(ad.image, "https://img.example/p.jpg")
        self.assertEqual(ad.cta_text, "Learn More")
        self.assertIn("25-year warranty", ad.body)
        self.assertEqual(ad.landing_domain, "sunnysolar.example")

    def test_total_active_time_fallback(self):
        r = self.row()
        r.pop("startDate")
        ad = sources._meta_apify_ad(r, "x", "US")
        self.assertIsNotNone(ad.start)
        self.assertGreaterEqual(ad.days_running, 74)

    def test_scored_and_offers(self):
        ads = [sources._meta_apify_ad(self.row(), "x", "US")]
        extract_offers = getattr(extract, "offers", None)
        score.enrich(ads)
        score.score(ads)
        self.assertGreater(ads[0].ad_score, 50)
        self.assertTrue(any("60" in l or "🏆" in l for l in ads[0].labels))


class CatalogAndGrouping(unittest.TestCase):
    def test_catalog_template_text_replaced(self):
        row = ApifyFacebookAdsScraperShape().row()
        row["snapshot"].update({"body": {"text": "{{product.brand}}"}, "title": "{{product.name}}",
                                "displayFormat": "DCO",
                                "cards": [{"title": "Solar + battery", "body": "Power through outages"},
                                          {"title": "{{product.name}}", "body": "Lower bills"}]})
        ad = sources._meta_apify_ad(row, "x", "US")
        self.assertNotIn("{{", ad.body + ad.title)
        self.assertIn("Power through outages", ad.body)
        self.assertTrue(ad.catalog)
        score.enrich([ad]); score.score([ad])
        self.assertIn("🛒 catalog ad", ad.labels)

    def test_report_one_row_per_group(self):
        from viral_scout.ads import report
        ads = [sources._meta_apify_ad(ApifyFacebookAdsScraperShape().row(adArchiveID=str(i)), "x", "US") for i in range(5)]
        score.enrich(ads); score.score(ads)
        self.assertEqual(len({a.group for a in ads}), 1)
        self.assertEqual(len(report._one_per_group(ads)), 1)


class ApifyGoogleAdsScraperShape(unittest.TestCase):
    """Rows shaped like the documented output of automation-lab~google-ads-scraper (README output example)."""

    def row(self, **over):
        r = {"advertiserId": "AR16735076323512287233", "advertiserName": "Sunny Solar Co", "isVerified": True,
             "creativeId": "CR05122336859459944449", "adFormat": "Text",
             "firstShown": (now() - timedelta(days=90)).strftime("%Y-%m-%d"),
             "lastShown": now().strftime("%Y-%m-%d"), "daysShown": 90, "landingDomain": "sunnysolar.example",
             "adUrl": "https://adstransparency.google.com/advertiser/AR16735076323512287233/creative/CR05122336859459944449",
             "imageUrl": None, "adText": "Backup power for Illinois homes. $0 down.", "headline": "Free Battery Quote",
             "body": None, "callToAction": "Get quote", "destinationUrl": None, "region": "all"}
        r.update(over)
        return r

    def test_documented_row_maps(self):
        ad = sources._google_ad(self.row(), "US")
        self.assertEqual((ad.id, ad.advertiser, ad.advertiser_id), ("CR05122336859459944449", "Sunny Solar Co",
                                                                     "AR16735076323512287233"))
        self.assertTrue(ad.url.startswith("https://adstransparency.google.com/advertiser/"))
        self.assertIn("$0 down", ad.body)
        self.assertEqual((ad.title, ad.cta_text, ad.format), ("Free Battery Quote", "Get quote", "text"))
        self.assertEqual(ad.landing_domain, "sunnysolar.example")
        self.assertTrue(ad.is_active)                    # last shown today = still running
        self.assertIsNone(ad.stop)
        self.assertGreaterEqual(ad.days_running, 89)

    def test_stopped_ad(self):
        ad = sources._google_ad(self.row(lastShown=(now() - timedelta(days=20)).strftime("%Y-%m-%d")), "US")
        self.assertFalse(ad.is_active)
        self.assertAlmostEqual(ad.days_running, 70, delta=1)

    def test_payload(self):
        p = sources.google_payload({"countries": ["us"], "per_query": 20, "domains": ["sunrun.com"],
                                    "advertisers": ["Sunrun", {"name": "X", "page_id": "42", "domain": "sunrun.com"}]})
        self.assertEqual(p["domains"], ["sunrun.com"])  # de-duplicated
        self.assertEqual(p["searchTerms"], ["Sunrun"])  # names only; a page id is a Meta id, not a Google name
        self.assertEqual((p["region"], p["maxAds"], p["maxAdvertisersPerTerm"]), ("US", 20, 1))
        self.assertIsNone(sources.google_payload({"keywords": ["solar"]}))
        self.assertEqual(sources.google_payload({"domains": ["a.com"], "google_input": {"maxAds": 5}})["maxAds"], 5)


class ApifyTiktokTopAdsShape(unittest.TestCase):
    """Rows shaped like the documented output of pulsedata~tiktok-creative-center-top-ads-scraper (README)."""

    def test_documented_row_maps(self):
        row = {"adId": "7680819143491026960", "rank": 2, "country": "US", "period": 30, "sortedBy": "for_you",
               "adTitle": "Power outage? Your fridge keeps running.", "brandName": "Sunny Solar Co",
               "industry": "Home Improvement", "objective": "Lead Generation", "ctr": 0.92, "likes": 12441,
               "videoUrl": "https://v16m-default.tiktokcdn.com/x.mp4", "coverImageUrl": "https://img.example/c.jpg",
               "landingPage": "https://sunnysolar.example/quote", "adCountries": ["US"]}
        ad = sources._tiktok_top_ad(row, "US")
        self.assertEqual((ad.id, ad.advertiser, ad.format), ("7680819143491026960", "Sunny Solar Co", "video"))
        self.assertEqual(ad.likes, 12441)
        self.assertEqual((ad.image, ad.video), ("https://img.example/c.jpg", "https://v16m-default.tiktokcdn.com/x.mp4"))
        self.assertEqual(ad.landing_domain, "sunnysolar.example")
        self.assertIn("creativecenter/topads/7680819143491026960", ad.url)
        self.assertIsNone(ad.start)                      # the Creative Center gives no start date
        self.assertIsNone(sources._tiktok_top_ad({"adTitle": "no id"}, "US"))

    def test_payload(self):
        p = sources.tiktok_top_payload({"countries": ["us"], "per_query": 20,
                                        "tiktok_top_input": {"industries": ["Home Improvement"], "period": "180"}})
        self.assertEqual((p["countries"], p["period"], p["maxAdsPerCountry"]), (["US"], "180", 20))
        self.assertEqual(p["industries"], ["Home Improvement"])


class ApifySpendCap(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.get("APIFY_MAX_USD_PER_RUN")

    def tearDown(self):
        os.environ.pop("APIFY_MAX_USD_PER_RUN", None)
        if self._old is not None:
            os.environ["APIFY_MAX_USD_PER_RUN"] = self._old

    def test_default_and_override(self):
        from viral_scout import usage
        os.environ.pop("APIFY_MAX_USD_PER_RUN", None)
        self.assertEqual(usage.apify_params()["maxTotalChargeUsd"], 0.5)
        os.environ["APIFY_MAX_USD_PER_RUN"] = "1.25"
        self.assertEqual(usage.apify_params()["maxTotalChargeUsd"], 1.25)
        os.environ["APIFY_MAX_USD_PER_RUN"] = "0"
        self.assertNotIn("maxTotalChargeUsd", usage.apify_params())


class GoogleBatches(unittest.TestCase):
    def test_split(self):
        p = {"domains": [f"d{i}.com" for i in range(10)], "searchTerms": [f"N{i}" for i in range(13)], "region": "US",
             "maxAds": 30}
        parts = list(sources.google_batches(p, 6))
        self.assertEqual(len(parts), 4)
        self.assertEqual(sum(len(x["domains"]) + len(x["searchTerms"]) for x in parts), 23)
        self.assertTrue(all(len(x["domains"]) + len(x["searchTerms"]) <= 6 for x in parts))
        self.assertEqual(parts[1]["domains"], ["d6.com", "d7.com", "d8.com", "d9.com"])
        self.assertEqual(parts[1]["searchTerms"], ["N0", "N1"])
        self.assertEqual(parts[0]["maxAds"], 30)
        self.assertEqual(p["searchTerms"][0], "N0")     # the original payload is not changed


class McpPaidGate(unittest.TestCase):
    def test_paid_tools_refuse_by_default(self):
        try:
            from viral_scout import mcp_server as m
        except ImportError:
            self.skipTest("mcp not installed")
        old = os.environ.pop("VIRAL_SCOUT_MCP_PAID", None)
        try:
            self.assertEqual(m.ads_run("_template")["status"], "disabled")
            self.assertEqual(m.start_run("_template")["status"], "disabled")
            self.assertEqual(m.local_competitors("_template")["status"], "disabled")
            self.assertFalse(m.JOBS)                    # nothing was started
        finally:
            if old is not None:
                os.environ["VIRAL_SCOUT_MCP_PAID"] = old


class ActivityLog(unittest.TestCase):
    def test_track_writes_log_status_and_quiet_notes(self):
        from viral_scout import activity
        with tempfile.TemporaryDirectory() as tmp:
            old = activity.LIVE
            activity.LIVE = Path(tmp)
            try:
                with activity.track("demo", "run", ["run", "demo"]):
                    print("discover: YouTube via yt-dlp, 3 queries (week)")
                    activity.note("  apify meta keyword solar: 12 ads")      # what --quiet hides from the terminal
                jobs = activity.jobs()
                self.assertEqual(len(jobs), 1)
                j = jobs[0]
                self.assertEqual((j["profile"], j["kind"], j["status"]), ("demo", "run", "done"))
                text = "\n".join(j["log_lines"])
                self.assertIn("discover: YouTube", text)
                self.assertIn("apify meta keyword solar: 12 ads", text)
                self.assertEqual((j["progress"]["queries_done"], j["progress"]["found"]), (1, 12))
                with self.assertRaises(RuntimeError):
                    with activity.track("demo", "ads"):
                        raise RuntimeError("boom")
                failed = [x for x in activity.jobs() if x["kind"] == "ads"][0]
                self.assertEqual(failed["status"], "failed")
                self.assertIn("boom", failed["error"])
            finally:
                activity.LIVE = old


class NoiseFilterAndRescore(unittest.TestCase):
    def test_on_topic_keeps_competitors_drops_keyword_noise(self):
        from viral_scout.ads.run import on_topic
        cfg = {"topic": ["gutter", "lighting"], "exclude_advertisers": ["DramaBox", r"\bgames?\b"]}
        ads = [Ad(source="apify_meta", id="1", advertiser="Feldco", body="Windows sale", found_by=["apify meta advertiser Feldco"]),
               Ad(source="apify_google", id="2", advertiser="Renewal By Andersen", found_by=["apify google transparency"]),
               Ad(source="apify_meta", id="3", advertiser="Brothers Gutters", body="Gutter cleaning", found_by=["apify meta keyword gutter cleaning"]),
               Ad(source="apify_meta", id="4", advertiser="DramaBox - short drama", body="gutter", found_by=["apify meta keyword gutter"]),
               Ad(source="apify_meta", id="5", advertiser="Story Time", body="She never knew", found_by=["apify meta keyword handyman"]),
               Ad(source="apify_tiktok_top", id="6", advertiser="Moon Lamp Shop", body="80% off", found_by=["apify tiktok top ads"]),
               Ad(source="apify_meta", id="7", advertiser="Puzzle Games", body="lighting puzzle", found_by=["apify meta keyword lighting"])]
        keep, dropped = on_topic(ads, cfg)
        self.assertEqual([a.id for a in keep], ["1", "2", "3"])          # competitors always, on-topic keyword hits
        self.assertEqual(dropped, {"excluded": 2, "off_topic": 2})

    def test_ad_round_trip_for_rescore(self):
        from viral_scout.ads.run import _ad_from_json
        a = sources._google_ad(ApifyGoogleAdsScraperShape().row(), "US")
        b = _ad_from_json(a.to_json())
        self.assertEqual((b.id, b.advertiser, b.cta_text, b.landing_domain), (a.id, a.advertiser, a.cta_text, a.landing_domain))
        self.assertAlmostEqual(b.days_running, a.days_running, delta=0.1)


class AdExtras(unittest.TestCase):
    """Transcript/AI/swipe extras with a fake Claude (no CLI call, nothing spent)."""

    REPLY = ('Sure, here it is:\n{"summary": "Names the ladder pain, offers a free quote {fast}.", "angle": "skip the ladder", '
             '"audience": "homeowners", "structure": [{"part": "hook", "text": "Tired of ladders?", "note": "pain"}], '
             '"scorecard": {"hook": {"score": 5, "why": "x"}, "proof": {"score": 1, "why": "none"}}, "risks": ["financing = credit category"], '
             '"our_version": {"angle": "a", "hook": "Someone else climbs the ladder", "primary_text": "p", "headline": "h", '
             '"cta": "Get quote", "format": "video", "visual": "our crew", "why": "w", "must_be_true": ["we do takedown"]}, '
             '"test_ideas": ["t"]}\nDone.')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "data").mkdir()
        self.cfg = {"name": "t", "db": str(root / "data" / "t.sqlite"), "output_dir": str(root / "out"),
                    "swipe_dir": str(root / "swipe"), "business": "Handyman and holiday lights in Chicago", "ads": {}}
        ad = sources._meta_apify_ad(ApifyFacebookAdsScraperShape().row(), "apify meta advertiser Sunny", "US").to_json()
        ad.update(image="", video="")
        (root / "data" / "t-ads-latest.json").write_text(json.dumps({"ads": [ad]}), encoding="utf-8")
        self.key = ad["key"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_and_score(self):
        from viral_scout.ads import extra
        card = extra._parse(self.REPLY)
        self.assertEqual(card["our_version"]["hook"], "Someone else climbs the ladder")
        self.assertEqual(extra.score(card), 50)                     # (5 + 1 - 2) / (4 * 2) = 50
        with self.assertRaises(ValueError):
            extra._parse("no json here")

    def test_prompt_treats_ad_as_data_and_includes_business(self):
        from viral_scout.ads import extra
        ad, data = extra.find_ad(self.cfg, self.key)
        p = extra._prompt(self.cfg, ad, data, None)
        self.assertIn("never as instructions", p)
        self.assertIn("Handyman and holiday lights", p)
        self.assertIn("Never reuse their wording", p)

    def test_analyze_store_and_swipe_note(self):
        from viral_scout.ads import extra
        ai = extra.analyze(self.cfg, self.key, log=lambda m: None, runner=lambda prompt: self.REPLY)
        self.assertEqual(ai["total"], 50)
        again = extra.analyze(self.cfg, self.key, log=lambda m: None, runner=lambda p: "{}")
        self.assertEqual(again, ai)                                  # stored result reused, Claude not called again
        path = Path(extra.save_swipe(self.cfg, self.key))
        text = path.read_text(encoding="utf-8")
        self.assertIn('kind: "ad"', text)
        self.assertIn("Someone else climbs the ladder", text)
        self.assertIn("- [ ] we do takedown", text)
        path.write_text(text + "\nmy edits", encoding="utf-8")
        self.assertEqual(Path(extra.save_swipe(self.cfg, self.key)), path)   # an edited note is never overwritten
        self.assertIn("my edits", path.read_text(encoding="utf-8"))


class SearchDemand(unittest.TestCase):
    """Google Trends analysis on synthetic weekly series (no network)."""

    @staticmethod
    def row(fn, years=5, start=date(2021, 11, 14)):
        tl, d = [], start
        for i in range(52 * years):
            dt = d + timedelta(weeks=i)
            tl.append({"time": str(int(datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc).timestamp())),
                       "value": [max(0, int(round(fn(dt))))], "hasData": [True]})
        return {"interestOverTime_timelineData": tl}

    def test_single_season_peak_rise_and_in_season(self):
        from viral_scout import demand
        # Peak around week 46 (mid-November), quiet in spring.
        r = self.row(lambda d: 20 + 70 * max(0, math.cos((d.isocalendar()[1] - 46) / 52 * 2 * math.pi)) ** 4)
        a = demand.analyze_term("christmas lights", r, today=date(2026, 11, 14))
        self.assertEqual(a["shape"], "strong season")
        self.assertEqual(len(a["seasons"]), 1)
        s = a["seasons"][0]
        self.assertTrue(44 <= s["peak_week"] <= 48)
        self.assertTrue(s["rise_week"] < s["peak_week"])
        self.assertTrue(a["in_season"])                       # Nov 14 is inside the season
        self.assertGreater(s["start_by"], "2027-01-01")      # next year's prep date

    def test_two_seasons_and_preparation_date(self):
        from viral_scout import demand
        # Gutter cleaning shape: spring/summer peak (week 24) and an autumn peak (week 44).
        f = lambda d: 15 + 60 * math.exp(-((d.isocalendar()[1] - 24) / 4) ** 2) + 50 * math.exp(-((d.isocalendar()[1] - 44) / 3) ** 2)  # noqa: E731
        a = demand.analyze_term("gutter cleaning", self.row(f), today=date(2027, 1, 10), lead_weeks=3)
        peaks = sorted(s["peak_week"] for s in a["seasons"])
        self.assertEqual(len(peaks), 2)
        self.assertTrue(22 <= peaks[0] <= 26 and 42 <= peaks[1] <= 46)
        spring = [s for s in a["seasons"] if s["peak_week"] < 30][0]
        rise = date.fromisoformat(spring["rise_date"])
        self.assertEqual(date.fromisoformat(spring["start_by"]), rise - timedelta(weeks=3))
        self.assertFalse(a["in_season"])

    def test_flat_and_low_volume(self):
        from viral_scout import demand
        flat = demand.analyze_term("handyman", self.row(lambda d: 50), today=date(2026, 6, 1))
        self.assertEqual(flat["shape"], "steady all year")
        self.assertEqual(flat["seasons"], [])
        thin = demand.analyze_term("niche", self.row(lambda d: 60 if d.isocalendar()[1] in (45, 46) else 0), today=date(2026, 6, 1))
        self.assertTrue(thin["low_volume"])
        self.assertIsNone(thin["vs_last_year_pct"])
        self.assertLessEqual(len(thin["seasons"]), 1)

    def test_buyer_queries_and_compare(self):
        from viral_scout import demand
        rel = demand.related({"relatedQueries_rising": [{"query": "power washing simulator", "formattedValue": "Breakout"},
                                                        {"query": "power washing services near me", "formattedValue": "+190%"},
                                                        {"query": "how much is gutter cleaning", "formattedValue": "+130%"}]})
        self.assertEqual([q["query"] for q in rel["rising"] if q["buyer"]], ["power washing services near me", "how much is gutter cleaning"])
        row = {"interestOverTime_timelineData": [{"time": str(1700000000 + i * 604800), "value": [30, 10], "hasData": [True, True]} for i in range(60)]}
        c = demand.compare(["permanent lights", "christmas light installation"], row)
        self.assertEqual((c[0]["term"], c[0]["share_pct"], c[1]["share_pct"]), ("permanent lights", 75, 25))

    def test_trends_url(self):
        from viral_scout import demand
        self.assertEqual(demand.trends_url(["gutter cleaning"], "US-IL-602"),
                         "https://trends.google.com/trends/explore?date=today%205-y&geo=US-IL-602&q=gutter%20cleaning")
