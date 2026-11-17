"""Meta Marketing API for the Paid ads page: the account, its campaigns with budgets, this month's spend and results,
and the three changes the dashboard makes (pause, resume, daily budget).

Token: META_ADS_TOKEN (a system user token). Reading needs `ads_read`; pause / resume / budget need
`ads_management`. Budgets come back in the account currency's minor units (cents for USD).

  GET  /act_{id}?fields=name,currency,account_status,amount_spent,spend_cap
  GET  /act_{id}/campaigns?fields=id,name,status,effective_status,objective,daily_budget,lifetime_budget,budget_remaining,...
  GET  /act_{id}/adsets?fields=campaign_id,effective_status,daily_budget,lifetime_budget,budget_remaining  (ad-set budgets)
  GET  /act_{id}/insights?level=campaign&date_preset=this_month&fields=campaign_id,spend,impressions,clicks,...,actions
  POST /{campaign_id}  status=ACTIVE|PAUSED   ·   daily_budget=<cents>
"""
import os

import requests

from .. import usage
from ..perf.meta_ads import ACTIONS, action

API = "https://graph.facebook.com/v26.0"
RESULTS = {"leads": ACTIONS["leads"], "sales": ACTIONS["purchases"], "traffic": ["link_click"],
           "messages": ["onsite_conversion.messaging_conversation_started_7d"], "calls": ["click_to_call_native_call_placed"]}


def available():
    return bool(os.environ.get("META_ADS_TOKEN"))


def _act(a):
    return a if a.startswith("act_") else f"act_{a}"


def _call(method, path, params):
    usage.add("meta_ads_requests")
    r = requests.request(method, f"{API}/{path}", timeout=60,
                         **({"params": params} if method == "GET" else {"data": params}),
                         headers={"Authorization": f"Bearer {os.environ['META_ADS_TOKEN']}"})
    try:
        d = r.json()
    except ValueError:
        raise RuntimeError(f"Meta {path}: HTTP {r.status_code}") from None
    if isinstance(d, dict) and "error" in d:
        raise RuntimeError(f"Meta {path}: {d['error'].get('message', 'error')}")
    return d


def _all(path, params, pages=10):
    out, after = [], None
    for _ in range(pages):
        d = _call("GET", path, {**params, "limit": 200, **({"after": after} if after else {})})
        out += d.get("data") or []
        after = ((d.get("paging") or {}).get("cursors") or {}).get("after")
        if not (d.get("paging") or {}).get("next"):
            break
    return out


def _money(v):
    try:
        return round(float(v) / 100, 2)
    except (TypeError, ValueError):
        return None


def pull(account, goal="leads"):
    act = _act(account)
    info = _call("GET", act, {"fields": "name,currency,account_status,amount_spent,spend_cap"})
    camps = _all(f"{act}/campaigns", {"fields": "id,name,status,effective_status,objective,daily_budget,lifetime_budget,"
                                                "budget_remaining,start_time,stop_time,created_time"})
    sets = _all(f"{act}/adsets", {"fields": "campaign_id,effective_status,daily_budget,lifetime_budget,budget_remaining"})
    ins = _all(f"{act}/insights", {"level": "campaign", "date_preset": "this_month",
                                   "fields": "campaign_id,spend,impressions,reach,clicks,inline_link_clicks,actions"})
    by_ins = {i["campaign_id"]: i for i in ins}
    set_budget = {}
    for s in sets:                       # ad-set budgets (no campaign budget): count the running ones
        if s.get("effective_status") != "ACTIVE":
            continue
        b = set_budget.setdefault(s["campaign_id"], {"daily": 0.0, "remaining": 0.0})
        b["daily"] += _money(s.get("daily_budget")) or 0
        if not s.get("daily_budget"):
            b["remaining"] += _money(s.get("budget_remaining")) or 0
    results_types = RESULTS.get(goal, ACTIONS["leads"])
    rows = []
    for c in camps:
        i = by_ins.get(c["id"], {})
        spend = float(i.get("spend") or 0)
        res = action(i.get("actions"), results_types)
        sb = set_budget.get(c["id"], {})
        daily = _money(c.get("daily_budget")) or (sb.get("daily") or None)
        remaining = None if daily else (_money(c.get("budget_remaining")) if c.get("lifetime_budget") else sb.get("remaining") or None)
        rows.append({
            "id": c["id"], "name": c.get("name", ""), "status": c.get("effective_status") or c.get("status"),
            "running": c.get("effective_status") == "ACTIVE", "objective": c.get("objective"),
            "daily_budget": daily, "budget_remaining": remaining, "budget_level": "campaign" if c.get("daily_budget") or c.get("lifetime_budget") else "ad set",
            "start": c.get("start_time"), "stop": c.get("stop_time"), "created": c.get("created_time"),
            "month_spend": round(spend, 2), "impressions": int(float(i.get("impressions") or 0)),
            "clicks": int(float(i.get("inline_link_clicks") or i.get("clicks") or 0)),
            "results": res, "cost_per_result": round(spend / res, 2) if res else None,
        })
    rows.sort(key=lambda r: (not r["running"], -(r["month_spend"] or 0)))
    return {"ok": True, "account": act, "name": info.get("name"), "currency": info.get("currency"),
            "account_status": info.get("account_status"), "month_spend": round(sum(r["month_spend"] for r in rows), 2),
            "result_label": goal, "campaigns": rows,
            "manage_url": f"https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={act.removeprefix('act_')}"}


def set_status(account, campaign_id, active):
    return _call("POST", str(campaign_id), {"status": "ACTIVE" if active else "PAUSED"})


def set_daily_budget(account, campaign_id, usd):
    return _call("POST", str(campaign_id), {"daily_budget": str(int(round(usd * 100)))})
