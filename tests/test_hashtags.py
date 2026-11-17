import unittest

from viral_scout import hashtags


class HashtagsTest(unittest.TestCase):
    def test_business_tag_like_the_service(self):
        # Same results as service/src/lib/ui.ts businessTag for the same names.
        self.assertEqual(hashtags.business({"name": "x", "studio": {"brand": "Bright Solar"}}), "#BrightSolar")
        self.assertEqual(hashtags.business({"name": "x", "display_name": "Acme Agency"}), "#AcmeAgency")
        self.assertEqual(hashtags.business({"name": "x", "studio": {"brand": "DIS IT"}}), "#DISIT")
        self.assertEqual(hashtags.business({"name": "homes", "studio": {}}), "#homes")
        self.assertEqual(hashtags.business({"name": "x", "studio": {"brand": "A B", "hashtag": "Mine"}}), "#Mine")

    def test_line_dedupes_and_drops_tags_without_a_letter(self):
        cfg = {"name": "x", "studio": {"brand": "Bright Solar"}}
        self.assertEqual(hashtags.line(cfg, "post", "post", platforms=["tiktok", "instagram_story", "tiktok"]),
                         "#BrightSolar #post #tiktok #instagram_story")
        self.assertEqual(hashtags.hashtag("2026"), "")
        self.assertEqual(hashtags.hashtag("YouTube Shorts"), "#YouTubeShorts")


if __name__ == "__main__":
    unittest.main()
