"""One ads run: sources → merge → hook/offer/CTA → variants + score → history → report + JSON → dashboard export."""
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from .. import usage
from . import report, score, sources

EU_NOTE = ("Meta Ad Library API: skipped for coverage, not a key. Commercial ads are only in the API when they "
           "reached the EU; the profile's countries ({countries}) have none, so it would return political/issue ads "
           "only. Set ads.meta_countries (e.g. [DE, PL]) to read EU ads, or use apify_meta for the US.")


def _log(msg, quiet):
    if not quiet:
        print(msg, flush=True)


def _merge_same_meta_ad(ads):
    """The same Meta Library ID from the official API and from Apify: keep one, fill the gaps from the other."""
    by_id = {}
    out = []
    for a in ads:
        if a.source in ("meta_api", "apify_meta"):
            other = by_id.get(a.id)
            if other:
                main, extra = (other, a) if other.source == "meta_api" else (a, other)
                for f in ("image", "video", "link_url", "cta_text", "body", "title", "link_caption", "advertiser"):
                    if not getattr(main, f) and getattr(extra, f):
                        setattr(main, f, getattr(extra, f))
                if (not main.format or main.format == "image/other") and extra.format:
                    main.format = extra.format
                main.variants_reported = main.variants_reported or extra.variants_reported
                main.platforms = main.platforms or extra.platforms
                main.found_by = sorted(set(main.found_by + extra.found_by))
                if main is not other:
                    out[out.index(other)] = main
                by_id[a.id] = main
                continue
            by_id[a.id] = a
        out.append(a)
    return out


def _history(db_path, ads):
    """Remember every ad we've seen (first/last seen) so the report can flag ads new since the last run."""
    db = sqlite3.connect(db_path)
    db.execute("create table if not exists ads (key text primary key, advertiser text, first_seen text, "
               "last_seen text, active integer, days real, score real)")
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    seen_any = db.execute("select count(*) from ads").fetchone()[0] > 0
    for a in ads:
        row = db.execute("select first_seen from ads where key=?", (a.key,)).fetchone()
        a.new = seen_any and row is None
        db.execute("insert into ads values (?,?,?,?,?,?,?) on conflict(key) do update set advertiser=excluded.advertiser, "
                   "last_seen=excluded.last_seen, active=excluded.active, days=excluded.days, score=excluded.score",
                   (a.key, a.advertiser, row[0] if row else ts, ts, int(a.is_active), a.days_running, a.ad_score))
    db.commit()
    db.close()


def _alert_long_runners(cfg, ads, store, report_path, errors):
    """Telegram (same bot/creds as the organic alerts): competitor ads that just passed `ads.alert_days` (default 30)
    and are still running. Each ad is alerted once (table ads_alerted)."""
    from .. import alerts
    if not cfg.get("alerts") or not alerts.available(cfg):
        return 0
    days = (cfg.get("ads") or {}).get("alert_days", 30)
    store.db.execute("create table if not exists ads_alerted (key text primary key, ts text)")
    done = {r[0] for r in store.db.execute("select key from ads_alerted")}
    hits = sorted([a for a in ads if a.is_active and (a.days_running or 0) >= days and a.key not in done],
                  key=lambda a: -a.ad_score)[: (cfg.get("ads") or {}).get("alert_max", 3)]
    if not hits:
        return 0
    import requests
    token, chat = alerts._creds(cfg)
    lines = [f"🏆 ads scout · {cfg['name']}: {len(hits)} competitor ad(s) running {days}+ days"]
    nl = chr(10)
    for a in hits:
        part = f"{nl}{a.advertiser} · {a.days_running} days · score {round(a.ad_score)}"
        if a.hook:
            part += f"{nl}“{a.hook[:120]}”"
        if a.offers:
            part += f"{nl}Offer: {', '.join(a.offers[:3])}"
        if a.url:
            part += f"{nl}{a.url}"
        lines.append(part)
    lines.append(f"{nl}Report: {Path(report_path).name}")
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=30,
                          json={"chat_id": chat, "text": nl.join(lines)[:4000], "disable_web_page_preview": True})
        if not r.ok:
            errors.append(f"ads alerts: HTTP {r.status_code}")
            return 0
    except requests.RequestException as err:
        errors.append(f"ads alerts: {err}")
        return 0
    store.db.executemany("insert or ignore into ads_alerted values (?, ?)",
                         [(a.key, datetime.now(timezone.utc).isoformat()) for a in hits])
    store.db.commit()
    return len(hits)


