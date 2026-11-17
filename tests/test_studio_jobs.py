"""Studio jobs: lock, markers, tries, prompt assembly, the schedule plan. No Claude, no network, no Task Scheduler.

  python -m pytest tests/test_studio_jobs.py -q
"""
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from viral_scout import config  # noqa: E402
from viral_scout.jobs import prompts, runner, schedule  # noqa: E402
from viral_scout.jobs import settings as S  # noqa: E402
from viral_scout.jobs.state import Lock, Markers, period_key  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._root, self._vault = config.ROOT, S.vault
        config.ROOT = self.tmp                       # data/ (state, logs, lock) lands in the temp dir
        S.vault = lambda: str(self.tmp / "vault")
        (self.tmp / "vault" / "projects" / "demo").mkdir(parents=True)

    def tearDown(self):
        config.ROOT, S.vault = self._root, self._vault

    def profile(self, extra=None, name="demo"):
        vd = self.tmp / "vault" / "projects" / "demo"
        doc = {"name": name, "business": "Demo gutters",
               "studio": {"brand": "Demo Co", "vault_dir": str(vd), "instructions": str(vd / "studio-instructions.md"),
                          "cta": {"text": "Free checklist", "link": "https://demo.example/c"}},
               "jobs": {"owner": "Alex", **(extra or {})}}
        p = self.tmp / f"{name}.yaml"
        p.write_text(yaml.safe_dump(doc), encoding="utf-8")
        return config.load(str(p))


class LockTest(Base):
    def test_one_holder(self):
        p = self.tmp / "claude.lock"
        a, b = Lock(p, 3, "a"), Lock(p, 3, "b")
        self.assertTrue(a.acquire())
        self.assertFalse(b.acquire())
        self.assertEqual(b.info()["owner"], "a")
        a.release()
        self.assertTrue(b.acquire())
        b.release()
        self.assertFalse(p.exists())

    def test_stale_lock_is_taken_over(self):
        p = self.tmp / "claude.lock"
        p.write_text("{}", encoding="utf-8")
        old = time.time() - 4 * 3600
        os.utime(p, (old, old))
        with Lock(p, 3, "new") as got:
            self.assertTrue(got)
            self.assertEqual(Lock(p).info()["owner"], "new")
        self.assertFalse(p.exists())

    def test_fresh_lock_blocks(self):
        p = self.tmp / "claude.lock"
        p.write_text("{}", encoding="utf-8")
        with Lock(p, 3) as got:
            self.assertFalse(got)
        self.assertTrue(p.exists())      # someone else's lock is never removed


class MarkerTest(Base):
    def test_period_keys(self):
        d = datetime(2026, 11, 15, 7, 0)
        self.assertEqual(period_key("day", d), "2026-11-15")
        self.assertEqual(period_key("week", d), "2026-W46")
        self.assertIsNone(period_key(None, d))

    def test_done_and_tries(self):
        m = Markers(self.tmp, "film", "2026-11-15")
        self.assertFalse(m.done())
        self.assertEqual(m.tries(), 0)
        self.assertEqual(m.add_try(), 1)
        self.assertEqual(m.add_try(), 2)
        m.mark_done("slug")
        self.assertTrue(m.done())
        self.assertEqual(m.done_file.name, "film-2026-11-15.done")


