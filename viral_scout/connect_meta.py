"""Connect Meta: one Facebook sign-in fills every Meta key (official Facebook Login, your own accounts).

  python -m viral_scout keys connect meta [--no-browser] [--port 8765]   sign in → META_USER_TOKEN, then auto-pick
  python -m viral_scout keys meta accounts                              Instagram + ad accounts the sign-in can reach (JSON)
  python -m viral_scout keys meta use [--ig ID|@username] [--ad-account ID] [--replace-ads-token]
  python -m viral_scout keys meta status                                what each Meta token is and when it expires

Once (by hand, Meta has no API for it): a Meta for Developers app with the "Facebook Login for Business" (or
"Facebook Login") product, http://localhost:8765/ in its Valid OAuth Redirect URIs, and its id and secret saved as
META_APP_ID / META_APP_SECRET. The app can stay in Development mode: people with a role on the app (you) get every
permission without App Review. If the login product asks for a configuration, put its id in META_LOGIN_CONFIG_ID.

What the sign-in does:
  1. Facebook's OAuth dialog on a loopback redirect; code → short-lived user token → long-lived user token (~60 days),
     saved as META_USER_TOKEN.
  2. Instagram: the Page linked to the Instagram business account gives a Page token. A Page token made from a
     long-lived user token has no expiry date, so IG_GRAPH_TOKEN stops expiring. IG_GRAPH_USER_ID is filled too.
  3. Ads: META_AD_ACCOUNT_ID from the ad accounts you can reach. META_ADS_TOKEN gets the user token, unless it already
     holds a token that never expires (a system-user token), which is kept unless --replace-ads-token.
  4. META_AD_LIBRARY_TOKEN gets the user token when it's empty and the Ad Library accepts it (identity-verified accounts).
With exactly one Instagram account or one ad account it's picked on its own; with several, pick with `keys meta use`.
"""
import os
import secrets
import urllib.parse
import webbrowser
from datetime import datetime, timezone

import requests

from . import config

VERSION = os.environ.get("META_GRAPH_VERSION", "v26.0")
GRAPH = f"https://graph.facebook.com/{VERSION}"
DIALOG = f"https://www.facebook.com/{VERSION}/dialog/oauth"
PORT = 8765
SCOPES = ["instagram_basic", "instagram_manage_insights", "instagram_manage_comments", "pages_show_list",
          "pages_read_engagement", "business_management", "ads_read", "ads_management",
          # Posting and comment challenges (publish <profile> autopost): Reels, Page posts, replies under comments.
          "instagram_content_publish", "pages_manage_posts", "pages_read_user_content", "pages_manage_engagement"]


class MetaError(RuntimeError):
    pass


def _app():
    config.load_env()
    aid, sec = os.environ.get("META_APP_ID", ""), os.environ.get("META_APP_SECRET", "")
    if not aid or not sec:
        raise MetaError("Set META_APP_ID and META_APP_SECRET first (Meta for Developers → your app → App settings → "
                        "Basic). See docs/setup.md#connect-meta.")
    return aid, sec


def _get(path, params, token):
    try:
        r = requests.get(f"{GRAPH}/{path}", params={**params, "access_token": token}, timeout=30)
        d = r.json()
    except (requests.RequestException, ValueError) as e:
        raise MetaError(f"{path}: {e}") from e
    if not r.ok or "error" in d:
        raise MetaError(f"{path}: {(d.get('error') or {}).get('message') or r.text[:160]}")
    return d


def _pages(path, params, token, limit=10):
    out, d = [], _get(path, {**params, "limit": 100}, token)
    for _ in range(limit):
        out += d.get("data") or []
        nxt = (d.get("paging") or {}).get("next")
        if not nxt:
            break
        d = requests.get(nxt, timeout=30).json()
    return out


def login_url(app_id, redirect, state):
    q = {"client_id": app_id, "redirect_uri": redirect, "state": state, "response_type": "code"}
    cfg_id = os.environ.get("META_LOGIN_CONFIG_ID", "")
    if cfg_id:                                       # Facebook Login for Business: the configuration holds the permissions
        q["config_id"] = cfg_id
    else:
        q["scope"] = ",".join(SCOPES)
    return DIALOG + "?" + urllib.parse.urlencode(q)


