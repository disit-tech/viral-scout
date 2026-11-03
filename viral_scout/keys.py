"""API keys: what each unlocks, where to get it, a cheap live test, and saving to .env (local only).

  python -m viral_scout keys                 # status (values masked)
  python -m viral_scout keys test [NAME]     # live test
  python -m viral_scout keys set NAME VALUE  # write to .env
Values are never printed in full.
"""
import json
import os
import re

import requests

from . import config

KEYS = [
    {"name": "YOUTUBE_API_KEY", "group": "YouTube Data API", "cost": "free (10,000 units/day)",
     "unlocks": "Keyword search for Shorts (per language), age-matched baselines.",
     "get": "Google Cloud console → APIs & Services → enable YouTube Data API v3 → Credentials → API key.",
     "docs": "https://developers.google.com/youtube/v3/getting-started"},
    {"name": "IG_GRAPH_TOKEN", "group": "Instagram Graph API", "cost": "free (needs a business account)",
     "unlocks": "Instagram watch list (Business Discovery) and hashtag top posts (30 hashtags / 7 days).",
     "get": "Meta for Developers → app with instagram_basic + pages_read_engagement → long-lived token.",
     "docs": "https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/business_discovery"},
    {"name": "IG_GRAPH_USER_ID", "group": "Instagram Graph API", "cost": "",
     "unlocks": "Your Instagram business account id (pairs with IG_GRAPH_TOKEN).",
     "get": "Graph API Explorer: me/accounts → instagram_business_account.id.",
     "docs": "https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/getting-started"},
    {"name": "APIFY_TOKEN", "group": "Apify", "cost": "paid per result",
     "unlocks": "TikTok discovery, TikTok watch list, trending hashtags.",
     "get": "apify.com → Settings → Integrations → Personal API token.",
     "docs": "https://docs.apify.com/api/v2"},
    {"name": "APIFY_TRENDS_ACTOR", "group": "Apify", "cost": "",
     "unlocks": "Actor id for trending hashtags (e.g. a TikTok Creative Center trends actor from the Apify store).",
     "get": "Pick an actor in the Apify store; copy its id (user~actor).",
     "docs": "https://apify.com/store?search=tiktok%20trends"},
    {"name": "META_AD_LIBRARY_TOKEN", "group": "Ads: Meta Ad Library API", "cost": "free (identity-verified developer)",
     "unlocks": "Ads scout: ads delivered in the EU (copy, start/stop dates, platforms, EU reach) plus political/issue "
                "ads anywhere. US commercial ads are NOT in the API; use APIFY_ADS_ACTOR for those.",
     "get": "Confirm your identity and location at facebook.com/ID → Meta for Developers app → Graph API Explorer → "
            "user access token (exchange it for a long-lived one).",
     "docs": "https://developers.facebook.com/docs/graph-api/reference/ads_archive/"},
    {"name": "TIKTOK_RESEARCH_CLIENT_KEY", "group": "Ads: TikTok Commercial Content API", "cost": "free (application)",
     "unlocks": "Ads scout: TikTok ads shown in the EEA (first/last shown, reach, video/images; no ad copy).",
     "get": "TikTok for Developers → apply for the Commercial Content API → after approval, copy the research "
            "client key from the portal's research section.",
     "docs": "https://developers.tiktok.com/doc/commercial-content-api-getting-started"},
    {"name": "TIKTOK_RESEARCH_CLIENT_SECRET", "group": "Ads: TikTok Commercial Content API", "cost": "",
     "unlocks": "Pairs with TIKTOK_RESEARCH_CLIENT_KEY (client-credentials token, valid 2 hours).",
     "get": "Same place as the client key.",
     "docs": "https://developers.tiktok.com/doc/client-access-token-management"},
    {"name": "APIFY_ADS_ACTOR", "group": "Ads: Apify actors", "cost": "paid per ad (uses APIFY_TOKEN)",
     "unlocks": "Ads scout: the Meta Ad Library for any country, including the US (e.g. apify~facebook-ads-scraper).",
     "get": "Pick a Meta Ad Library actor in the Apify store; copy its id (user~actor). Check its price per result.",
     "docs": "https://apify.com/apify/facebook-ads-scraper"},
    {"name": "APIFY_TIKTOK_ADS_ACTOR", "group": "Ads: Apify actors", "cost": "paid (uses APIFY_TOKEN)",
     "unlocks": "Ads scout: TikTok Creative Center Top Ads (no public API). Input in the profile: ads.tiktok_top_input.",
     "get": "Pick a TikTok Creative Center top-ads actor in the Apify store; copy its id.",
     "docs": "https://apify.com/store?search=tiktok%20top%20ads"},
    {"name": "APIFY_GOOGLE_ADS_ACTOR", "group": "Ads: Apify actors", "cost": "paid (uses APIFY_TOKEN)",
     "unlocks": "Ads scout: Google Ads Transparency Center by domain/advertiser (no public API). Input: ads.google_input.",
     "get": "Pick a Google Ads Transparency actor in the Apify store; copy its id.",
     "docs": "https://apify.com/store?search=google%20ads%20transparency"},
    {"name": "GOOGLE_PLACES_API_KEY", "group": "Google Places API (New)", "cost": "free monthly credit, then paid",
     "unlocks": "Local competitors: nearby businesses in your niche and their public social channels.",
     "get": "Google Cloud console → enable Places API (New) → Credentials → API key (restrict it).",
     "docs": "https://developers.google.com/maps/documentation/places/web-service/text-search"},
    {"name": "TELEGRAM_BOT_TOKEN", "group": "Telegram alerts", "cost": "free",
     "unlocks": "Push alerts for new outliers (or point a profile's alerts.env_file at another app's bot).",
     "get": "Telegram → @BotFather → /newbot.",
     "docs": "https://core.telegram.org/bots/api#sendmessage"},
    {"name": "TELEGRAM_CHAT_ID", "group": "Telegram alerts", "cost": "",
     "unlocks": "Where alerts go.",
     "get": "Message your bot, open https://api.telegram.org/bot<token>/getUpdates, copy message.chat.id.",
     "docs": "https://core.telegram.org/bots/api#getupdates"},
    {"name": "VIRAL_SCOUT_YTDLP", "group": "Tools", "cost": "free",
     "unlocks": "Path to a yt-dlp clone with newer extractors than the pip package.",
     "get": "git clone https://github.com/yt-dlp/yt-dlp",
     "docs": "https://github.com/yt-dlp/yt-dlp"},
]
NAMES = {k["name"] for k in KEYS}
ENV = config.ROOT / ".env"


