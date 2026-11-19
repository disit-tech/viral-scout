"""Posting keys for ONE business: `python -m viral_scout publish <profile> connect meta|google|linkedin`.

Every business posts to its own accounts, so these keys go to the profile's publish.env_file (default
data/publish/<profile>/keys.env, git-ignored), never to the shared .env:
  meta      from the shared Facebook sign-in (META_USER_TOKEN, `keys meta connect`, with the publishing permissions):
            picks the business's Page (--page name|id, else the Page whose name or Instagram handle matches
            publish.handles) → FACEBOOK_PAGE_ID, FACEBOOK_PAGE_TOKEN, INSTAGRAM_USER_ID, INSTAGRAM_ACCESS_TOKEN.
            A Page token made from a long-lived user token does not expire.
  google    a Google sign-in for the business's channel (YouTube upload + comments) → YOUTUBE_CLIENT_ID/SECRET/
            REFRESH_TOKEN. The OAuth client is YOUTUBE_CLIENT_ID or YT_OAUTH_CLIENT_ID from the shared .env.
  linkedin  a LinkedIn sign-in (app: LINKEDIN_CLIENT_ID/SECRET in the shared .env, redirect http://127.0.0.1:8766/)
            → LINKEDIN_ACCESS_TOKEN (60 days), LINKEDIN_TOKEN_EXPIRES, LINKEDIN_AUTHOR (the member, or --org ID
            for a company Page: needs the Community Management API product).
"""
import base64
import hashlib
import os
import re
import secrets
import urllib.parse
import webbrowser
from datetime import date, timedelta
from pathlib import Path

import requests

from .. import config, loopback
from . import core, pack

META_PUBLISH_SCOPES = ["instagram_content_publish", "pages_manage_posts", "pages_read_user_content",
                       "pages_manage_engagement", "instagram_manage_messages", "pages_messaging"]
YT_SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"]
LI_PORT = 8766


class ConnectError(RuntimeError):
    pass


def env_path(cfg):
    return Path(core.settings(cfg)["env_file"])


def set_env(path, values):
    """KEY=VALUE into the profile's keys file (other lines kept). Values are never printed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out, seen = [], set()
    for line in lines:
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if m and m.group(1) in values:
            if m.group(1) not in seen:
                out.append(f"{m.group(1)}={values[m.group(1)]}")
                seen.add(m.group(1))
            continue
        out.append(line)
    out += [f"{k}={v}" for k, v in values.items() if k not in seen]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


def keys_for(cfg):
    """The keys a posting run sees: the shared .env, then the profile's own file on top (it wins)."""
    config.load_env()
    return {**os.environ, **pack.read_env_file(core.settings(cfg)["env_file"])}


# ───────────── Meta ─────────────
def meta(cfg, page=None):
    config.load_env()
    token = os.environ.get("META_USER_TOKEN", "")
    if not token:
        raise ConnectError("META_USER_TOKEN missing: sign in first (Setup page → Connect Meta, or `keys meta connect`)")
    v = os.environ.get("META_GRAPH_VERSION", "v26.0")
    r = requests.get(f"https://graph.facebook.com/{v}/me/accounts", timeout=30, params={
        "fields": "id,name,access_token,instagram_business_account{id,username}", "limit": 100, "access_token": token}).json()
    if r.get("error"):
        raise ConnectError(f"Meta: {r['error'].get('message')}")
    pages = r.get("data") or []
    handles = {k: str(x).lstrip("@").lower() for k, x in (core.settings(cfg)["handles"] or {}).items()}

    def match(p):
        if page:
            return page in (p["id"], p["name"]) or page.lower() == p["name"].lower()
        ig = ((p.get("instagram_business_account") or {}).get("username") or "").lower()
        name = re.sub(r"\W", "", p["name"].lower())
        return bool((ig and ig in handles.values()) or (handles.get("facebook") and handles["facebook"] in (name, p["id"])))

    found = [p for p in pages if match(p)]
    if len(found) != 1:
        raise ConnectError(("No Page matches" if not found else "Several Pages match") + " this business: pass --page "
                           "\"<name or id>\". Pages you manage: " + ", ".join(f"{p['name']} ({p['id']})" for p in pages))
    p = found[0]
    vals = {"FACEBOOK_PAGE_ID": p["id"], "FACEBOOK_PAGE_TOKEN": p["access_token"]}
    ig = p.get("instagram_business_account") or {}
    if ig:
        vals |= {"INSTAGRAM_USER_ID": ig["id"], "INSTAGRAM_ACCESS_TOKEN": p["access_token"]}
    perms = requests.get(f"https://graph.facebook.com/{v}/me/permissions", params={"access_token": token}, timeout=30).json()
    granted = {x["permission"] for x in perms.get("data") or [] if x.get("status") == "granted"}
    f = set_env(env_path(cfg), vals)
    lines = [f"Facebook Page: {p['name']} → FACEBOOK_PAGE_ID, FACEBOOK_PAGE_TOKEN ({f})",
             f"Instagram: @{ig['username']} → INSTAGRAM_USER_ID, INSTAGRAM_ACCESS_TOKEN" if ig else
             "Instagram: no business account linked to this Page (link it in the Page settings, then run this again)"]
    miss = [s for s in META_PUBLISH_SCOPES if s not in granted]
    if miss:
        lines.append("Not granted yet: " + ", ".join(miss) + ". Posting needs instagram_content_publish and "
                     "pages_manage_posts; comment replies need pages_manage_engagement / pages_read_user_content; DMs "
                     "need the messaging ones (App Review for people without a role in the app). Sign in again on the "
                     "Setup page and allow them.")
    return lines