def exchange(app_id, secret, code, redirect):
    """Code → short-lived token → long-lived user token. Returns (token, expires_in_seconds or None)."""
    short = _get("oauth/access_token", {"client_id": app_id, "client_secret": secret, "redirect_uri": redirect,
                                        "code": code}, "")["access_token"]
    d = _get("oauth/access_token", {"grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": secret,
                                    "fb_exchange_token": short}, "")
    return d["access_token"], d.get("expires_in")


def debug(token):
    """What Meta says about a token: type, expiry (0 = never), data access expiry, scopes, valid."""
    aid, sec = _app()
    return _get("debug_token", {"input_token": token}, f"{aid}|{sec}").get("data") or {}


def _date(ts):
    return "never" if not ts else datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def describe(token):
    d = debug(token)
    if not d.get("is_valid"):
        return {"valid": False, "error": (d.get("error") or {}).get("message", "invalid")}
    return {"valid": True, "type": d.get("type"), "expires": _date(d.get("expires_at")),
            "data_access_expires": _date(d.get("data_access_expires_at")), "scopes": d.get("scopes") or []}


def accounts(token=None):
    """Instagram business accounts (through their Pages) and ad accounts the sign-in reaches. No tokens in the result."""
    config.load_env()
    token = token or os.environ.get("META_USER_TOKEN", "")
    if not token:
        raise MetaError("Not signed in: run python -m viral_scout keys connect meta")
    pages = _pages("me/accounts", {"fields": "id,name,instagram_business_account{id,username}"}, token)
    ig = [{"id": p["instagram_business_account"]["id"], "username": p["instagram_business_account"].get("username", ""),
           "page_id": p["id"], "page": p.get("name", "")} for p in pages if p.get("instagram_business_account")]
    try:
        ads = [{"id": a.get("id"), "account_id": a.get("account_id"), "name": a.get("name", ""),
                "currency": a.get("currency", ""), "active": a.get("account_status") == 1}
               for a in _pages("me/adaccounts", {"fields": "account_id,name,currency,account_status"}, token)]
    except MetaError:
        ads = []                                      # no ads_read granted: Instagram still works
    return {"instagram": ig, "ad_accounts": ads, "pages_without_instagram": [p.get("name", "") for p in pages
                                                                              if not p.get("instagram_business_account")]}


def _find_ig(found, want):
    w = want.lstrip("@").lower()
    for a in found["instagram"]:
        if w in (a["id"], a["username"].lower()):
            return a
    raise MetaError(f"No Instagram business account '{want}' in this sign-in. Found: "
                    + (", ".join("@" + a["username"] for a in found["instagram"]) or "none"))


def _find_ad(found, want):
    w = str(want).removeprefix("act_")
    for a in found["ad_accounts"]:
        if w == str(a["account_id"]):
            return a
    raise MetaError(f"No ad account {want} in this sign-in. Found: "
                    + (", ".join(f"{a['account_id']} ({a['name']})" for a in found["ad_accounts"]) or "none"))


