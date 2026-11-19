"""Comment challenges: answer every qualifying comment under a post that asked for one (publish.challenges).

A caption with `challenge: GUIDE` qualifies comments containing the word GUIDE; `mentions: 2` qualifies comments that
tag at least two accounts (Instagram only: Facebook demotes "tag a friend" posts as engagement bait). Each comment is
answered once (data/publish/<profile>/replied.json) with publish.challenges.reply_text, {link} = the caption's
`reward:` (default publish.link) with utm_source per platform.

  instagram  public reply under the comment; dm: true tries a private reply (one DM per comment) first. A private
             reply needs instagram_manage_messages, which Meta grants beyond the app's own testers only after App Review.
  facebook   the same (pages_manage_engagement; private replies need pages_messaging).
  youtube    a reply in the thread (needs the youtube.force-ssl scope: `publish <p> connect google`).
  linkedin   not supported: reading comments needs an API product LinkedIn grants case by case.
Only posts from the last publish.challenges.days days are read, at most MAX_REPLIES replies per run.
"""
import json
import re
from datetime import datetime, timedelta, timezone

import requests

from . import connect, core
from .auto import data_dir

MAX_REPLIES = 25


def qualifies(text, keyword="", mentions=0):
    text = text or ""
    if keyword and re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text, re.I):
        return True
    return bool(mentions) and len(set(re.findall(r"@[\w.]+", text))) >= int(mentions)


class Meta:
    def __init__(self, env, platform):
        self.v = env.get("META_GRAPH_VERSION", "v26.0")
        self.token = env.get("INSTAGRAM_ACCESS_TOKEN" if platform == "instagram" else "FACEBOOK_PAGE_TOKEN", "")
        host = "graph.instagram.com" if self.token.startswith("IG") else "graph.facebook.com"
        self.api = f"https://{host}/{self.v}"
        self.platform, self.env = platform, env

    def comments(self, media_id):
        fields = "id,text,username" if self.platform == "instagram" else "id,message,from"
        r = requests.get(f"{self.api}/{media_id}/comments", params={"fields": fields, "limit": 100, "access_token": self.token}, timeout=30).json()
        if r.get("error"):
            raise RuntimeError(r["error"].get("message"))
        return [{"id": c["id"], "text": c.get("text") or c.get("message") or "",
                 "author": c.get("username") or (c.get("from") or {}).get("id", "")} for c in r.get("data") or []]

    def reply(self, comment_id, text, dm=False):
        if dm:
            # Facebook Login (Page token): /{page}/messages for both; Instagram Login: /{ig user}/messages.
            sender = self.env.get("FACEBOOK_PAGE_ID") if "graph.facebook.com" in self.api else self.env.get("INSTAGRAM_USER_ID")
            r = requests.post(f"{self.api}/{sender}/messages", timeout=30, json={
                "recipient": {"comment_id": comment_id}, "message": {"text": text}}, params={"access_token": self.token}).json()
            if not r.get("error"):
                return "dm"
        path = "replies" if self.platform == "instagram" else "comments"
        r = requests.post(f"{self.api}/{comment_id}/{path}", data={"message": text, "access_token": self.token}, timeout=30).json()
        if r.get("error"):
            raise RuntimeError(r["error"].get("message"))
        return "reply"


class YouTube:
    def __init__(self, env):
        d = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
            "client_id": env.get("YOUTUBE_CLIENT_ID"), "client_secret": env.get("YOUTUBE_CLIENT_SECRET"),
            "refresh_token": env.get("YOUTUBE_REFRESH_TOKEN"), "grant_type": "refresh_token"}).json()
        if not d.get("access_token"):
            raise RuntimeError(d.get("error_description") or "YouTube token refresh failed")
        self.h = {"Authorization": f"Bearer {d['access_token']}"}
        self.own = env.get("YOUTUBE_CHANNEL_ID", "")

    def comments(self, video_id):
        r = requests.get("https://www.googleapis.com/youtube/v3/commentThreads", headers=self.h, timeout=30,
                         params={"part": "snippet", "videoId": video_id, "maxResults": 100}).json()
        if r.get("error"):
            raise RuntimeError(r["error"].get("message"))
        out = []
        for t in r.get("items") or []:
            c = t["snippet"]["topLevelComment"]
            sn = c["snippet"]
            out.append({"id": c["id"], "text": sn.get("textOriginal", ""), "author": (sn.get("authorChannelId") or {}).get("value", "")})
        return out

    def reply(self, comment_id, text, dm=False):
        r = requests.post("https://www.googleapis.com/youtube/v3/comments?part=snippet", headers=self.h, timeout=30,
                          json={"snippet": {"parentId": comment_id, "textOriginal": text}}).json()
        if r.get("error"):
            raise RuntimeError(r["error"].get("message"))
        return "reply"


def _entries(cfg, days):
    f = data_dir(cfg) / "challenges.jsonl"
    if not f.exists():
        return []
    since = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
            t = datetime.fromisoformat(r["time"].replace("Z", "+00:00"))
        except (ValueError, KeyError):
            continue
        if t >= since and r.get("id"):
            out.append(r)
    return out


def run(cfg, dry=False, clients=None):
    """Returns lines for the job log. clients: {platform: client} for tests."""
    s = core.settings(cfg)
    ch = s["challenges"]
    env = connect.keys_for(cfg)
    state_f = data_dir(cfg) / "replied.json"
    replied = set(json.loads(state_f.read_text(encoding="utf-8"))) if state_f.exists() else set()
    own = {str(x).lstrip("@").lower() for x in (s["handles"] or {}).values()} | {env.get("FACEBOOK_PAGE_ID", ""), env.get("YOUTUBE_CHANNEL_ID", "")}
    clients = dict(clients or {})
    out, sent = [], 0
    for e in _entries(cfg, int(ch.get("days", 7))):
        p = e["platform"]
        if p == "linkedin":
            continue
        mentions = e.get("mentions", 0) if p == "instagram" else 0
        if not e.get("challenge") and not mentions:
            continue
        try:
            if p not in clients:
                clients[p] = YouTube(env) if p == "youtube" else Meta(env, p)
            c = clients[p]
            for cm in c.comments(e["id"]):
                if cm["id"] in replied or str(cm["author"]).lower() in own or not qualifies(cm["text"], e.get("challenge", ""), mentions):
                    continue
                if sent >= MAX_REPLIES:
                    return out + [f"challenges: {MAX_REPLIES} replies this run, the rest next run"]
                link = core.utm_link(e.get("reward") or s["link"], p, "challenge", s)
                text = (ch.get(f"reply_text_{p}") or ch["reply_text"]).replace("{link}", link)
                how = "dry run" if dry else c.reply(cm["id"], text, dm=bool(ch.get("dm")) and p != "youtube")
                replied.add(cm["id"])
                sent += 1
                out.append(f"challenge {p} {e.get('challenge') or f'{mentions} tags'}: answered a comment ({how})")
        except Exception as x:  # one platform's error must not stop the others
            out.append(f"challenge {p}: {str(x)[:200]}")
    if not dry:
        state_f.write_text(json.dumps(sorted(replied)), encoding="utf-8")
    return out

