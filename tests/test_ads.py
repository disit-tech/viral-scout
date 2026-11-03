"""Ads scout checks that need no keys or network: parsing, offer/CTA extraction, variants, scoring, report.

  python -m unittest discover -s tests -v
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import timedelta
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
