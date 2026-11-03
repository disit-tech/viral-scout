"""One own-performance run: pull configured sources → KPIs → medians → diagnose → 5 tests → snapshot → report."""
import json
from datetime import datetime
from pathlib import Path

from .. import usage
from . import diagnose as D
from . import kpis as K
from .store import PerfStore

SOURCES = [
    # name, module, label, keys
    ("instagram", "instagram", "Instagram media insights (your reels)", "IG_GRAPH_TOKEN + IG_GRAPH_USER_ID"),
    ("youtube", "youtube", "YouTube Analytics (your channel)",
     "YT_OAUTH_CLIENT_ID + YT_OAUTH_CLIENT_SECRET + YT_OAUTH_REFRESH_TOKEN (python -m viral_scout perf auth youtube)"),
    ("meta_ads", "meta_ads", "Meta ad account insights", "META_ADS_TOKEN + META_AD_ACCOUNT_ID"),
    ("tiktok_ads", "tiktok_ads", "TikTok ad account report", "TIKTOK_ADS_TOKEN + TIKTOK_ADVERTISER_ID"),
]


def _log(msg, quiet):
    if not quiet:
        print(msg, flush=True)


def _module(name):
    import importlib
    return importlib.import_module(f"viral_scout.perf.{name}")


def settings(cfg):
    p = cfg.get("perf") or {}
    econ = {k: v for k, v in (cfg.get("economics") or {}).items() if isinstance(v, (int, float))}
    goal = p.get("goal") or ("leads" if econ.get("lead_to_customer_rate") and not econ.get("avg_order_value")
                             else "sales")
    return p, econ, goal


def pull(cfg, store, errors, skipped, quiet=False):
    p, _, _ = settings(cfg)
    wanted = p.get("sources")
    pulled = {}
    for name, mod, label, need in SOURCES:
        if wanted and name not in wanted:
            continue
        m = _module(mod)
        if not m.available():
            skipped.append(f"{label}: no {need}. See docs/performance.md.")
            continue
        _log(f"perf: {label}", quiet)
        n_err = len(errors)
        try:
            recs = m.pull(cfg, errors)
        except Exception as err:                    # never fail the run over one source
            errors.append(f"{name}: {type(err).__name__}: {err}")
            recs = []
        if recs:
            store.replace_source(name, recs)
        elif len(errors) > n_err:
            skipped.append(f"{label}: pull failed (see errors); previous data kept.")
        pulled[name] = len(recs)
    return pulled


def analyze(records, econ, goal, history=None):
    """Pure analysis (no I/O): KPIs, curves, medians, fatigue, diagnosis and the 5 tests for every record."""
    history = history or {}
    rows = []
    for r in records:
        row = dict(r)
        row["kpis"] = K.compute(r, econ)
        row["curve"] = K.curve(r)
        row["curve_summary"] = K.curve_summary(row["curve"], r.get("duration"))
        row["band"] = K.duration_band(r.get("duration"))
        rows.append(row)
    meds = {kind: K.medians([x for x in rows if x["kind"] == kind]) for kind in ("organic", "paid")}
    by_platform = {}
    for kind, plat in {(x["kind"], x["platform"]) for x in rows}:
        by_platform[(kind, plat)] = K.medians([x for x in rows if x["kind"] == kind and x["platform"] == plat])
    for row in rows:
        m = K.scoped_medians(meds[row["kind"]], by_platform.get((row["kind"], row["platform"])), row["platform"])
        fat = D.fatigue(D.daily_series(row)) if row["kind"] == "paid" else None
        hist = history.get(row["key"]) or []
        if (not fat or not fat["detected"]) and row["kind"] == "paid" and len(hist) >= 3:
            series = [(ts[:10], d.get("frequency"), d.get("link_ctr", d.get("ctr"))) for ts, d in hist]
            fat = D.fatigue(series, min_points=3) or fat
        row["fatigue"] = fat
        row["diagnosis"] = D.diagnose(row, m, econ, goal, fat)
        row["tests"] = D.five_tests(row, m, econ, goal)
        if len(hist) >= 2:
            row["trend"] = {k: [hist[0][1].get(k), hist[-1][1].get(k)] for k in ("hook_rate", "ctr", "link_ctr",
                            "frequency", "cpa", "roas", "views", "engagement_rate")
                            if hist[-1][1].get(k) is not None and hist[0][1].get(k) != hist[-1][1].get(k)}
            row["history"] = [[ts, d] for ts, d in hist[-30:]]
    account = {}
    for kind in ("organic", "paid"):
        sub = [r for r in rows if r["kind"] == kind]
        if sub:
            tot = K.aggregate(sub)
            account[kind] = {"records": len(sub), "totals": {k: v for k, v in tot.items() if v is not None},
                             "kpis": K.account_kpis(sub, econ)}
    m = K.mer(econ, [r for r in records if r["kind"] == "paid"])
    if m:
        account.setdefault("paid", {})["mer"] = m
    return rows, meds, account


def build(cfg, do_pull=True, quiet=False):
    usage.reset()
    errors, skipped = [], []
    store = PerfStore(cfg["db"])
    pulled = pull(cfg, store, errors, skipped, quiet) if do_pull else {}
    if not do_pull:
        skipped.append("API sources: not pulled this time (import only); their last pulled data is reused.")
    p, econ, goal = settings(cfg)
    records = store.records()
    rows, meds, account = analyze(records, econ, goal)
    store.snapshot(rows)
    history = {r["key"]: store.history(r["key"]) for r in records}
    rows, meds, account = analyze(records, econ, goal, history)       # again, with this run in the history

    now = datetime.now()
    srcs = store.sources()
    store.close()
    data = {
        "name": cfg["name"], "date": now.isoformat(timespec="seconds"), "goal": goal, "days": p.get("days", 28),
        "economics": econ, "unit_economics": K.unit_economics(econ),
        "sources": {"pulled": pulled, "skipped": skipped, "errors": errors,
                    "stored": {s: {"records": n, "updated": u} for s, (n, u) in srcs.items()}},
        "records": rows, "medians": meds, "account": account, "priorities": D.priorities(goal),
        "kpi_defs": K.definitions(), "groups": K.GROUPS, "platform_differences": K.PLATFORM_DIFFERENCES,
        "usage": usage.snapshot(),
    }
    js = Path(cfg["db"]).parent / f"{cfg['name']}-perf-latest.json"
    js.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
    from .report import markdown
    out = Path(cfg["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    md = out / f"{now:%Y-%m-%d}-performance.md"
    md.write_text(markdown(data), encoding="utf-8")
    try:
        from ..export import export_perf
        export_perf([cfg["name"]])
    except Exception as err:                          # never fail over the dashboard
        _log(f"export for the dashboard failed: {err}", quiet)
    return data, (str(md), str(js))


def import_csv(cfg, path, source):
    from .csvimport import read
    recs, unknown = read(path, source)
    store = PerfStore(cfg["db"])
    store.upsert(recs)
    store.close()
    return recs, unknown


def latest(cfg):
    p = Path(cfg["db"]).parent / f"{cfg['name']}-perf-latest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
