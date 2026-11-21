"""Publishing: caption file, UTM links, the weekly plan, post dry-run planning, the morning pack, the notes client.
No network: Telegram and the notes API are replaced by fakes.

  python -m pytest tests/test_publish.py -q
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["VIRAL_SCOUT_NO_ALERTS"] = "1"   # never message the real bot from a test

import yaml  # noqa: E402

from viral_scout import config, notes  # noqa: E402
from viral_scout.publish import cli as pcli  # noqa: E402
from viral_scout.publish import core, pack  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._root = config.ROOT
        config.ROOT = self.tmp
        self.vd = self.tmp / "vault" / "projects" / "demo"
        (self.vd / "05 Marketing" / "Video Studio").mkdir(parents=True)
        film = self.tmp / "films" / "gutter-tips"
        (film / "out").mkdir(parents=True)
        self.mp4 = film / "out" / "gutter-tips.mp4"
        self.mp4.write_bytes(b"x")
        (film / "still.png").write_bytes(b"png")
        (film / "POST.md").write_text("---\nx: 1\n---\n🎬 Gutter tips\n\n▶ TIKTOK (search)\nGutters {link}\n\n"
                                      "▶ INSTAGRAM STORY\nSticker {link}\n", encoding="utf-8")
        (self.vd / "05 Marketing" / "Video Studio" / "ready-to-post.md").write_text(
            "| Date | Title | Video | Script | Status |\n|---|---|---|---|---|\n"
            f"| 2026-11-16 | Gutter tips | `{self.mp4}` | [[s]] | waiting for Alex |\n"
            "| 2026-11-17 | Old one | `x.mp4` | [[s]] | posted |\n"
            "| 2026-11-19 | Ice dams | `y.mp4` | [[s]] | ✅ approved |\n", encoding="utf-8")

    def tearDown(self):
        config.ROOT = self._root

    def profile(self, publish=None, jobs=None):
        doc = {"name": "demo", "studio": {"brand": "Demo", "vault_dir": str(self.vd), "cta": {"text": "c", "link": "https://demo.example/c"}},
               "publish": {"handles": {"instagram": "@demo"}, **(publish or {})}, "jobs": jobs or {}}
        p = self.tmp / "demo.yaml"
        p.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
        return config.load(str(p))


class CaptionTest(unittest.TestCase):
    def test_sections(self):
        c = core.parse_caption("ai: true\ntitle: Panels\nBase text #a\r\n\r\n## Instagram\r\nIG\r\n## TikTok\nTT\n")
        self.assertTrue(c["ai"])
        self.assertEqual(c["title"], "Panels")
        self.assertEqual((c["instagram"], c["tiktok"], c["facebook"]), ("IG", "TT", "Base text #a"))

    def test_youtube_title(self):
        self.assertEqual(core.youtube_title("What one battery runs #shorts"), "What one battery runs #Shorts")
        t = core.youtube_title("word " * 40)
        self.assertLessEqual(len(t), 100)
        self.assertTrue(t.endswith("… #Shorts"))

    def test_problems(self):
        self.assertIn("hashtags > 30", ",".join(core.caption_problems(core.parse_caption(" ".join(f"#t{i}" for i in range(31))))))
        self.assertEqual(core.caption_problems(core.parse_caption("ok")), [])


class UtmTest(unittest.TestCase):
    def test_link(self):
        u = core.utm_link("https://x.com/c?a=1", "instagram", "gutter-tips")
        self.assertEqual(u, "https://x.com/c?a=1&utm_source=instagram&utm_medium=social&utm_campaign=gutter-tips")

    def test_keeps_existing_and_maps_sources(self):
        s = core._merge(core.DEFAULTS, {"utm": {"sources": {"instagram_story": "ig_story"}, "campaign": "{platform}-{slug}"}})
        u = core.utm_link("https://x.com/?utm_source=keep", "instagram_story", "s1", s)
        self.assertIn("utm_source=keep", u)
        self.assertIn("utm_campaign=instagram_story-s1", u)
        self.assertEqual(core.utm_link("", "x"), "")


class PlanTest(Base):
    def test_week(self):
        cfg = self.profile({"auto_post": {"youtube": True, "tiktok": True}})
        rows = core.plan(cfg, date(2026, 11, 15), 7)
        self.assertEqual([r["title"] for r in rows], ["Gutter tips", "Ice dams"])     # posted one left out
        first = {p["platform"]: p for p in rows[0]["posts"]}
        self.assertEqual(first["youtube"]["mode"], "auto")
        self.assertEqual(first["tiktok"]["mode"], "auto")         # opted in: a draft in the TikTok app (publish/tiktok.py)
        self.assertEqual(first["instagram"]["mode"], "manual")    # not opted in
        self.assertEqual(first["instagram"]["at"], "2026-11-16 18:30")
        self.assertEqual(first["instagram"]["handle"], "@demo")
        self.assertIn("utm_campaign=gutter-tips", first["instagram"]["link"])
        self.assertTrue(rows[1]["approved"])

    def test_free_dates(self):
        cfg = self.profile()
        self.assertEqual(core.free_dates(cfg, date(2026, 11, 16), 5), ["2026-11-18", "2026-11-20"])


class PostPlanTest(Base):
    def test_default_is_manual_only(self):
        cfg = self.profile()
        pp = pcli.post_plan(cfg, self.mp4, "AI voice of me. Gutters #a\n")
        self.assertEqual(pp["auto"], [])
        self.assertEqual(pp["manual"], ["tiktok", "instagram", "youtube", "facebook"])

    def test_opt_in_needs_tokens(self):
        cfg = self.profile({"auto_post": {"youtube": True}, "env_file": str(self.tmp / "e.env"),
                            "tokens": {"youtube": {"YOUTUBE_REFRESH_TOKEN": "MY_YT"}}})
        pp = pcli.post_plan(cfg, self.mp4, "x\n")
        self.assertEqual(pp["auto"], [])
        self.assertIn("youtube", pp["missing"])
        (self.tmp / "e.env").write_text("YOUTUBE_CLIENT_ID=a\nYOUTUBE_CLIENT_SECRET=b\nMY_YT=c\n", encoding="utf-8")
        pp = pcli.post_plan(cfg, self.mp4, "x\n", only=["youtube", "tiktok"])
        self.assertEqual((pp["auto"], pp["manual"]), (["youtube"], ["tiktok"]))
        env = pcli.node_env(cfg)
        self.assertEqual(env["YOUTUBE_REFRESH_TOKEN"], "c")       # the profile's name mapped to the standard one

    def test_node_command_dry(self):
        cfg = self.profile({"timezone": "Europe/Warsaw"})
        pp = {"video": str(self.mp4), "auto": ["youtube"]}
        args = type("A", (), {"dry_run": True, "at": "2026-11-16 18:30", "video_url": None, "cover_url": None, "cover": None})()
        cmd = pcli.node_command(cfg, pp, self.tmp / "c.md", args)
        self.assertEqual(cmd[0], "node")
        self.assertTrue(cmd[1].endswith("publish.mjs"))
        self.assertIn("--dry-run", cmd)
        self.assertEqual(cmd[cmd.index("--tz") + 1], "Europe/Warsaw")
        self.assertEqual(cmd[cmd.index("--only") + 1], "youtube")


class MorningPackTest(Base):
    def test_build(self):
        row, msgs = pack.build(self.profile(), "2026-11-16")
        self.assertEqual(row["title"], "Gutter tips")
        self.assertEqual([m["kind"] for m in msgs], ["video", "photo", "text", "text", "text"])
        self.assertIn("utm_source=tiktok", msgs[3]["text"])
        self.assertIn("utm_source=instagram_story", msgs[4]["text"])
        self.assertNotIn("x: 1", "".join(m["text"] for m in msgs))     # frontmatter dropped

    def test_no_video_today(self):
        row, msgs = pack.build(self.profile(), "2026-11-18")
        self.assertIsNone(row)
        self.assertIn("2026-11-19", msgs[0]["text"])

    def test_today_marker_and_hour(self):
        cfg = self.profile()
        sent = []
        early = datetime(2026, 11, 16, 7, 0)
        self.assertIn("before", pack.today(cfg, now=early, sender=sent.append))
        late = datetime(2026, 11, 16, 9, 30)
        self.assertIn("sent 2026-11-16", pack.today(cfg, now=late, sender=sent.append))
        self.assertEqual(len(sent), 5)
        self.assertIn("already sent", pack.today(cfg, now=late, sender=sent.append))
        self.assertEqual(len(sent), 5)

    def test_dry_sends_nothing(self):
        cfg = self.profile()
        self.assertIn("nothing sent", pack.today(cfg, day="2026-11-16", dry=True, sender=lambda m: self.fail("sent")))
        self.assertFalse((self.tmp / "data" / "jobs" / "demo" / "post-2026-11-16.done").exists())

    def test_chunks(self):
        parts = core.chunks("a" * 5000 + "\n\n" + "b" * 10, 3900)
        self.assertTrue(all(len(p) <= 3900 for p in parts))
        self.assertEqual("".join(parts).replace("\n", ""), "a" * 5000 + "b" * 10)


class NotesClientTest(unittest.TestCase):
    def fake(self, responses):
        seen = []

        def opener(req):
            seen.append(req)
            return responses.pop(0)
        return opener, seen

    def test_pending_and_close(self):
        opener, seen = self.fake([(200, b'{"pending": 3}'), (200, b'{"ok": true}')])
        c = notes.Client("https://x.example", "s3cret", "demo", opener)
        self.assertEqual(c.pending(), 3)
        self.assertIn("project=demo", seen[0].full_url)
        self.assertEqual(seen[0].get_header("Authorization"), "Bearer s3cret")
        c.close(7, "done", "new version sent", reply="✅ new version sent")
        body = json.loads(seen[1].data)
        self.assertEqual((seen[1].get_method(), body["id"], body["status"]), ("PATCH", 7, "done"))

    def test_not_configured(self):
        with self.assertRaises(RuntimeError):
            notes.Client("", "", "demo").pending()

    def test_pending_is_zero_when_down(self):
        cfg = {"name": "demo", "jobs": {}}
        self.assertEqual(notes.pending(cfg, client=type("C", (), {"pending": lambda self: 1 / 0})()), 0)

    def test_show(self):
        s = notes.show({"id": 4, "from": "Alex", "kind": "voice", "status": "new", "about": "📝 Script · idea #12", "text": "shorter"}, "a.ogg")
        self.assertIn("↪ about: 📝 Script · idea #12", s)
        self.assertIn("📎 a.ogg", s)


TOKEN = "4242:SECRET-token-value"
PLAN = {"bot_id": "4242", "chat_id": "-100", "method": "sendVideo", "field": "video",
        "caption": "🔨 Homeworks · 🎬 Film\n\n#Homeworks #video #film", "reply_parameters": {"message_id": 77}}


class NotesDirectTest(unittest.TestCase):
    """Files over the service's ~4.5 MB limit go straight to the Bot API; retries never double a message."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.big = self.tmp / "film.mp4"
        self.big.write_bytes(b"\0" * (notes.SERVICE_MAX + 10))          # a 22-26 MB master, as far as the limit goes
        self.small = self.tmp / "alert.txt"
        self.small.write_text("details", encoding="utf-8")
        self.sleeps = []

    def client(self, answers, direct=True, plan=PLAN):
        seen = []

        def opener(req):
            seen.append(req)
            if "/api/notes" in req.full_url and req.get_method() == "POST" and b'"prepare": true' in (req.data or b""):
                return (200, json.dumps(plan).encode()) if plan else (400, b'{"error":"multipart: project, file"}')
            a = answers.pop(0)
            if isinstance(a, Exception):
                raise a
            return a
        d = {"token": TOKEN, "chat": "-100", "header": "🔨 Homeworks", "token_env": "T_TOKEN",
             "tags": lambda kind, extra: " ".join(["#Homeworks", f"#{kind}", *(f"#{e}" for e in extra)])} if direct else None
        return notes.Client("https://svc.example", "s3cret", "homes", opener, direct=d, sleep=self.sleeps.append), seen

    def test_big_master_goes_to_telegram_with_the_services_plan(self):
        c, seen = self.client([(200, b'{"ok": true, "result": {"message_id": 235}}')])
        r = c.send(str(self.big), "🎬 Film", reply_to=5, tags="film")
        self.assertEqual((r["message_id"], r["route"]), (235, "telegram"))
        prep, tg = seen
        self.assertEqual(json.loads(prep.data)["reply_to"], 5)
        self.assertTrue(tg.full_url.startswith("https://api.telegram.org/bot4242:"))
        self.assertTrue(tg.full_url.endswith("/sendVideo"))
        body = tg.data
        self.assertIn(b'name="chat_id"\r\n\r\n-100', body)
        self.assertIn('#Homeworks #video #film'.encode(), body)
        self.assertIn(b'"message_id": 77', body)
        self.assertIn(b'name="video"; filename="film.mp4"', body)
        self.assertGreater(len(body), notes.SERVICE_MAX)                 # the whole master, not a preview

    def test_without_a_token_a_big_file_is_refused_clearly(self):
        c, seen = self.client([], direct=False)
        with self.assertRaises(RuntimeError) as e:
            c.send(str(self.big), "x")
        self.assertIn("token_env", str(e.exception))
        self.assertEqual(seen, [])
        c, seen = self.client([(200, b'{"message_id": 3}')], direct=False)
        self.assertEqual(c.send(str(self.small), "x")["route"], "service")

    def test_other_bot_falls_back_to_the_service_for_small_files(self):
        c, seen = self.client([(200, b'{"message_id": 3}')], plan={**PLAN, "bot_id": "999"})
        self.assertEqual(c.send(str(self.small), "x")["route"], "service")
        c, _ = self.client([], plan={**PLAN, "bot_id": "999"})
        with self.assertRaises(RuntimeError) as e:
            c.send(str(self.big), "x")
        self.assertIn("not the service's video bot", str(e.exception))

    def test_old_service_without_prepare_uses_the_local_header_and_tags(self):
        c, seen = self.client([(200, b'{"ok": true, "result": {"message_id": 9}}')], plan=None)
        r = c.send(str(self.big), "🎬 Film", tags="film")
        self.assertEqual(r["route"], "telegram")
        self.assertIn("🔨 Homeworks · 🎬 Film\n\n#Homeworks #video #film".encode(), seen[-1].data)

    def test_a_failed_connection_is_retried_once(self):
        import urllib.error
        c, seen = self.client([urllib.error.URLError("connection refused"), (200, b'{"ok": true, "result": {"message_id": 4}}')])
        self.assertEqual(c.send(str(self.small), "⚠️ alert", tags="alert")["message_id"], 4)
        self.assertEqual(len([r for r in seen if "telegram" in r.full_url]), 2)
        self.assertEqual(self.sleeps, [notes.RETRY_WAIT])

    def test_a_timeout_on_the_answer_is_never_resent(self):
        c, seen = self.client([TimeoutError("The read operation timed out"), (200, b'{"ok": true, "result": {"message_id": 4}}')])
        with self.assertRaises(RuntimeError) as e:
            c.send(str(self.small), "⚠️ alert")
        self.assertIn("not resent", str(e.exception))
        self.assertEqual(len([r for r in seen if "telegram" in r.full_url]), 1)

    def test_429_waits_and_retries(self):
        c, seen = self.client([(429, b'{"ok": false, "parameters": {"retry_after": 5}}'),
                               (200, b'{"ok": true, "result": {"message_id": 4}}')])
        self.assertEqual(c.send(str(self.small), "x")["message_id"], 4)
        self.assertEqual(self.sleeps, [5])

    def test_the_token_never_shows_in_errors(self):
        c, _ = self.client([(401, f'{{"ok": false, "description": "Unauthorized {TOKEN}"}}'.encode())])
        with self.assertRaises(RuntimeError) as e:
            c.send(str(self.small), "x")
        self.assertNotIn("SECRET-token", str(e.exception))
        import urllib.error
        c, _ = self.client([urllib.error.URLError(f"bad host api.telegram.org/bot{TOKEN}")] * 2)
        with self.assertRaises(notes.NotSent) as e:
            c.send(str(self.small), "x")
        self.assertNotIn("SECRET-token", str(e.exception))

    def test_over_50_mb_sends_a_preview(self):
        orig_max, orig_prev = notes.TELEGRAM_MAX, notes.preview
        notes.TELEGRAM_MAX = notes.SERVICE_MAX + 5
        small = self.tmp / "film-preview.mp4"
        small.write_bytes(b"p" * 100)
        notes.preview = lambda f: small
        try:
            c, seen = self.client([(200, b'{"ok": true, "result": {"message_id": 8}}')])
            r = c.send(str(self.big), "🎬 Film")
        finally:
            notes.TELEGRAM_MAX, notes.preview = orig_max, orig_prev
        self.assertEqual(r["preview"], str(small))
        self.assertIn("master is over Telegram", json.loads(seen[0].data)["caption"])
        self.assertLess(len(seen[-1].data), 2000)

    def test_alert_not_sent_falls_back_once_but_a_timeout_does_not(self):
        from viral_scout.publish import notify
        cfg = {"name": "demo", "jobs": {}}
        calls = []

        class C:
            def __init__(self, exc):
                self.exc = exc

            def send(self, *a, **k):
                calls.append("bot")
                raise self.exc
        orig_client, orig_settings, orig_tg = notes.client, notes.api_settings, pack._telegram
        notes.api_settings = lambda cfg: {"url": "u", "secret": "s", "project": "demo", "token": "", "command": ""}
        pack._telegram = lambda *a, **k: calls.append("morning bot")
        os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"] = "1:x", "-1"
        try:
            notes.client = lambda cfg: C(notes.NotSent("not sent"))
            self.assertEqual(notify._deliver(cfg, "t", "b"), "telegram")
            notes.client = lambda cfg: C(RuntimeError("no answer; not resent"))
            with self.assertRaises(RuntimeError):
                notify._deliver(cfg, "t", "b")
        finally:
            notes.client, notes.api_settings, pack._telegram = orig_client, orig_settings, orig_tg
            del os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
        self.assertEqual(calls, ["bot", "morning bot", "bot"])


if __name__ == "__main__":
    unittest.main()


def test_queue_keeps_wikilink_alias_pipes(tmp_path):
    """An Obsidian alias inside a table cell escapes its pipe; the status column must still be read."""
    from viral_scout.publish import core
    q = tmp_path / "ready-to-post.md"
    q.write_text("| Date | Title | Video | Script | Status |\n|---|---|---|---|---|\n"
                 "| 2026-11-16 | Grid truth | `D:/v/a.mp4` | [[scripts/a\|script]] | approved |\n", encoding="utf-8")
    rows = core.read_queue(q)
    assert rows[0]["script"] == "[[scripts/a\|script]]"
    assert rows[0]["status"] == "approved"


def test_queue_keeps_unescaped_wikilink_alias(tmp_path):
    """A hand-written `[[note|label]]` in the script cell must not shift the status column."""
    from viral_scout.publish import core
    q = tmp_path / "ready-to-post.md"
    q.write_text("| 2026-11-16 | Grid truth | `D:/v/a.mp4` | [[scripts/a|script]] | ✅ approved |\n", encoding="utf-8")
    rows = core.read_queue(q)
    assert rows[0]["script"] == "[[scripts/a|script]]"
    assert core.approved(rows[0])
