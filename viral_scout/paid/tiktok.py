"""TikTok API for Business for the Paid ads page: campaigns with budgets, this month's spend and results, and
pause / resume / daily budget. No official MCP exists, so this is also how Claude changes TikTok campaigns.

Token: TIKTOK_ADS_TOKEN (long-term access token of your TikTok for Business developer app). Reading needs the
Campaign and Reporting permissions; changes need Campaign management. Budgets are in the account currency.

  GET  advertiser/info/?advertiser_ids=[id]&fields=["name","currency","status"]
  GET  campaign/get/?advertiser_id=…&page_size=100
  GET  report/integrated/get/  data_level=AUCTION_CAMPAIGN, dimensions=["campaign_id"], this month
  POST campaign/status/update/  {advertiser_id, campaign_ids, operation_status: ENABLE|DISABLE}
  POST campaign/update/         {advertiser_id, campaign_id, budget}
Ad-group budgets aren't read yet: a campaign without its own budget counts as 0 in the cap check (said on the page).
"""
import json
import os
from datetime import date

import requests

from .. import usage

API = "https://business-api.tiktok.com/open_api/v1.3/"


def available():
    return bool(os.environ.get("TIKTOK_ADS_TOKEN"))


def _call(method, path, params):
    usage.add("tiktok_ads_requests")
    h = {"Access-Token": os.environ["TIKTOK_ADS_TOKEN"]}
    if method == "GET":
        q = {k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in params.items()}
        r = requests.get(API + path, params=q, headers=h, timeout=60)
    else:
        r = requests.post(API + path, json=params, headers=h, timeout=60)
    try:
        d = r.json()
    except ValueError:
        raise RuntimeError(f"TikTok {path}: HTTP {r.status_code}") from None
    if d.get("code") != 0:
        raise RuntimeError(f"TikTok {path}: {d.get('message', 'error')}")
    return d.get("data") or {}


def pull(account, goal="leads"):
    info = (_call("GET", "advertiser/info/", {"advertiser_ids": [account], "fields": ["name", "currency", "status"]})
            .get("list") or [{}])[0]
    camps, page = [], 1
    while page <= 10:
        d = _call("GET", "campaign/get/", {"advertiser_id": account, "page": page, "page_size": 100})
        camps += d.get("list") or []
        if page >= ((d.get("page_info") or {}).get("total_page") or 1):
            break
        page += 1
    today = date.today()
    rep = _call("GET", "report/integrated/get/", {
        "advertiser_id": account, "report_type": "BASIC", "data_level": "AUCTION_CAMPAIGN", "dimensions": ["campaign_id"],
        "metrics": ["spend", "impressions", "clicks", "conversion"], "start_date": today.replace(day=1).isoformat(),
        "end_date": today.isoformat(), "page_size": 1000}).get("list") or []
    by = {str((r.get("dimensions") or {}).get("campaign_id")): r.get("metrics") or {} for r in rep}
    rows = []
    for c in camps:
        m = by.get(str(c.get("campaign_id")), {})
        spend = float(m.get("spend") or 0)
        res = float(m.get("conversion") or 0) or None
        mode, budget = c.get("budget_mode"), float(c.get("budget") or 0) or None
        running = c.get("operation_status") == "ENABLE"
        rows.append({
            "id": str(c.get("campaign_id")), "name": c.get("campaign_name", ""),
            "status": c.get("secondary_status") or c.get("operation_status"), "running": running,
            "objective": c.get("objective_type"), "created": c.get("create_time"),
            "daily_budget": budget if mode == "BUDGET_MODE_DAY" else None,
            "budget_remaining": max(0.0, (budget or 0) - spend) if mode == "BUDGET_MODE_TOTAL" else None,
            "budget_level": "campaign" if mode in ("BUDGET_MODE_DAY", "BUDGET_MODE_TOTAL") else "ad group",
            "month_spend": round(spend, 2), "impressions": int(float(m.get("impressions") or 0)),
            "clicks": int(float(m.get("clicks") or 0)), "results": res,
            "cost_per_result": round(spend / res, 2) if res else None,
        })
    rows.sort(key=lambda r: (not r["running"], -(r["month_spend"] or 0)))
    return {"ok": True, "account": str(account), "name": info.get("name"), "currency": info.get("currency"),
            "account_status": info.get("status"), "month_spend": round(sum(r["month_spend"] for r in rows), 2),
            "result_label": "conversions", "campaigns": rows,
            "manage_url": f"https://ads.tiktok.com/i18n/perf/campaign?aadvid={account}"}


def set_status(account, campaign_id, active):
    return _call("POST", "campaign/status/update/", {"advertiser_id": str(account), "campaign_ids": [str(campaign_id)],
                                                     "operation_status": "ENABLE" if active else "DISABLE"})


def set_daily_budget(account, campaign_id, usd):
    return _call("POST", "campaign/update/", {"advertiser_id": str(account), "campaign_id": str(campaign_id), "budget": usd})
