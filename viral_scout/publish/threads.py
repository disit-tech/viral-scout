"""Threads through the official Threads API (graph.threads.net): text posts, and for a film a text post with the link
to the film once it is up on Instagram / YouTube (Threads takes images and videos only from a public URL).

Connect (per business): Meta app → use case "Access the Threads API" (threads_basic, threads_content_publish) →
App roles → add the business's Threads account as a Threads Tester and accept the invite in the Threads app
(Settings → Account → Website permissions) → Threads use case → User Token Generator → Generate → paste it on the
Posting page (`publish <p> connect threads`, token on stdin). With THREADS_APP_SECRET set a short token is swapped for a
60-day one; every token is refreshed for another 60 days when it has fewer than 15 left.
Keys (data/publish/<p>/keys.env): THREADS_ACCESS_TOKEN, THREADS_USER_ID, THREADS_EXPIRES (YYYY-MM-DD).
"""
import os
from datetime import date, timedelta

import requests

from .. import config

API = "https://graph.threads.net"
LIMIT = 500


class ThreadsError(RuntimeError):
    pass


def _get(path, params, http=requests):
    r = http.get(f"{API}/{path}", params=params, timeout=30).json()
    if r.get("error"):
        raise ThreadsError(r["error"].get("message") or str(r["error"]))
    return r


def connect(cfg, token, http=requests):
    from . import connect as c
    token = (token or "").strip()
    if not token or any(ch.isspace() for ch in token):
        raise ThreadsError("paste the token from the Threads User Token Generator (one line)")
    config.load_env()
    secret = os.environ.get("THREADS_APP_SECRET", "")
    days = 60
    if secret:
        try:
            d = _get("access_token", {"grant_type": "th_exchange_token", "client_secret": secret, "access_token": token}, http)
            token, days = d["access_token"], int(d.get("expires_in", 5184000)) // 86400
        except ThreadsError:
            pass                    # already a long-lived token: keep it
    me = _get("v1.0/me", {"fields": "id,username", "access_token": token}, http)
    exp = (date.today() + timedelta(days=days)).isoformat()
    f = c.set_env(c.env_path(cfg), {"THREADS_ACCESS_TOKEN": token, "THREADS_USER_ID": me["id"], "THREADS_EXPIRES": exp})
    return [f"Threads: @{me.get('username', '?')} → THREADS_* ({f})", f"Renewed automatically before {exp} while posting runs."]


def token(cfg, http=requests):
    """The business's token, refreshed for 60 more days when it has fewer than 15 left."""
    from . import connect as c
    env = c.keys_for(cfg)
    tok = env.get("THREADS_ACCESS_TOKEN", "")
    if not tok:
        raise ThreadsError("Threads not connected for this business (Posting page → Threads)")
    try:
        left = (date.fromisoformat(env.get("THREADS_EXPIRES", "")) - date.today()).days
    except ValueError:
        left = 0
    if left < 15:
        try:
            d = _get("refresh_access_token", {"grant_type": "th_refresh_token", "access_token": tok}, http)
            tok = d["access_token"]
            c.set_env(c.env_path(cfg), {"THREADS_ACCESS_TOKEN": tok,
                                        "THREADS_EXPIRES": (date.today() + timedelta(seconds=int(d.get("expires_in", 5184000)))).isoformat()})
        except ThreadsError:
            if left < 0:
                raise
    return tok


def fit(text, link=""):
    """≤ 500 characters with the link kept whole at the end."""
    text = text.strip()
    tail = f"\n\n{link}" if link and link not in text else ""
    room = LIMIT - len(tail)
    if len(text) > room:
        cut = text[: room - 1]
        text = (cut[: cut.rfind(" ")] if cut.rfind(" ") > room // 2 else cut).rstrip() + "…"
    return text + tail


def post(cfg, text, link="", http=requests):
    """A text post (a link in it shows as a preview card). Returns {id, link}."""
    tok = token(cfg, http)
    body = fit(text, link)
    r = http.post(f"{API}/v1.0/me/threads", timeout=30, data={"media_type": "TEXT", "text": body, "access_token": tok}).json()
    if r.get("error"):
        raise ThreadsError(r["error"].get("message"))
    p = http.post(f"{API}/v1.0/me/threads_publish", timeout=30, data={"creation_id": r["id"], "access_token": tok}).json()
    if p.get("error"):
        raise ThreadsError(p["error"].get("message"))
    try:
        url = _get(f"v1.0/{p['id']}", {"fields": "permalink", "access_token": tok}, http).get("permalink")
    except ThreadsError:
        url = None
    return {"id": p["id"], "link": url}