class RunnerTest(Base):
    NOW = datetime(2026, 11, 15, 6, 0)

    def run_job(self, cfg, job, code=0, **kw):
        calls = []

        def execute(cmd, prompt, log, cwd):
            calls.append((cmd, prompt))
            return code
        res = runner.run(cfg, job, now=self.NOW, execute=execute, which=lambda _: "claude", **kw)
        return res, calls

    def test_off_by_default(self):
        (code, msg), calls = self.run_job(self.profile(), "film")
        self.assertEqual(code, 0)
        self.assertIn("off", msg)
        self.assertEqual(calls, [])

    def test_bare_on_key_works(self):
        cfg = self.profile()
        cfg["jobs"]["film"] = {True: True}       # what `film: {on: true}` becomes in YAML 1.1
        self.assertTrue(S.settings(cfg)["film"]["enabled"])

    def test_film_tries_then_stops(self):
        cfg = self.profile({"film": {"enabled": True}})
        for i in range(2):                       # Claude never writes the .done file: a failed day
            (code, _), calls = self.run_job(cfg, "film", code=1)
            self.assertEqual(code, 1)
            self.assertEqual(len(calls), 1)
        (code, msg), calls = self.run_job(cfg, "film")
        self.assertEqual(calls, [])
        self.assertIn("tries used", msg)
        self.assertFalse(S.lock_path().exists())

    def test_film_done_file_is_claudes(self):
        cfg = self.profile({"film": {"enabled": True}})
        (code, _), calls = self.run_job(cfg, "film")
        done = S.state_dir(cfg) / "film-2026-11-15.done"
        self.assertIn(str(done), calls[0][1])    # the prompt tells Claude where to write it
        self.assertFalse(done.exists())          # exit 0 alone does not count as delivered
        done.write_text("slug")
        (code, msg), calls = self.run_job(cfg, "film")
        self.assertEqual(calls, [])
        self.assertIn("already done", msg)

    def test_runner_marks_done_on_success(self):
        cfg = self.profile({"ideas": {"enabled": True}})
        self.run_job(cfg, "ideas")
        self.assertTrue((S.state_dir(cfg) / "ideas-2026-11-15.done").exists())
        (_, msg), calls = self.run_job(cfg, "ideas")
        self.assertEqual(calls, [])

    def test_prompt_says_how_to_type_commands(self):
        cfg = self.profile({"ideas": {"enabled": True}})
        text = prompts.assemble(cfg, "ideas", self.NOW)
        self.assertIn("no `PYTHONIOENCODING=…` or `$env:…` in front", text)   # a prefix fails --allowedTools (2026-11-16)

    def test_busy_lock_skips(self):
        cfg = self.profile({"ideas": {"enabled": True}})
        S.lock_path().write_text('{"owner": "other:film"}', encoding="utf-8")
        (code, msg), calls = self.run_job(cfg, "ideas", wait_minutes=0)
        self.assertEqual((code, calls), (0, []))
        self.assertIn("other:film", msg)
        self.assertTrue(S.lock_path().exists())

    def test_busy_lock_waits_then_runs(self):
        cfg = self.profile({"ideas": {"enabled": True}})
        lock = S.lock_path()
        lock.write_text('{"owner": "other:ideas"}', encoding="utf-8")
        slept = []

        def sleep(sec):                          # the other job finishes after two polls
            slept.append(sec)
            if len(slept) == 2:
                lock.unlink()
        (code, msg), calls = self.run_job(cfg, "ideas", sleep=sleep)
        self.assertEqual((code, len(calls), len(slept)), (0, 1, 2))
        self.assertFalse(lock.exists())

    def test_busy_lock_gives_up_after_wait(self):
        cfg = self.profile({"ideas": {"enabled": True}})
        S.lock_path().write_text('{"owner": "other:film"}', encoding="utf-8")
        slept = []
        (code, msg), calls = self.run_job(cfg, "ideas", wait_minutes=2, sleep=slept.append)
        self.assertEqual((code, calls, len(slept)), (0, [], 4))
        self.assertIn("after 2 min", msg)

    def test_notes_never_wait_for_lock(self):
        cfg = self.profile({"notes": {"enabled": True}})
        S.lock_path().write_text('{"owner": "other:film"}', encoding="utf-8")
        slept = []
        (_, msg), calls = self.run_job(cfg, "notes", pending=lambda c: 1, sleep=slept.append)
        self.assertEqual((calls, slept), ([], []))
        self.assertIn("busy", msg)

    def test_notes_only_when_waiting(self):
        cfg = self.profile({"notes": {"enabled": True}})
        (_, msg), calls = self.run_job(cfg, "notes", pending=lambda c: 0)
        self.assertEqual(calls, [])
        self.assertEqual(msg, "nothing waiting")
        (_, msg), calls = self.run_job(cfg, "notes", pending=lambda c: 2)
        self.assertEqual(len(calls), 1)
        (_, msg), calls = self.run_job(cfg, "notes", pending=lambda c: 1)
        self.assertEqual(len(calls), 1)          # no marker: notes runs whenever there is work

    def test_dry_run_changes_nothing(self):
        cfg = self.profile({"film": {"enabled": True}})
        (code, msg), calls = self.run_job(cfg, "film", dry=True)
        self.assertEqual((code, calls), (0, []))
        self.assertIn("--allowedTools", msg)
        self.assertEqual(Markers(S.state_dir(cfg), "film", "2026-11-15").tries(), 0)

    def test_claude_command(self):
        cfg = self.profile({"film": {"enabled": True}, "add_dirs": ["D:/repo/demo"]})
        cmd = runner.claude_command(cfg, "film")
        self.assertEqual(cmd[:4], ["claude", "-p", "--permission-mode", "acceptEdits"])
        dirs = [cmd[i + 1] for i, c in enumerate(cmd) if c == "--add-dir"]
        self.assertEqual(dirs[0], str(self.tmp / "vault"))
        self.assertIn("D:/repo/demo", dirs)


