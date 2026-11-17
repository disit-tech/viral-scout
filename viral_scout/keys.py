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
    {"name": "APIFY_TRENDS_ACTOR", "secret": False, "group": "Apify", "cost": "",
     "unlocks": "Actor id for trending hashtags (e.g. a TikTok Creative Center trends actor from the Apify store).",
     "get": "Pick an actor in the Apify store; copy its id (user~actor).",
     "docs": "https://apify.com/store?search=tiktok%20trends"},
    {"name": "META_AD_LIBRARY_TOKEN", "group": "Ads: Meta Ad Library API", "cost": "free (identity-verified developer)",
     "unlocks": "Ads scout: ads delivered in the EU (copy, start/stop dates, platforms, EU reach) plus political/issue "
                "ads anywhere. US commercial ads are NOT in the API; use APIFY_ADS_ACTOR for those.",
     "get": "Confirm your identity and location at facebook.com/ID → Meta for Developers app → Graph API Explorer → "
            "user access token (exchange it for a long-lived one).",
     "docs": "https://developers.facebook.com/docs/graph-api/reference/ads_archive/"},
    {"name": "TIKTOK_RESEARCH_CLIENT_KEY", "group": "Ads: TikTok Commercial Content API", "cost": "free, once TikTok approves your application",
     "unlocks": "Ads scout: TikTok ads shown in the EEA (first/last shown, reach, video/images; no ad copy).",
     "get": "TikTok for Developers → apply for the Commercial Content API → after approval, copy the research "
            "client key from the portal's research section.",
     "docs": "https://developers.tiktok.com/doc/commercial-content-api-getting-started"},
    {"name": "TIKTOK_RESEARCH_CLIENT_SECRET", "group": "Ads: TikTok Commercial Content API", "cost": "",
     "unlocks": "Pairs with TIKTOK_RESEARCH_CLIENT_KEY (client-credentials token, valid 2 hours).",
     "get": "Same place as the client key.",
     "docs": "https://developers.tiktok.com/doc/client-access-token-management"},
    {"name": "APIFY_ADS_ACTOR", "secret": False, "group": "Ads: Apify actors", "cost": "$3.40–5.80 per 1,000 ads by Apify plan",
     "unlocks": "Ads scout: the Meta Ad Library for any country, including the US (e.g. apify~facebook-ads-scraper).",
     "get": "Pick a Meta Ad Library actor in the Apify store; copy its id (user~actor). Check its price per result.",
     "docs": "https://apify.com/apify/facebook-ads-scraper"},
    {"name": "APIFY_TIKTOK_ADS_ACTOR", "secret": False, "group": "Ads: Apify actors", "cost": "$2 per 1,000 ads + $0.005 per run",
     "unlocks": "Ads scout: TikTok Creative Center Top Ads for an industry (no keyword search, no start dates). "
                "Set ads.tiktok_top_input.industries in the profile, e.g. [Home Improvement].",
     "get": "Use pulsedata~tiktok-creative-center-top-ads-scraper (the mapping is written and tested for it).",
     "docs": "https://apify.com/pulsedata/tiktok-creative-center-top-ads-scraper"},
    {"name": "APIFY_GOOGLE_ADS_ACTOR", "secret": False, "group": "Ads: Apify actors", "cost": "$1.30 per 1,000 ads + $0.005 per run",
     "unlocks": "Ads scout: Google Ads Transparency Center (Search, YouTube, Display) by competitor domain and name, "
                "with first/last shown dates. Runs in batches of 6 competitors.",
     "get": "Use automation-lab~google-ads-scraper (the mapping is written and tested for it).",
     "docs": "https://apify.com/automation-lab/google-ads-scraper"},
    {"name": "APIFY_GOOGLE_TRENDS_ACTOR", "secret": False, "group": "Search demand (Google Trends)",
     "cost": "$0.005 per term (Starter) + run", "unlocks": "Seasonality, rising searches and wording per business "
     "(profile demand: block). Default apify~google-trends-scraper when empty. Uses APIFY_TOKEN.",
     "get": "Leave empty for Apify's own actor, or paste another Google Trends actor id.",
     "docs": "https://apify.com/apify/google-trends-scraper"},
    {"name": "APIFY_MAX_USD_PER_RUN", "group": "Spend controls", "cost": "default 0.50", "secret": False,
     "unlocks": "Spend cap for each Apify actor run (Apify maxTotalChargeUsd): a run stops at it instead of using up "
                "the month. 0 = no cap. It caps one run, not the total: each advertiser and keyword is its own run.",
     "get": "A number in USD, e.g. 0.5.",
     "docs": "https://docs.apify.com/api/v2/act-run-sync-get-dataset-items-post"},
    {"name": "VIRAL_SCOUT_MCP_PAID", "group": "Spend controls", "cost": "default off", "secret": False,
     "unlocks": "1 lets MCP clients (any Claude session, any repo) start paid runs: start_run, ads_run, "
                "local_competitors. Off: they get the latest results and the CLI command instead. Restart the MCP "
                "server after changing it.",
     "get": "1 to allow, empty or 0 to block.",
     "docs": "https://modelcontextprotocol.io/specification"},
    {"name": "GOOGLE_PLACES_API_KEY", "group": "Google Places API (New)", "cost": "free: a monthly allowance per API, billed above it",
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
                "CPC, CPM, leads, purchases, ROAS, daily frequency for fatigue. Paid ads page: campaigns, budgets, "
                "spend this month against the cap, and the Pause / Resume / Budget buttons.",
     "get": "Meta for Developers → app with Marketing API → Business Settings → System user assigned to every "
            "business's ad account → generate token with ads_read (reading) and ads_management (pause, resume, "
            "budget). Each business's account id goes in its profile (Paid ads page), not here.",
     "docs": "https://developers.facebook.com/documentation/ads-commerce/marketing-api/insights"},
    {"name": "META_AD_ACCOUNT_ID", "group": "Meta Marketing API (your ads)", "cost": "",
     "unlocks": "Which ad account to read (act_123… or the number).",
     "get": "Ads Manager → account dropdown, or Business Settings → Ad accounts.",
     "docs": "https://developers.facebook.com/documentation/ads-commerce/marketing-api/insights"},
    {"name": "TIKTOK_ADS_TOKEN", "group": "TikTok API for Business (your ads)", "cost": "free",
     "unlocks": "Your performance: your TikTok ads' 2-s/6-s views, 25–100% views, avg play time, CTR, CPC, CPM, "
                "conversions, CPA, ROAS, daily frequency. Paid ads page: campaigns, budgets, spend, Pause / Resume / Budget.",
     "get": "TikTok for Business developers → create an app with Reporting and Campaign Management permissions → "
            "authorize every business's advertiser account → long-term access token.",
     "docs": "https://business-api.tiktok.com/portal/docs"},
    {"name": "TIKTOK_ADVERTISER_ID", "group": "TikTok API for Business (your ads)", "cost": "",
     "unlocks": "Which advertiser account to read.",
     "get": "TikTok Ads Manager → account info (Advertiser ID).",
     "docs": "https://business-api.tiktok.com/portal/docs"},
    {"name": "VIRAL_SCOUT_YTDLP", "group": "Tools", "cost": "free",
     "unlocks": "Path to a yt-dlp clone with newer extractors than the pip package.",
     "get": "git clone https://github.com/yt-dlp/yt-dlp",
     "docs": "https://github.com/yt-dlp/yt-dlp"},
    {"name": "OBSIDIAN_VAULT", "group": "Tools", "cost": "free", "secret": False,
     "unlocks": "Your Obsidian vault folder. Profiles write reports, ideas notes and the swipe file to "
                "${OBSIDIAN_VAULT}/projects/<project>/…; New business lists the vault's projects. Unset, they go to "
                "reports/<profile>/ in the repo.",
     "get": "The folder that holds your vault's .obsidian folder. Best as a user environment variable "
            "(PowerShell: [Environment]::SetEnvironmentVariable('OBSIDIAN_VAULT','D:\\Obsidian\\vault','User')), "
            "then restart the terminal and the dashboard. Saved here it goes into .env, which only the Python CLI reads.",
     "docs": "https://help.obsidian.md/Files+and+folders/Manage+vaults"},
]

