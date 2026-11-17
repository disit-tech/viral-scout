"""Connect Google: one Google sign-in for YouTube Analytics (your channel) and the Google Ads API (your ads).

  python -m viral_scout keys connect google [--no-browser] [--port N] [--only youtube|ads]
  python -m viral_scout keys google accounts      your channel and the Google Ads accounts the sign-in reaches (JSON)

Before, `perf auth youtube` and `paid auth google` were two consents with two refresh tokens. This asks once for
every scope and saves the same refresh token as YT_OAUTH_REFRESH_TOKEN and GOOGLE_ADS_REFRESH_TOKEN (both old
commands still work).

Once (by hand): a Google Cloud project with YouTube Analytics API, YouTube Data API v3 and Google Ads API enabled,
an OAuth consent screen (published "In production", or the refresh token stops after 7 days) and an OAuth client
of type Desktop app, saved as YT_OAUTH_CLIENT_ID / YT_OAUTH_CLIENT_SECRET. Desktop clients accept any loopback
port, so nothing else has to be registered. Google Ads calls may also need GOOGLE_ADS_DEVELOPER_TOKEN (Google's
review; it can't be automated).
"""
import base64
import hashlib
import os
import secrets
import webbrowser

import requests

from . import config, loopback
from .perf import youtube as yt
from .paid import google as gads

SCOPES = {"youtube": yt.SCOPES, "ads": gads.SCOPES}


class GoogleError(RuntimeError):
    pass


def _client():
    config.load_env()
    cid = os.environ.get("YT_OAUTH_CLIENT_ID") or os.environ.get("GOOGLE_ADS_CLIENT_ID")
    sec = os.environ.get("YT_OAUTH_CLIENT_SECRET") or os.environ.get("GOOGLE_ADS_CLIENT_SECRET")
    if not cid or not sec:
        raise GoogleError("Set YT_OAUTH_CLIENT_ID and YT_OAUTH_CLIENT_SECRET first (Google Cloud → Credentials → OAuth "
                          "client ID → Desktop app). See docs/setup.md#connect-google.")
    return cid, sec


def scopes_for(only=None):
    parts = [only] if only else ["youtube", "ads"]
    return [s for p in parts for s in SCOPES[p]]


def save(refresh, cid, sec, only=None):
    """Store the refresh token for every part it covers. Returns lines to print."""
    from . import keys
    out = []
    if only in (None, "youtube"):
        keys.set_key("YT_OAUTH_REFRESH_TOKEN", refresh)
        if os.environ.get("YT_OAUTH_CLIENT_ID") != cid:    # signed in with the Google Ads client: YouTube needs it too
            keys.set_key("YT_OAUTH_CLIENT_ID", cid)
            keys.set_key("YT_OAUTH_CLIENT_SECRET", sec)
        out.append("YouTube Analytics → YT_OAUTH_REFRESH_TOKEN")
    if only in (None, "ads"):
        keys.set_key("GOOGLE_ADS_REFRESH_TOKEN", refresh)
        # A refresh token only works with the client that made it: point Google Ads at that client.
        if (os.environ.get("GOOGLE_ADS_CLIENT_ID") or cid) != cid:
            keys.set_key("GOOGLE_ADS_CLIENT_ID", cid)
            keys.set_key("GOOGLE_ADS_CLIENT_SECRET", sec)
            out.append("GOOGLE_ADS_CLIENT_ID / _SECRET set to the client this sign-in used (the token needs it)")
        out.append("Google Ads → GOOGLE_ADS_REFRESH_TOKEN")
    return out


def accounts():
    """Your channel (YouTube Data API, mine=true) and the Google Ads customers the token reaches. No tokens."""
    config.load_env()
    res = {"channel": None, "ads_customers": [], "errors": []}
    if yt.available():
        tok = yt.access_token(res["errors"])
        if tok:
            r = requests.get(f"{yt.DATA}/channels", params={"part": "snippet", "mine": "true"},
                             headers={"Authorization": f"Bearer {tok}"}, timeout=20)
            items = (r.json().get("items") or []) if r.ok else []
            if items:
                res["channel"] = {"id": items[0]["id"], "title": items[0]["snippet"].get("title", "")}
            elif not r.ok:
                res["errors"].append(f"youtube: {r.json().get('error', {}).get('message', r.status_code)}")
    if gads.available():
        try:
            r = requests.get(f"{gads.API}/customers:listAccessibleCustomers", headers=gads._headers(), timeout=20)
            d = r.json()
            if r.ok:
                res["ads_customers"] = [n.split("/")[-1] for n in d.get("resourceNames") or []]
            else:
                res["errors"].append(f"google ads: {(d.get('error') or {}).get('message', r.status_code)}")
        except RuntimeError as e:
            res["errors"].append(str(e))
    return res


def connect(open_browser=True, port=0, timeout=300, only=None, status_file=None):
    """Loopback + PKCE consent for every scope; saves the refresh token. Returns lines to print."""
    note = loopback.Status(status_file)
    try:
        cid, sec = _client()
        verifier = secrets.token_urlsafe(64)[:96]
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(16)
        try:
            srv, got = loopback.server(port, state)
        except loopback.CallbackError as e:
            raise GoogleError(str(e)) from e
        redirect = f"http://127.0.0.1:{srv.server_address[1]}"
        url = yt.auth_url(cid, redirect, challenge, state, scopes_for(only))
        note("waiting", "Waiting for the Google sign-in in the browser…", url=url)
        print("Open this URL, pick the Google account that owns the channel and manages the Google Ads accounts, and "
              "allow every box:\n" + url, flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            got = loopback.wait(srv, got, timeout)
        except loopback.CallbackError as e:
            raise GoogleError(str(e)) from e
        if not got.get("code"):
            raise GoogleError(f"No sign-in received ({got.get('error') or 'no code'}).")
        r = requests.post(yt.TOKEN, data={"code": got["code"], "client_id": cid, "client_secret": sec,
                                          "redirect_uri": redirect, "grant_type": "authorization_code",
                                          "code_verifier": verifier}, timeout=30)
        d = r.json()
        if not d.get("refresh_token"):
            raise GoogleError(f"Token exchange failed: {d.get('error_description') or d.get('error') or r.text[:200]}")
        granted = set((d.get("scope") or "").split())
        lines = ["Signed in with Google"]
        missing = [s.rsplit("/", 1)[-1] for s in scopes_for(only) if s not in granted]
        if missing:
            lines.append("Not allowed: " + ", ".join(missing) + " (sign in again and tick every box)")
        lines += save(d["refresh_token"], cid, sec, only)
        found = accounts()
        if found["channel"]:
            lines.append(f"Channel: {found['channel']['title']}")
        if found["ads_customers"]:
            lines.append("Google Ads accounts reachable: " + ", ".join(found["ads_customers"])
                         + " (each business's account goes on its Paid ads page)")
        lines += [f"Check: {e}" for e in found["errors"]]
        lines.append("If the OAuth consent screen is still in Testing, this token stops working after 7 days: publish "
                     "it (Google Cloud → OAuth consent screen → Publish app).")
        note("done", "\n".join(lines))
        return lines
    except GoogleError as e:
        note("failed", str(e))
        raise
