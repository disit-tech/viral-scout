"""TikTok drafts through the official Content Posting API ("upload to inbox"): at the post time the film lands in the
business's TikTok app as a draft notification, and the owner gets its caption in the bot; they open TikTok, paste the
caption and tap Post. TikTok wants that last tap from a person, so this is the hands-off-as-allowed way.

  python -m viral_scout publish <profile> connect tiktok   sign in (scopes user.info.basic, video.upload)
App (once, developers.tiktok.com → Manage apps): products Login Kit + Content Posting API (Upload), platform Desktop,
redirect URI http://localhost:8767/callback/, keys TIKTOK_POST_CLIENT_KEY / TIKTOK_POST_CLIENT_SECRET in .env.
Tokens (per business, data/publish/<p>/keys.env): TIKTOK_POST_ACCESS_TOKEN (24 h), TIKTOK_POST_REFRESH_TOKEN (365 days,
renewed on every refresh), TIKTOK_POST_EXPIRES (epoch seconds), TIKTOK_POST_OPEN_ID.
"""
import hashlib
import math
import os
import secrets
import tempfile
import time
import urllib.parse
import webbrowser
from datetime import date, timedelta
from pathlib import Path

import requests

from .. import config, loopback

AUTH = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN = "https://open.tiktokapis.com/v2/oauth/token/"
INIT = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
STATUS = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
PORT = 8767
REDIRECT = f"http://localhost:{PORT}/callback/"
SCOPES = "user.info.basic,video.upload"
MB = 1024 * 1024


class TikTokError(RuntimeError):
    pass


def _app():
    config.load_env()
    key, sec = os.environ.get("TIKTOK_POST_CLIENT_KEY", ""), os.environ.get("TIKTOK_POST_CLIENT_SECRET", "")
    if not key or not sec:
        raise TikTokError("TIKTOK_POST_CLIENT_KEY / TIKTOK_POST_CLIENT_SECRET missing (Setup page; how: Posting page → TikTok step 1)")
    return key, sec, os.environ.get("TIKTOK_POST_REDIRECT_URI") or REDIRECT


def _save(cfg, d):
    from . import connect
    if d.get("error") or not d.get("access_token"):
        raise TikTokError(f"TikTok token: {d.get('error_description') or d.get('error') or d}")
    vals = {"TIKTOK_POST_ACCESS_TOKEN": d["access_token"], "TIKTOK_POST_REFRESH_TOKEN": d["refresh_token"],
            "TIKTOK_POST_EXPIRES": str(int(time.time()) + int(d.get("expires_in") or 86400) - 300),
            "TIKTOK_POST_REFRESH_EXPIRES": (date.today() + timedelta(seconds=int(d.get("refresh_expires_in") or 31536000))).isoformat()}
    if d.get("open_id"):
        vals["TIKTOK_POST_OPEN_ID"] = d["open_id"]
    connect.set_env(connect.env_path(cfg), vals)
    return vals


def connect(cfg, open_browser=True, timeout=300):
    key, sec, redirect = _app()
    verifier = secrets.token_urlsafe(48)
    challenge = hashlib.sha256(verifier.encode()).hexdigest()       # TikTok desktop PKCE: hex, not base64url
    state = secrets.token_urlsafe(16)
    srv, got = loopback.server(PORT, state)
    url = AUTH + "?" + urllib.parse.urlencode({"client_key": key, "scope": SCOPES, "response_type": "code", "redirect_uri": redirect,
                                               "state": state, "code_challenge": challenge, "code_challenge_method": "S256"})
    print(f"Sign in to the TikTok account of {cfg.get('display_name') or cfg['name']}:\n{url}", flush=True)
    if open_browser:
        webbrowser.open(url)
    got = loopback.wait(srv, got, timeout)
    if not got.get("code"):
        raise TikTokError(f"No sign-in received ({got.get('error_description') or got.get('error') or 'no code'})")
    d = requests.post(TOKEN, timeout=30, headers={"Content-Type": "application/x-www-form-urlencoded"}, data={
        "client_key": key, "client_secret": sec, "code": got["code"], "grant_type": "authorization_code",
        "redirect_uri": redirect, "code_verifier": verifier}).json()
    if "video.upload" not in (d.get("scope") or "video.upload"):
        raise TikTokError("TikTok did not grant video.upload: add the Content Posting API product to the app and sign in again")
    vals = _save(cfg, d)
    return [f"TikTok: connected → TIKTOK_POST_* ({vals['TIKTOK_POST_REFRESH_EXPIRES']} the sign-in must be renewed)",
            "Films go to the TikTok app as drafts at their time; the caption comes in the bot."]


