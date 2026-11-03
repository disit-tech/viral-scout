"""Your own YouTube channel: YouTube Analytics API (official, OAuth, your channel only).

Setup (once): a Google Cloud project with "YouTube Analytics API" and "YouTube Data API v3" enabled, an OAuth
client of type "Desktop app", then
  python -m viral_scout keys set YT_OAUTH_CLIENT_ID <id>
  python -m viral_scout keys set YT_OAUTH_CLIENT_SECRET -          (value from stdin)
  python -m viral_scout perf auth youtube                          (browser consent → YT_OAUTH_REFRESH_TOKEN)
The flow is Google's installed-app flow with a loopback redirect (http://127.0.0.1:<port>) and PKCE; the
out-of-band copy/paste flow is no longer supported by Google.

Reports (https://youtubeanalytics.googleapis.com/v2/reports, ids=channel==MINE):
  per video   views, engagedViews, estimatedMinutesWatched, averageViewDuration, averageViewPercentage, likes,
              comments, shares, subscribersGained (dimension=video, sorted by views)
  retention   audienceWatchRatio, relativeRetentionPerformance by elapsedVideoTimeRatio (one video per request)
Titles and lengths come from the Data API videos.list with the same token.
"""
import base64
import hashlib
import http.server
import os
import re
import secrets
import threading
import urllib.parse
import webbrowser
from datetime import date, timedelta

import requests

from .. import usage
from .schema import blank

AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
REPORTS = "https://youtubeanalytics.googleapis.com/v2/reports"
DATA = "https://www.googleapis.com/youtube/v3"
SCOPES = ["https://www.googleapis.com/auth/yt-analytics.readonly", "https://www.googleapis.com/auth/youtube.readonly"]
METRICS = ["views", "engagedViews", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage",
           "likes", "comments", "shares", "subscribersGained"]


def available():
    return all(os.environ.get(k) for k in ("YT_OAUTH_CLIENT_ID", "YT_OAUTH_CLIENT_SECRET", "YT_OAUTH_REFRESH_TOKEN"))


def missing_keys():
    return [k for k in ("YT_OAUTH_CLIENT_ID", "YT_OAUTH_CLIENT_SECRET", "YT_OAUTH_REFRESH_TOKEN") if not os.environ.get(k)]


# ---- OAuth installed-app flow -----------------------------------------------------------------------------------
def auth_url(client_id, redirect, challenge, state):
    return AUTH + "?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": redirect, "response_type": "code", "scope": " ".join(SCOPES),
        "access_type": "offline", "prompt": "consent", "code_challenge": challenge,
        "code_challenge_method": "S256", "state": state})


def authorize(open_browser=True, timeout=300, port=0):
    """Run the consent flow on a loopback port; save the refresh token to .env. Returns a message."""
    from .. import keys
    cid, secret = os.environ.get("YT_OAUTH_CLIENT_ID"), os.environ.get("YT_OAUTH_CLIENT_SECRET")
    if not cid or not secret:
        raise SystemExit("Set YT_OAUTH_CLIENT_ID and YT_OAUTH_CLIENT_SECRET first (Google Cloud → Credentials → "
                         "OAuth client ID → Desktop app). See docs/performance.md.")
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] != state:
                self.send_response(400)
                self.end_headers()
                return
            got["code"], got["error"] = q.get("code", [None])[0], q.get("error", [None])[0]
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h3>viral-scout: done, you can close this tab.</h3>".encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", port), H)
    redirect = f"http://127.0.0.1:{srv.server_address[1]}"
    url = auth_url(cid, redirect, challenge, state)
    print("Open this URL, pick the Google account that owns the channel, and allow read-only access:\n" + url,
          flush=True)
    if open_browser:
        webbrowser.open(url)
    srv.timeout = timeout
    t = threading.Thread(target=lambda: [srv.handle_request() for _ in range(5) if "code" not in got and
                                         "error" not in got])
    t.start()
    t.join(timeout)
    srv.server_close()
    if not got.get("code"):
        raise SystemExit(f"No authorization code received ({got.get('error') or 'timed out'}).")
    r = requests.post(TOKEN, data={"code": got["code"], "client_id": cid, "client_secret": secret,
                                   "redirect_uri": redirect, "grant_type": "authorization_code",
                                   "code_verifier": verifier}, timeout=30)
    d = r.json()
    if not d.get("refresh_token"):
        raise SystemExit(f"Token exchange failed: {d.get('error_description') or d.get('error') or r.text[:200]}")
    keys.set_key("YT_OAUTH_REFRESH_TOKEN", d["refresh_token"])
    return "YT_OAUTH_REFRESH_TOKEN saved to .env"


def access_token(errors=None):
    r = requests.post(TOKEN, data={"client_id": os.environ["YT_OAUTH_CLIENT_ID"],
                                   "client_secret": os.environ["YT_OAUTH_CLIENT_SECRET"],
                                   "refresh_token": os.environ["YT_OAUTH_REFRESH_TOKEN"],
                                   "grant_type": "refresh_token"}, timeout=30)
    d = r.json()
    if "access_token" not in d:
        msg = d.get("error_description") or d.get("error") or r.text[:160]
        if errors is not None:
            errors.append(f"youtube oauth: {msg} (run: python -m viral_scout perf auth youtube)")
        return None
    return d["access_token"]


