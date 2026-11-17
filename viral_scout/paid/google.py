"""Google Ads API (official, REST v26) for the Paid ads page: campaigns with budgets, this month's spend and
conversions, and pause / resume / daily budget.

Keys (.env, Setup page → "paid ads"):
  GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET   OAuth client (Google Cloud → Credentials → Desktop app); falls back
                                                   to YT_OAUTH_CLIENT_ID / _SECRET when it's the same Cloud project
  GOOGLE_ADS_REFRESH_TOKEN                         `python -m viral_scout paid auth google` (scope .../auth/adwords)
  GOOGLE_ADS_DEVELOPER_TOKEN                       Google Ads → Tools → API Center. Sent when set (Google's REST auth
                                                   page no longer lists it; older docs require it)
  GOOGLE_ADS_LOGIN_CUSTOMER_ID                     only when you reach the accounts through a manager (MCC) account

  POST /v26/customers/{id}/googleAds:searchStream   GAQL: customer currency, campaigns + budgets, this month's metrics
  POST /v26/customers/{id}/campaigns:mutate         status ENABLED | PAUSED
  POST /v26/customers/{id}/campaignBudgets:mutate   amount_micros (daily budget). A shared budget is refused: it would
                                                    change every campaign on it
Google's own MCP (googleads/google-ads-mcp) is read-only; Claude uses this module (through the paid CLI) to change.
"""
import os

import requests

from .. import usage

API = "https://googleads.googleapis.com/v26"
TOKEN = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/adwords"]


def _env(name, fallback=None):
    return os.environ.get(name) or (os.environ.get(fallback) if fallback else None)


def creds():
    return (_env("GOOGLE_ADS_CLIENT_ID", "YT_OAUTH_CLIENT_ID"), _env("GOOGLE_ADS_CLIENT_SECRET", "YT_OAUTH_CLIENT_SECRET"),
            os.environ.get("GOOGLE_ADS_REFRESH_TOKEN"))


def available():
    return all(creds())


def missing():
    names = ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN")
    return [n for n, v in zip(names, creds()) if not v]


def authorize(open_browser=True, port=0):
    from ..perf.youtube import consent
    cid, secret, _ = creds()
    if not cid or not secret:
        raise SystemExit("Set GOOGLE_ADS_CLIENT_ID and GOOGLE_ADS_CLIENT_SECRET first (Google Cloud → enable the Google Ads "
                         "API → Credentials → OAuth client ID → Desktop app). See docs/paid-ads.md.")
    return consent(cid, secret, SCOPES, "GOOGLE_ADS_REFRESH_TOKEN",
                   "pick the Google account that manages the Google Ads accounts, and allow access", open_browser, port=port)


def _cid(v):
    return str(v).replace("-", "").strip()


