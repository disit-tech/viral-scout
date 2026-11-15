"""Ideas CLI: pack-note parsing, limit and banned-word checks, project-slug safety, request building (no network).

  python -m pytest tests/test_ideas.py   or   python -m unittest tests.test_ideas -v
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from viral_scout.ideas import cli, packs  # noqa: E402
from viral_scout.ideas.client import Client, check_batch  # noqa: E402
from viral_scout.ideas.settings import IdeasError, credentials, ideas_cfg, market_files  # noqa: E402

LIMITS = {"threads": {"per_part": 500}, "google": {"total": 1500}, "linkedin": {"total": 3000, "hashtags": [3, 8]}}
BANNED = [{"pattern": r"\b(insured|bonded)\b", "why": "says insured/bonded"},
          {"pattern": r"\bcrews?\b", "why": 'says "crew"'}]

NOTE = """---
type: post-pack
idea: 40
---

# Posts: gutters (idea #40)

Vault-only intro text.

## LinkedIn
> Photo: the full bucket next to the ladder
Gutters full before the freeze? We clean them and send photos.

#Springfield #Gutters #HomeMaintenance

## Threads
### 1/2
First post.
### 2/2
> Second one is a question
Who else waits until December?

## Reels / Shorts / TikTok
### Hook
> spoken + on screen
### Shots
1. Ladder
2. Bucket

