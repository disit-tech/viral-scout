"""Ads scout: the best-performing ads in a niche (competitors and the category), per business profile.

  python -m viral_scout ads <profile>   →  <output_dir>/<date>-ads-scout.md + data/<profile>-ads-latest.json

Sources (all optional; a missing key lists the source under "Skipped sources"):
  meta_api          Meta Ad Library API (ads_archive). EU-delivered ads + political/issue ads globally. META_AD_LIBRARY_TOKEN
  tiktok_api        TikTok Commercial Content API (ads shown in the EEA). TIKTOK_RESEARCH_CLIENT_KEY/_SECRET
  apify_meta        Meta Ad Library through an Apify actor (the practical US route, paid). APIFY_TOKEN + APIFY_ADS_ACTOR
  apify_tiktok_top  TikTok Creative Center Top Ads through an Apify actor (paid). APIFY_TOKEN + APIFY_TIKTOK_ADS_ACTOR
  apify_google      Google Ads Transparency Center through an Apify actor (paid). APIFY_TOKEN + APIFY_GOOGLE_ADS_ACTOR

Scores are proxies (how long an ad keeps running, how many variants, reach where published), never spend or ROAS.
See docs/ads-scout.md.
"""