def use(ig=None, ad_account=None, replace_ads_token=False, auto=False):
    """Save the chosen accounts' keys. auto=True picks an account only when it's the only one. Returns lines to print."""
    from . import keys
    config.load_env()
    token = os.environ.get("META_USER_TOKEN", "")
    found = accounts(token)
    out = []

    acc = _find_ig(found, ig) if ig else (found["instagram"][0] if auto and len(found["instagram"]) == 1 else None)
    if acc:
        page = _get(acc["page_id"], {"fields": "access_token"}, token).get("access_token")
        if not page:
            raise MetaError(f"Meta gave no Page token for {acc['page']} (needs pages_show_list on that Page)")
        keys.set_key("IG_GRAPH_TOKEN", page)
        keys.set_key("IG_GRAPH_USER_ID", acc["id"])
        exp = describe(page).get("expires", "?")
        out.append(f"Instagram: @{acc['username']} (Page {acc['page']}) → IG_GRAPH_TOKEN (expires: {exp}), IG_GRAPH_USER_ID")
    elif found["instagram"]:
        out.append("Instagram: several accounts, pick one: python -m viral_scout keys meta use --ig @username  ("
                   + ", ".join("@" + a["username"] for a in found["instagram"]) + ")")
    else:
        out.append("Instagram: no Instagram business account linked to a Page you manage"
                   + (f" (Pages without one: {', '.join(found['pages_without_instagram'])})"
                      if found["pages_without_instagram"] else ""))

    ad = _find_ad(found, ad_account) if ad_account else (
        found["ad_accounts"][0] if auto and len(found["ad_accounts"]) == 1 else None)
    if ad:
        keys.set_key("META_AD_ACCOUNT_ID", f"act_{ad['account_id']}")
        out.append(f"Ads: {ad['name']} ({ad['currency']}) → META_AD_ACCOUNT_ID. Each business's own account is set on "
                   "its Paid ads page.")
    elif found["ad_accounts"]:
        out.append("Ads: several ad accounts, pick the default: python -m viral_scout keys meta use --ad-account ID  ("
                   + ", ".join(f"{a['account_id']} {a['name']}" for a in found["ad_accounts"]) + ")")

    if found["ad_accounts"] and (ad or ad_account or auto):
        cur = os.environ.get("META_ADS_TOKEN", "")
        keep = False
        if cur and cur != token and not replace_ads_token:
            try:
                info = describe(cur)
                keep = info.get("valid") and info.get("expires") == "never"
            except MetaError:
                keep = False
        if keep:
            out.append("Ads: META_ADS_TOKEN already holds a token that never expires (system user): kept "
                       "(--replace-ads-token to use the sign-in instead)")
        elif cur != token:
            keys.set_key("META_ADS_TOKEN", token)
            out.append(f"Ads: META_ADS_TOKEN ← sign-in token (expires {describe(token).get('expires', '?')}; "
                       "a system-user token from Business Settings never expires)")

    if not os.environ.get("META_AD_LIBRARY_TOKEN"):
        try:
            _get("ads_archive", {"search_terms": "solar", "ad_reached_countries": '["DE"]', "ad_type": "ALL",
                                 "fields": "id", "limit": 1}, token)
            keys.set_key("META_AD_LIBRARY_TOKEN", token)
            out.append("Ad Library: the sign-in works for the Ad Library API → META_AD_LIBRARY_TOKEN")
        except MetaError:
            out.append("Ad Library: not available to this account (needs identity confirmation at facebook.com/ID)")
    return out


def status():
    config.load_env()
    res = {}
    for name in ("META_USER_TOKEN", "IG_GRAPH_TOKEN", "META_ADS_TOKEN", "META_AD_LIBRARY_TOKEN"):
        v = os.environ.get(name, "")
        if not v:
            res[name] = {"set": False}
            continue
        try:
            res[name] = {"set": True, **describe(v)}
        except MetaError as e:
            res[name] = {"set": True, "error": str(e)}
    return res


def connect(open_browser=True, port=PORT, timeout=300, status_file=None):
    """Sign-in on a loopback port, then save META_USER_TOKEN and auto-pick single accounts. Returns lines to print."""
    from . import keys, loopback
    note = loopback.Status(status_file)
    try:
        aid, sec = _app()
        state = secrets.token_urlsafe(16)
        try:
            srv, got = loopback.server(port, state)
        except loopback.CallbackError as e:
            raise MetaError(str(e)) from e
        redirect = f"http://localhost:{port}/"
        url = login_url(aid, redirect, state)
        note("waiting", "Waiting for the Facebook sign-in in the browser…", url=url)
        print("Open this URL and sign in with the Facebook account that manages the Pages and ad accounts:\n" + url,
              flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            got = loopback.wait(srv, got, timeout)
        except loopback.CallbackError as e:
            raise MetaError(str(e)) from e
        if not got.get("code"):
            raise MetaError(f"No sign-in received ({got.get('error_description') or got.get('error') or 'no code'}).")
        token, _ = exchange(aid, sec, got["code"], redirect)
        keys.set_key("META_USER_TOKEN", token)
        info = describe(token)
        missing = [s for s in SCOPES if s not in info.get("scopes", [])]
        lines = [f"Signed in → META_USER_TOKEN (expires {info.get('expires')}, data access until "
                 f"{info.get('data_access_expires')})"]
        if missing:
            lines.append("Not granted: " + ", ".join(missing) + " (sign in again and allow them, or add them to the app)")
        lines += use(auto=True)
        note("done", "\n".join(lines))
        return lines
    except MetaError as e:
        note("failed", str(e))
        raise
