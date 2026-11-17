"""Hashtags at the end of every Telegram message viral-scout sends, so the group can be searched by business, kind,
platform or idea (#LightsOnIllinois #post #tiktok). Same rules as the bot service (service/src/lib/ui.ts, tagsLine):
the business tag is `studio.hashtag`, else `studio.brand` (or display_name) in CamelCase, else the profile name.
"""
import re

_NOT_TAG = re.compile(r"[^\w]+", re.UNICODE)


def hashtag(text):
    """'#word' from any text: letters, digits and _ only; '' when no letter is left (Telegram wouldn't link it)."""
    t = _NOT_TAG.sub("", str(text or ""))
    return f"#{t}" if re.search(r"[^\W\d_]", t) else ""


def business(cfg):
    st = cfg.get("studio") if isinstance(cfg.get("studio"), dict) else {}
    if st.get("hashtag"):
        return hashtag(st["hashtag"])
    name = st.get("brand") or cfg.get("display_name") or ""
    camel = "".join(w[:1].upper() + w[1:] for w in re.split(r"[^\w]+|_", name) if w)
    return hashtag(camel) or hashtag(cfg.get("name", ""))


def line(cfg, *kinds, platforms=()):
    """'#Business #kind … #platform …', each tag once."""
    tags = [business(cfg), *map(hashtag, kinds), *map(hashtag, platforms)]
    return " ".join(dict.fromkeys(t for t in tags if t))
