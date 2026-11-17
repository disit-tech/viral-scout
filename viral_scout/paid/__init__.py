"""Paid ads: your own ad accounts (Meta, Google, TikTok) per business, in one place.

  core.py    the profile's paid: block, the monthly cap check, the change log, the saved snapshot
  meta.py    Meta Marketing API: account, campaigns, ad sets, this month's spend; pause / resume / budget
  tiktok.py  TikTok API for Business: the same
  google.py  Google Ads: read through Claude's google-ads connector for now (see docs/paid-ads.md)
  cli.py     python -m viral_scout paid <profile> pull | status | cap | pause | resume | budget | log

Claude builds and launches campaigns through the official connectors (Meta's ads MCP), but always asks
`paid <profile> cap <daily>` first and records what it did with `paid <profile> log`. The dashboard's Paid ads page
reads the snapshot and uses the same commands for its Pause / Resume / Budget buttons.
"""