def token(cfg, env=None):
    """A valid access token for this business, refreshed (and saved) when it is about to expire."""
    from . import connect as c
    env = env or c.keys_for(cfg)
    if env.get("TIKTOK_POST_ACCESS_TOKEN") and int(env.get("TIKTOK_POST_EXPIRES") or 0) > time.time():
        return env["TIKTOK_POST_ACCESS_TOKEN"]
    if not env.get("TIKTOK_POST_REFRESH_TOKEN"):
        raise TikTokError("TikTok not connected for this business (Posting page → TikTok)")
    key, sec, _ = _app()
    d = requests.post(TOKEN, timeout=30, headers={"Content-Type": "application/x-www-form-urlencoded"}, data={
        "client_key": key, "client_secret": sec, "grant_type": "refresh_token", "refresh_token": env["TIKTOK_POST_REFRESH_TOKEN"]}).json()
    return _save(cfg, d)["TIKTOK_POST_ACCESS_TOKEN"]


def chunks(size):
    """TikTok's chunk rules: one chunk up to 64 MB; else 10 MB chunks, the last one takes the remainder."""
    if size <= 64 * MB:
        return size, 1
    c = 10 * MB
    return c, math.floor(size / c)


def upload_draft(cfg, video, http=requests):
    """The mp4 → the business's TikTok inbox. Returns {id: publish_id}."""
    tok = token(cfg)
    size = Path(video).stat().st_size
    csize, n = chunks(size)
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"}
    r = http.post(INIT, headers=h, timeout=60, json={"source_info": {"source": "FILE_UPLOAD", "video_size": size,
                                                                     "chunk_size": csize, "total_chunk_count": n}}).json()
    if (r.get("error") or {}).get("code", "ok") != "ok":
        raise TikTokError(f"TikTok init: {r['error'].get('code')} {r['error'].get('message')}")
    data = r["data"]
    with open(video, "rb") as f:
        for i in range(n):
            start = i * csize
            end = size - 1 if i == n - 1 else start + csize - 1
            f.seek(start)
            body = f.read(end - start + 1)
            u = http.put(data["upload_url"], timeout=600, data=body, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(body)), "Content-Range": f"bytes {start}-{end}/{size}"})
            if u.status_code not in (200, 201, 206):
                raise TikTokError(f"TikTok upload chunk {i + 1}/{n}: HTTP {u.status_code} {u.text[:200]}")
    return {"id": data["publish_id"]}


def tell_owner(cfg, title, caption):
    """The caption to paste goes to the owner's bot (as a .txt plus the text); without a bot it stays on the Posting page."""
    from .. import notes
    a = notes.api_settings(cfg)
    if not a["url"] or not a["secret"]:
        return "no bot: caption on the Posting page"
    text = caption.strip()
    f = Path(tempfile.gettempdir()) / f"tiktok-caption-{cfg['name']}.txt"
    f.write_text(text + "\n", encoding="utf-8")
    msg = (f"📱 TikTok draft ready: \"{title}\". Open TikTok → inbox notification → paste this caption → Post.\n\n{text}")
    notes.Client(a["url"], a["secret"], a["project"]).send(str(f), msg, tags="tiktok")
    return "caption sent to the bot"