# ---- reports ------------------------------------------------------------------------------------------------------
def _report(tok, params, errors):
    usage.add("youtube_analytics_requests")
    try:
        r = requests.get(REPORTS, params={"ids": "channel==MINE", **params},
                         headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        d = r.json()
    except (requests.RequestException, ValueError) as err:
        errors.append(f"youtube analytics: {err}")
        return None
    if "error" in d:
        return {"_error": d["error"].get("message", "error")}
    cols = [c["name"] for c in d.get("columnHeaders") or []]
    return [dict(zip(cols, row)) for row in d.get("rows") or []]


def per_video(tok, start, end, limit, errors):
    for metrics in (METRICS, [m for m in METRICS if m != "engagedViews"]):
        rows = _report(tok, {"startDate": start, "endDate": end, "dimensions": "video", "metrics": ",".join(metrics),
                             "sort": "-views", "maxResults": min(limit, 200)}, errors)
        if rows is None:
            return []
        if isinstance(rows, list):
            return rows
    errors.append(f"youtube analytics per-video report: {rows['_error']}")
    return []


def retention(tok, vid, start, end, errors):
    rows = _report(tok, {"startDate": start, "endDate": end, "dimensions": "elapsedVideoTimeRatio",
                         "metrics": "audienceWatchRatio,relativeRetentionPerformance", "filters": f"video=={vid}",
                         "sort": "elapsedVideoTimeRatio"}, errors)
    if not isinstance(rows, list):
        if rows:
            errors.append(f"youtube retention {vid}: {rows['_error']}")
        return None
    return [[r["elapsedVideoTimeRatio"], r.get("audienceWatchRatio"), r.get("relativeRetentionPerformance")]
            for r in rows] or None


def iso_seconds(s):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return None
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def details(tok, ids, errors):
    out = {}
    for i in range(0, len(ids), 50):
        usage.add("youtube_api_units")
        try:
            d = requests.get(f"{DATA}/videos", params={"part": "snippet,contentDetails", "id": ",".join(ids[i:i + 50])},
                             headers={"Authorization": f"Bearer {tok}"}, timeout=30).json()
        except (requests.RequestException, ValueError) as err:
            errors.append(f"youtube videos.list: {err}")
            continue
        for v in d.get("items") or []:
            out[v["id"]] = {"title": v["snippet"].get("title", ""), "published": v["snippet"].get("publishedAt"),
                            "duration": iso_seconds(v["contentDetails"].get("duration")),
                            "thumbnail": f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg"}
    return out


def comment_texts(tok, vid, errors, n=50):
    usage.add("youtube_api_units")
    try:
        d = requests.get(f"{DATA}/commentThreads", params={"part": "snippet", "videoId": vid, "maxResults": n,
                                                           "textFormat": "plainText", "order": "relevance"},
                         headers={"Authorization": f"Bearer {tok}"}, timeout=30).json()
    except (requests.RequestException, ValueError):
        return None
    if "error" in d:
        return None
    return [c["snippet"]["topLevelComment"]["snippet"].get("textDisplay", "") for c in d.get("items") or []]


def pull(cfg, errors):
    pc = (cfg.get("perf") or {}).get("youtube") or {}
    tok = access_token(errors)
    if not tok:
        return []
    days = (cfg.get("perf") or {}).get("days", 28)
    end = date.today() - timedelta(days=1)          # analytics lag ~1–2 days
    start = end - timedelta(days=days)
    s, e = start.isoformat(), end.isoformat()
    rows = per_video(tok, s, e, pc.get("limit", 50), errors)
    info = details(tok, [r["video"] for r in rows], errors) if rows else {}
    out = []
    for i, row in enumerate(rows):
        vid = row["video"]
        meta = info.get(vid, {})
        r = blank("youtube", "organic", vid, platform="youtube", title=meta.get("title", vid),
                  url=f"https://www.youtube.com/watch?v={vid}", thumbnail=meta.get("thumbnail"),
                  published=meta.get("published"), duration=meta.get("duration"), date_start=s, date_stop=e)
        r.update(views=row.get("views"), engaged_views=row.get("engagedViews"),
                 total_watch_time=(row["estimatedMinutesWatched"] * 60) if row.get("estimatedMinutesWatched") is not None else None,
                 avg_watch_time=row.get("averageViewDuration"), avg_pct_viewed_given=row.get("averageViewPercentage"),
                 likes=row.get("likes"), comments=row.get("comments"), shares=row.get("shares"),
                 follows=row.get("subscribersGained"))
        r["notes"].append("YouTube Analytics gives no impressions/reach per video through the API; import a "
                          "YouTube Studio CSV for impressions and impressions CTR.")
        if i < pc.get("retention_videos", 10):
            r["retention"] = retention(tok, vid, s, e, errors)
        if pc.get("comments", True) and i < pc.get("comment_posts", 10) and (row.get("comments") or 0) > 0:
            r["comment_texts"] = comment_texts(tok, vid, errors)
        out.append(r)
    return out
