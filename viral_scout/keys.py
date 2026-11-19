"""API keys: what each unlocks, where to get it, a cheap live test, and saving to .env (local only).

  python -m viral_scout keys                 # status (values masked)
  python -m viral_scout keys test [NAME]     # live test
  python -m viral_scout keys set NAME VALUE  # write to .env
  python -m viral_scout keys connect meta    # Facebook sign-in fills every Meta key (connect_meta.py)
  python -m viral_scout keys connect google  # one Google sign-in: YouTube Analytics + Google Ads (connect_google.py)
  python -m viral_scout keys connect tiktok  # TikTok advertiser authorization (connect_tiktok.py)
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
    {"name": "META_APP_ID", "group": "Connect Meta (Facebook sign-in)", "cost": "free", "secret": False,
     "unlocks": "Sign in with Facebook once and the Meta keys are filled for you: Instagram token and account id "
                "(a Page token that doesn't expire), ad account, ads token, Ad Library token.",
     "get": "Once: Meta for Developers → Create app (Business) → add Facebook Login for Business → Valid OAuth "
            "Redirect URIs: http://localhost:8765/ → App settings → Basic → App ID. Then press Sign in with Facebook "
            "at the top of this page, or run: python -m viral_scout keys connect meta",
     "docs": "https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow"},
    {"name": "META_APP_SECRET", "group": "Connect Meta (Facebook sign-in)", "cost": "",
     "unlocks": "The app's secret: swaps the sign-in code for tokens and checks when tokens expire.",
     "get": "Same app → App settings → Basic → App secret (Show).",
     "docs": "https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived"},
    {"name": "META_LOGIN_CONFIG_ID", "group": "Connect Meta (Facebook sign-in)", "cost": "", "secret": False,
     "unlocks": "Only if your app's Facebook Login for Business uses a configuration: its id (the configuration holds "
                "the permissions). Empty: the sign-in asks for the permissions itself.",
     "get": "App → Facebook Login for Business → Configurations → the configuration's id.",
     "docs": "https://developers.facebook.com/docs/facebook-login/facebook-login-for-business"},
    {"name": "META_USER_TOKEN", "group": "Connect Meta (Facebook sign-in)", "cost": "",
     "unlocks": "The long-lived token from the Facebook sign-in (about 60 days). The other Meta keys are made from it; "
                "sign in again before it expires (Test shows the date).",
     "get": "Written by Sign in with Facebook (python -m viral_scout keys connect meta), not pasted by hand.",
     "docs": "https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived"},
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
    {"name": "LINKEDIN_CLIENT_ID", "group": "LinkedIn (posting)", "cost": "free",
     "unlocks": "Auto-posting to LinkedIn: each business signs in on its Posting page (Connect LinkedIn).",
     "get": "linkedin.com/developers → Create app → Products: Share on LinkedIn + Sign In with LinkedIn using OpenID "
            "Connect (Community Management API to post as a company Page) → Auth: redirect http://127.0.0.1:8766/ → Client ID.",
     "docs": "https://learn.microsoft.com/linkedin/marketing/community-management/shares/posts-api"},
    {"name": "LINKEDIN_CLIENT_SECRET", "group": "LinkedIn (posting)", "cost": "",
     "unlocks": "The LinkedIn app's secret (pairs with LINKEDIN_CLIENT_ID).",
     "get": "Same app → Auth → Primary Client Secret.",
     "docs": "https://learn.microsoft.com/linkedin/shared/authentication/authorization-code-flow"},
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
    {"name": "TIKTOK_APP_ID", "group": "Connect TikTok (advertiser sign-in)", "cost": "free (after TikTok approves the app)",
     "secret": False,
     "unlocks": "Authorize your TikTok advertiser accounts once and TIKTOK_ADS_TOKEN (no expiry) and TIKTOK_ADVERTISER_ID "
                "are filled for you.",
     "get": "Once: TikTok API for Business → My apps → create an app with Ad Account Management, Campaign Management "
            "and Reporting → Advertiser redirect URL http://localhost:8766/ → wait for approval → App ID. Then press "
            "Sign in with TikTok at the top of this page, or run: python -m viral_scout keys connect tiktok",
     "docs": "https://business-api.tiktok.com/portal/docs?id=1738373164380162"},
    {"name": "TIKTOK_APP_SECRET", "group": "Connect TikTok (advertiser sign-in)", "cost": "",
     "unlocks": "The app's secret: swaps the authorization code for the long-term token.",
     "get": "Same app → Basic information → Secret.",
     "docs": "https://business-api.tiktok.com/portal/docs?id=1738373141733378"},
    {"name": "TIKTOK_APP_REDIRECT_URI", "group": "Connect TikTok (advertiser sign-in)", "cost": "", "secret": False,
     "unlocks": "The Advertiser redirect URL registered on the app. Default http://localhost:8766/ (the callback runs "
                "on this PC). If TikTok only accepts https, put that address here and paste where the browser lands.",
     "get": "Exactly what's in the app's Advertiser redirect URL field.",
     "docs": "https://business-api.tiktok.com/portal/docs?id=1738373164380162"},
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
    {"name": "GOOGLE_ADS_CLIENT_ID", "group": "Google Ads API (your ads)", "cost": "free",
     "unlocks": "Paid ads page: your Google Ads campaigns, budgets, this month's spend and conversions, and the "
                "Pause / Resume / Budget buttons. Without it the cap check can't total a business that lists a Google account.",
     "get": "Google Cloud console → enable the Google Ads API → Credentials → OAuth client ID → Desktop app. The same "
            "client as YouTube Analytics works (it falls back to YT_OAUTH_CLIENT_ID).",
     "docs": "https://developers.google.com/google-ads/api/rest/auth"},
    {"name": "GOOGLE_ADS_CLIENT_SECRET", "group": "Google Ads API (your ads)", "cost": "",
     "unlocks": "The secret of that OAuth client (falls back to YT_OAUTH_CLIENT_SECRET).",
     "get": "Shown next to the client ID in Google Cloud → Credentials.",
     "docs": "https://developers.google.com/google-ads/api/rest/auth"},
    {"name": "GOOGLE_ADS_REFRESH_TOKEN", "group": "Google Ads API (your ads)", "cost": "",
     "unlocks": "Lets viral-scout act as you in Google Ads (scope adwords).",
     "get": "Run `python -m viral_scout paid auth google` and sign in with the Google account that manages the Google Ads "
            "accounts. Publish the OAuth consent screen (In production), or the token dies after 7 days.",
     "docs": "https://developers.google.com/google-ads/api/rest/auth"},
    {"name": "GOOGLE_ADS_DEVELOPER_TOKEN", "group": "Google Ads API (your ads)", "cost": "free (after Google's review)",
     "unlocks": "Sent with every Google Ads API call when set. Google's REST auth page no longer lists it; set it if calls "
                "are refused without it.",
     "get": "Google Ads (a manager account) → Tools → API Center → developer token; apply for Basic access.",
     "docs": "https://developers.google.com/google-ads/api/docs/get-started/dev-token"},
    {"name": "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "group": "Google Ads API (your ads)", "cost": "", "secret": False,
     "unlocks": "Only when you reach the businesses' Google Ads accounts through a manager (MCC) account: its id.",
     "get": "Google Ads → the manager account's id in the top bar (with or without dashes).",
     "docs": "https://developers.google.com/google-ads/api/rest/auth"},
    {"name": "STUDIO_SERVICE_URL", "group": "Ideas bot service", "cost": "free", "secret": False,
     "unlocks": "Ideas board, the idea generator, notes and films: the address of the Telegram bot service "
                "(the studio-ideas-service deployment).",
     "get": "The service's production URL, e.g. https://<your-service>.vercel.app (docs/telegram-service.md).",
     "docs": "https://github.com/disit-tech/viral-scout/blob/main/docs/telegram-service.md"},
    {"name": "IDEAS_API_SECRET", "group": "Ideas bot service", "cost": "",
     "unlocks": "Read and change every business's ideas (ideas board, generator, notes, content packs).",
     "get": "The same value as IDEAS_API_SECRET in the service's Vercel environment variables.",
     "docs": "https://github.com/disit-tech/viral-scout/blob/main/docs/telegram-service.md"},
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
    "META_APP_ID": "recommended", "META_APP_SECRET": "recommended", "META_USER_TOKEN": "recommended",
    "META_LOGIN_CONFIG_ID": "advanced",
    "IG_GRAPH_TOKEN": "recommended", "IG_GRAPH_USER_ID": "recommended", "META_ADS_TOKEN": "recommended",
    "META_AD_ACCOUNT_ID": "recommended", "TELEGRAM_BOT_TOKEN": "recommended", "TELEGRAM_CHAT_ID": "recommended",
    "YT_OAUTH_CLIENT_ID": "recommended", "YT_OAUTH_CLIENT_SECRET": "recommended", "YT_OAUTH_REFRESH_TOKEN": "recommended",
    "STUDIO_SERVICE_URL": "recommended", "IDEAS_API_SECRET": "recommended",
    "LINKEDIN_CLIENT_ID": "optional", "LINKEDIN_CLIENT_SECRET": "optional",
    "GOOGLE_ADS_CLIENT_ID": "optional", "GOOGLE_ADS_CLIENT_SECRET": "optional", "GOOGLE_ADS_REFRESH_TOKEN": "optional",
    "GOOGLE_ADS_DEVELOPER_TOKEN": "optional", "GOOGLE_ADS_LOGIN_CUSTOMER_ID": "advanced",
    "TIKTOK_APP_ID": "optional", "TIKTOK_APP_SECRET": "optional", "TIKTOK_APP_REDIRECT_URI": "advanced",
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
HAS_DEFAULT = {"META_LOGIN_CONFIG_ID", "TIKTOK_APP_REDIRECT_URI", "APIFY_GOOGLE_TRENDS_ACTOR", "APIFY_MAX_USD_PER_RUN", "VIRAL_SCOUT_MCP_PAID",
               "GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_LOGIN_CUSTOMER_ID"}   # optional: only some setups need them
# What each key is for (tags and filters on the Setup pages).
USES = {
    "META_APP_ID": ["videos", "performance", "paid", "ads"], "META_APP_SECRET": ["videos", "performance", "paid", "ads"],
    "META_USER_TOKEN": ["videos", "performance", "paid", "ads"], "META_LOGIN_CONFIG_ID": ["videos", "performance", "paid"],
    "YOUTUBE_API_KEY": ["videos"], "IG_GRAPH_TOKEN": ["videos", "performance"], "IG_GRAPH_USER_ID": ["videos", "performance"],
    "APIFY_TOKEN": ["videos", "ads", "demand"], "APIFY_TRENDS_ACTOR": ["videos"],
    "META_AD_LIBRARY_TOKEN": ["ads"], "TIKTOK_RESEARCH_CLIENT_KEY": ["ads"], "TIKTOK_RESEARCH_CLIENT_SECRET": ["ads"],
    "APIFY_ADS_ACTOR": ["ads"], "APIFY_TIKTOK_ADS_ACTOR": ["ads"], "APIFY_GOOGLE_ADS_ACTOR": ["ads"],
    "APIFY_GOOGLE_TRENDS_ACTOR": ["demand"], "APIFY_MAX_USD_PER_RUN": ["videos", "ads", "demand"],
    "VIRAL_SCOUT_MCP_PAID": ["tools"], "GOOGLE_PLACES_API_KEY": ["local"],
    "TELEGRAM_BOT_TOKEN": ["alerts"], "TELEGRAM_CHAT_ID": ["alerts"],
    "YT_OAUTH_CLIENT_ID": ["performance"], "YT_OAUTH_CLIENT_SECRET": ["performance"], "YT_OAUTH_REFRESH_TOKEN": ["performance"],
    "STUDIO_SERVICE_URL": ["ideas"], "IDEAS_API_SECRET": ["ideas"],
    "LINKEDIN_CLIENT_ID": ["posting"], "LINKEDIN_CLIENT_SECRET": ["posting"],
    "GOOGLE_ADS_CLIENT_ID": ["paid"], "GOOGLE_ADS_CLIENT_SECRET": ["paid"], "GOOGLE_ADS_REFRESH_TOKEN": ["paid"],
    "GOOGLE_ADS_DEVELOPER_TOKEN": ["paid"], "GOOGLE_ADS_LOGIN_CUSTOMER_ID": ["paid"],
    "META_ADS_TOKEN": ["performance", "paid"], "META_AD_ACCOUNT_ID": ["performance"],
    "TIKTOK_APP_ID": ["performance", "paid"], "TIKTOK_APP_SECRET": ["performance", "paid"],
    "TIKTOK_APP_REDIRECT_URI": ["performance", "paid"],
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
            return r.ok, f"ok: {d.get('username') or d.get('name')}{_meta_expiry(os.environ.get('IG_GRAPH_TOKEN', ''))}" \
                if r.ok else d.get("error", {}).get("message", "")
        if name in ("META_APP_ID", "META_APP_SECRET", "META_USER_TOKEN"):
            from . import connect_meta as cm
            aid, sec = os.environ.get("META_APP_ID", ""), os.environ.get("META_APP_SECRET", "")
            if not aid or not sec:
                return False, "set both META_APP_ID and META_APP_SECRET"
            if name != "META_USER_TOKEN":
                r = requests.get(f"{cm.GRAPH}/{aid}", params={"fields": "name", "access_token": f"{aid}|{sec}"}, timeout=20)
                d = r.json()
                return r.ok, f"ok: app {d.get('name')}" if r.ok else d.get("error", {}).get("message", r.text[:160])
            info = cm.describe(v)
            if not info.get("valid"):
                return False, f"{info.get('error')} (sign in again: python -m viral_scout keys connect meta)"
            return True, f"ok: expires {info['expires']}, data access until {info['data_access_expires']}"
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
            return r.ok, f"ok: {d.get('name')} ({d.get('currency')}){_meta_expiry(os.environ.get('META_ADS_TOKEN', ''))}" \
                if r.ok else d.get("error", {}).get("message", "")
        if name in ("STUDIO_SERVICE_URL", "IDEAS_API_SECRET"):
            base = (os.environ.get("STUDIO_SERVICE_URL") or "").rstrip("/")
            if not base or not os.environ.get("IDEAS_API_SECRET"):
                return False, "set both STUDIO_SERVICE_URL and IDEAS_API_SECRET"
            r = requests.get(f"{base}/api/board", headers={"Authorization": f"Bearer {os.environ['IDEAS_API_SECRET']}"}, timeout=30)
            if r.status_code == 401:
                return False, "the service refused the secret (401)"
            if not r.ok:
                return False, f"HTTP {r.status_code} from {base}/api/board"
            d = r.json()
            return True, f"ok: {len(d.get('ideas') or [])} ideas from {len(d.get('projects') or [])} businesses"
        if name.startswith("GOOGLE_ADS_"):
            from .paid import google as gads
            if gads.missing():
                return False, "set " + ", ".join(gads.missing()) + " (refresh token: python -m viral_scout paid auth google)"
            try:
                r = requests.get(f"{gads.API}/customers:listAccessibleCustomers", headers=gads._headers(), timeout=20)
            except RuntimeError as e:
                return False, str(e)
            d = r.json()
            if not r.ok:
                return False, (d.get("error") or {}).get("message", r.text[:160])
            n = len(d.get("resourceNames") or [])
            return True, f"ok: {n} Google Ads account{'s' if n != 1 else ''} reachable"
        if name in ("TIKTOK_APP_ID", "TIKTOK_APP_SECRET", "TIKTOK_APP_REDIRECT_URI"):
            if not (os.environ.get("TIKTOK_APP_ID") and os.environ.get("TIKTOK_APP_SECRET")):
                return False, "set both TIKTOK_APP_ID and TIKTOK_APP_SECRET"
            if not os.environ.get("TIKTOK_ADS_TOKEN"):
                return True, "set (checked on Sign in with TikTok: TikTok has no app-only test call)"
            from . import connect_tiktok as ct
            try:
                n = len(ct.accounts())
            except ct.TikTokError as e:
                return False, str(e)
            return True, f"ok: {n} advertiser account{'s' if n != 1 else ''} authorized"
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


def _meta_expiry(token):
    """', expires 2027-01-13' from debug_token when the app keys are set; '' otherwise (never fails a test)."""
    if not (token and os.environ.get("META_APP_ID") and os.environ.get("META_APP_SECRET")):
        return ""
    try:
        from . import connect_meta as cm
        exp = cm.describe(token).get("expires")
        return f", expires {exp}" if exp else ""
    except Exception:  # noqa: BLE001
        return ""


def _meta_cli(args):
    import argparse
    from . import connect_meta as cm
    try:
        if args[0] == "connect":
            a = argparse.ArgumentParser(prog="viral_scout keys connect meta")
            a.add_argument("--no-browser", action="store_true")
            a.add_argument("--port", type=int, default=cm.PORT)
            a.add_argument("--timeout", type=int, default=300)
            a.add_argument("--status-file")
            o = a.parse_args(args[2:])
            print("\n".join(cm.connect(not o.no_browser, o.port, o.timeout, o.status_file)))
            return 0
        sub = args[1] if len(args) > 1 else "status"
        if sub == "accounts":
            print(json.dumps(cm.accounts(), indent=1, ensure_ascii=False))
            return 0
        if sub == "status":
            print(json.dumps(cm.status(), indent=1))
            return 0
        if sub == "use":
            a = argparse.ArgumentParser(prog="viral_scout keys meta use")
            a.add_argument("--ig")
            a.add_argument("--ad-account")
            a.add_argument("--replace-ads-token", action="store_true")
            o = a.parse_args(args[2:])
            print("\n".join(cm.use(o.ig, o.ad_account, o.replace_ads_token, auto=not (o.ig or o.ad_account))))
            return 0
    except cm.MetaError as e:
        print(f"error: {e}")
        return 1
    print(cm.__doc__)
    return 2


def _google_cli(args):
    import argparse
    from . import connect_google as cg
    try:
        if args[0] == "connect":
            a = argparse.ArgumentParser(prog="viral_scout keys connect google")
            a.add_argument("--no-browser", action="store_true")
            a.add_argument("--port", type=int, default=0, help="loopback port (default: any free port)")
            a.add_argument("--timeout", type=int, default=300)
            a.add_argument("--only", choices=["youtube", "ads"])
            a.add_argument("--status-file")
            o = a.parse_args(args[2:])
            print("\n".join(cg.connect(not o.no_browser, o.port, o.timeout, o.only, o.status_file)))
            return 0
        if (args[1:2] or ["accounts"])[0] == "accounts":
            print(json.dumps(cg.accounts(), indent=1, ensure_ascii=False))
            return 0
    except cg.GoogleError as e:
        print(f"error: {e}")
        return 1
    print(cg.__doc__)
    return 2


def _tiktok_cli(args):
    import argparse
    from . import connect_tiktok as ct
    try:
        if args[0] == "connect":
            a = argparse.ArgumentParser(prog="viral_scout keys connect tiktok")
            a.add_argument("--no-browser", action="store_true")
            a.add_argument("--port", type=int)
            a.add_argument("--timeout", type=int, default=300)
            a.add_argument("--paste", help="the address the browser landed on (or '-' to read it from stdin)")
            a.add_argument("--status-file")
            o = a.parse_args(args[2:])
            paste = input() if o.paste == "-" else o.paste
            print("\n".join(ct.connect(not o.no_browser, o.port, o.timeout, paste, o.status_file)))
            return 0
        sub = args[1] if len(args) > 1 else "accounts"
        if sub == "accounts":
            print(json.dumps(ct.accounts(), indent=1, ensure_ascii=False))
            return 0
        if sub == "use":
            a = argparse.ArgumentParser(prog="viral_scout keys tiktok use")
            a.add_argument("--advertiser", required=True)
            o = a.parse_args(args[2:])
            print("\n".join(ct.use(o.advertiser)))
            return 0
    except ct.TikTokError as e:
        print(f"error: {e}")
        return 1
    print(ct.__doc__)
    return 2


def cli(args):
    if args[:2] == ["connect", "meta"] or args[:1] == ["meta"]:
        return _meta_cli(args)
    if args[:2] == ["connect", "google"] or args[:1] == ["google"]:
        return _google_cli(args)
    if args[:2] == ["connect", "tiktok"] or args[:1] == ["tiktok"]:
        return _tiktok_cli(args)
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
    print("usage: keys [status] | keys test [NAME...] | keys set NAME [VALUE] | keys connect meta|google|tiktok | "
          "keys meta [accounts | use | status] | keys google accounts | keys tiktok [accounts | use]")
    return 2
