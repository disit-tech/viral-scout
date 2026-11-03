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
     "unlocks": "Instagram watch list (Business Discovery), hashtag top posts (30 hashtags / 7 days), and your own "
                "reels' insights for Your performance (needs instagram_manage_insights).",
     "get": "Meta for Developers → app with instagram_basic + pages_read_engagement (+ instagram_manage_insights, "
            "instagram_manage_comments for own performance) → long-lived token.",
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
    {"name": "YT_OAUTH_CLIENT_ID", "group": "YouTube Analytics (your channel)", "cost": "free",
     "unlocks": "Your performance: your own channel's views, watch time, avg % viewed, retention curves, shares, "
                "subscribers gained (OAuth client, pairs with the secret and refresh token).",
     "get": "Google Cloud console → enable YouTube Analytics API + YouTube Data API v3 → OAuth consent screen → "
            "Credentials → OAuth client ID → Desktop app.",
     "docs": "https://developers.google.com/youtube/reporting/guides/authorization/installed-apps"},
    {"name": "YT_OAUTH_CLIENT_SECRET", "group": "YouTube Analytics (your channel)", "cost": "",
     "unlocks": "The Desktop OAuth client's secret.",
     "get": "Same OAuth client → Client secret.",
     "docs": "https://developers.google.com/identity/protocols/oauth2/native-app"},
    {"name": "YT_OAUTH_REFRESH_TOKEN", "group": "YouTube Analytics (your channel)", "cost": "",
     "unlocks": "Read-only access to your channel's analytics without logging in each time.",
     "get": "Run: python -m viral_scout perf auth youtube (opens Google's consent page, saves the token here).",
     "docs": "https://developers.google.com/youtube/analytics/reference/reports/query"},
    {"name": "META_ADS_TOKEN", "group": "Meta Marketing API (your ads)", "cost": "free",
     "unlocks": "Your performance: your Meta ads' impressions, hook rate (3-s plays), ThruPlays, quartiles, CTR, "
                "CPC, CPM, leads, purchases, ROAS, daily frequency for fatigue.",
     "get": "Meta for Developers → app with Marketing API → Business Settings → System user with ads_read on the "
            "ad account → generate token.",
     "docs": "https://developers.facebook.com/documentation/ads-commerce/marketing-api/insights"},
    {"name": "META_AD_ACCOUNT_ID", "group": "Meta Marketing API (your ads)", "cost": "",
     "unlocks": "Which ad account to read (act_123… or the number).",
     "get": "Ads Manager → account dropdown, or Business Settings → Ad accounts.",
     "docs": "https://developers.facebook.com/documentation/ads-commerce/marketing-api/insights"},
    {"name": "TIKTOK_ADS_TOKEN", "group": "TikTok API for Business (your ads)", "cost": "free",
     "unlocks": "Your performance: your TikTok ads' 2-s/6-s views, 25–100% views, avg play time, CTR, CPC, CPM, "
                "conversions, CPA, ROAS, daily frequency.",
     "get": "TikTok for Business developers → create an app with Reporting permission → authorize your advertiser "
            "account → long-term access token.",
     "docs": "https://business-api.tiktok.com/portal/docs"},
    {"name": "TIKTOK_ADVERTISER_ID", "group": "TikTok API for Business (your ads)", "cost": "",
     "unlocks": "Which advertiser account to read.",
     "get": "TikTok Ads Manager → account info (Advertiser ID).",
     "docs": "https://business-api.tiktok.com/portal/docs"},
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
        if name in ("YT_OAUTH_CLIENT_ID", "YT_OAUTH_CLIENT_SECRET", "YT_OAUTH_REFRESH_TOKEN"):
            from .perf import youtube as ytp
            if ytp.missing_keys():
                return False, "set all three: " + ", ".join(ytp.missing_keys()) + " missing"
            errs = []
            tok = ytp.access_token(errs)
            if not tok:
                return False, errs[0] if errs else "token refresh failed"
            r = requests.get(ytp.REPORTS, params={"ids": "channel==MINE", "startDate": "2026-01-01",
                                                  "endDate": "2026-01-02", "metrics": "views"},
                             headers={"Authorization": f"Bearer {tok}"}, timeout=20)
            return r.ok, "ok (analytics read)" if r.ok else r.json().get("error", {}).get("message", r.text[:120])
        if name in ("META_ADS_TOKEN", "META_AD_ACCOUNT_ID"):
            from .perf.meta_ads import API, account
            if not os.environ.get("META_AD_ACCOUNT_ID"):
                return False, "META_AD_ACCOUNT_ID not set"
            r = requests.get(f"{API}/{account()}", params={"fields": "name,currency",
                                                          "access_token": os.environ.get("META_ADS_TOKEN", "")}, timeout=20)
            d = r.json()
            return r.ok, f"ok: {d.get('name')} ({d.get('currency')})" if r.ok else d.get("error", {}).get("message", "")
        if name in ("TIKTOK_ADS_TOKEN", "TIKTOK_ADVERTISER_ID"):
            r = requests.get("https://business-api.tiktok.com/open_api/v1.3/advertiser/info/",
                             params={"advertiser_ids": json.dumps([os.environ.get("TIKTOK_ADVERTISER_ID", "")])},
                             headers={"Access-Token": os.environ.get("TIKTOK_ADS_TOKEN", "")}, timeout=20)
            d = r.json()
            ok = d.get("code") == 0
            return ok, "ok" if ok else d.get("message", r.text[:120])
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
