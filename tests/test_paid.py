import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from viral_scout import config
from viral_scout.paid import cli, core

TODAY = date(2026, 11, 21)          # 10 days left in November, today included


def snap(spend=50.0, campaigns=None, currency="USD", **plat):
    return {"pulled": "x", "platforms": {"meta": {"ok": True, "currency": currency, "month_spend": spend,
                                                  "campaigns": campaigns or []}, **plat}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        p = mock.patch.object(config, "ROOT", self.tmp)
        p.start()
        self.addCleanup(p.stop)
        self.cfg = {"name": "demo", "paid": {"monthly_cap_usd": 300, "accounts": {"meta": "act_1"}}}


class CapTest(Base):

    def test_days_left_counts_today(self):
        self.assertEqual(core.days_left(TODAY), 10)
        self.assertEqual(core.days_left(date(2026, 11, 30)), 1)

    def test_projection_counts_running_daily_and_lifetime_budgets(self):
        s = snap(50, [{"id": "1", "name": "a", "running": True, "daily_budget": 10},
                      {"id": "2", "name": "b", "running": True, "budget_remaining": 40},
                      {"id": "3", "name": "c", "running": False, "daily_budget": 99}])
        self.assertEqual(core.committed(s, TODAY)[:2], (50.0, 140.0))     # 10×10 + 40; the paused one doesn't count
        ok, msg, n = core.check(self.cfg, s, daily_usd=11, today=TODAY)   # 50 + 140 + 110 = 300
        self.assertTrue(ok, msg)
        ok, msg, n = core.check(self.cfg, s, daily_usd=12, today=TODAY)   # 310 > 300
        self.assertFalse(ok)
        self.assertIn("over the cap", msg)

    def test_changing_a_running_campaign_leaves_its_old_budget_out(self):
        s = snap(50, [{"id": "1", "name": "a", "running": True, "daily_budget": 20}])
        ok, _, n = core.check(self.cfg, s, daily_usd=25, skip=("meta", "1"), today=TODAY)
        self.assertEqual(n["projected"], 300.0)
        self.assertTrue(ok)

    def test_refuses_without_cap_snapshot_usd_or_a_readable_account(self):
        self.assertFalse(core.check({"name": "demo", "paid": {}}, snap(), today=TODAY)[0])
        self.assertFalse(core.check(self.cfg, None, today=TODAY)[0])
        self.assertIn("isn't USD", core.check(self.cfg, snap(currency="EUR"), today=TODAY)[1])
        broken = snap(tiktok={"ok": False, "error": "token"})
        cfg = {"name": "demo", "paid": {"monthly_cap_usd": 300, "accounts": {"meta": "act_1", "tiktok": "7"}}}
        self.assertIn("couldn't read tiktok", core.check(cfg, broken, today=TODAY)[1])

    def test_accounts_fall_back_to_perf_ids_never_to_env(self):
        with mock.patch.dict("os.environ", {"META_AD_ACCOUNT_ID": "act_other"}):
            s = core.settings({"name": "x", "perf": {"meta_ad_account_id": "act_9"}})
            self.assertEqual(s["accounts"], {"meta": "act_9"})
            self.assertEqual(core.settings({"name": "x"})["accounts"], {})

    def test_resume_over_cap_is_refused_and_logged_pause_always_works(self):
        camp = {"id": "1", "name": "a", "running": False, "daily_budget": 40, "budget_level": "campaign"}
        fake = mock.Mock()
        with mock.patch.object(cli, "pull", return_value=snap(50, [camp])), mock.patch.dict(cli.MODS, {"meta": fake}), \
                mock.patch.object(core, "days_left", return_value=10):
            code, msg = cli.change(self.cfg, "resume", "meta", "1", by="test")   # 50 + 400 > 300
            self.assertEqual(code, 3)
            fake.set_status.assert_not_called()
            code, msg = cli.change(self.cfg, "pause", "meta", "1", by="test")
            self.assertEqual(code, 0)
            fake.set_status.assert_called_once_with("act_1", "1", False)
        log = core.read_log(self.cfg)
        self.assertEqual([r["action"] for r in log], ["pause", "refused"])
        self.assertEqual(log[0]["by"], "test")


class BackstopTest(Base):
    def test_pauses_only_campaigns_created_during_the_run_newest_first(self):
        from datetime import datetime, timezone
        from viral_scout.paid import ask
        old = {"id": "1", "name": "old", "running": True, "daily_budget": 10, "created": "2026-11-01T10:00:00+0000"}
        new1 = {"id": "2", "name": "new1", "running": True, "daily_budget": 30, "created": "2026-11-21T10:01:00+0000"}
        new2 = {"id": "3", "name": "new2", "running": True, "daily_budget": 30, "created": "2026-11-21T10:02:00+0000"}
        snaps = [snap(50, [old, new1, new2]), snap(50, [old, new1, dict(new2, running=False)])]
        fake = mock.Mock()
        with mock.patch("viral_scout.paid.cli.pull", side_effect=snaps + snaps[-1:] * 3),                 mock.patch.dict("viral_scout.paid.cli.MODS", {"meta": fake}), mock.patch.object(core, "days_left", return_value=10):
            paused = ask.enforce(self.cfg, datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc))
        # 50 + 700 > 300 → new2 paused; 50 + 400 still > 300 → new1 paused too; "old" is never touched
        self.assertEqual(paused, ["new2", "new1"])
        self.assertEqual([c.args[1] for c in fake.set_status.call_args_list], ["3", "2"])

    def test_nothing_paused_when_under_the_cap(self):
        from datetime import datetime, timezone
        from viral_scout.paid import ask
        s = snap(10, [{"id": "2", "name": "n", "running": True, "daily_budget": 5, "created": "2026-11-21T10:01:00+0000"}])
        with mock.patch("viral_scout.paid.cli.pull", return_value=s), mock.patch.object(core, "days_left", return_value=10):
            self.assertEqual(ask.enforce(self.cfg, datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc)), [])

    def test_headless_tools_are_narrow(self):
        from viral_scout.paid import ask
        t = ask.tools("demo")
        self.assertIn("Bash(python -m viral_scout paid demo:*)", t)
        self.assertNotIn("Bash", t)
        self.assertFalse([x for x in t if x.startswith("Bash(") and "paid demo" not in x])


if __name__ == "__main__":
    unittest.main()
