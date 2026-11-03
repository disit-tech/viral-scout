"""One ad, with what the sources give and what we derive (days running, hook, offers, score)."""
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse


@dataclass
class Ad:
    source: str                      # meta_api | tiktok_api | apify_meta | apify_tiktok_top | apify_google
    id: str
    advertiser: str = ""
    advertiser_id: str = ""
    url: str = ""                    # public library page for this ad (Ad Library, TikTok library, Transparency Center)
    snapshot_url: str = ""           # Meta ad_snapshot_url (needs the access token to render; never shown in public exports)
    image: str = ""                  # creative image / video preview, when the source gives one
    video: str = ""
    body: str = ""                   # primary text
    title: str = ""                  # headline / link title
    link_caption: str = ""           # Meta: usually the display domain
    link_url: str = ""
    cta_text: str = ""               # button text when the source gives it
    format: str = ""                 # video | image | carousel | text | dco | unknown
    platforms: list = field(default_factory=list)
    countries: list = field(default_factory=list)
    start: Optional[datetime] = None
    stop: Optional[datetime] = None
    active: Optional[bool] = None
    reach: Optional[int] = None      # EU reach (Meta), unique users seen (TikTok), views/impressions (Creative Center)
    reach_label: str = ""            # what reach means for this source
    likes: Optional[int] = None      # Creative Center likes, when given
    variants_reported: Optional[int] = None   # source's own count (Meta collationCount)
    found_by: list = field(default_factory=list)
    # derived (score.py / extract.py)
    hook: str = ""
    offers: list = field(default_factory=list)
    offer_text: list = field(default_factory=list)
    cta: str = ""
    variants: int = 1
    group: str = ""
    reach_pct: Optional[float] = None
    ad_score: float = 0.0
    labels: list = field(default_factory=list)
    catalog: bool = False            # Meta dynamic/catalog ad (text filled per viewer from a product feed)
    new: bool = False

    @property
    def key(self):
        return f"{self.source}:{self.id}"

    @property
    def landing_domain(self):
        for v in (self.link_url, self.link_caption):
            d = domain(v)
            if d:
                return d
        return ""

    @property
    def is_active(self):
        if self.active is not None:
            return self.active
        return self.stop is None or self.stop >= now()

    @property
    def days_running(self):
        """Days from the start date to the stop date, or to now while it still runs. None without a start date."""
        if not self.start:
            return None
        if self.active is False and self.stop is None:
            return None           # stopped, but the source didn't say when: unknown, not counted as long-running
        end = self.stop if self.stop and self.stop < now() else now()
        return max((end - self.start).total_seconds() / 86400, 0.0)

    @property
    def age_days(self):
        return None if not self.start else max((now() - self.start).total_seconds() / 86400, 0.0)

    def text(self):
        return " ".join(x for x in (self.title, self.body, self.link_caption, self.cta_text) if x)

    def to_json(self):
        return {
            "key": self.key, "source": self.source, "id": self.id, "advertiser": self.advertiser,
            "advertiser_id": self.advertiser_id, "url": self.url, "image": self.image, "video": self.video,
            "body": self.body[:1500], "title": self.title, "link_caption": self.link_caption, "link_url": self.link_url,
            "landing_domain": self.landing_domain, "cta_text": self.cta_text, "format": self.format or "unknown",
            "platforms": self.platforms, "countries": self.countries,
            "start": self.start.isoformat() if self.start else None,
            "stop": self.stop.isoformat() if self.stop else None,
            "active": self.is_active, "days_running": round(self.days_running, 1) if self.days_running is not None else None,
            "reach": self.reach, "reach_label": self.reach_label, "likes": self.likes,
            "variants": self.variants, "variants_reported": self.variants_reported, "group": self.group,
            "hook": self.hook, "offers": self.offers, "offer_text": self.offer_text, "cta": self.cta,
            "reach_pct": self.reach_pct, "ad_score": self.ad_score, "labels": self.labels,
            "found_by": self.found_by, "new": self.new,
            "has_snapshot": bool(self.snapshot_url),
        }


def now():
    return datetime.now(timezone.utc)


def domain(v):
    """'https://www.Sunrun.com/x' or 'SUNRUN.COM' → 'sunrun.com'. Tracking redirects (l.facebook.com) are unwrapped."""
    if not v:
        return ""
    v = str(v).strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", v, re.I):
        if not re.fullmatch(r"(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/\S*)?", v, re.I):
            return ""
        v = "https://" + v
    try:
        p = urlparse(v)
    except ValueError:
        return ""
    host = (p.hostname or "").lower()
    if host in ("l.facebook.com", "lm.facebook.com") and "u=" in p.query:
        from urllib.parse import parse_qs
        return domain((parse_qs(p.query).get("u") or [""])[0])
    return host[4:] if host.startswith("www.") else host


def unwrap(url):
    """Facebook's outbound redirect (l.facebook.com/l.php?u=...) → the real URL."""
    if not url or "facebook.com/l.php" not in url:
        return url or ""
    from urllib.parse import parse_qs
    try:
        return (parse_qs(urlparse(url).query).get("u") or [url])[0]
    except ValueError:
        return url


_MONTHS = "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"


def parse_when(v):
    """Unix seconds/ms, ISO 8601, YYYYMMDD, YYYY-MM-DD or 'Jan 5, 2026' → aware UTC datetime, else None."""
    if v in (None, "", 0):
        return None
    try:
        if isinstance(v, int) and 19000101 <= v <= 21001231:
            v = str(v)                                           # TikTok returns YYYYMMDD as a number
        if isinstance(v, (int, float)) or (isinstance(v, str) and re.fullmatch(r"\d{9,13}", v.strip())):
            x = float(v)
            if x > 1e12:
                x /= 1000
            return datetime.fromtimestamp(x, tz=timezone.utc)
        s = str(v).strip()
        if re.fullmatch(r"\d{8}", s):
            return datetime.strptime(s, "%Y%m%d").replace(tzinfo=timezone.utc)
        if re.match(r"\d{4}-\d{2}-\d{2}", s):
            s = s.replace("Z", "+00:00")
            s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)       # Graph API: +0000 → +00:00
            d = datetime.fromisoformat(s if "T" in s or " " in s else s[:10])
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        for fmt in _MONTHS:
            try:
                return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
    except (ValueError, OSError, OverflowError):
        return None
    return None


def parse_count(v):
    """12345, '12,345', '11K', '1.2M', '100K+' → int, else None."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, dict):                       # {lower_bound, upper_bound} ranges
        lo, hi = parse_count(v.get("lower_bound")), parse_count(v.get("upper_bound"))
        return lo if hi is None else (hi if lo is None else (lo + hi) // 2)
    m = re.match(r"^\s*([\d.,]+)\s*([kmb])?", str(v), re.I)
    if not m:
        return None
    try:
        x = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    return int(x * {"k": 1e3, "m": 1e6, "b": 1e9}.get((m.group(2) or "").lower(), 1))
