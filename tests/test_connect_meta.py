"""Connect Meta: Facebook sign-in → keys, against a fake Graph API (no network).

python -m unittest tests.test_connect_meta -v
"""
import os
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

from viral_scout import connect_meta as cm
from viral_scout import keys


class R:
    def __init__(self, d, ok=True):
        self._d, self.ok, self.text = d, ok, str(d)

    def json(self):
        return self._d


USER, PAGE, SYS = "EAAuser", "EAApage", "EAAsystem"
NEVER = {"is_valid": True, "type": "PAGE", "expires_at": 0, "data_access_expires_at": 0, "scopes": cm.SCOPES}
SIXTY = {"is_valid": True, "type": "USER", "expires_at": 1_900_000_000, "data_access_expires_at": 1_900_000_000,
         "scopes": cm.SCOPES}


def fake_graph(ig_accounts=1, ad_accounts=1, library_ok=True):
    pages = [{"id": f"p{i}", "name": f"Page {i}", "instagram_business_account": {"id": f"17{i}", "username": f"brand{i}"}}
             for i in range(ig_accounts)] + [{"id": "px", "name": "Old page"}]
    ads = [{"id": f"act_{i}", "account_id": str(100 + i), "name": f"Ads {i}", "currency": "USD", "account_status": 1}
           for i in range(ad_accounts)]

    def get(url, params=None, timeout=None):
        path = url.split(cm.VERSION + "/", 1)[-1]
        p = params or {}
        if path == "oauth/access_token":
            return R({"access_token": "short" if "code" in p else USER, "expires_in": 5_184_000})
        if path == "debug_token":
            d = {PAGE: NEVER, SYS: {**NEVER, "type": "SYSTEM_USER"}, USER: SIXTY}.get(
                p["input_token"], {"is_valid": False, "error": {"message": "expired"}})
            return R({"data": d})
        if path == "me/accounts":
            return R({"data": pages})
        if path == "me/adaccounts":
            return R({"data": ads})
        if path.startswith("p") and p.get("fields") == "access_token":
            return R({"id": path, "access_token": PAGE})
        if path == "ads_archive":
            return R({"data": []}) if library_ok else R({"error": {"message": "identity not confirmed"}}, ok=False)
        raise AssertionError(f"unexpected call {path}")
    return get


class ConnectMeta(unittest.TestCase):
    def setUp(self):
        self.env = Path(tempfile.mkdtemp()) / ".env"
        clean = {k: v for k, v in os.environ.items() if not k.startswith(("META_", "IG_GRAPH_"))}
        for p in (mock.patch.dict(os.environ, {**clean, "META_APP_ID": "123", "META_APP_SECRET": "sec"}, clear=True),
                  mock.patch.object(keys, "ENV", self.env),
                  mock.patch.object(cm.config, "load_env", lambda: None)):
            p.start()
            self.addCleanup(p.stop)

    def graph(self, **kw):
        p = mock.patch.object(cm.requests, "get", fake_graph(**kw))
        p.start()
        self.addCleanup(p.stop)

    def test_login_url_asks_for_every_scope_or_uses_config(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(cm.login_url("123", "http://localhost:8765/", "st")).query)
        self.assertEqual(q["scope"][0].split(","), cm.SCOPES)
        self.assertEqual(q["redirect_uri"], ["http://localhost:8765/"])
        os.environ["META_LOGIN_CONFIG_ID"] = "999"
        q = urllib.parse.parse_qs(urllib.parse.urlparse(cm.login_url("123", "http://localhost:8765/", "st")).query)
        self.assertEqual(q["config_id"], ["999"])
        self.assertNotIn("scope", q)

    def test_exchange_returns_long_lived(self):
        self.graph()
        self.assertEqual(cm.exchange("123", "sec", "code", "http://localhost:8765/"), (USER, 5_184_000))

    def test_single_accounts_fill_every_key(self):
        self.graph()
        os.environ["META_USER_TOKEN"] = USER
        out = cm.use(auto=True)
        self.assertEqual(os.environ["IG_GRAPH_TOKEN"], PAGE)
        self.assertEqual(os.environ["IG_GRAPH_USER_ID"], "170")
        self.assertEqual(os.environ["META_AD_ACCOUNT_ID"], "act_100")
        self.assertEqual(os.environ["META_ADS_TOKEN"], USER)
        self.assertEqual(os.environ["META_AD_LIBRARY_TOKEN"], USER)
        self.assertIn("expires: never", out[0])
        text = self.env.read_text(encoding="utf-8")
        self.assertIn(f"IG_GRAPH_TOKEN={PAGE}", text)
        self.assertIn("META_AD_ACCOUNT_ID=act_100", text)

    def test_several_accounts_wait_for_a_pick(self):
        self.graph(ig_accounts=2, ad_accounts=2, library_ok=False)
        os.environ["META_USER_TOKEN"] = USER
        out = "\n".join(cm.use(auto=True))
        self.assertNotIn("IG_GRAPH_USER_ID", os.environ)
        self.assertNotIn("META_AD_ACCOUNT_ID", os.environ)
        for s in ("@brand0", "@brand1", "not available"):
            self.assertIn(s, out)
        cm.use(ig="@brand1", ad_account="act_101")
        self.assertEqual(os.environ["IG_GRAPH_USER_ID"], "171")
        self.assertEqual(os.environ["META_AD_ACCOUNT_ID"], "act_101")
        with self.assertRaisesRegex(cm.MetaError, "No Instagram"):
            cm.use(ig="@nobody")

    def test_never_expiring_ads_token_is_kept(self):
        self.graph()
        os.environ["META_USER_TOKEN"] = USER
        os.environ["META_ADS_TOKEN"] = SYS
        out = "\n".join(cm.use(auto=True))
        self.assertEqual(os.environ["META_ADS_TOKEN"], SYS)
        self.assertIn("kept", out)
        cm.use(ad_account="100", replace_ads_token=True)
        self.assertEqual(os.environ["META_ADS_TOKEN"], USER)

    def test_accounts_lists_no_tokens(self):
        self.graph()
        found = cm.accounts(USER)
        self.assertNotIn(PAGE, str(found))
        self.assertNotIn(USER, str(found))
        self.assertEqual(found["pages_without_instagram"], ["Old page"])

    def test_missing_app_keys(self):
        del os.environ["META_APP_SECRET"]
        with self.assertRaisesRegex(cm.MetaError, "META_APP_SECRET"):
            cm.connect(open_browser=False, timeout=0)


if __name__ == "__main__":
    unittest.main()