## Checks
- prices checked
"""


class Recorder:
    """A fake HTTP layer: records every request and answers from a table."""

    def __init__(self, ideas=()):
        self.calls = []
        self.ideas = list(ideas)

    def __call__(self, method, url, headers, body, timeout=60):
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body})
        if method == "GET" and "/api/ideas" in url:
            return 200, json.dumps({"ideas": self.ideas, "storms": []})
        if method == "POST":
            return 200, json.dumps({"created": [101]})
        return 200, json.dumps({"ok": True})


def ideas_block(**over):
    base = {"project": "homes", "api": {"env_file": "", "url_env": "T_URL", "secret_env": "T_SECRET"},
            "packs": {"enabled": True, "limits": LIMITS, "banned_words": BANNED}}
    base.update(over)
    return base


class TestPackParsing(unittest.TestCase):
    def test_sections_labels_notes(self):
        s = packs.parse(NOTE)
        self.assertEqual([x["title"] for x in s], ["LinkedIn", "Threads", "Reels / Shorts / TikTok"])
        li = s[0]["parts"]
        self.assertEqual(len(li), 1)
        self.assertEqual(li[0]["note"], "Photo: the full bucket next to the ladder")
        self.assertTrue(li[0]["text"].startswith("Gutters full"))
        self.assertNotIn("label", li[0])
        th = s[1]["parts"]
        self.assertEqual([p["label"] for p in th], ["1/2", "2/2"])
        self.assertEqual(th[1]["note"], "Second one is a question")
        self.assertEqual(th[1]["text"], "Who else waits until December?")

    def test_note_only_block_carries_to_next(self):
        reel = packs.parse(NOTE)[2]["parts"]
        self.assertEqual(reel, [{"label": "Shots", "note": "Hook: spoken + on screen", "text": "1. Ladder\n2. Bucket"}])

    def test_checks_and_vault_intro_skipped(self):
        s = packs.parse(NOTE)
        self.assertFalse(any(x["title"].lower().startswith("check") for x in s))
        self.assertFalse(any("Vault-only" in p["text"] for x in s for p in x["parts"]))
        self.assertEqual(packs.parse("## Notes\nx\n## Перевірка\ny"), [])

    def test_trailing_note_only_becomes_block(self):
        s = packs.parse("## Yelp\n### Photos\n> upload 3 photos\n")
        self.assertEqual(s, [{"title": "Yelp", "parts": [{"text": "Photos: upload 3 photos"}]}])

    def test_crlf(self):
        s = packs.parse(NOTE.replace("\n", "\r\n"))
        self.assertEqual(len(s), 3)


class TestPackChecks(unittest.TestCase):
    def test_clean_note_passes(self):
        errors, warnings = packs.check(packs.parse(NOTE), LIMITS, BANNED)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_threads_per_post(self):
        s = [{"title": "Threads", "parts": [{"label": "1/2", "text": "x" * 501}]}]
        errors, _ = packs.check(s, LIMITS, BANNED)
        self.assertTrue(any("501 chars" in e and "500" in e for e in errors))

    def test_google_total(self):
        s = [{"title": "Google Business Profile", "parts": [{"text": "x" * 1501}]}]
        errors, _ = packs.check(s, LIMITS, BANNED)
        self.assertTrue(any("1,500" in e for e in errors))

    def test_linkedin_total_and_hashtags(self):
        s = [{"title": "LinkedIn", "parts": [{"text": "short post #one"}]}]
        errors, warnings = packs.check(s, LIMITS, BANNED)
        self.assertEqual(errors, [])
        self.assertTrue(any("1 hashtags" in w for w in warnings))
        s = [{"title": "LinkedIn", "parts": [{"text": "x" * 2990 + " #a #b #c"}, {"text": "y" * 20}]}]
        errors, _ = packs.check(s, LIMITS, BANNED)
        self.assertTrue(any("3,000" in e for e in errors))

    def test_banned_words_and_em_dash(self):
        s = [{"title": "Facebook page", "parts": [{"text": "Our crew is fully Insured — call now"}]}]
        errors, warnings = packs.check(s, LIMITS, BANNED)
        self.assertTrue(any("insured" in e for e in errors))
        self.assertTrue(any("crew" in e for e in errors))
        self.assertTrue(any("em dash" in w for w in warnings))

    def test_plain_string_banned_word_and_warning_level(self):
        s = [{"title": "Nextdoor", "parts": [{"text": "A seamless experience, guaranteed"}]}]
        errors, warnings = packs.check(s, {}, ["seamless", {"pattern": "guaranteed", "level": "warning"}])
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(warnings), 1)

    def test_api_limits(self):
        s = [{"title": "Facebook page", "parts": [{"text": "x" * 1900}, {"text": "y" * 1900}, {"text": "z" * 200}]}]
        errors, _ = packs.check(s, {}, [])
        self.assertTrue(any("one Telegram message" in e for e in errors))
        errors, _ = packs.check([], {}, [])
        self.assertTrue(errors)


class TestBatchChecks(unittest.TestCase):
    def setUp(self):
        self.ic = ideas_cfg({"name": "t", "ideas": ideas_block(packs={"platforms": ["instagram", "nextdoor"],
                                                                       "banned_words": ["crew"]})})

    def idea(self, **kw):
        return {"title": "Gutter photos", "hook": "Full gutters?", "score": 41, **kw}

    def test_ok(self):
        self.assertEqual(check_batch({"batch": "nf-1", "ideas": [self.idea()]}, self.ic), ([], []))

    def test_field_limits(self):
        errors, _ = check_batch({"batch": "nf-1", "ideas": [self.idea(hook="x" * 301, cta="")]}, self.ic)
        self.assertTrue(any("hook is 301" in e for e in errors))
        self.assertTrue(any("cta must be non-empty" in e for e in errors))
        errors, _ = check_batch({"batch": "nf-1", "ideas": [{"title": "t"}]}, self.ic)
        self.assertTrue(any("hook is required" in e for e in errors))
        errors, _ = check_batch({"batch": "x" * 61, "ideas": [self.idea()] * 21}, self.ic)
        self.assertEqual(len(errors), 2)

    def test_threshold_platforms_banned(self):
        errors, warnings = check_batch({"batch": "b", "ideas": [
            self.idea(score=30), self.idea(platforms=["instagram", "tiktok"]), self.idea(hook="Our crew")]}, self.ic)
        self.assertTrue(any("threshold 38" in e for e in errors))
        self.assertTrue(any("tiktok" in e for e in errors))
        self.assertTrue(any("crew" in w for w in warnings))


class TestSlugSafety(unittest.TestCase):
    def test_bad_or_missing_slug(self):
        for bad in ("", "Solar", "solar&project=agency", "a b", None):
            with self.assertRaises(IdeasError):
                ideas_cfg({"name": "t", "ideas": {"project": bad}})
        with self.assertRaises(IdeasError):
            ideas_cfg({"name": "t"})

    def test_push_with_other_project_refused(self):
        rec = Recorder()
        c = Client("homes", "http://x", "s", rec)
        with self.assertRaises(IdeasError):
            c.push({"project": "solar", "batch": "b", "ideas": []})
        self.assertEqual(rec.calls, [])

    def test_ids_of_other_projects_refused(self):
        rec = Recorder(ideas=[{"id": 40}, {"id": 41}])
        c = Client("homes", "http://x", "s", rec)
        for fn in (lambda: c.tracked([40, 7]), lambda: c.repost([7]), lambda: c.stage(7, "draft"),
                   lambda: c.script(7, "x" * 30)):
            with self.assertRaises(IdeasError):
                fn()
        self.assertTrue(all(x["method"] == "GET" for x in rec.calls))
        self.assertTrue(all(x["url"].endswith("/api/ideas?project=homes") for x in rec.calls))

    def test_env_project_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            prof = Path(d) / "nf.yaml"
            prof.write_text(json.dumps({"name": "nf", "ideas": ideas_block()}), encoding="utf-8")
            rec = Recorder()
            env = {"T_URL": "https://site.test/", "T_SECRET": "sek", "IDEAS_PROJECT": "solar"}
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main([str(prof), "pull"], rec, env), 0)
            self.assertEqual(rec.calls[0]["url"], "https://site.test/api/ideas?project=homes")


class TestRequests(unittest.TestCase):
    def setUp(self):
        self.rec = Recorder(ideas=[{"id": 12}, {"id": 40}])
        self.c = Client("homes", "http://localhost:3000/", "sek", self.rec)

    def body(self, n=-1):
        return self.rec.calls[n]["body"].decode("utf-8")

    def test_headers_and_pull(self):
        self.c.pull()
        call = self.rec.calls[0]
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["url"], "http://localhost:3000/api/ideas?project=homes")
        self.assertEqual(call["headers"], {"Authorization": "Bearer sek", "Content-Type": "application/json"})
        self.assertIsNone(call["body"])

    def test_push_body_like_ideas_mjs(self):
        # ideas.mjs: JSON.stringify({ project, ...file }) → compact, project first, unicode as is
        self.c.push({"batch": "nf-2026-11-15-a", "ideas": [{"title": "Лампи", "hook": "h", "score": 40}]})
        self.assertEqual(self.body(), '{"project":"homes","batch":"nf-2026-11-15-a",'
                                      '"ideas":[{"title":"Лампи","hook":"h","score":40}]}')
        self.assertEqual(self.rec.calls[-1]["method"], "POST")

    def test_patch_bodies(self):
        self.c.tracked([12, 40])
        self.assertEqual(self.body(), '{"ids":[12,40],"status":"tracked"}')
        self.c.repost([12])
        self.assertEqual(self.body(), '{"ids":[12],"repost":true}')
        self.c.stage(12, "making", "D:/v.mp4")
        self.assertEqual(self.body(), '{"id":12,"stage":"making","draftPath":"D:/v.mp4"}')
        self.c.stage(12, "posted")
        self.assertEqual(self.body(), '{"id":12,"stage":"posted"}')
        self.c.script(12, "scene one, scene two, the end")
        self.assertEqual(self.body(), '{"id":12,"script":"scene one, scene two, the end"}')

    def test_pack_body(self):
        sec = [{"title": "Threads", "parts": [{"label": "1/2", "text": "hi"}]}]
        self.c.pack(40, sec, "projects/myhomes/05 Marketing/posts/x.md")
        self.assertEqual(self.body(), '{"id":40,"project":"homes","pack":[{"title":"Threads","parts":'
                                      '[{"label":"1/2","text":"hi"}]}],"note":"projects/myhomes/05 Marketing/posts/x.md"}')
        self.c.pack(40, sec, "x.md", store_only=True)
        self.assertTrue(self.body().endswith(',"note":"x.md","send":false}'))

    def test_blog_paths(self):
        self.c.blog("s", "T", "sum")
        self.c.blog_list()
        self.c.blog_published(3)
        self.assertEqual([(x["method"], x["url"].split("3000")[1]) for x in self.rec.calls],
                         [("POST", "/api/blog-review"), ("GET", "/api/blog-review"), ("PATCH", "/api/blog-review")])
        self.assertEqual(self.body(), '{"id":3,"status":"published"}')

    def test_http_error(self):
        c = Client("homes", "http://x", "s", lambda *a, **k: (400, '{"error":"too long"}'))
        with self.assertRaises(IdeasError) as e:
            c.pull()
        self.assertIn("400", str(e.exception))


class TestCredentialsAndCli(unittest.TestCase):
    def test_env_file_then_env_wins(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / ".env.local"
            f.write_text('# c\nT_URL="https://live.test/"\nT_SECRET=from-file\n', encoding="utf-8")
            ic = ideas_cfg({"name": "t", "ideas": ideas_block(api={"env_file": str(f), "url_env": "T_URL",
                                                                    "secret_env": "T_SECRET"})})
            self.assertEqual(credentials(ic, {}), ("https://live.test", "from-file"))
            self.assertEqual(credentials(ic, {"T_SECRET": "env"})[1], "env")
            ic["api"]["secret_env"] = "MISSING"
            with self.assertRaises(IdeasError):
                credentials(ic, {})

    def run_cli(self, prof, argv, rec, env):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main([str(prof), *argv], rec, env)
        return code, out.getvalue(), err.getvalue()

    def test_pack_dry_run_and_send(self):
        with tempfile.TemporaryDirectory() as d:
            prof = Path(d) / "nf.yaml"
            prof.write_text(json.dumps({"name": "nf", "ideas": ideas_block()}), encoding="utf-8")
            note = Path(d) / "pack.md"
            note.write_text(NOTE, encoding="utf-8")
            env = {"T_URL": "http://site.test", "T_SECRET": "s"}
            rec = Recorder()
            code, out, _ = self.run_cli(prof, ["pack", "40", str(note), "--dry-run"], rec, env)
            self.assertEqual(code, 0)
            self.assertIn("3 messages for idea #40", out)
            self.assertEqual(rec.calls, [])
            code, _, _ = self.run_cli(prof, ["pack", "40", str(note)], rec, env)
            self.assertEqual(code, 0)
            body = json.loads(rec.calls[0]["body"])
            self.assertEqual((body["id"], body["project"], body["note"]), (40, "homes", "pack.md"))
            note.write_text(NOTE.replace("First post.", "Our crew posts."), encoding="utf-8")
            code, _, err = self.run_cli(prof, ["pack", "40", str(note)], rec, env)
            self.assertEqual(code, 1)
            self.assertIn("crew", err)
            self.assertEqual(len(rec.calls), 1)

    def test_pack_off_and_blog_off(self):
        with tempfile.TemporaryDirectory() as d:
            prof = Path(d) / "solar.yaml"
            prof.write_text(json.dumps({"name": "solar", "ideas": {"project": "solar"}}), encoding="utf-8")
            note = Path(d) / "n.md"
            note.write_text(NOTE, encoding="utf-8")
            rec = Recorder()
            env = {"IDEAS_API_SECRET": "s"}
            self.assertEqual(self.run_cli(prof, ["pack", "1", str(note), "--dry-run"], rec, env)[0], 1)
            self.assertEqual(self.run_cli(prof, ["blog-list"], rec, env)[0], 1)
            self.assertEqual(rec.calls, [])

    def test_push_dry_run_and_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            prof = Path(d) / "nf.yaml"
            prof.write_text(json.dumps({"name": "nf", "ideas": ideas_block()}), encoding="utf-8")
            batch = Path(d) / "b.json"
            batch.write_text(json.dumps({"batch": "b", "ideas": [{"title": "t", "hook": "h", "score": 20}]}),
                             encoding="utf-8")
            rec = Recorder()
            env = {"T_SECRET": "s"}
            code, _, err = self.run_cli(prof, ["push", str(batch)], rec, env)
            self.assertEqual(code, 1)
            self.assertIn("threshold", err)
            batch.write_text(json.dumps({"batch": "b", "ideas": [{"title": "t", "hook": "h", "score": 40}]}),
                             encoding="utf-8")
            self.assertEqual(self.run_cli(prof, ["push", str(batch), "--dry-run"], rec, env)[0], 0)
            self.assertEqual(rec.calls, [])
            self.assertEqual(self.run_cli(prof, ["push", str(batch)], rec, env)[0], 0)
            self.assertEqual(rec.calls[0]["url"], "http://localhost:3000/api/ideas")

    def test_defaults_not_shared(self):
        a = ideas_cfg({"name": "a", "output_dir": "A", "ideas": {"project": "homes"}})
        b = ideas_cfg({"name": "b", "output_dir": "B", "ideas": {"project": "agency"}})
        self.assertEqual((a["market_data"]["dir"], b["market_data"]["dir"]), ("A", "B"))

    def test_market_files(self):
        from datetime import date
        with tempfile.TemporaryDirectory() as d:
            for name in ("2026-11-01-viral-scout.md", "2026-11-14-viral-scout.md", "2026-10-01-ads-scout.md",
                         "notes.md"):
                (Path(d) / name).write_text("x", encoding="utf-8")
            ic = ideas_cfg({"name": "t", "output_dir": d, "ideas": {"project": "homes"}})
            m = market_files(ic, today=date(2026, 11, 15))
            self.assertEqual(m["viral-scout"]["date"], "2026-11-14")
            self.assertTrue(m["viral-scout"]["fresh"])
            self.assertFalse(m["ads-scout"]["fresh"])
            self.assertNotIn("search-demand", m)


if __name__ == "__main__":
    unittest.main()


class TestStatus(unittest.TestCase):
    """`ideas <p> status`: asks the bot service (STUDIO_SERVICE_URL, else the ideas API) about this business's bots."""

    def test_status_goes_to_the_service_and_can_send_a_test(self):
        class Svc:
            def __init__(self):
                self.calls = []

            def __call__(self, method, url, headers, body, timeout=60):
                self.calls.append((method, url, json.loads(body) if body else None))
                if method == "POST":
                    return 200, json.dumps({"ok": True, "bot": "studio-video", "message_id": 7})
                return 200, json.dumps({"checkedAt": "2026-11-15T16:00:00Z",
                                        "projects": [{"project": "homes", "ideas": {"where": "service"}}]})

        with tempfile.TemporaryDirectory() as d:
            prof = Path(d) / "nf.yaml"
            prof.write_text(json.dumps({"name": "nf", "ideas": ideas_block()}), encoding="utf-8")
            env = {"T_URL": "http://site.test", "T_SECRET": "s", "STUDIO_SERVICE_URL": "https://svc.test/"}
            rec = Svc()
            out = io.StringIO()
            with redirect_stdout(out):
                code = cli.main([str(prof), "status", "--test", "video"], rec, env)
            self.assertEqual(code, 0)
            self.assertEqual(rec.calls[0], ("POST", "https://svc.test/api/status", {"project": "homes", "role": "video"}))
            self.assertEqual(rec.calls[1][:2], ("GET", "https://svc.test/api/status?project=homes"))
            row = json.loads(out.getvalue())
            self.assertEqual(row["ideas"], {"where": "service"})
            self.assertEqual(row["test"]["message_id"], 7)
            # Without STUDIO_SERVICE_URL it asks the ideas API's own URL.
            rec2 = Svc()
            with redirect_stdout(io.StringIO()):
                cli.main([str(prof), "status"], rec2, {"T_URL": "http://site.test", "T_SECRET": "s"})
            self.assertEqual(rec2.calls[0][1], "http://site.test/api/status?project=homes")
