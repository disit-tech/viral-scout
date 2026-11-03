from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Item:
    """One post (video/reel/short) with the numbers we could get."""
    platform: str            # youtube | instagram | tiktok
    id: str
    url: str
    title: str = ""
    channel: str = ""
    channel_url: str = ""
    channel_id: str = ""
    followers: Optional[int] = None
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    duration: Optional[float] = None
    published: Optional[datetime] = None
    found_by: list = field(default_factory=list)   # e.g. ["search:english idioms", "watch:@x", "seed"]
    channel_median: Optional[float] = None
    rise_per_day: Optional[float] = None          # view growth between our snapshots

    @property
    def key(self):
        return f"{self.platform}:{self.id}"

    @property
    def age_days(self):
        if not self.published:
            return None
        return max((datetime.now(timezone.utc) - self.published).total_seconds() / 86400, 0.25)

    @property
    def reach(self):
        """The best audience number we have: views, else likes (Instagram/TikTok without view counts)."""
        return self.views if self.views is not None else self.likes

    @property
    def per_day(self):
        if self.reach is None or self.age_days is None:
            return None
        return self.reach / self.age_days

    @property
    def vs_followers(self):
        if not self.reach or not self.followers:
            return None
        return self.reach / self.followers

    @property
    def vs_channel(self):
        if not self.reach or not self.channel_median:
            return None
        return self.reach / self.channel_median

    @property
    def engagement(self):
        if not self.views:
            return None
        return ((self.likes or 0) + (self.comments or 0)) / self.views

    @property
    def outlier(self):
        """How far above normal for its creator: channel median first, else follower count."""
        return self.vs_channel or self.vs_followers

    def merge(self, other: "Item"):
        for f in ("title", "channel", "channel_url", "channel_id", "followers", "views", "likes",
                  "comments", "duration", "published", "channel_median"):
            v = getattr(other, f)
            if v not in (None, "") and getattr(self, f) in (None, ""):
                setattr(self, f, v)
        for f in ("views", "likes", "comments", "followers"):   # newest numbers win
            v = getattr(other, f)
            if v is not None:
                setattr(self, f, max(v, getattr(self, f) or 0))
        for s in other.found_by:
            if s not in self.found_by:
                self.found_by.append(s)


def parse_date(v):
    """yt-dlp upload_date (YYYYMMDD) or a unix timestamp → aware datetime."""
    if v in (None, ""):
        return None
    try:
        if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit() and len(v) > 8):
            return datetime.fromtimestamp(int(v), tz=timezone.utc)
        return datetime.strptime(str(v)[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
    except (ValueError, OSError):
        return None