# How much each key matters (the Setup pages group by this, most important first) and what it costs.
#   essential    videos, ads and search demand run on these
#   recommended  your own numbers, alerts
#   optional     specific cases: local competitors, TikTok ads, EU-only ad libraries
#   advanced     settings you rarely change
TIER = {
    "YOUTUBE_API_KEY": "essential", "APIFY_TOKEN": "essential", "APIFY_ADS_ACTOR": "essential",
    "APIFY_GOOGLE_ADS_ACTOR": "essential", "APIFY_TIKTOK_ADS_ACTOR": "essential",
    "APIFY_GOOGLE_TRENDS_ACTOR": "essential", "APIFY_MAX_USD_PER_RUN": "essential",
    "IG_GRAPH_TOKEN": "recommended", "IG_GRAPH_USER_ID": "recommended", "META_ADS_TOKEN": "recommended",
    "META_AD_ACCOUNT_ID": "recommended", "TELEGRAM_BOT_TOKEN": "recommended", "TELEGRAM_CHAT_ID": "recommended",
    "YT_OAUTH_CLIENT_ID": "recommended", "YT_OAUTH_CLIENT_SECRET": "recommended", "YT_OAUTH_REFRESH_TOKEN": "recommended",
    "GOOGLE_PLACES_API_KEY": "optional", "TIKTOK_ADS_TOKEN": "optional", "TIKTOK_ADVERTISER_ID": "optional",
    "META_AD_LIBRARY_TOKEN": "optional", "TIKTOK_RESEARCH_CLIENT_KEY": "optional",
    "TIKTOK_RESEARCH_CLIENT_SECRET": "optional", "APIFY_TRENDS_ACTOR": "optional",
    "VIRAL_SCOUT_MCP_PAID": "advanced", "VIRAL_SCOUT_YTDLP": "advanced", "OBSIDIAN_VAULT": "recommended",
}
#   free        no charge (some need an account or an application)
#   free_tier   a free monthly allowance, then paid
#   paid        every run costs money (Apify bills per result; the actor ids pick what gets billed)
#   control     a spending setting, not a source
PRICE = {
    "APIFY_TOKEN": "paid", "APIFY_ADS_ACTOR": "paid", "APIFY_GOOGLE_ADS_ACTOR": "paid", "APIFY_TIKTOK_ADS_ACTOR": "paid",
    "APIFY_GOOGLE_TRENDS_ACTOR": "paid", "APIFY_TRENDS_ACTOR": "paid",
    "GOOGLE_PLACES_API_KEY": "free_tier",
    "APIFY_MAX_USD_PER_RUN": "control", "VIRAL_SCOUT_MCP_PAID": "control",
}
# Settings that work unset (the code has a default): the Setup pages count them as done.
HAS_DEFAULT = {"APIFY_GOOGLE_TRENDS_ACTOR", "APIFY_MAX_USD_PER_RUN", "VIRAL_SCOUT_MCP_PAID"}
# What each key is for (tags and filters on the Setup pages).
USES = {
    "YOUTUBE_API_KEY": ["videos"], "IG_GRAPH_TOKEN": ["videos", "performance"], "IG_GRAPH_USER_ID": ["videos", "performance"],
    "APIFY_TOKEN": ["videos", "ads", "demand"], "APIFY_TRENDS_ACTOR": ["videos"],
    "META_AD_LIBRARY_TOKEN": ["ads"], "TIKTOK_RESEARCH_CLIENT_KEY": ["ads"], "TIKTOK_RESEARCH_CLIENT_SECRET": ["ads"],
    "APIFY_ADS_ACTOR": ["ads"], "APIFY_TIKTOK_ADS_ACTOR": ["ads"], "APIFY_GOOGLE_ADS_ACTOR": ["ads"],
    "APIFY_GOOGLE_TRENDS_ACTOR": ["demand"], "APIFY_MAX_USD_PER_RUN": ["videos", "ads", "demand"],
    "VIRAL_SCOUT_MCP_PAID": ["tools"], "GOOGLE_PLACES_API_KEY": ["local"],
    "TELEGRAM_BOT_TOKEN": ["alerts"], "TELEGRAM_CHAT_ID": ["alerts"],
    "YT_OAUTH_CLIENT_ID": ["performance"], "YT_OAUTH_CLIENT_SECRET": ["performance"], "YT_OAUTH_REFRESH_TOKEN": ["performance"],
    "META_ADS_TOKEN": ["performance", "paid"], "META_AD_ACCOUNT_ID": ["performance"],
    "TIKTOK_ADS_TOKEN": ["performance", "paid"], "TIKTOK_ADVERTISER_ID": ["performance"], "VIRAL_SCOUT_YTDLP": ["videos"],
    "OBSIDIAN_VAULT": ["tools"],
}
for _k in KEYS:
    _k.setdefault("tier", TIER.get(_k["name"], "optional"))
    _k.setdefault("price", PRICE.get(_k["name"], "free"))
    _k.setdefault("has_default", _k["name"] in HAS_DEFAULT)
    _k.setdefault("uses", USES.get(_k["name"], []))

