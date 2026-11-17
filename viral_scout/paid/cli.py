"""python -m viral_scout paid <profile> <command>     (and: paid auth google  →  Google Ads login, refresh token in .env)

  pull                               read every connected ad account → data/paid/<profile>.json + the dashboard
  status                             what's running, spend this month, the cap
  cap <daily_usd> [--lifetime <usd>] would a new campaign with this budget fit under the monthly cap? (exit 0 yes, 3 no)
  pause  <platform> <campaign_id>    always allowed
  resume <platform> <campaign_id>    only if the month stays under the cap
  budget <platform> <campaign_id> <daily_usd>   only if the month stays under the cap
  log <action> "<text>" [--platform p] [--campaign id] [--amount usd]   record a change made elsewhere (e.g. Claude
                                     launching through Meta's ads MCP)
  ask ["extra"]                      Claude builds and (within the cap) launches one campaign from the brief (headless)
  enforce                            pause campaigns created today while the month is over the cap
  every change command takes --by <who> (dashboard | claude | cli) for the log.
"""
import json
from datetime import datetime

from .. import config
from . import core, google, meta, tiktok

MODS = {"meta": meta, "google": google, "tiktok": tiktok}
WRITABLE = ("meta", "google", "tiktok")
KEYS = {"meta": "META_ADS_TOKEN", "tiktok": "TIKTOK_ADS_TOKEN",
        "google": "GOOGLE_ADS_CLIENT_ID + GOOGLE_ADS_CLIENT_SECRET + GOOGLE_ADS_REFRESH_TOKEN"}


def pull(cfg, quiet=False):
    s = core.settings(cfg)
    goal = s["brief"].get("goal") or "leads"
    snap = {"pulled": datetime.now().isoformat(timespec="seconds"), "platforms": {}}
    for p in s["platforms"]:
        acc = s["accounts"].get(p)
        m = MODS[p]
        key = KEYS[p]
        if not acc:
            snap["platforms"][p] = {"ok": False, "missing": "account", "error": f"no paid.accounts.{p} in the profile"}
        elif not m.available():
            snap["platforms"][p] = {"ok": False, "missing": "key", "account": acc, "error": f"no {key} in .env"}
        else:
            try:
                snap["platforms"][p] = m.pull(acc, goal)
            except Exception as err:  # noqa: BLE001 (one platform never stops the others)
                snap["platforms"][p] = {"ok": False, "account": acc, "error": str(err)[:300]}
        if not quiet:
            a = snap["platforms"][p]
            print(f"  {core.NAMES[p]}: " + (f"{len(a['campaigns'])} campaigns, ${a['month_spend']:.2f} this month"
                                            if a.get("ok") else a.get("error", "")))
    core.save(cfg, snap)
    export(cfg)
    return snap


def export(cfg, out=None):
    """web/data/paid/<profile>.json: settings, the snapshot, the cap projection and the change log."""
    from ..export import WEB_DATA
    s = core.settings(cfg)
    snap = core.load(cfg)
    spent, future, rows = core.committed(snap)
    ok, msg, nums = core.check(cfg, snap) if snap else (False, "not pulled yet", {})
    data = {"profile": cfg["name"], "cap": s["cap"], "platforms": s["platforms"], "accounts": s["accounts"],
            "brief": s["brief"], "snapshot": snap, "month": {"spent": spent, "running": future, "rows": rows,
                                                               "projected": round(spent + future, 2),
                                                               "days_left": core.days_left(), "check": msg},
            "log": core.read_log(cfg)}
    folder = (out or WEB_DATA) / "paid"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{cfg['name']}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def _opt(args, name, cast=str, default=None):
    if name in args:
        i = args.index(name)
        v = args[i + 1]
        del args[i:i + 2]
        return cast(v)
    return default


def _find(snap, platform, cid):
    for c in ((snap or {}).get("platforms", {}).get(platform) or {}).get("campaigns") or []:
        if str(c["id"]) == str(cid):
            return c
    return None


