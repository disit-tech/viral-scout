import tempfile
import unittest
from pathlib import Path
from unittest import mock

from viral_scout import setup_check
from viral_scout.keys import KEYS

BLANK = {k["name"]: "" for k in KEYS} | {"IDEAS_SITE_URL": "", "VIRAL_SCOUT_YTDLP": ""}


def cfg(**over):
    tmp = Path(tempfile.mkdtemp())
    c = {"name": "demo", "db": str(tmp / "demo.sqlite"), "business": "", "discover": {"youtube": {}, "tiktok": {}},
         "watch": {}, "own": {}}
    c.update(over)
    return c


class FreshInstallTest(unittest.TestCase):
    def sections(self, c, env=BLANK):
        with mock.patch.dict("os.environ", env):
            return {s["id"]: s for s in setup_check.sections(c)}

    def open_ids(self, sec):
        return [i["id"] for i in sec["items"] if not i["done"] and not i["optional"]]

    def test_nothing_set_up_lists_what_each_feature_needs_with_a_fix(self):
        s = self.sections(cfg())
        self.assertEqual(self.open_ids(s["business"]), ["business"])
        self.assertEqual(self.open_ids(s["videos"]), ["search", "run"])            # no keywords yet: the key is optional
        self.assertEqual(self.open_ids(s["demand"]), ["terms", "geo", "apify", "run"])
        self.assertEqual(self.open_ids(s["ideas"]), ["block", "service", "secret"] + ([] if setup_check._claude() else ["claude"]))
        for sec in s.values():                                                     # every open item says where to fix it
            for i in sec["items"]:
                if not i["done"] and i["id"] != "bots":
                    self.assertIsNotNone(i["fix"], (sec["id"], i["id"]))
        self.assertEqual(s["business"]["items"][0]["fix"], {"kind": "field", "path": "business"})
        self.assertEqual(s["demand"]["items"][2]["fix"], {"kind": "key", "name": "APIFY_TOKEN", "use": "demand"})

    def test_what_you_search_decides_which_keys_are_required(self):
        s = self.sections(cfg(discover={"youtube": {"keywords": ["gutters"]}, "tiktok": {"hashtags": ["diy"]}},
                              watch={"instagram": ["@x"]}))
        self.assertEqual(self.open_ids(s["videos"]), ["yt_key", "apify_tt", "ig", "run"])
        s = self.sections(cfg(discover={"youtube": {"keywords": ["gutters"]}, "tiktok": {}}),
                          BLANK | {"YOUTUBE_API_KEY": "k"})
        self.assertEqual(self.open_ids(s["videos"]), ["run"])

    def test_counts_and_optional_features(self):
        s = self.sections(cfg(business="We clean gutters", demand={"terms": ["gutter cleaning"], "geo": "US-IL"}),
                          BLANK | {"APIFY_TOKEN": "t"})
        self.assertEqual((s["business"]["open"], s["demand"]["open"], s["demand"]["total"]), (0, 1, 4))   # only the first run
        self.assertTrue(s["local"]["optional"] and s["paid"]["optional"])


if __name__ == "__main__":
    unittest.main()