NAMES = {k["name"] for k in KEYS}
ENV = config.ROOT / ".env"


def mask(v):
    if not v:
        return ""
    return "•" * 6 + v[-4:] if len(v) > 8 else "•" * len(v)


def status():
    config.load_env()
    return [{**k, "set": bool(os.environ.get(k["name"])),
             "masked": os.environ.get(k["name"], "") if k.get("secret") is False else mask(os.environ.get(k["name"], ""))}
            for k in KEYS]


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
            if not r.ok:
                return False, r.text[:120]
            me = r.json()["data"]
            msg = f"ok: {me.get('username')} ({(me.get('plan') or {}).get('id', '?')} plan)"
            # Spend this cycle (free reads): the plan's limit blocks every run once it's used up.
            lim = requests.get("https://api.apify.com/v2/users/me/limits", params={"token": v}, timeout=20)
            if lim.ok:
                d = lim.json()["data"]
                used = (d.get("current") or {}).get("monthlyUsageUsd") or 0
                cap = (d.get("limits") or {}).get("maxMonthlyUsageUsd") or 0
                end = ((d.get("monthlyUsageCycle") or {}).get("endAt") or "")[:10]
                msg += f" · ${used:.2f} of ${cap:.0f} used this cycle (resets {end})"
                if cap and used >= cap:
                    return False, msg + " · LIMIT REACHED: every Apify run is blocked"
                if cap and used >= 0.8 * cap:
                    msg += " · over 80%"
            return True, msg
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
        if name in ("APIFY_ADS_ACTOR", "APIFY_TIKTOK_ADS_ACTOR", "APIFY_GOOGLE_ADS_ACTOR", "APIFY_TRENDS_ACTOR",
                    "APIFY_GOOGLE_TRENDS_ACTOR"):
            # Looks the actor up (free); doesn't run it.
            r = requests.get(f"https://api.apify.com/v2/acts/{v}", params={"token": os.environ.get("APIFY_TOKEN", "")},
                             timeout=20)
            return r.ok, f"ok: {r.json()['data'].get('title') or v}" if r.ok else r.text[:160]
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
        if name == "APIFY_MAX_USD_PER_RUN":
            try:
                cap = float(v)
            except ValueError:
                return False, "not a number"
            return cap >= 0, f"ok: ${cap:.2f} per run" if cap > 0 else "ok: no cap"
        if name == "VIRAL_SCOUT_MCP_PAID":
            on = v.strip().lower() in ("1", "true", "yes", "on")
            return True, "ok: MCP clients may start paid runs" if on else "ok: paid MCP tools are off"
        if name == "VIRAL_SCOUT_YTDLP":
            return os.path.isdir(os.path.join(v, "yt_dlp")), "ok" if os.path.isdir(os.path.join(v, "yt_dlp")) else "no yt_dlp folder there"
        if name == "OBSIDIAN_VAULT":
            if not os.path.isdir(v):
                return False, "no such folder"
            if not os.path.isdir(os.path.join(v, ".obsidian")):
                return False, "folder exists but has no .obsidian folder (not a vault root?)"
            n = len([d for d in os.listdir(os.path.join(v, "projects"))]) if os.path.isdir(os.path.join(v, "projects")) else 0
            return True, f"ok: vault with {n} project folder{'s' if n != 1 else ''}" if n else "ok: vault (no projects/ folder yet)"
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
