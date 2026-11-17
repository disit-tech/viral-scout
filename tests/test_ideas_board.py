import unittest
from unittest import mock

from viral_scout.ideas import board
from viral_scout.ideas.settings import IdeasError


class FakeClient:
    def __init__(self, project, has_board=False, ideas=None):
        self.project, self.has_board, self.ideas, self.calls = project, has_board, ideas or [], []

    def call(self, method, body=None, path="/api/ideas"):
        self.calls.append((method, path, body))
        if path.startswith("/api/board") and not self.has_board:
            raise IdeasError('404 {"error":"Not Found"}')
        if method == "GET" and path == "/api/board":
            return {"projects": [{"slug": "solar", "label": "Solar"}], "ideas": [{"id": 1, "project": "solar"}], "final": []}
        return {"ok": True, "changed": len((body or {}).get("ids") or [1])}

    def pull(self):
        return {"ideas": self.ideas}


PROFS = [("nfSolar", "Bright Solar", {"project": "solar"}), ("homes", "Homeworks", {"project": "homes"})]


class BoardTest(unittest.TestCase):
    def run_with(self, clients, fn, *a):
        it = iter(clients)
        with mock.patch.object(board, "_profiles", return_value=PROFS), \
                mock.patch.object(board, "_client", side_effect=lambda ic, project=None: next(it)):
            return fn(*a)

    def test_fallback_reads_every_project_and_marks_films(self):
        a = FakeClient("solar")
        s = FakeClient("solar", ideas=[{"id": 3, "project": "solar", "batch": "film-2026-11-18"}, {"id": 2, "project": "solar"}])
        h = FakeClient("homes", ideas=[{"id": 5, "project": "homes"}])
        d = self.run_with([a, s, h], board.get)
        self.assertEqual(d["source"], "ideas")
        self.assertEqual([i["id"] for i in d["ideas"]], [5, 3, 2])                     # newest first
        self.assertEqual({i["id"]: i["kind"] for i in d["ideas"]}, {5: "idea", 3: "film", 2: "idea"})
        self.assertEqual([p["display"] for p in d["projects"]], ["Bright Solar", "Homeworks"])
        self.assertEqual(d["can"], ["rate", "comment", "remove"])

    def test_board_when_deployed(self):
        d = self.run_with([FakeClient("solar", has_board=True)], board.get)
        self.assertEqual((d["source"], d["projects"][0]["profile"]), ("board", "nfSolar"))
        self.assertIn("tag", d["can"])

    def test_fallback_writes_one_idea_at_a_time_and_refuses_what_needs_the_board(self):
        first, second = FakeClient("solar"), FakeClient("solar")
        out = self.run_with([first, second], board.set_, {"ids": [7, 8], "op": "rate", "value": "good", "project": "solar"})
        self.assertEqual(out["changed"], 2)
        self.assertEqual([c[2] for c in second.calls], [{"id": 7, "project": "solar", "rate": "good"},
                                                       {"id": 8, "project": "solar", "rate": "good"}])
        for body in ({"ids": [7], "op": "tag", "value": "hk", "project": "solar"},
                     {"ids": [7], "op": "rate", "value": "variants", "project": "solar"},
                     {"ids": [7], "op": "comment", "value": "", "project": "solar"}):
            c = FakeClient("solar")
            out = self.run_with([c, FakeClient("solar")], board.set_, body)
            self.assertIn("error", out, body)

    def test_board_patch_passes_through(self):
        c = FakeClient("solar", has_board=True)
        out = self.run_with([c], board.set_, {"ids": [7], "op": "note", "value": "re-cut it", "project": "solar"})
        self.assertTrue(out["ok"])
        self.assertEqual(c.calls[0], ("PATCH", "/api/board", {"ids": [7], "op": "note", "value": "re-cut it"}))


if __name__ == "__main__":
    unittest.main()