def change(cfg, cmd, platform, cid, usd=None, by="cli"):
    """pause | resume | budget on one campaign, with the cap check and a log line. → (exit code, message)."""
    s = core.settings(cfg)
    if platform not in WRITABLE:
        return 2, f"{platform}: changes go through the {core.NAMES.get(platform, platform)} app for now"
    acc = s["accounts"].get(platform)
    if not acc:
        return 2, f"no paid.accounts.{platform} for {cfg['name']}"
    snap = pull(cfg, quiet=True)                     # always decide on fresh numbers
    c = _find(snap, platform, cid)
    if not c:
        return 2, f"campaign {cid} isn't in {cfg['name']}'s {platform} account"
    m = MODS[platform]
    if cmd == "pause":
        m.set_status(acc, cid, False)
        core.log(cfg, "pause", f"paused {c['name']}", by, platform, str(cid))
        pull(cfg, quiet=True)
        return 0, f"paused {c['name']}"
    daily = usd if cmd == "budget" else (c.get("daily_budget") or 0)
    lifetime = 0 if daily else (c.get("budget_remaining") or 0)
    skip = (platform, cid) if c.get("running") else None
    ok, msg, nums = core.check(cfg, snap, daily_usd=daily, lifetime_usd=lifetime, skip=skip)
    if not ok:
        core.log(cfg, "refused", f"{cmd} {c['name']}: {msg}", by, platform, str(cid), usd)
        return 3, f"refused: {msg}"
    if cmd == "resume":
        m.set_status(acc, cid, True)
        core.log(cfg, "resume", f"resumed {c['name']} ({msg})", by, platform, str(cid), daily or lifetime)
    else:
        if c.get("budget_level") != "campaign":
            return 2, f"{c['name']} has its budget on the {c.get('budget_level')}s: change it in the ads app"
        m.set_daily_budget(acc, cid, usd)
        core.log(cfg, "budget", f"{c['name']}: daily budget ${c.get('daily_budget') or 0:.2f} → ${usd:.2f} ({msg})",
                 by, platform, str(cid), usd)
    pull(cfg, quiet=True)
    return 0, msg


def main(argv):
    if argv[:2] == ["auth", "google"]:              # OAuth consent → GOOGLE_ADS_REFRESH_TOKEN in .env
        print(google.authorize(open_browser="--no-browser" not in argv))
        return 0
    if len(argv) < 2:
        print(__doc__)
        return 2
    cfg = config.load(argv[0])
    cmd, args = argv[1], list(argv[2:])
    by = _opt(args, "--by", default="cli")
    if cmd == "pull":
        pull(cfg)
        return 0
    if cmd == "status":
        snap = core.load(cfg)
        d = export(cfg)
        if not snap:
            print("not pulled yet: python -m viral_scout paid <profile> pull")
            return 0
        print(f"{cfg['name']}: cap ${d['cap']:.0f}/month · spent ${d['month']['spent']:.2f} · running campaigns will add "
              f"${d['month']['running']:.2f} by month end · {d['month']['check']}")
        for p, a in snap["platforms"].items():
            print(f"\n{core.NAMES[p]}: " + ("" if a.get("ok") else a.get("error", "")))
            for c in a.get("campaigns") or []:
                if c["running"] or c["month_spend"]:
                    b = f"${c['daily_budget']:.2f}/day" if c.get("daily_budget") else (
                        f"${c['budget_remaining']:.2f} left" if c.get("budget_remaining") else "no budget read")
                    print(f"  {'▶' if c['running'] else '⏸'} {c['name']} [{c['id']}] {b} · ${c['month_spend']:.2f} this month"
                          + (f" · {c['results']:.0f} results, ${c['cost_per_result']:.2f} each" if c.get("results") else ""))
        return 0
    if cmd == "cap":
        if not args:
            print("usage: paid <profile> cap <daily_usd> [--lifetime <usd>]")
            return 2
        lifetime = _opt(args, "--lifetime", float, 0.0)
        snap = pull(cfg, quiet=True)
        ok, msg, nums = core.check(cfg, snap, daily_usd=float(args[0]), lifetime_usd=lifetime)
        print(("OK " if ok else "REFUSED ") + msg)
        print(json.dumps(nums))
        return 0 if ok else 3
    if cmd in ("pause", "resume", "budget"):
        need = 3 if cmd == "budget" else 2
        if len(args) < need:
            print(__doc__)
            return 2
        code, msg = change(cfg, cmd, args[0], args[1], float(args[2]) if cmd == "budget" else None, by)
        print(msg)
        return code
    if cmd == "ask":
        from . import ask
        return ask.run(cfg, args[0] if args else "", by)
    if cmd == "enforce":                             # the backstop by hand: pause today's new campaigns while over the cap
        from datetime import datetime, timezone
        from . import ask
        paused = ask.enforce(cfg, datetime.now(timezone.utc).replace(hour=0, minute=0, second=0), by)
        print(f"paused: {', '.join(paused)}" if paused else "nothing to pause")
        return 0
    if cmd == "log":
        if len(args) < 2:
            print('usage: paid <profile> log <action> "<text>" [--platform p] [--campaign id] [--amount usd]')
            return 2
        plat, camp = _opt(args, "--platform", default=""), _opt(args, "--campaign", default="")
        amount = _opt(args, "--amount", float)
        core.log(cfg, args[0], args[1], by, plat, camp, amount)
        export(cfg)
        print("logged")
        return 0
    print(__doc__)
    return 2
