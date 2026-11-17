"""The paid: block, the monthly cap, the change log and the latest snapshot of a business's ad accounts.

profiles/<name>.yaml:

  paid:
    monthly_cap_usd: 300          # hard limit per calendar month across all platforms; 0 or missing = nothing may start
    platforms: [meta, google, tiktok]
    accounts: {meta: act_123, google: "123-456-7890", tiktok: "7000000000000000000"}
    brief:                        # the default brief Claude starts from (the dashboard edits it)
      goal: leads                 # leads | sales | traffic | awareness | messages | calls
      daily_budget_usd: 20
      geo: "Chicago metro, 25 mi around 60601"
      audience: "homeowners 35-65"
      offer: "free outage checklist"
      landing: https://example.com/checklist
      notes: ""

The Meta and TikTok account ids fall back to perf.meta_ad_account_id / perf.tiktok_advertiser_id. There is no
fallback to the .env defaults on purpose: one token sees every business's account, and a wrong default would show
(or spend on) another business's account.

The cap check (`check`) projects the month: spend so far + every running campaign's daily budget for the days left
(lifetime budgets: what remains of them) + the new or changed budget. Above the cap → refused. Pausing is always
allowed. Amounts are in the ad account's currency; an account that isn't in USD is refused, since the cap is USD.
"""
import calendar
import json
from datetime import date, datetime
from pathlib import Path

from .. import config

PLATFORMS = ("meta", "google", "tiktok")
NAMES = {"meta": "Meta (Facebook + Instagram)", "google": "Google Ads", "tiktok": "TikTok Ads"}
GOALS = ("leads", "sales", "traffic", "awareness", "messages", "calls")


def settings(cfg):
    p = cfg.get("paid") if isinstance(cfg.get("paid"), dict) else {}
    perf = cfg.get("perf") if isinstance(cfg.get("perf"), dict) else {}
    acc = dict(p.get("accounts") or {})
    acc.setdefault("meta", perf.get("meta_ad_account_id"))
    acc.setdefault("tiktok", perf.get("tiktok_advertiser_id"))
    acc = {k: str(v).strip() for k, v in acc.items() if k in PLATFORMS and v}
    return {
        "cap": float(p.get("monthly_cap_usd") or 0),
        "platforms": [x for x in (p.get("platforms") or PLATFORMS) if x in PLATFORMS],
        "accounts": acc,
        "brief": dict(p.get("brief") or {}),
    }


def folder():
    d = config.ROOT / "data" / "paid"
    d.mkdir(parents=True, exist_ok=True)
    return d


def snapshot_path(cfg):
    return folder() / f"{cfg['name']}.json"


def ledger_path(cfg):
    return folder() / f"{cfg['name']}-log.jsonl"


def load(cfg):
    try:
        return json.loads(snapshot_path(cfg).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save(cfg, snap):
    snapshot_path(cfg).write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")


def log(cfg, action, text, by="cli", platform="", campaign="", amount=None):
    """One line per change (launch, pause, resume, budget, refused): who, what, when."""
    row = {"at": datetime.now().isoformat(timespec="seconds"), "by": by, "action": action, "platform": platform,
           "campaign": campaign, "amount_usd": amount, "text": text[:500]}
    with open(ledger_path(cfg), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def read_log(cfg, limit=50):
    try:
        lines = ledger_path(cfg).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return list(reversed(out))


def days_left(today=None):
    """Days left in the month, today included."""
    t = today or date.today()
    return calendar.monthrange(t.year, t.month)[1] - t.day + 1


def committed(snap, today=None, skip=None):
    """Spend so far this month + what the running campaigns will still spend this month. skip=(platform, id) leaves
    one campaign out (the one being changed). Returns (spent, still_to_spend, details)."""
    left = days_left(today)
    spent, future, rows = 0.0, 0.0, []
    for plat, acc in (snap or {}).get("platforms", {}).items():
        if not acc.get("ok"):
            continue
        spent += acc.get("month_spend") or 0
        for c in acc.get("campaigns") or []:
            if not c.get("running") or (skip and (plat, str(c["id"])) == (skip[0], str(skip[1]))):
                continue
            if c.get("daily_budget"):
                f = c["daily_budget"] * left
            elif c.get("budget_remaining"):
                f = c["budget_remaining"]
            else:
                f = 0.0
            future += f
            rows.append({"platform": plat, "campaign": c["name"], "id": c["id"], "to_spend": round(f, 2)})
    return round(spent, 2), round(future, 2), rows


def check(cfg, snap, daily_usd=0.0, lifetime_usd=0.0, skip=None, today=None):
    """Would a new or changed budget keep the month under the cap? → (ok, message, numbers)."""
    s = settings(cfg)
    if s["cap"] <= 0:
        return False, f"no monthly cap set for {cfg['name']} (paid.monthly_cap_usd): nothing may start", {}
    if not snap:
        return False, "no snapshot of the ad accounts yet: run `paid <profile> pull` first", {}
    bad = [p for p, a in snap.get("platforms", {}).items() if a.get("ok") and (a.get("currency") or "USD") != "USD"]
    if bad:
        return False, f"account currency isn't USD on {', '.join(bad)}; the cap is in USD, so it can't be checked", {}
    stale = [p for p, a in snap.get("platforms", {}).items() if a.get("error") and p in s["accounts"]]
    spent, future, _ = committed(snap, today, skip)
    new = daily_usd * days_left(today) + lifetime_usd
    total = round(spent + future + new, 2)
    nums = {"cap": s["cap"], "spent": spent, "running": future, "new": round(new, 2), "projected": total,
            "days_left": days_left(today), "unreadable": stale}
    if stale:
        return False, f"couldn't read {', '.join(stale)} at the last pull, so the month can't be totalled", nums
    if total > s["cap"]:
        return False, (f"over the cap: ${spent:.0f} spent + ${future:.0f} still running + ${new:.0f} new = ${total:.0f} "
                       f"> ${s['cap']:.0f} this month"), nums
    return True, f"fits: ${total:.0f} of ${s['cap']:.0f} projected this month (${s['cap'] - total:.0f} to spare)", nums
