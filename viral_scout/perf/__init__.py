"""Own performance: KPIs for the business's OWN videos and ads, from official APIs or the user's own exports.

viral-scout's main pipeline looks at other creators' public numbers. Hook rate, watch time, retention, shares,
saves, CTR, CVR, CPA, ROAS are private to the posting account, so they are only measured here, for your own
posts and ads. Modules:

  schema.py     the normalized record every source produces
  kpis.py       every KPI with its formula and denominator (sections A–E)
  diagnose.py   biggest problem per video/ad, the 5 tests, fatigue, organic vs paid priorities
  instagram.py  Instagram Graph API media insights (IG_GRAPH_TOKEN, IG_GRAPH_USER_ID)
  youtube.py    YouTube Analytics API + OAuth installed-app flow (YT_OAUTH_*)
  meta_ads.py   Meta Marketing API ad insights (META_ADS_TOKEN, META_AD_ACCOUNT_ID)
  tiktok_ads.py TikTok Marketing API integrated report (TIKTOK_ADS_TOKEN, TIKTOK_ADVERTISER_ID)
  csvimport.py  Meta / TikTok / YouTube Studio / generic CSV exports (no keys)
  store.py      SQLite tables perf_records (latest) and perf_snapshots (history)
  run.py        pull → KPIs → diagnose → JSON + Markdown report
"""
