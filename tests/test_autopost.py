"""Auto mode: two films a day, auto approval, the autopost job, text/photo posts, comment challenges. No network:
the node publisher and the platform clients are fakes.

  python -m pytest tests/test_autopost.py -q
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["VIRAL_SCOUT_NO_ALERTS"] = "1"   # never message the real bot from a test

import yaml  # noqa: E402

from viral_scout import config  # noqa: E402
from viral_scout.jobs import prompts, runner, schedule  # noqa: E402
from viral_scout.jobs import settings as S  # noqa: E402
from viral_scout.publish import auto, connect, core, replies  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._root, self._vault = config.ROOT, S.vault
        config.ROOT = self.tmp
        S.vault = lambda: str(self.tmp / "vault")
        self.vd = self.tmp / "vault" / "projects" / "demo"
        (self.vd / "05 Marketing" / "Video Studio").mkdir(parents=True)
        (self.vd / "05 Marketing" / "Social" / "posts").mkdir(parents=True)
        self.films = []
        for slug in ("a-film", "b-film"):
            d = self.tmp / "films" / slug / "out"
            d.mkdir(parents=True)
            mp4 = d / f"{slug}.mp4"
            mp4.write_bytes(b"x")
            (d.parent / "caption.md").write_text("challenge: GUIDE\nreward: https://demo.example/guide\nText #a\n## LinkedIn\nLI text\n",
                                                 encoding="utf-8")
            self.films.append(mp4)
        self.queue = self.vd / "05 Marketing" / "Video Studio" / "ready-to-post.md"
        self.queue.write_text("| Date | Title | Video | Script | Status |\n|---|---|---|---|---|\n"
                              f"| 2026-11-18 | A | `{self.films[0]}` | [[s]] | ✅ auto |\n"
                              f"| 2026-11-18 | B | `{self.films[1]}` | [[s]] | waiting for Alex |\n", encoding="utf-8")

    def tearDown(self):
        config.ROOT, S.vault = self._root, self._vault

    def profile(self, publish=None, jobs=None):
        doc = {"name": "demo", "business": "Demo",
               "studio": {"brand": "Demo", "vault_dir": str(self.vd), "cta": {"text": "c", "link": "https://demo.example/c"}},
               "publish": {"handles": {"instagram": "@demo"}, "platforms": ["tiktok", "instagram", "youtube", "linkedin"],
                           "auto_post": {"instagram": True, "youtube": True, "linkedin": True}, "per_day": 2,
                           "times": ["12:00", "18:30"], **(publish or {})},
               "jobs": {"owner": "Alex", **(jobs or {})}}
        p = self.tmp / "demo.yaml"
        p.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
        cfg = config.load(str(p))
        keys = Path(core.settings(cfg)["env_file"])
        keys.parent.mkdir(parents=True, exist_ok=True)
        keys.write_text("INSTAGRAM_ACCESS_TOKEN=t\nINSTAGRAM_USER_ID=1\nYOUTUBE_CLIENT_ID=a\nYOUTUBE_CLIENT_SECRET=b\n"
                        "YOUTUBE_REFRESH_TOKEN=c\nLINKEDIN_ACCESS_TOKEN=l\nLINKEDIN_AUTHOR=urn:li:person:x\n", encoding="utf-8")
        return cfg


class FakeNode:
    """Stands in for node publish.mjs / post.mjs: logs every --only platform as published."""

    def __init__(self, cfg):
        self.calls, self.log = [], config.ROOT / "data" / "publish" / cfg["name"] / "published.jsonl"

    def __call__(self, cmd, cfg, dry):
        self.calls.append(cmd)
        only = cmd[cmd.index("--only") + 1].split(",")
        key = Path(cmd[2]).name if cmd[1].endswith("publish.mjs") else Path(cmd[cmd.index("--caption-file") + 1]).name
        field = "video" if cmd[1].endswith("publish.mjs") else "post"
        self.log.parent.mkdir(parents=True, exist_ok=True)
        with self.log.open("a", encoding="utf-8") as fh:
            for p in only:
                fh.write(json.dumps({"time": "2026-11-18T18:00:00Z", "platform": p, "id": f"{p}-{key}", field: key}) + "\n")
        return 0, "ok"


class QueueTest(Base):
    def test_two_films_per_date_and_times(self):
        cfg = self.profile()
        s = core.settings(cfg)
        rows = core.read_queue(s["queue"])
        self.assertEqual([core.post_time(s, rows, r) for r in rows], ["12:00", "18:30"])
        self.assertNotIn("2026-11-18", core.free_dates(cfg, datetime(2026, 11, 18).date()))
        self.assertTrue(core.approved(rows[0]))
        self.assertFalse(core.approved(rows[1]))
        self.assertFalse(core.approved({"status": "🛑 stopped (was ✅ auto)"}))

    def test_caption_headers(self):
        c = core.parse_caption("photo: p.jpg\nchallenge: guide\nmentions: 2\nreward: https://x\nBody\n## LinkedIn\nLI\n")
        self.assertEqual((c["photo"], c["challenge"], c["mentions"], c["reward"]), ("p.jpg", "GUIDE", 2, "https://x"))
        self.assertEqual((c["linkedin"], c["facebook"]), ("LI", "Body"))


class AutopostTest(Base):
    def test_posts_due_approved_film_once(self):
        cfg = self.profile()
        node = FakeNode(cfg)
        out = auto.run(cfg, now=datetime(2026, 11, 18, 12, 5), run_node=node, replier=lambda c, dry: [])
        self.assertEqual(len(node.calls), 1)                         # A is due and approved; B waits for approval and 18:30
        self.assertIn("instagram,youtube,linkedin", " ".join(node.calls[0]))
        self.assertIn("📤 posted 2026-11-18", self.queue.read_text(encoding="utf-8").split("\n")[2])
        self.assertIn("waiting for approval", auto.run(cfg, now=datetime(2026, 11, 18, 19, 0), run_node=node, replier=lambda c, dry: []))
        self.assertEqual(len(node.calls), 1)                         # A is not posted twice
        lines = (config.ROOT / "data" / "publish" / "demo" / "challenges.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual({json.loads(x)["challenge"] for x in lines}, {"GUIDE"})
        self.assertIn("A", out)

    def test_auto_approval_posts_without_owner(self):
        cfg = self.profile({"approval": "auto"})                    # B still says "waiting for Alex": auto mode posts it
        node = FakeNode(cfg)
        out = auto.run(cfg, now=datetime(2026, 11, 18, 18, 31), run_node=node, replier=lambda c, dry: [])
        self.assertEqual(len(node.calls), 1)                         # one film per run: no burst after the PC was off
        self.assertIn("next run (max_per_run 1)", out)
        auto.run(cfg, now=datetime(2026, 11, 18, 19, 1), run_node=node, replier=lambda c, dry: [])
        self.assertEqual(len(node.calls), 2)                         # the next tick posts the other one
        auto.run(cfg, now=datetime(2026, 11, 18, 19, 31), run_node=node, replier=lambda c, dry: [])
        self.assertEqual(len(node.calls), 2)

    def test_max_per_run_setting(self):
        cfg = self.profile({"approval": "auto", "max_per_run": 2})
        node = FakeNode(cfg)
        auto.run(cfg, now=datetime(2026, 11, 18, 18, 31), run_node=node, replier=lambda c, dry: [])
        self.assertEqual(len(node.calls), 2)

    def test_stopped_and_future_rows_wait(self):
        cfg = self.profile()
        self.queue.write_text(self.queue.read_text(encoding="utf-8").replace("✅ auto", "🛑 stopped by Alex"), encoding="utf-8")
        node = FakeNode(cfg)
        auto.run(cfg, now=datetime(2026, 11, 18, 20, 0), run_node=node, replier=lambda c, dry: [])
        auto.run(cfg, now=datetime(2026, 11, 17, 20, 0), run_node=node, replier=lambda c, dry: [])
        self.assertEqual(node.calls, [])

    def test_text_posts(self):
        cfg = self.profile({"auto_post": {"linkedin": True, "facebook": True},
                            "posts": {"enabled": True, "times": ["10:00"], "platforms": ["linkedin", "facebook", "instagram"]}})
        post = self.vd / "05 Marketing" / "Social" / "posts" / "2026-11-18-1-tip.md"
        post.write_text("photo: tip.jpg\n## LinkedIn\nLI\n## Facebook\nFB\n", encoding="utf-8")
        (post.parent / "tip.jpg").write_bytes(b"j")
        q = Path(core.settings(cfg)["posts_queue"])
        q.write_text(f"| date | title | post | status |\n|---|---|---|---|\n| 2026-11-18 | Tip | `{post}` | ✅ auto |\n", encoding="utf-8")
        node = FakeNode(cfg)
        auto.posts(cfg, datetime(2026, 11, 18, 10, 1), run_node=node)
        cmd = node.calls[0]
        self.assertEqual(cmd[cmd.index("--only") + 1], "linkedin,facebook")     # instagram: no API for local photos
        self.assertEqual(cmd[cmd.index("--photo") + 1], str(post.parent / "tip.jpg"))
        self.assertIn("📤 posted", q.read_text(encoding="utf-8"))

    def test_schedule_adds_autopost_task(self):
        names = [t["name"] for t in schedule.plan(self.profile())]
        self.assertIn("viral-scout demo.autopost", names)


class FilmJobTest(Base):
    def test_two_films_a_day_markers(self):
        cfg = self.profile(jobs={"film": {"enabled": True}})
        now = datetime(2026, 11, 18, 6, 0)
        seen = []

        def execute(cmd, prompt, log, cwd):
            seen.append(prompt)
            done = [l for l in prompt.split("`") if l.endswith(".done")][0]
            Path(done).write_text("x", encoding="utf-8")            # Claude's last step
            return 0
        for _ in range(3):
            runner.run(cfg, "film", now=now, execute=execute, which=lambda _: "claude", wait_minutes=0)
        self.assertEqual(len(seen), 2)
        self.assertIn("film-2026-11-18-2.done", seen[1])
        self.assertIn("✅ auto", prompts.assemble(self.profile({"approval": "auto"}, {"film": {"enabled": True}}), "film"))
        self.assertIn("waiting for Alex", prompts.assemble(cfg, "film"))

    def test_posts_job_assembles_and_never_posts(self):
        cfg = self.profile(jobs={"posts": {"enabled": True}})
        self.assertIn("Tag 2 friends", prompts.assemble(cfg, "posts"))
        self.assertFalse([t for t in prompts.allowed_tools(cfg, "posts") if "publish" in t and "plan" not in t])


class ChallengeTest(Base):
    def test_qualifies(self):
        self.assertTrue(replies.qualifies("guide please", "GUIDE"))
        self.assertFalse(replies.qualifies("guidelines", "GUIDE"))
        self.assertTrue(replies.qualifies("@a @b nice", mentions=2))
        self.assertFalse(replies.qualifies("@a @a", mentions=2))

    def test_replies_once(self):
        cfg = self.profile({"challenges": {"enabled": True}})
        f = config.ROOT / "data" / "publish" / "demo" / "challenges.jsonl"
        f.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        f.write_text(json.dumps({"time": now, "platform": "instagram", "id": "m1", "challenge": "GUIDE", "reward": "https://demo.example/g"}) + "\n",
                     encoding="utf-8")

        class Fake:
            sent = []

            def comments(self, mid):
                return [{"id": "c1", "text": "GUIDE", "author": "joe"}, {"id": "c2", "text": "nice", "author": "ann"},
                        {"id": "c3", "text": "guide", "author": "demo"}]

            def reply(self, cid, text, dm=False):
                self.sent.append((cid, text))
                return "reply"
        fake = Fake()
        replies.run(cfg, clients={"instagram": fake})
        replies.run(cfg, clients={"instagram": fake})
        self.assertEqual([c for c, _ in fake.sent], ["c1"])          # own account and non-matching skipped, once only
        self.assertIn("utm_source=instagram", fake.sent[0][1])


class ConnectTest(Base):
    def test_set_env_keeps_other_lines_and_expiry_warns(self):
        cfg = self.profile()
        path = connect.env_path(cfg)
        connect.set_env(path, {"LINKEDIN_TOKEN_EXPIRES": "2026-11-20", "INSTAGRAM_USER_ID": "2"})
        text = path.read_text(encoding="utf-8")
        self.assertIn("INSTAGRAM_USER_ID=2", text)
        self.assertEqual(text.count("INSTAGRAM_USER_ID"), 1)
        self.assertIn("YOUTUBE_CLIENT_ID=a", text)
        self.assertTrue(connect.expiring(cfg, datetime(2026, 11, 18).date()))


if __name__ == "__main__":
    unittest.main()


class DashboardTest(Base):
    def test_status_and_row_buttons(self):
        from viral_scout.publish import status
        cfg = self.profile({"approval": "auto"})
        d = status.build(cfg, now=datetime(2026, 11, 18, 12, 5))
        self.assertEqual([(f["time"], f["state"]) for f in d["films"]], [("12:00", "due now"), ("18:30", "scheduled")])
        self.assertTrue(d["keys"]["instagram"]["connected"])
        self.assertFalse(d["keys"]["facebook"]["connected"])
        self.assertNotIn("urn:li:person:x", json.dumps(d))                # key names only, never values
        self.assertEqual(status.set_row(cfg, "stop", str(self.films[0])), "🛑 stopped (dashboard)")
        self.assertEqual(status.build(cfg, now=datetime(2026, 11, 18, 12, 5))["films"][0]["state"], "stopped")
        self.assertEqual(status.set_row(cfg, "resume", str(self.films[0])), "✅ auto")

    def test_profile_edit_writes_publish_fields(self):
        from viral_scout import profile_edit
        cfg = self.profile()
        prof = config.PROFILES / "zz-autotest.yaml"
        prof.write_text("name: zz-autotest\npublish:\n  per_day: 1\n  posts: {enabled: false, per_day: 1}\njobs:\n  film: {enabled: false}\n",
                        encoding="utf-8")
        try:
            profile_edit.set_fields("zz-autotest", {"publish.approval": "auto", "publish.per_day": 2, "publish.times": ["11:30", "18:30"],
                                                    "publish.posts.enabled": True, "publish.auto_post.linkedin": True, "jobs.film.enabled": True})
            doc = yaml.safe_load(prof.read_text(encoding="utf-8"))
            self.assertEqual(doc["publish"]["approval"], "auto")
            self.assertEqual(doc["publish"]["times"], ["11:30", "18:30"])
            self.assertEqual(doc["publish"]["posts"], {"enabled": True, "per_day": 1})
            self.assertTrue(doc["publish"]["auto_post"]["linkedin"])
            self.assertTrue(doc["jobs"]["film"]["enabled"])
            with self.assertRaises(ValueError):
                profile_edit.set_fields("zz-autotest", {"publish.times": ["25:00"]})
        finally:
            prof.unlink()
        self.assertTrue(cfg)


class TikTokTest(Base):
    def test_chunks(self):
        from viral_scout.publish import tiktok
        self.assertEqual(tiktok.chunks(30 * tiktok.MB), (30 * tiktok.MB, 1))
        self.assertEqual(tiktok.chunks(105 * tiktok.MB), (10 * tiktok.MB, 10))   # the last chunk takes the remaining 15 MB

    def test_upload_draft_puts_every_byte(self):
        from viral_scout.publish import tiktok
        cfg = self.profile()
        calls = []

        class R:
            def __init__(self, j=None, code=201):
                self.j, self.status_code, self.text = j, code, ""

            def json(self):
                return self.j

        class Http:
            def post(self, url, **kw):
                calls.append(("init", kw["json"]))
                return R({"data": {"publish_id": "p1", "upload_url": "https://up"}, "error": {"code": "ok"}})

            def put(self, url, **kw):
                calls.append(("put", kw["headers"]["Content-Range"]))
                return R()
        orig = tiktok.token
        tiktok.token = lambda cfg, env=None: "tok"
        try:
            self.assertEqual(tiktok.upload_draft(cfg, self.films[0], http=Http()), {"id": "p1"})
        finally:
            tiktok.token = orig
        self.assertEqual(calls[1], ("put", "bytes 0-0/1"))

    def test_autopost_sends_tiktok_draft_and_caption(self):
        from viral_scout.publish import tiktok
        cfg = self.profile({"auto_post": {"instagram": True, "tiktok": True}})
        keys = Path(core.settings(cfg)["env_file"])
        keys.write_text(keys.read_text(encoding="utf-8") + "TIKTOK_POST_REFRESH_TOKEN=r\n", encoding="utf-8")
        sent = []
        orig = (tiktok.upload_draft, tiktok.tell_owner)
        tiktok.upload_draft = lambda cfg, video, http=None: {"id": "pub-1"}
        tiktok.tell_owner = lambda cfg, title, caption: sent.append((title, caption)) or "caption sent to the bot"
        try:
            node = FakeNode(cfg)
            out = auto.run(cfg, now=datetime(2026, 11, 18, 12, 5), run_node=node, replier=lambda c, dry: [])
        finally:
            tiktok.upload_draft, tiktok.tell_owner = orig
        self.assertIn("tiktok draft: caption sent to the bot", out)
        self.assertEqual(node.calls[0][node.calls[0].index("--only") + 1], "instagram")   # node never gets tiktok
        self.assertEqual(sent, [("A", "Text #a")])
        self.assertIn(("tiktok", self.films[0].name), auto.published(cfg))
        self.assertIn("📤 posted", self.queue.read_text(encoding="utf-8").split("\n")[2])


class ThreadsTest(Base):
    def test_fit_keeps_the_link(self):
        from viral_scout.publish import threads
        out = threads.fit("word " * 200, "https://instagram.com/reel/x")
        self.assertLessEqual(len(out), 500)
        self.assertTrue(out.endswith("https://instagram.com/reel/x"))

    def test_film_threads_links_to_the_reel(self):
        from viral_scout.publish import threads
        cfg = self.profile({"auto_post": {"instagram": True, "threads": True}, "platforms": ["instagram", "threads"]})
        keys = Path(core.settings(cfg)["env_file"])
        keys.write_text(keys.read_text(encoding="utf-8") + "THREADS_ACCESS_TOKEN=x\nTHREADS_USER_ID=1\n", encoding="utf-8")
        got = []

        class Node(FakeNode):
            def __call__(self, cmd, cfg, dry):
                code, out = super().__call__(cmd, cfg, dry)
                with self.log.open("a", encoding="utf-8") as fh:    # the Reel's permalink, as publish.mjs logs it
                    fh.write(json.dumps({"platform": "instagram", "video": Path(cmd[2]).name, "permalink": "https://ig/reel/1"}) + "\n")
                return code, out
        orig = threads.post
        threads.post = lambda cfg, text, link="", http=None: got.append((text, link)) or {"id": "t1", "link": "https://threads/t1"}
        try:
            node = Node(cfg)
            auto.run(cfg, now=datetime(2026, 11, 18, 12, 5), run_node=node, replier=lambda c, dry: [])
        finally:
            threads.post = orig
        self.assertEqual(node.calls[0][node.calls[0].index("--only") + 1], "instagram")
        self.assertEqual(got, [("Text #a", "https://ig/reel/1")])
        self.assertIn(("threads", self.films[0].name), auto.published(cfg))


class AlertTest(Base):
    def test_failed_post_alerts_once_a_day(self):
        cfg = self.profile()
        sent = []

        def bad_node(cmd, cfg, dry):
            return 1, "✖ instagram failed: token expired"
        alert = lambda cfg, title, lines, now: sent.append(lines) or "bot"   # noqa: E731
        from viral_scout.publish import notify
        real = lambda cfg, title, lines, now: notify.alert(cfg, title, lines, now, send=lambda c, t, b: sent.append(b) or "bot")  # noqa: E731
        auto.run(cfg, now=datetime(2026, 11, 18, 12, 5), run_node=bad_node, replier=lambda c, dry: [], alert=real)
        auto.run(cfg, now=datetime(2026, 11, 18, 12, 35), run_node=bad_node, replier=lambda c, dry: [], alert=real)
        self.assertEqual(len(sent), 1)                                   # the second run repeats nothing
        self.assertIn("exit 1", sent[0])
        self.assertTrue(alert)

    def test_short_day_and_missed(self):
        cfg = self.profile()
        s = core.settings(cfg)
        self.assertEqual(auto.short_day(cfg, s, datetime(2026, 11, 18, 11, 0)), [])          # before the first time
        self.assertEqual(auto.short_day(cfg, s, datetime(2026, 11, 18, 12, 1)), [])          # 2 queued, 2 wanted
        self.assertIn("only 0 of 2", auto.short_day(cfg, s, datetime(2026, 11, 19, 12, 1))[0])
        out = auto.films(cfg, datetime(2026, 11, 20, 9, 0))            # 11-18 rows: late_days 1 → missed on 11-20
        self.assertTrue(any("missed, never posted" in l for l in out))

    def test_problem_lines(self):
        from viral_scout.publish import notify
        self.assertEqual(notify.problems(["film A → instagram: exit 0", "film B: waiting for approval", "film C → tiktok: TikTok not connected for this business"]),
                         ["film C → tiktok: TikTok not connected for this business"])

    def test_film_job_failure_alerts(self):
        from viral_scout.publish import notify
        cfg = self.profile(jobs={"film": {"enabled": True}})
        got = []
        orig = notify.alert
        notify.alert = lambda cfg, title, lines, now=None, send=None: got.append(lines)
        try:
            runner.run(cfg, "film", now=datetime(2026, 11, 18, 6, 0), execute=lambda *a: 1, which=lambda _: "claude", wait_minutes=0)
            runner.run(cfg, "film", now=datetime(2026, 11, 18, 7, 0), execute=lambda *a: 0, which=lambda _: "claude", wait_minutes=0)
        finally:
            notify.alert = orig
        self.assertIn("didn't finish (exit 1)", got[0][0])
        self.assertIn("gave up for today", got[1][0])                   # exit 0 but no film delivered, last try


class PerfLoopTest(Base):
    def test_own_keys_and_daily_measure(self):
        from viral_scout.perf import run as perf
        cfg = self.profile()
        own = perf.own_keys(cfg)
        self.assertEqual((own["IG_GRAPH_TOKEN"], own["IG_GRAPH_USER_ID"], own["YT_OAUTH_REFRESH_TOKEN"]), ("t", "1", "c"))
        calls = []

        def build(cfg, pull, quiet):
            calls.append(pull)
            return {"records": [1, 2], "sources": {"errors": []}}, ("report.md", "x.json")
        self.assertEqual(auto.measure(cfg, datetime(2026, 11, 18, 6, 0), build), [])          # before 07:00
        self.assertIn("2 of your own posts", auto.measure(cfg, datetime(2026, 11, 18, 8, 0), build)[0])
        self.assertEqual(auto.measure(cfg, datetime(2026, 11, 18, 9, 0), build), [])          # once a day
        self.assertEqual(calls, [True])

    def test_prompts_point_at_the_newest_report(self):
        cfg = self.profile(jobs={"film": {"enabled": True}})
        out = Path(cfg["output_dir"])
        out.mkdir(parents=True, exist_ok=True)
        (out / "2026-11-17-performance.md").write_text("x", encoding="utf-8")
        (out / "2026-11-18-performance.md").write_text("x", encoding="utf-8")
        self.assertIn("2026-11-18-performance.md", prompts.assemble(cfg, "film"))