def _headers():
    cid, secret, refresh = creds()
    r = requests.post(TOKEN, data={"client_id": cid, "client_secret": secret, "refresh_token": refresh,
                                   "grant_type": "refresh_token"}, timeout=30)
    d = r.json()
    if "access_token" not in d:
        raise RuntimeError(f"Google OAuth: {d.get('error_description') or d.get('error') or r.status_code} "
                           "(run: python -m viral_scout paid auth google)")
    h = {"Authorization": f"Bearer {d['access_token']}", "content-type": "application/json"}
    if os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN"):
        h["developer-token"] = os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"]
    if os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID"):
        h["login-customer-id"] = _cid(os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"])
    return h


def _post(path, body, headers):
    usage.add("google_ads_requests")
    r = requests.post(f"{API}/{path}", json=body, headers=headers, timeout=60)
    try:
        d = r.json()
    except ValueError:
        raise RuntimeError(f"Google Ads {path}: HTTP {r.status_code}") from None
    err = d.get("error") if isinstance(d, dict) else (d[0].get("error") if d and isinstance(d[0], dict) else None)
    if err:
        details = (err.get("details") or [{}])[0].get("errors") or [{}]
        raise RuntimeError(f"Google Ads: {details[0].get('message') or err.get('message', 'error')}")
    return d


def _search(customer, query, headers):
    rows = []
    for chunk in _post(f"customers/{customer}/googleAds:searchStream", {"query": query}, headers) or []:
        rows += chunk.get("results") or []
    return rows


def pull(account, goal="leads"):
    c = _cid(account)
    h = _headers()
    cust = (_search(c, "SELECT customer.descriptive_name, customer.currency_code, customer.status FROM customer", h)
            or [{}])[0].get("customer", {})
    camps = _search(c, "SELECT campaign.id, campaign.name, campaign.status, campaign.serving_status, "
                       "campaign.advertising_channel_type, campaign.start_date, campaign.end_date, campaign_budget.id, "
                       "campaign_budget.amount_micros, campaign_budget.total_amount_micros, "
                       "campaign_budget.explicitly_shared FROM campaign WHERE campaign.status != 'REMOVED'", h)
    mets = _search(c, "SELECT campaign.id, metrics.cost_micros, metrics.impressions, metrics.clicks, metrics.conversions "
                      "FROM campaign WHERE segments.date DURING THIS_MONTH", h)
    by = {}
    for m in mets:
        k = str(m.get("campaign", {}).get("id"))
        a = by.setdefault(k, {"cost": 0.0, "impressions": 0, "clicks": 0, "conversions": 0.0})
        mm = m.get("metrics", {})
        a["cost"] += int(mm.get("costMicros") or 0) / 1e6
        a["impressions"] += int(mm.get("impressions") or 0)
        a["clicks"] += int(mm.get("clicks") or 0)
        a["conversions"] += float(mm.get("conversions") or 0)
    seen_budgets, rows = set(), []
    for r in camps:
        k = r.get("campaign", {})
        b = r.get("campaignBudget", {})
        m = by.get(str(k.get("id")), {})
        running = k.get("status") == "ENABLED"
        shared = bool(b.get("explicitlyShared"))
        daily = int(b.get("amountMicros") or 0) / 1e6 or None
        # A shared budget is spent once for all its campaigns: count it on the first running one only.
        counted = daily if not (shared and b.get("id") in seen_budgets) else None
        if running and shared:
            seen_budgets.add(b.get("id"))
        spend, res = round(m.get("cost", 0.0), 2), m.get("conversions") or None
        rows.append({
            "id": str(k.get("id")), "name": k.get("name", ""), "status": k.get("servingStatus") or k.get("status"),
            "running": running, "objective": k.get("advertisingChannelType"),
            "daily_budget": counted, "budget_remaining": None,
            "budget_level": "shared budget" if shared else "campaign", "budget_id": b.get("id"),
            "start": k.get("startDate"), "stop": k.get("endDate"), "created": None,
            "month_spend": spend, "impressions": m.get("impressions", 0), "clicks": m.get("clicks", 0),
            "results": round(res, 1) if res else None, "cost_per_result": round(spend / res, 2) if res else None,
        })
    rows.sort(key=lambda x: (not x["running"], -(x["month_spend"] or 0)))
    return {"ok": True, "account": c, "name": cust.get("descriptiveName"), "currency": cust.get("currencyCode"),
            "account_status": cust.get("status"), "month_spend": round(sum(x["month_spend"] for x in rows), 2),
            "result_label": "conversions", "campaigns": rows,
            "manage_url": f"https://ads.google.com/aw/campaigns?ocid={c}"}


def set_status(account, campaign_id, active):
    c = _cid(account)
    return _post(f"customers/{c}/campaigns:mutate", {"operations": [{
        "update": {"resourceName": f"customers/{c}/campaigns/{campaign_id}", "status": "ENABLED" if active else "PAUSED"},
        "updateMask": "status"}]}, _headers())


def set_daily_budget(account, campaign_id, usd):
    c = _cid(account)
    h = _headers()
    r = (_search(c, f"SELECT campaign_budget.id, campaign_budget.explicitly_shared FROM campaign WHERE campaign.id = {int(campaign_id)}", h)
         or [{}])[0].get("campaignBudget", {})
    if not r.get("id"):
        raise RuntimeError(f"campaign {campaign_id} has no budget")
    if r.get("explicitlyShared"):
        raise RuntimeError("this campaign uses a shared budget: change it in Google Ads (it moves every campaign on it)")
    return _post(f"customers/{c}/campaignBudgets:mutate", {"operations": [{
        "update": {"resourceName": f"customers/{c}/campaignBudgets/{r['id']}", "amountMicros": str(int(round(usd * 1e6)))},
        "updateMask": "amount_micros"}]}, h)
