"""Connect Google / TikTok and the shared loopback callback, against fake APIs (no network).

python -m unittest tests.test_connect_google_tiktok -v
"""
import os
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request
from pathlib import Path
from unittest import mock

from viral_scout import connect_google as cg
from viral_scout import connect_tiktok as ct
from viral_scout import keys, loopback


class R:
    def __init__(self, d, ok=True):
        self._d, self.ok, self.text, self.status_code = d, ok, str(d), 200 if ok else 400

    def json(self):
        return self._d


def hit_when_ready(status_file, port_of_url=None, path="/", params=None):
    """Act as the browser: wait for the waiting status, then call the redirect with the right state."""
    def go():
        for _ in range(100):
            if status_file.exists() and '"waiting"' in status_file.read_text():
                break
            time.sleep(0.05)
        import json
        url = json.loads(status_file.read_text())["url"]
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        redirect = q["redirect_uri"][0]
        urllib.request.urlopen(f"{redirect.rstrip('/')}{path}?" + urllib.parse.urlencode({**params, "state": q["state"][0]}))
    t = threading.Thread(target=go)
    t.start()
    return t


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        clean = {k: v for k, v in os.environ.items()
                 if not k.startswith(("YT_OAUTH_", "GOOGLE_ADS_", "TIKTOK_"))}
        for p in (mock.patch.dict(os.environ, clean, clear=True), mock.patch.object(keys, "ENV", self.dir / ".env"),
                  mock.patch.object(cg.config, "load_env", lambda: None),
                  mock.patch.object(ct, "PENDING", self.dir / "pending")):
            p.start()
            self.addCleanup(p.stop)


class Loopback(unittest.TestCase):
    def test_parse_pasted(self):
        q = loopback.parse_pasted("https://example.com/cb?auth_code=abc&code=abc&state=s1", "s1")
        self.assertEqual(q["auth_code"], "abc")
        self.assertEqual(loopback.parse_pasted("rawcode")["auth_code"], "rawcode")
        with self.assertRaises(loopback.CallbackError):
            loopback.parse_pasted("https://example.com/cb?auth_code=abc&state=other", "s1")

    def test_wrong_state_is_ignored_then_right_one_wins(self):
        srv, got = loopback.server(0, "good")
        port = srv.server_address[1]

        def browser():
            time.sleep(0.2)
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/?state=bad&code=x")
            except Exception:  # noqa: BLE001 (404 expected)
                pass
            urllib.request.urlopen(f"http://127.0.0.1:{port}/?state=good&code=y")
        threading.Thread(target=browser).start()
        self.assertEqual(loopback.wait(srv, got, 10)["code"], "y")


class Google(Base):
    def test_one_consent_fills_both_refresh_tokens(self):
        os.environ.update({"YT_OAUTH_CLIENT_ID": "cid", "YT_OAUTH_CLIENT_SECRET": "sec"})
        posted = {}

        def post(url, data=None, **kw):
            posted.update(data)
            return R({"refresh_token": "1//r", "access_token": "a", "scope": " ".join(cg.scopes_for())})
        sf = self.dir / "google.json"
        with mock.patch.object(cg.requests, "post", post), mock.patch.object(cg, "accounts",
                                                                             lambda: {"channel": {"id": "UC1", "title": "Brand"},
                                                                                      "ads_customers": ["111"], "errors": []}):
            t = hit_when_ready(sf, params={"code": "authcode"})
            out = cg.connect(open_browser=False, timeout=10, status_file=str(sf))
            t.join()
        self.assertEqual(os.environ["YT_OAUTH_REFRESH_TOKEN"], "1//r")
        self.assertEqual(os.environ["GOOGLE_ADS_REFRESH_TOKEN"], "1//r")
        self.assertEqual(posted["code"], "authcode")
        self.assertIn("code_verifier", posted)
        self.assertIn("Channel: Brand", "\n".join(out))
        self.assertNotIn("Not allowed", "\n".join(out))
        self.assertIn('"done"', sf.read_text())

    def test_other_ads_client_is_repointed(self):
        os.environ.update({"YT_OAUTH_CLIENT_ID": "cid", "YT_OAUTH_CLIENT_SECRET": "sec",
                           "GOOGLE_ADS_CLIENT_ID": "other", "GOOGLE_ADS_CLIENT_SECRET": "x"})
        out = cg.save("1//r", "cid", "sec")
        self.assertEqual(os.environ["GOOGLE_ADS_CLIENT_ID"], "cid")
        self.assertTrue(any("client this sign-in used" in o for o in out))

    def test_only_youtube_scopes(self):
        self.assertTrue(all("adwords" not in s for s in cg.scopes_for("youtube")))
        self.assertTrue(any("adwords" in s for s in cg.scopes_for()))

    def test_missing_client(self):
        with self.assertRaisesRegex(cg.GoogleError, "YT_OAUTH_CLIENT_ID"):
            cg.connect(open_browser=False, timeout=0)