def scout_ads(cfg, quiet=False):
    from ..db import Store
    usage.reset()
    cfg_ads = dict(cfg.get("ads") or {})
    cfg_ads.setdefault("countries", ["US"])
    errors, skipped, coverage = [], [], []
    ads = []
    configured = any(cfg_ads.get(k) for k in ("advertisers", "keywords", "domains"))
    wanted = [s for s in (cfg_ads.get("sources") or sources.SOURCES) if s in sources.SOURCES]
    unknown = [s for s in (cfg_ads.get("sources") or []) if s not in sources.SOURCES]
    if unknown:
        errors.append(f"ads.sources: unknown {', '.join(map(str, unknown))} (known: {', '.join(sources.SOURCES)})")
    if not configured:
        skipped.append("All ad sources: the profile has no ads: block with advertisers, keywords or domains "
                       "(see docs/profiles.md).")
        wanted = []
    for src in wanted:
        if not sources.available(src):
            skipped.append(sources.NEEDS[src][1])
            continue
        if src == "meta_api" and not sources.meta_countries(cfg_ads):
            skipped.append(EU_NOTE.format(countries=", ".join(cfg_ads["countries"])))
            continue
        _log(f"ads: {src}", quiet)
        try:
            got = sources.RUNNERS[src](cfg_ads, errors, log=lambda m: _log(m, quiet))
        except Exception as err:                       # one broken source never fails the run
            errors.append(f"{src}: {type(err).__name__}: {err}"[:300])
            continue
        ads += got
        if src == "meta_api":
            coverage.append(f"Meta Ad Library API: {len(got)} ads that reached {', '.join(sources.meta_countries(cfg_ads))} "
                            "(EU-delivered ads; US-only commercial ads aren't in the API).")
        elif src == "tiktok_api":
            coverage.append(f"TikTok Commercial Content API: {len(got)} ads shown in the EEA (the API has no US ads "
                            "and no ad copy, only media, dates and reach).")
        elif src == "apify_meta":
            coverage.append(f"Meta Ad Library via Apify: {len(got)} ads, country {cfg_ads['countries'][0]} "
                            "(the public Ad Library shows all active and inactive ads, without spend for non-political ads).")
        elif src == "apify_tiktok_top":
            coverage.append(f"TikTok Creative Center Top Ads via Apify: {len(got)} ads (TikTok's own top-ads selection; "
                            "usually no start date, so longevity isn't scored).")
        elif src == "apify_google":
            coverage.append(f"Google Ads Transparency Center via Apify: {len(got)} ads (first/last shown dates; "
                            "no copy for some formats).")

    ads = _merge_same_meta_ad([a for a in ads if a.id])
    score.enrich(ads)
    score.score(ads)
    _history(cfg["db"], ads)

    now = datetime.now(timezone.utc)
    store = Store(cfg["db"])
    month_apify = store.usage_since(now.strftime("%Y-%m-01T00:00:00"), "apify_items") + usage.COUNTS["apify_items"]
    result = {
        "ads": ads, "advertisers": score.advertisers(ads), "offers": score.offer_summary(ads),
        "errors": errors, "skipped": skipped, "coverage": coverage, "lookup": sources.lookup_links(cfg_ads),
        "usage": usage.snapshot(), "budget": usage.warnings(cfg, 0, month_apify), "countries": cfg_ads["countries"],
        "sources_requested": wanted,
    }
    paths = report.write(cfg, result)
    sent = _alert_long_runners(cfg, ads, store, paths[0], errors)
    if sent:
        _log(f"ads alerts: sent {sent}", quiet)
    store.log_run(cfg["name"], {"kind": "ads", "ads": len(ads), "errors": len(errors), "report": paths[0],
                                "usage": usage.snapshot()})
    store.db.close()
    try:
        from ..export import export_ads
        export_ads(cfg)
    except Exception as err:                           # never fail a run over the dashboard
        _log(f"export for the dashboard failed: {err}", quiet)
    return result, paths
