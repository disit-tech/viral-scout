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
    description: str = ""
    caption_url: str = ""                          # public caption track (json3), fetched only for top posts
    transcript: str = ""
    hook: str = ""                                 # what is said in the first seconds
    cta: str = ""                                  # what is said in the last seconds (call to action)
    wpm: Optional[float] = None                    # speaking pace, words per minute
    creator_pct: Optional[float] = None            # share of the creator's recent posts this one beats (0–100)
    pace_median: Optional[float] = None            # creator's median views/day (YouTube API, age-normalised)
    topic_median: Optional[float] = None           # median views/day of this run's discovered posts (the niche)
    own: bool = False                              # one of the business's own posts
    questions: list = field(default_factory=list)  # viewer questions from the comments
    top_comments: list = field(default_factory=list)
    thumb_url: str = ""                            # thumbnail for non-YouTube posts (from yt-dlp)
    frame: str = ""                                # local copy of the thumbnail/first frame (for on-screen text)

    @property
    def key(self):
        return f"{self.platform}:{self.id}"

    @property
    def age_days(self):
        if not self.published:
            return None
        return max((datetime.now(timezone.utc) - self.published).total_seconds() / 86400, 1 / 24)

    @property
    def reach(self):
        """The best audience number we have: views, else likes (Instagram/TikTok without view counts)."""
        return self.views if self.views is not None else self.likes

    @property
    def per_day(self):
        if self.reach is None or self.age_days is None:
            return None
        return self.reach / max(self.age_days, 0.25)   # under 6 h: don't extrapolate wildly

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
    def vs_pace(self):
        """Views/day vs the creator's median views/day: an age-matched outlier (vidIQ-style)."""
        if not self.per_day or not self.pace_median:
            return None
        return self.per_day / self.pace_median

    @property
    def vs_topic(self):
        """Views/day vs the niche median in this run (Mysocial-style topic-relative score)."""
        if not self.per_day or not self.topic_median:
            return None
        return self.per_day / self.topic_median

    @property
    def emerging(self):
        """A small creator (<=50K followers) with a clear outlier: worth watching early."""
        return bool(self.followers and self.followers <= 50_000 and (self.outlier or 0) >= 3)

    @property
    def engagement(self):
        if not self.views:
            return None
        return ((self.likes or 0) + (self.comments or 0)) / self.views

    @property
    def outlier(self):
        """How far above normal for its creator: channel median first, else follower count."""
        return self.vs_channel or self.vs_followers

    @property
    def label(self):
        """Outlier band, the way Virlo/vidIQ label them."""
        o = self.outlier
        if o is None:
            return ""
        return "🔥 mega" if o >= 10 else "⚡ viral" if o >= 3 else "↑ above" if o >= 1.5 else ""

    @property
    def weighted(self):
        """ln(× usual) × ln(baseline): a 20× hit on a 50-view channel ranks below a 5× hit on a 100K channel."""
        import math
        o = self.outlier
        base = self.channel_median or self.followers
        if not o or o <= 1 or not base or base <= 1:
            return 0.0
        return math.log(o) * math.log(base)

    @property
    def early(self):
        """Under 6 hours old: per-day numbers are still unreliable."""
        return self.age_days is not None and self.age_days < 0.25

    @property
    def thumbnail(self):
        if self.platform == "youtube":
            return f"https://i.ytimg.com/vi/{self.id}/hqdefault.jpg"
        return self.thumb_url

    def merge(self, other: "Item"):
        for f in ("title", "channel", "channel_url", "channel_id", "followers", "views", "likes",
                  "comments", "duration", "published", "channel_median", "description", "caption_url",
                  "transcript", "hook", "cta", "wpm", "creator_pct", "thumb_url", "frame", "pace_median",
                  "topic_median"):
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
