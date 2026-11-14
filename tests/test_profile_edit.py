"""Profile editor: in-place edits keep comments, line endings and untouched values.

  python -m unittest tests.test_profile_edit -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from viral_scout import config, profile_edit as pe  # noqa: E402

SAMPLE = """# top comment
name: demo
output_dir: ${OBSIDIAN_VAULT}/projects/demo

business: >
  Old description
  on two lines.

discover:
  youtube:
    window: month
    keywords:
      - one
      - two
  tiktok:
    hashtags: [a, b]

filters:
  min_views: 5000
  exclude:
    - minecraft|roblox
    - '\\blive:|24/7'

local: {query: "gutter cleaning", near: "Norridge, IL", limit: 15}

demand:
  geo: US-IL-602        # Chicago DMA
ads:
  # competitors, widened 2026-11-12
  advertisers:
    - {name: Brothers, match: "Brothers that just do Gutters"}   # one page per city
    - Feldco
  days: 180
"""


class ProfileEditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "profiles").mkdir()
        self.old = config.PROFILES, config.ROOT
        config.PROFILES, config.ROOT = root / "profiles", root
        self.path = root / "profiles" / "demo.yaml"

    def tearDown(self):
        config.PROFILES, config.ROOT = self.old
        self.tmp.cleanup()

    def write(self, text, crlf=False):
        self.path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))

    def test_edits_keep_comments_and_other_values(self):
        self.write(SAMPLE)
        base = pe.get("demo")["base"]
        out = pe.set_fields("demo", {
            "display_name": "Demo Co",
            "business": "New description.",
            "discover.youtube.keywords": ["two", "three"],
            "discover.tiktok.hashtags": ["a", "c"],
            "local.limit": 20,
            "demand.geo": "US-IL",
            "ads.advertisers": [{"name": "Brothers", "match": "Brothers that just do Gutters"}, "New Co"],
            "own.youtube": ["@demo"],
        }, base)
        self.assertEqual(len(out["changed"]), 8)
        text = self.path.read_text(encoding="utf-8")
        for kept in ["# top comment", "# competitors, widened 2026-11-12", "# one page per city", "# Chicago DMA",
                     "'\\blive:|24/7'", "${OBSIDIAN_VAULT}/projects/demo"]:
            self.assertIn(kept, text)
        d = yaml.safe_load(text)
        self.assertEqual(d["display_name"], "Demo Co")
        self.assertEqual(d["business"], "New description.")
        self.assertEqual(d["discover"]["youtube"]["keywords"], ["two", "three"])
        self.assertEqual(d["local"], {"query": "gutter cleaning", "near": "Norridge, IL", "limit": 20})
        self.assertEqual(d["own"], {"youtube": ["@demo"]})
        self.assertEqual(d["ads"]["days"], 180)
        self.assertEqual(d["filters"]["exclude"], ["minecraft|roblox", "\\blive:|24/7"])
        self.assertTrue((config.ROOT / "data" / "profile-backups").exists())

    def test_crlf_kept_and_noop(self):
        self.write(SAMPLE, crlf=True)
        pe.set_fields("demo", {"ads.days": 90})
        raw = self.path.read_bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))
        self.assertEqual(pe.set_fields("demo", {"ads.days": 90})["changed"], [])

    def test_rejects_bad_input_without_writing(self):
        self.write(SAMPLE)
        before = self.path.read_bytes()
        for patch in ({"filters.must_match": "(bad"}, {"demand.geo": "chicago"}, {"ads.days": "many"},
                      {"report.top": 5}):
            with self.assertRaises(ValueError):
                pe.set_fields("demo", patch)
        with self.assertRaises(ValueError):
            pe.set_fields("demo", {"ads.days": 1}, base="stale")
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
