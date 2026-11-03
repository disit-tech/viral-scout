"""Comment mining (Trendhaus / Mysocial-style): what viewers ask, object to and love under the hits.

YouTube only: the official commentThreads API when YOUTUBE_API_KEY is set (1 unit per video), else yt-dlp's public
comment extraction. Capped per run (profile: comments: {top_posts: 6, max: 40}) because each one is extra requests.
Questions are the gold: they are video ideas your audience already asked for.
"""
import os
import re

import requests

from . import usage

Q = re.compile(r"\?|^(how|what|why|when|where|which|who|can|is|are|do|does|should|could|would)\b|"
               r"^(как|что|почему|зачем|где|когда|можно|як|що|чому|де|коли|чи)\b", re.I)


def _api(video_id, limit):
    usage.add("youtube_api_units", 1)
    r = requests.get("https://www.googleapis.com/youtube/v3/commentThreads", timeout=30, params={
        "part": "snippet", "videoId": video_id, "order": "relevance", "maxResults": min(limit, 100),
        "textFormat": "plainText", "key": os.environ["YOUTUBE_API_KEY"]})
    d = r.json()
    if not r.ok:
        raise RuntimeError(d.get("error", {}).get("message", r.text[:120]))
    out = []
    for t in d.get("items") or []:
        s = t["snippet"]["topLevelComment"]["snippet"]
        out.append({"text": s.get("textDisplay", ""), "likes": s.get("likeCount")})
    return out


def _ytdlp(url, limit):
    from .ytdlp import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "getcomments": True,
            "extractor_args": {"youtube": {"max_comments": [str(limit), str(limit), "0", "0"], "comment_sort": ["top"]}}}
    usage.add("page_requests")
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return [{"text": c.get("text", ""), "likes": c.get("like_count")} for c in info.get("comments") or []
            if c.get("parent") in (None, "root")]


def fill(item, cfg, errors):
    if item.platform != "youtube" or item.top_comments:
        return False
    limit = (cfg.get("comments") or {}).get("max", 40)
    try:
        rows = _api(item.id, limit) if os.environ.get("YOUTUBE_API_KEY") else _ytdlp(item.url, limit)
    except Exception as err:
        errors.append(f"comments {item.key}: {str(err)[:140]}")
        return False
    rows = [r for r in rows if r["text"].strip()]
    rows.sort(key=lambda r: -(r["likes"] or 0))
    item.top_comments = [{"text": r["text"][:300], "likes": r["likes"]} for r in rows[:8]]
    item.questions = [r["text"][:240] for r in rows if Q.search(r["text"].strip())][:8]
    return True