def tiktok_api(advertisers):
    def post(url, json=None, **kw):
        assert url.endswith("oauth2/access_token/") and json["auth_code"] == "tc"
        return R({"code": 0, "data": {"access_token": "tt-token", "advertiser_ids": [a[0] for a in advertisers]}})

    def get(url, params=None, headers=None, **kw):
        assert url.endswith("oauth2/advertiser/get/") and headers["Access-Token"] == "tt-token"
        return R({"code": 0, "data": {"list": [{"advertiser_id": a, "advertiser_name": n} for a, n in advertisers]}})
    return post, get


class TikTok(Base):
    def setUp(self):
        super().setUp()
        os.environ.update({"TIKTOK_APP_ID": "app", "TIKTOK_APP_SECRET": "sec"})

    def run_loopback(self, advertisers):
        post, get = tiktok_api(advertisers)
        sf = self.dir / "tiktok.json"
        with mock.patch.object(ct.requests, "post", post), mock.patch.object(ct.requests, "get", get):
            t = hit_when_ready(sf, params={"auth_code": "tc", "code": "tc"})
            out = ct.connect(open_browser=False, port=18766, timeout=10, status_file=str(sf))
            t.join()
        return "\n".join(out)

    def test_one_advertiser_is_picked(self):
        out = self.run_loopback([("7001", "Brand ads")])
        self.assertEqual(os.environ["TIKTOK_ADS_TOKEN"], "tt-token")
        self.assertEqual(os.environ["TIKTOK_ADVERTISER_ID"], "7001")
        self.assertIn("Brand ads", out)

    def test_several_advertisers_wait_for_a_pick(self):
        out = self.run_loopback([("7001", "A"), ("7002", "B")])
        self.assertNotIn("TIKTOK_ADVERTISER_ID", os.environ)
        self.assertIn("pick the default", out)
        post, get = tiktok_api([("7001", "A"), ("7002", "B")])
        with mock.patch.object(ct.requests, "get", get):
            ct.use("7002")
            self.assertEqual(os.environ["TIKTOK_ADVERTISER_ID"], "7002")
            with self.assertRaisesRegex(ct.TikTokError, "No advertiser"):
                ct.use("9999")

    def test_https_redirect_goes_through_paste(self):
        os.environ["TIKTOK_APP_REDIRECT_URI"] = "https://example.com/tiktok"
        sf = self.dir / "tiktok.json"
        out = ct.connect(open_browser=False, status_file=str(sf))
        self.assertIn("pasted address", out[0])
        self.assertIn('"paste"', sf.read_text())
        state = ct.PENDING.read_text()
        post, get = tiktok_api([("7001", "Brand ads")])
        with mock.patch.object(ct.requests, "post", post), mock.patch.object(ct.requests, "get", get):
            with self.assertRaises(ct.TikTokError):
                ct.connect(paste="https://example.com/tiktok?auth_code=tc&state=wrong")
            ct.connect(paste=f"https://example.com/tiktok?auth_code=tc&code=tc&state={state}")
        self.assertEqual(os.environ["TIKTOK_ADS_TOKEN"], "tt-token")
        self.assertFalse(ct.PENDING.exists())


if __name__ == "__main__":
    unittest.main()
