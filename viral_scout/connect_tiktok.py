"""Connect TikTok: authorize your advertiser accounts once → TIKTOK_ADS_TOKEN (long-term) + TIKTOK_ADVERTISER_ID.

  python -m viral_scout keys connect tiktok [--no-browser] [--port 8766]   sign in, callback on this PC
  python -m viral_scout keys connect tiktok --paste "<address you landed on>"   when the redirect isn't localhost
  python -m viral_scout keys tiktok accounts                                advertiser accounts the token reaches (JSON)
  python -m viral_scout keys tiktok use --advertiser ID                     pick the default one

Once (by hand, TikTok reviews it): TikTok API for Business → My apps → create a developer app with the Ad Account
Management, Campaign Management and Reporting permissions, Advertiser redirect URL = TIKTOK_APP_REDIRECT_URI
(default http://localhost:8766/). Save its App ID and Secret as TIKTOK_APP_ID / TIKTOK_APP_SECRET.
If TikTok only accepts an https redirect URL, register any https address you control, set TIKTOK_APP_REDIRECT_URI
to it, sign in, then paste the address the browser lands on (it holds auth_code; it works even on a 404 page).

The token from the advertiser authorization has no expiry date; it stops when you revoke the app's access.
"""
import json
import os
import secrets
import urllib.parse
import webbrowser

import requests

from . import config, loopback

API = "https://business-api.tiktok.com/open_api/v1.3/"
PORTAL = "https://business-api.tiktok.com/portal/auth"
REDIRECT = "http://localhost:8766/"
PENDING = config.ROOT / "data" / "connect-tiktok-state"     # the state of a sign-in waiting for a pasted address


class TikTokError(RuntimeError):
    pass


def _app():
    config.load_env()
    aid, sec = os.environ.get("TIKTOK_APP_ID", ""), os.environ.get("TIKTOK_APP_SECRET", "")
    if not aid or not sec:
        raise TikTokError("Set TIKTOK_APP_ID and TIKTOK_APP_SECRET first (TikTok API for Business → My apps → your app). "
                          "See docs/setup.md#connect-tiktok.")
    return aid, sec, os.environ.get("TIKTOK_APP_REDIRECT_URI") or REDIRECT


def _call(method, path, token=None, **body):
    h = {"Access-Token": token} if token else {}
    try:
        if method == "GET":
            r = requests.get(API + path, params={k: json.dumps(v) if isinstance(v, (list, dict)) else v
                                                 for k, v in body.items()}, headers=h, timeout=30)
        else:
            r = requests.post(API + path, json=body, headers=h, timeout=30)
        d = r.json()
    except (requests.RequestException, ValueError) as e:
        raise TikTokError(f"TikTok {path}: {e}") from e
    if d.get("code") != 0:
        raise TikTokError(f"TikTok {path}: {d.get('message', 'error')}")
    return d.get("data") or {}


def login_url(app_id, redirect, state):
    return PORTAL + "?" + urllib.parse.urlencode({"app_id": app_id, "state": state, "redirect_uri": redirect})


def exchange(app_id, secret, auth_code):
    """auth_code → {access_token, advertiser_ids, scope}."""
    return _call("POST", "oauth2/access_token/", app_id=app_id, secret=secret, auth_code=auth_code)


def accounts(token=None):
    aid, sec, _ = _app()
    token = token or os.environ.get("TIKTOK_ADS_TOKEN", "")
    if not token:
        raise TikTokError("Not connected: run python -m viral_scout keys connect tiktok")
    rows = _call("GET", "oauth2/advertiser/get/", token, app_id=aid, secret=sec).get("list") or []
    return [{"advertiser_id": str(a.get("advertiser_id")), "name": a.get("advertiser_name", "")} for a in rows]


def use(advertiser=None, auto=False):
    from . import keys
    found = accounts()
    pick = next((a for a in found if a["advertiser_id"] == str(advertiser)), None) if advertiser else (
        found[0] if auto and len(found) == 1 else None)
    if advertiser and not pick:
        raise TikTokError(f"No advertiser {advertiser} in this authorization. Found: "
                          + (", ".join(f"{a['advertiser_id']} ({a['name']})" for a in found) or "none"))
    if pick:
        keys.set_key("TIKTOK_ADVERTISER_ID", pick["advertiser_id"])
        return [f"Advertiser: {pick['name']} → TIKTOK_ADVERTISER_ID. Each business's own account is set on its Paid ads page."]
    if found:
        return ["Several advertiser accounts, pick the default: python -m viral_scout keys tiktok use --advertiser ID  ("
                + ", ".join(f"{a['advertiser_id']} {a['name']}" for a in found) + ")"]
    return ["No advertiser accounts were authorized: sign in again and tick them."]


def finish(auth_code):
    from . import keys
    aid, sec, _ = _app()
    d = exchange(aid, sec, auth_code)
    if not d.get("access_token"):
        raise TikTokError("TikTok returned no access token")
    keys.set_key("TIKTOK_ADS_TOKEN", d["access_token"])
    lines = [f"Connected → TIKTOK_ADS_TOKEN (no expiry; {len(d.get('advertiser_ids') or [])} advertiser account(s))"]
    return lines + use(auto=True)


def connect(open_browser=True, port=None, timeout=300, paste=None, status_file=None):
    note = loopback.Status(status_file)
    try:
        aid, sec, redirect = _app()
        if paste is not None:                         # second half of a sign-in whose redirect isn't on this PC
            want = PENDING.read_text(encoding="utf-8").strip() if PENDING.exists() else None
            try:
                q = loopback.parse_pasted(paste, want)
            except loopback.CallbackError as e:
                raise TikTokError(str(e)) from e
            code = q.get("auth_code") or q.get("code")
            if not code:
                raise TikTokError("No auth_code in that address. Copy the whole address from the browser's bar.")
            lines = finish(code)
            PENDING.unlink(missing_ok=True)
            note("done", "\n".join(lines))
            return lines
        state = secrets.token_urlsafe(16)
        u = urllib.parse.urlparse(redirect)
        local = u.hostname in ("localhost", "127.0.0.1")
        if port and local:
            redirect = f"{u.scheme}://{u.hostname}:{port}{u.path or '/'}"
            u = urllib.parse.urlparse(redirect)
        url = login_url(aid, redirect, state)
        if not local:
            PENDING.parent.mkdir(parents=True, exist_ok=True)
            PENDING.write_text(state, encoding="utf-8")
            note("paste", "Sign in, then paste the address the browser lands on.", url=url)
            print("Open this URL, authorize the advertiser accounts, then run\n  python -m viral_scout keys connect "
                  "tiktok --paste \"<the address you land on>\"\n" + url, flush=True)
            if open_browser:
                webbrowser.open(url)
            return ["Waiting for the pasted address (keys connect tiktok --paste ...)"]
        try:
            srv, got = loopback.server(u.port or 80, state)
        except loopback.CallbackError as e:
            raise TikTokError(str(e)) from e
        note("waiting", "Waiting for the TikTok sign-in in the browser…", url=url)
        print("Open this URL and authorize every advertiser account viral-scout should read:\n" + url, flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            got = loopback.wait(srv, got, timeout)
        except loopback.CallbackError as e:
            raise TikTokError(str(e)) from e
        code = got.get("auth_code") or got.get("code")
        if not code:
            raise TikTokError("No auth_code received (the authorization was cancelled?)")
        lines = finish(code)
        note("done", "\n".join(lines))
        return lines
    except TikTokError as e:
        note("failed", str(e))
        raise