class PromptTest(Base):
    def test_core_plus_profile(self):
        cfg = self.profile({"instructions": {"film": "Never show a ladder."}})
        Path(cfg["studio"]["instructions"]).write_text("Reference film: first-film. Voice: cloned.", encoding="utf-8")
        p = prompts.assemble(cfg, "film", datetime(2026, 11, 15), "X:/done.done")
        self.assertIn("running unattended", p)                       # header
        self.assertIn("## Job: one finished film per day", p)       # core
        self.assertIn("Reference film: first-film", p)              # profile note
        self.assertIn("Never show a ladder.", p)                    # jobs.instructions.film
        self.assertIn("## Never (unattended)", p)                   # footer
        self.assertIn("python -m viral_scout ideas demo pull", p)
        self.assertIn("X:/done.done", p)
        self.assertIn("2026-11-15", p)
        self.assertNotRegex(p, r"\{\{\w+\}\}")                      # every placeholder filled

    def test_missing_note_is_said(self):
        cfg = self.profile()
        p = prompts.assemble(cfg, "script")
        self.assertIn("is missing", p)

    def test_every_job_assembles(self):
        cfg = self.profile()
        for j in S.JOBS:
            self.assertNotRegex(prompts.assemble(cfg, j), r"\{\{\w+\}\}", j)

    def test_allowed_tools_never_post(self):
        cfg = self.profile({"allowed_tools": {"all": ["Bash(python -m viral_scout publish demo post:*)",
                                                      "Bash(python -m viral_scout publish:*)"],
                                              "film": ["Bash(npx hyperframes:*)"]}})
        film = prompts.allowed_tools(cfg, "film")
        self.assertIn("Bash(npx hyperframes:*)", film)
        self.assertIn("Bash(python -m viral_scout publish demo plan:*)", film)
        self.assertIn("Bash(python -m viral_scout check demo:*)", film)
        self.assertIn("Bash(python -m viral_scout check demo:*)", prompts.allowed_tools(cfg, "notes"))
        self.assertFalse([t for t in film if "publish" in t and not t.endswith(" plan:*)")])
        self.assertNotIn("Bash(npx hyperframes:*)", prompts.allowed_tools(cfg, "ideas"))
        self.assertNotIn("Bash", " ".join(t for t in prompts.allowed_tools(cfg, "script") if "ideas" not in t))


class ScheduleTest(Base):
    def test_plan(self):
        cfg = self.profile({"ideas": {"enabled": True}, "notes": {"enabled": True}, "film": {"enabled": True},
                            "blog": {"enabled": True, "days": "Monday"}})
        cfg["publish"] = {"morning_pack": {"enabled": True, "hour": 9}}
        tasks = {t["job"]: t for t in schedule.plan(cfg)}
        self.assertEqual(set(tasks), {"ideas", "notes", "film", "blog", "post"})
        self.assertEqual(tasks["film"]["name"], "viral-scout demo.film")
        self.assertEqual(tasks["film"]["trigger"], {"type": "daily", "days": None, "at": "06:00", "repeat_minutes": 60, "repeat_hours": 17})
        self.assertEqual(tasks["notes"]["trigger"], {"type": "every", "minutes": 15})
        self.assertEqual(tasks["blog"]["trigger"]["type"], "weekly")
        self.assertEqual(tasks["blog"]["trigger"]["days"], ["Monday"])
        self.assertEqual(tasks["post"]["args"], "-Profile demo -Job post")
        self.assertEqual(tasks["film"]["time_limit_hours"], 3)
        import re
        for t in tasks.values():                 # the shape scripts/tasks.ps1 and /api/schedule accept
            self.assertRegex(t["name"], r"^viral-scout [\w.-]+$")
            self.assertTrue(re.match(r"^-Profile [\w.-]+ -Job \w+$", t["args"]))

    def test_nothing_on(self):
        self.assertEqual(schedule.plan(self.profile()), [])

    def test_bad_day(self):
        with self.assertRaises(ValueError):
            schedule.plan(self.profile({"blog": {"enabled": True, "days": "Funday"}}))

    def test_install_command_is_printed_not_run(self):
        c = schedule.install_command("demo")
        self.assertIn("schedule-studio.ps1", c)
        self.assertIn("-Profile demo", c)
        self.assertNotIn("\\", c)                # forward slashes: a Claude Code "!" prompt strips backslashes