# ───────────── Google / YouTube ─────────────
def google(cfg, open_browser=True, timeout=300):
    from ..perf import youtube as yt
    config.load_env()
    cid = os.environ.get("YOUTUBE_CLIENT_ID") or os.environ.get("YT_OAUTH_CLIENT_ID")
    sec = os.environ.get("YOUTUBE_CLIENT_SECRET") or os.environ.get("YT_OAUTH_CLIENT_SECRET")
    if not cid or not sec:
        raise ConnectError("No Google OAuth client: set YT_OAUTH_CLIENT_ID / YT_OAUTH_CLIENT_SECRET (Setup page)")
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    srv, got = loopback.server(0, state)
    redirect = f"http://127.0.0.1:{srv.server_address[1]}"
    url = yt.auth_url(cid, redirect, challenge, state, YT_SCOPES)
    print(f"Sign in with the Google account of {cfg.get('display_name') or cfg['name']}'s channel (pick the brand "
          f"channel if asked) and allow every box:\n{url}", flush=True)
    if open_browser:
        webbrowser.open(url)
    got = loopback.wait(srv, got, timeout)
    if not got.get("code"):
        raise ConnectError(f"No sign-in received ({got.get('error') or 'no code'})")
    d = requests.post(yt.TOKEN, timeout=30, data={"code": got["code"], "client_id": cid, "client_secret": sec, "redirect_uri": redirect,
                                                  "grant_type": "authorization_code", "code_verifier": verifier}).json()
    if not d.get("refresh_token"):
        raise ConnectError(f"Token exchange failed: {d.get('error_description') or d.get('error')}")
    ch = requests.get("https://www.googleapis.com/youtube/v3/channels", params={"part": "snippet", "mine": "true"},
                      headers={"Authorization": f"Bearer {d['access_token']}"}, timeout=30).json()
    item = (ch.get("items") or [{}])[0]
    f = set_env(env_path(cfg), {"YOUTUBE_CLIENT_ID": cid, "YOUTUBE_CLIENT_SECRET": sec, "YOUTUBE_REFRESH_TOKEN": d["refresh_token"],
                                "YOUTUBE_CHANNEL_ID": item.get("id", "")})
    return [f"YouTube channel: {(item.get('snippet') or {}).get('title', '?')} → YOUTUBE_* ({f})",
            "Uploads from an API project Google has not audited stay PRIVATE: request the audit (YouTube API Services "
            "audit form) before relying on auto-posting to YouTube."]


