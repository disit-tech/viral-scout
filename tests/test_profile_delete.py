import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from viral_scout import config, profile_delete


class DeleteTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "profiles").mkdir()
        (self.root / "data" / "frames" / "test").mkdir(parents=True)
        (self.root / "web" / "data" / "ads").mkdir(parents=True)
        for n in ("test", "test-2"):
            (self.root / "profiles" / f"{n}.yaml").write_text("name: x\n")
            (self.root / "data" / f"{n}.sqlite").write_text("db")
            (self.root / "data" / f"{n}-latest.json").write_text("{}")
            (self.root / "web" / "data" / f"{n}.json").write_text("{}")
        (self.root / "data" / "frames" / "test" / "a.jpg").write_text("jpg")
        (self.root / "web" / "data" / "ads" / "test.json").write_text("{}")
        for target, value in ((config, "ROOT"), (config, "PROFILES")):
            p = mock.patch.object(target, value, self.root if value == "ROOT" else self.root / "profiles")
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch("viral_scout.export.export_all")
        p.start()
        self.addCleanup(p.stop)

    def run_delete(self, confirm="test"):
        with mock.patch.object(profile_delete, "_tasks", return_value=["viral-scout test", "viral-scout test.ideas"]), \
                mock.patch.object(profile_delete, "_remove_task", return_value=True) as rm:
            out = profile_delete.delete("test", confirm, web_data=self.root / "web" / "data")
        return out, rm

    def test_moves_only_that_business_and_removes_its_tasks(self):
        out, rm = self.run_delete()
        dest = Path(out["folder"])
        self.assertFalse((self.root / "profiles" / "test.yaml").exists())
        self.assertTrue((dest / "profiles" / "test.yaml").exists())
        self.assertTrue((dest / "data" / "frames" / "test" / "a.jpg").exists())
        self.assertTrue((dest / "web" / "data" / "ads" / "test.json").exists())
        for f in ("profiles/test-2.yaml", "data/test-2.sqlite", "data/test-2-latest.json", "web/data/test-2.json"):
            self.assertTrue((self.root / f).exists(), f)                 # "test-2" is untouched
        self.assertEqual(out["tasks_removed"], ["viral-scout test", "viral-scout test.ideas"])
        self.assertIn("To restore", (dest / "DELETED.md").read_text(encoding="utf-8"))

    def test_needs_the_exact_name(self):
        with self.assertRaises(ValueError):
            self.run_delete(confirm="Test")
        self.assertTrue((self.root / "profiles" / "test.yaml").exists())


if __name__ == "__main__":
    unittest.main()