class IdeaSchedule(unittest.TestCase):
    """The dashboard's Idea generator: jobs.ideas edited in the profile file (comments kept)."""

    def setUp(self):
        from viral_scout import profile_edit
        self.pe = profile_edit
        self.tmp = Path(tempfile.mkdtemp())
        self._root, self._profiles = config.ROOT, config.PROFILES
        config.ROOT, config.PROFILES = self.tmp, self.tmp / "profiles"
        config.PROFILES.mkdir()
        # The file is "copy", its name: line says "demo": edits must go to the FILE, never to profiles/demo.yaml.
        self.text = ("# keep this comment\nname: demo\ntopic: test\nideas:\n  project: demo\n"
                     "  daily: {count: 4, at: '07:45', add_dirs: [D:/repo/site]}\n")
        (config.PROFILES / "copy.yaml").write_text(self.text, encoding="utf-8")
        (config.PROFILES / "demo.yaml").write_text("name: demo\ntopic: other\n", encoding="utf-8")

    def tearDown(self):
        config.ROOT, config.PROFILES = self._root, self._profiles

    def test_writes_the_file_named_on_the_command_line(self):
        from viral_scout.jobs import cli
        cli.set_ideas("copy", ["--enabled", "1", "--at", "09:10", "--days", "Thursday,Monday", "--count", "3"])
        got = yaml.safe_load((config.PROFILES / "copy.yaml").read_text(encoding="utf-8"))
        self.assertEqual(got["jobs"]["ideas"], {"enabled": True, "at": "09:10", "days": ["Monday", "Thursday"], "count": 3})
        self.assertIn("# keep this comment", (config.PROFILES / "copy.yaml").read_text(encoding="utf-8"))
        self.assertEqual((config.PROFILES / "demo.yaml").read_text(encoding="utf-8"), "name: demo\ntopic: other\n")

    def test_bad_values_change_nothing(self):
        from viral_scout.jobs import cli
        for args in (["--at", "9:5"], ["--days", "Funday"], ["--days", ""], ["--count", "x"]):
            with self.assertRaises(ValueError):
                cli.set_ideas("copy", args)
        self.assertEqual((config.PROFILES / "copy.yaml").read_text(encoding="utf-8"), self.text)

    def test_backups_in_the_same_second_do_not_overwrite(self):
        from viral_scout.jobs import cli
        cli.set_ideas("copy", ["--at", "09:00"])
        cli.set_ideas("copy", ["--at", "09:30"])
        backups = sorted((self.tmp / "data" / "profile-backups").glob("copy-*.yaml"))
        self.assertEqual(len(backups), 2)
        self.assertIn(self.text, [b.read_text(encoding="utf-8") for b in backups])   # the original survives

    def test_jobs_get_the_older_daily_folders(self):
        cfg = config.load("copy")
        self.assertEqual(S.settings(cfg)["add_dirs"], ["D:/repo/site"])

    def test_overview_suggests_the_older_daily_time_until_set(self):
        from viral_scout.jobs import cli
        row = next(r for r in cli.overview() if r["profile"] == "copy")
        self.assertEqual((row["configured"], row["at"], row["count"], row["days"]), (False, "07:45", 4, "daily"))
        cli.set_ideas("copy", ["--enabled", "0", "--at", "10:00", "--count", "2"])
        row = next(r for r in cli.overview() if r["profile"] == "copy")
        self.assertEqual((row["configured"], row["at"], row["count"]), (True, "10:00", 2))


if __name__ == "__main__":
    unittest.main()


def test_jobs_api_reads_the_ideas_api_block():
    from viral_scout.jobs import settings as js
    cfg = {"name": "myhomes", "ideas": {"project": "homes",
           "api": {"env_file": "D:/x/.env.local", "url_env": "MY_URL", "secret_env": "MY_SECRET"}}}
    api = js.settings(cfg)["api"]
    assert api == {"url_env": "MY_URL", "secret_env": "MY_SECRET", "env_file": "D:/x/.env.local", "project": "homes"}


def test_job_env_makes_viral_scout_importable_from_any_cwd(monkeypatch):
    from viral_scout import config
    from viral_scout.jobs import runner
    monkeypatch.setenv("PYTHONPATH", "X:/other")
    env = runner._env()
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(config.ROOT)
    assert "X:/other" in env["PYTHONPATH"]
    assert env["PYTHONIOENCODING"] == "utf-8"