def mask(v):
    if not v:
        return ""
    return "•" * 6 + v[-4:] if len(v) > 8 else "•" * len(v)


def status():
    config.load_env()
    return [{**k, "set": bool(os.environ.get(k["name"])), "masked": mask(os.environ.get(k["name"], ""))} for k in KEYS]


def set_key(name, value):
    if name not in NAMES:
        raise ValueError(f"unknown key {name}")
    if "\n" in value or "\r" in value:
        raise ValueError("value must be one line")
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    out, done = [], False
    for line in lines:
        if re.match(rf"\s*#?\s*{name}\s*=", line):
            if not done:
                out.append(f"{name}={value}" if value else f"# {name}=")
                done = True
            continue
        out.append(line)
    if not done:
        out.append(f"{name}={value}")
    ENV.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.environ[name] = value


def test(name):
    """Cheapest live call per key. Returns (ok, message)."""
    config.load_env()
    v = os.environ.get(name, "")
    if not v:
        return False, "not set"
    try:
        if name == "YOUTUBE_API_KEY":
            r = requests.get("https://www.googleapis.com/youtube/v3/videos",
                             params={"part": "id", "id": "jNQXAC9IVRw", "key": v}, timeout=20)  # 1 unit
            return r.ok, "ok (1 quota unit)" if r.ok else r.json().get("error", {}).get("message", r.text[:120])
        if name in ("IG_GRAPH_TOKEN", "IG_GRAPH_USER_ID"):
            uid = os.environ.get("IG_GRAPH_USER_ID", "")
            r = requests.get(f"https://graph.facebook.com/v21.0/{uid or 'me'}",
                             params={"fields": "id,username" if uid else "id,name",
                                     "access_token": os.environ.get("IG_GRAPH_TOKEN", "")}, timeout=20)
            d = r.json()
            return r.ok, f"ok: {d.get('username') or d.get('name')}" if r.ok else d.get("error", {}).get("message", "")
        if name == "APIFY_TOKEN":
            r = requests.get("https://api.apify.com/v2/users/me", params={"token": v}, timeout=20)
            return r.ok, f"ok: {r.json()['data'].get('username')}" if r.ok else r.text[:120]
        if name == "TELEGRAM_BOT_TOKEN":
            r = requests.get(f"https://api.telegram.org/bot{v}/getMe", timeout=20)
            return r.ok, f"ok: @{r.json()['result'].get('username')}" if r.ok else r.text[:120]
        if name == "GOOGLE_PLACES_API_KEY":
            # Minimal field mask (IDs only) keeps the call in the cheapest SKU.
            r = requests.post("https://places.googleapis.com/v1/places:searchText",
                              headers={"X-Goog-Api-Key": v, "X-Goog-FieldMask": "places.id"},
                              json={"textQuery": "coffee in Chicago", "pageSize": 1}, timeout=20)
            return r.ok, "ok (1 ID-only request)" if r.ok else r.json().get("error", {}).get("message", r.text[:120])
        if name == "META_AD_LIBRARY_TOKEN":
            # One EU ad, ID only: the cheapest read of the Ad Library API.
            from .ads.sources import GRAPH_VERSION
            r = requests.get(f"https://graph.facebook.com/{GRAPH_VERSION}/ads_archive",
                             params={"search_terms": "solar", "ad_reached_countries": '["DE"]', "ad_type": "ALL",
                                     "fields": "id", "limit": 1, "access_token": v}, timeout=20)
            d = r.json()
            return r.ok, "ok (1 request)" if r.ok else d.get("error", {}).get("message", r.text[:160])
        if name in ("TIKTOK_RESEARCH_CLIENT_KEY", "TIKTOK_RESEARCH_CLIENT_SECRET"):
            # Only fetches a client token; doesn't use the query quota.
            r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", timeout=20,
                              data={"client_key": os.environ.get("TIKTOK_RESEARCH_CLIENT_KEY", ""),
                                    "client_secret": os.environ.get("TIKTOK_RESEARCH_CLIENT_SECRET", ""),
                                    "grant_type": "client_credentials"})
            d = r.json()
            ok = bool(d.get("access_token"))
            return ok, "ok (client token issued)" if ok else (d.get("error_description") or d.get("error") or r.text[:160])
        if name in ("APIFY_ADS_ACTOR", "APIFY_TIKTOK_ADS_ACTOR", "APIFY_GOOGLE_ADS_ACTOR", "APIFY_TRENDS_ACTOR"):
            # Looks the actor up (free); doesn't run it.
            r = requests.get(f"https://api.apify.com/v2/acts/{v}", params={"token": os.environ.get("APIFY_TOKEN", "")},
                             timeout=20)
            return r.ok, f"ok: {r.json()['data'].get('title') or v}" if r.ok else r.text[:160]
        if name == "VIRAL_SCOUT_YTDLP":
            return os.path.isdir(os.path.join(v, "yt_dlp")), "ok" if os.path.isdir(os.path.join(v, "yt_dlp")) else "no yt_dlp folder there"
        return True, "set (no live test for this one)"
    except (requests.RequestException, ValueError, KeyError) as err:
        return False, str(err)[:160]


def cli(args):
    if not args or args[0] == "status":
        print(json.dumps(status(), indent=1))
        return 0
    if args[0] == "test":
        names = args[1:] or [k["name"] for k in KEYS if os.environ.get(k["name"])]
        res = {n: dict(zip(("ok", "message"), test(n))) for n in names}
        print(json.dumps(res, indent=1))
        return 0 if all(r["ok"] for r in res.values()) else 1
    if args[0] == "set" and len(args) in (2, 3):
        set_key(args[1], args[2] if len(args) == 3 else "")
        print(f"{args[1]} {'saved' if len(args) == 3 and args[2] else 'cleared'} ({mask(args[2] if len(args) == 3 else '')})")
        return 0
    print("usage: keys [status] | keys test [NAME...] | keys set NAME [VALUE]")
    return 2
