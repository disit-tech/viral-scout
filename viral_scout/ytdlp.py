"""yt-dlp loader. Uses the clone in $VIRAL_SCOUT_YTDLP (newer extractors) when set, else the installed package."""
import os
import sys

_src = os.environ.get("VIRAL_SCOUT_YTDLP")
if _src and os.path.isdir(os.path.join(_src, "yt_dlp")) and _src not in sys.path:
    sys.path.insert(0, _src)

import yt_dlp  # noqa: E402

VERSION = yt_dlp.version.__version__


class _QuietLogger:
    def __init__(self):
        self.errors = []

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        self.errors.append(msg)


def extract(url, flat=False, limit=None):
    """Return yt-dlp info for a URL, or raise RuntimeError with the extractor error."""
    log = _QuietLogger()
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "logger": log,
        "socket_timeout": 30,
        "retries": 2,
    }
    if flat:
        opts["extract_flat"] = "in_playlist"
    if limit:
        opts["playlistend"] = limit
    cookies = os.environ.get("VIRAL_SCOUT_COOKIES")
    if cookies and os.path.isfile(cookies):
        opts["cookiefile"] = cookies
    from . import usage
    usage.add("page_requests")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:  # yt-dlp raises DownloadError/ExtractorError
        raise RuntimeError(log.errors[-1] if log.errors else str(e)) from None
