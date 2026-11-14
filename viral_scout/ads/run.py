"""One ads run: sources → merge → hook/offer/CTA → variants + score → history → report + JSON → dashboard export."""
import re
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
    else:
        from .. import activity
        activity.note(msg)   # --quiet keeps it off the terminal, not out of the live log


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


def _competitor_query(ad):
    """Found by searching for a named competitor (Meta advertiser search, Google domain/name), not a keyword."""
    return any(("advertiser" in f) or ("google" in f) for f in ad.found_by)


def on_topic(ads, cfg_ads):
    """Drop noise from keyword and category searches. ads.exclude_advertisers (regexes) always drops; ads.topic
    (words) must appear in the advertiser, copy, title or landing page of ads that only keyword/category searches
    found (a keyword like "handyman near me" also returns drama apps and games). Competitor searches are kept."""
    topic = [str(t).lower() for t in cfg_ads.get("topic") or [] if str(t).strip()]
    excl = []
    for p in cfg_ads.get("exclude_advertisers") or []:
        try:
            excl.append(re.compile(str(p), re.I))
        except re.error:
            excl.append(re.compile(re.escape(str(p)), re.I))
    keep, dropped = [], {"excluded": 0, "off_topic": 0}
    for a in ads:
        if any(p.search(a.advertiser or "") for p in excl):
            dropped["excluded"] += 1
            continue
        if topic and not _competitor_query(a):
            text = " ".join(str(x or "") for x in (a.advertiser, a.body, a.title, a.link_url, a.link_caption,
                                                   a.landing_domain)).lower()
            if not any(t in text for t in topic):
                dropped["off_topic"] += 1
                continue
        keep.append(a)
    return keep, dropped


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

    return _finish(cfg, cfg_ads, [a for a in ads if a.id], errors, skipped, coverage, wanted, quiet)


def _finish(cfg, cfg_ads, ads, errors, skipped, coverage, wanted, quiet, fresh=True, old_usage=None):
    """Filter, merge, score, report and export. fresh=False (rescore) skips history, alerts and the run log, so
    "new since the last run" flags and the usage meter stay as the real run left them."""
    from ..db import Store
    import json
    if fresh:                                          # everything as fetched, so a rescore can widen a filter again
        raw = Path(cfg["db"]).parent / f"{cfg['name']}-ads-raw.json"
        raw.write_text(json.dumps({"date": datetime.now().isoformat(), "ads": [a.to_json() for a in ads]},
                                  ensure_ascii=False), encoding="utf-8")
    ads, dropped = on_topic(ads, cfg_ads)
    if dropped["excluded"] or dropped["off_topic"]:
        coverage.append(f"Noise filter: dropped {dropped['off_topic']} ads from keyword/category searches that mention "
                        f"none of ads.topic, and {dropped['excluded']} from ads.exclude_advertisers. Competitor "
                        "searches are never filtered.")
        _log(f"noise filter: dropped {dropped['off_topic']} off-topic, {dropped['excluded']} excluded", quiet)
    ads = _merge_same_meta_ad(ads)
    score.enrich(ads)
    score.score(ads)
    if fresh:
        _history(cfg["db"], ads)

    now = datetime.now(timezone.utc)
    store = Store(cfg["db"])
    month_apify = store.usage_since(now.strftime("%Y-%m-01T00:00:00"), "apify_items") + usage.COUNTS["apify_items"]
    result = {
        "ads": ads, "advertisers": score.advertisers(ads), "offers": score.offer_summary(ads),
        "errors": errors, "skipped": skipped, "coverage": coverage, "lookup": sources.lookup_links(cfg_ads),
        "usage": usage.snapshot() if fresh else (old_usage or {}), "budget": usage.warnings(cfg, 0, month_apify),
        "countries": cfg_ads["countries"], "sources_requested": wanted,
    }
    if fresh:                                          # video links expire within days: transcribe the top ones now
        try:
            from . import extra
            n = extra.transcribe_picks(cfg, [a.to_json() for a in ads], errors, log=lambda m: _log(m, quiet))
            if n:
                _log(f"ads transcripts: {n} video ads (local Whisper)", quiet)
                coverage.append(f"Transcripts: {n} video ads among the ones worth studying (local Whisper, free).")
        except Exception as err:                       # never fail a run over transcripts
            errors.append(f"transcripts: {err}"[:200])
    paths = report.write(cfg, result)
    if fresh:
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


_DERIVED = {"hook", "offers", "offer_text", "cta", "variants", "group", "reach_pct", "ad_score", "labels", "new",
            "catalog", "start", "stop"}


def _ad_from_json(d):
    import dataclasses
    from .model import Ad, parse_when
    names = {f.name for f in dataclasses.fields(Ad)}
    ad = Ad(**{k: v for k, v in d.items() if k in names and k not in _DERIVED and v is not None})
    ad.start, ad.stop = parse_when(d.get("start")), parse_when(d.get("stop"))
    ad.new = bool(d.get("new"))
    ad.catalog = any("\U0001f6d2" in str(x) for x in d.get("labels") or [])   # the catalog-ad label
    return ad


def rescore_ads(cfg, quiet=False):
    """Re-filter and re-score the last ads run without fetching anything (free): after editing ads.topic,
    ads.exclude_advertisers or the scoring. Reads data/<profile>-ads-latest.json and rewrites the report."""
    import json
    usage.reset()
    cfg_ads = dict(cfg.get("ads") or {})
    cfg_ads.setdefault("countries", ["US"])
    path = Path(cfg["db"]).parent / f"{cfg['name']}-ads-latest.json"
    if not path.exists():
        raise FileNotFoundError(f"no ads run yet for {cfg['name']} ({path})")
    last = json.loads(path.read_text(encoding="utf-8"))
    raw = Path(cfg["db"]).parent / f"{cfg['name']}-ads-raw.json"
    # Start from the unfiltered copy when there is one: the latest JSON is already filtered.
    source = json.loads(raw.read_text(encoding="utf-8")) if raw.exists() else last
    ads = [_ad_from_json(a) for a in source.get("ads") or []]
    coverage = [c for c in last.get("coverage") or [] if not c.startswith("Noise filter")]
    coverage.append(f"Rescored without fetching ({datetime.now():%Y-%m-%d %H:%M}) from the run of "
                    f"{str(last.get('date', ''))[:16].replace('T', ' ')}.")
    _log(f"rescore: {len(ads)} ads from the last run ({'unfiltered copy' if raw.exists() else 'filtered copy'}), "
         "nothing fetched", quiet)
    return _finish(cfg, cfg_ads, ads, list(last.get("errors") or []), list(last.get("skipped") or []), coverage,
                   last.get("sources_requested") or [], quiet, fresh=False, old_usage=last.get("usage"))