# ───────────── LinkedIn ─────────────
def linkedin(cfg, org=None, open_browser=True, timeout=300):
    config.load_env()
    cid, sec = os.environ.get("LINKEDIN_CLIENT_ID"), os.environ.get("LINKEDIN_CLIENT_SECRET")
    if not cid or not sec:
        raise ConnectError("LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET missing: create an app at "
                           "linkedin.com/developers (products: Sign In with LinkedIn using OpenID Connect + Share on "
                           f"LinkedIn; Community Management API for a company Page), redirect http://127.0.0.1:{LI_PORT}/")
    scopes = ["openid", "profile", "w_member_social"] + (["w_organization_social", "r_organization_admin"] if org else [])
    state = secrets.token_urlsafe(16)
    srv, got = loopback.server(LI_PORT, state)
    redirect = f"http://127.0.0.1:{LI_PORT}/"
    url = "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode(
        {"response_type": "code", "client_id": cid, "redirect_uri": redirect, "state": state, "scope": " ".join(scopes)})
    print(f"Sign in to LinkedIn for {cfg.get('display_name') or cfg['name']}:\n{url}", flush=True)
    if open_browser:
        webbrowser.open(url)
    got = loopback.wait(srv, got, timeout)
    if not got.get("code"):
        raise ConnectError(f"No sign-in received ({got.get('error_description') or got.get('error') or 'no code'})")
    d = requests.post("https://www.linkedin.com/oauth/v2/accessToken", timeout=30, data={
        "grant_type": "authorization_code", "code": got["code"], "redirect_uri": redirect, "client_id": cid, "client_secret": sec}).json()
    tok = d.get("access_token")
    if not tok:
        raise ConnectError(f"Token exchange failed: {d.get('error_description') or d.get('error')}")
    if org:
        author = f"urn:li:organization:{str(org).rsplit(':', 1)[-1]}"
    else:
        me = requests.get("https://api.linkedin.com/v2/userinfo", headers={"Authorization": f"Bearer {tok}"}, timeout=30).json()
        author = f"urn:li:person:{me['sub']}"
    expires = (date.today() + timedelta(seconds=int(d.get("expires_in") or 5184000))).isoformat()
    vals = {"LINKEDIN_ACCESS_TOKEN": tok, "LINKEDIN_AUTHOR": author, "LINKEDIN_TOKEN_EXPIRES": expires}
    if d.get("refresh_token"):
        vals["LINKEDIN_REFRESH_TOKEN"] = d["refresh_token"]
    f = set_env(env_path(cfg), vals)
    return [f"LinkedIn: posts as {author} → LINKEDIN_* ({f})", f"The token expires {expires}: run this again before then."]


def check(cfg, service):
    """Why a sign-in can't start yet ("" = it can). The dashboard asks before it opens a browser."""
    env = keys_for(cfg)
    if service == "meta" and not env.get("META_USER_TOKEN"):
        return "No Facebook sign-in yet: Setup page → Connect Meta first (needs META_APP_ID / META_APP_SECRET)."
    if service == "google" and not ((env.get("YOUTUBE_CLIENT_ID") or env.get("YT_OAUTH_CLIENT_ID")) and
                                    (env.get("YOUTUBE_CLIENT_SECRET") or env.get("YT_OAUTH_CLIENT_SECRET"))):
        return ("No Google sign-in client yet: put YT_OAUTH_CLIENT_ID and YT_OAUTH_CLIENT_SECRET on the Setup page "
                "(YouTube step 1 on the Posting page says how to make them).")
    if service == "tiktok" and not (env.get("TIKTOK_POST_CLIENT_KEY") and env.get("TIKTOK_POST_CLIENT_SECRET")):
        return ("No TikTok app yet: put TIKTOK_POST_CLIENT_KEY and TIKTOK_POST_CLIENT_SECRET on the Setup page "
                "(TikTok step 1 on the Posting page says how to make them).")
    if service == "linkedin" and not (env.get("LINKEDIN_CLIENT_ID") and env.get("LINKEDIN_CLIENT_SECRET")):
        return ("No LinkedIn app yet: put LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET on the Setup page "
                "(LinkedIn step 1 on the Posting page says how to make them).")
    return ""


def expiring(cfg, today=None, days=7):
    """Warnings for keys that stop working soon (LinkedIn tokens last 60 days)."""
    env = keys_for(cfg)
    out = []
    th = env.get("THREADS_EXPIRES", "")
    if th:
        try:
            if (date.fromisoformat(th) - (today or date.today())).days < 0:
                out.append(f"Threads token for {cfg['name']} expired {th}: Posting page → Threads → paste a new token")
        except ValueError:
            pass
    t = env.get("TIKTOK_POST_REFRESH_EXPIRES", "")
    if t:
        try:
            if (date.fromisoformat(t) - (today or date.today())).days <= days:
                out.append(f"TikTok sign-in for {cfg['name']} ends {t}: Posting page → TikTok → Connect again")
        except ValueError:
            pass
    e = env.get("LINKEDIN_TOKEN_EXPIRES", "")
    if e:
        try:
            left = (date.fromisoformat(e) - (today or date.today())).days
        except ValueError:
            left = None
        if left is not None and left <= days:
            out.append(f"LinkedIn token for {cfg['name']} {'expired' if left < 0 else f'expires in {left} day(s)'} ({e}): "
                       f"python -m viral_scout publish {cfg['name']} connect linkedin")
    return out

