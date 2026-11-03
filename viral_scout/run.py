"""One scouting run: discover → watch → seeds → re-check → enrich → score → save → report."""
import re
import time
from collections import Counter

from . import alerts, frames, report, swipe, transcripts, usage, whisper
from .db import Store
from .sources import instagram, links, tiktok, youtube, youtube_api


def _log(msg, quiet):
    if not quiet:
        print(msg, flush=True)


def scout(cfg, quiet=False, recheck=True, discover=True):
    errors, skipped = [], []
    usage.reset()
    pool = {}                       # key -> Item
    tracked = set()
    watched = set()

    def add(items, is_tracked=False, is_watch=False):
        for it in items:
            if it is None or not it.id:
                continue
            if it.key in pool:
                pool[it.key].merge(it)
            else:
                pool[it.key] = it
            if is_tracked:
                tracked.add(it.key)
            if is_watch:
                watched.add(it.key)

    store = Store(cfg["db"])
    d_yt, d_tt = cfg["discover"]["youtube"], cfg["discover"]["tiktok"]

    # 1. Independent discovery: what is big on the topic right now, whoever posted it.
    if discover:
        kws = d_yt["keywords"]
        if kws and youtube_api.available():
            _log(f"discover: YouTube Data API, {len(kws)} keywords ({d_yt['window']})", quiet)
            add(youtube_api.discover(kws, d_yt["window"], d_yt["shorts"], d_yt["per_query"],
                                     d_yt.get("languages"), d_yt.get("region"), errors))
            kws = []
        elif kws and d_yt["shorts"]:
            # yt-dlp can't read YouTube's Shorts search results, only hashtag feeds.
            skipped.append(f"YouTube keyword search for Shorts ({len(kws)} keywords): no YOUTUBE_API_KEY "
                           "(free, see README). Hashtag feeds still ran.")
            kws = []
        n = len(kws) + len(d_yt["hashtags"])
        if n:
            _log(f"discover: YouTube via yt-dlp, {n} queries ({d_yt['window']})", quiet)
            add(youtube.discover(kws, d_yt["hashtags"], d_yt["window"], d_yt["shorts"],
                                 d_yt["per_query"], errors))
        if d_tt["keywords"] or d_tt["hashtags"]:
            if tiktok.available():
                _log("discover: TikTok via Apify", quiet)
                add(tiktok.discover(d_tt["hashtags"], d_tt["keywords"], d_tt["per_query"], errors))
            else:
                skipped.append("TikTok discovery: no APIFY_TOKEN (see README)")

    # 2. Watch list: each creator's latest posts against their own median.
    for ch in cfg["watch"]["youtube"]:
        _log(f"watch: YouTube {ch}", quiet)
        recent = youtube.channel_recent(ch, 30, errors)
        med = youtube.median_views(recent)
        vs = [r.views for r in recent]
        for it in recent:
            it.channel_median = med
            it.creator_pct = youtube.percentile(it.views, vs)
        add(recent, is_watch=True)
        time.sleep(0.5)
    if cfg["watch"]["instagram"]:
        if instagram.available():
            for u in cfg["watch"]["instagram"]:
                _log(f"watch: Instagram {u}", quiet)
                add(instagram.watch(u, 25, errors), is_watch=True)
        else:
            skipped.append(f"Instagram watch list ({len(cfg['watch']['instagram'])} accounts): no IG_GRAPH_TOKEN "
                           "(see README). Their reels you send as seeds are still tracked.")
    if cfg["watch"]["tiktok"]:
        if tiktok.available():
            _log("watch: TikTok via Apify", quiet)
            add(tiktok.watch(cfg["watch"]["tiktok"], 30, errors), is_watch=True)
        else:
            skipped.append(f"TikTok watch list ({len(cfg['watch']['tiktok'])} accounts): no APIFY_TOKEN")

    # 3. Seeds from the profile + anything tracked in the DB, and 4. re-checks of recent posts for velocity.
    seeds = [links.clean_url(u) for u in cfg["seeds"]]
    rechecks = store.to_recheck(cfg["recheck"]["max_age_days"], cfg["recheck"]["limit"]) if recheck else []
    known = {it.url for it, _ in rechecks}
    jobs = [(u, True) for u in seeds if u not in known] + [(it.url, t) for it, t in rechecks]
    if jobs:
        _log(f"re-check: {len(jobs)} posts (seeds and recent finds)", quiet)
    done = set()
    for url, is_tracked in jobs:
        if url in done:
            continue
        done.add(url)
        it = links.fetch(url, "seed" if is_tracked else "re-check", errors)
        add([it], is_tracked=is_tracked)
        time.sleep(0.3)

    # 5. Filters. Dismissed posts never come back (unless tracked).
    for key in store.dismissed() - tracked:
        pool.pop(key, None)

    f = cfg["filters"]
    excl = [re.compile(p, re.I) for p in f["exclude"]]
    must = re.compile(f["must_match"], re.I) if f.get("must_match") else None

    def drop(key, final):
        """True if a post is off-topic, excluded, too small or too old. Untitled posts wait for enrichment."""
        it = pool[key]
        if key in tracked:
            return False
        if not it.title and not final:
            return key not in watched and it.reach is not None and it.reach < f["min_views"]
        # Hashtags are often spam (#english on gaming clips), so the topic check ignores them.
        text = re.sub(r"#\S+", " ", it.title or "") + " " + (it.channel or "")
        if any(p.search(f"{it.title} {it.channel}") for p in excl):
            return True
        if key in watched:
            return False
        if must and not must.search(text):
            return True
        if it.reach is not None and it.reach < f["min_views"]:
            return True
        return bool(final and it.age_days and it.age_days > f["max_age_days"])

    for key in [k for k in pool if drop(k, final=False)]:
        del pool[key]

    # 6. Enrich the best YouTube finds with likes, comments, date, subscribers (and titles for hashtag feeds).
    yt = sorted([i for i in pool.values() if i.platform == "youtube" and i.likes is None],
                key=lambda i: i.views or 0, reverse=True)[: cfg["enrich_top"]]
    if yt:
        _log(f"enrich: {len(yt)} YouTube videos", quiet)
    for it in yt:
        youtube.enrich(it, errors)
        if youtube.BLOCKED["hit"]:
            skipped.append("Part of enrichment: YouTube bot check. Space runs out (one per profile per day, "
                           "30+ min apart); untitled posts from hashtag feeds were dropped this run.")
            break
        time.sleep(1.0)
    for key in [k for k in pool if drop(k, final=True) or (not pool[k].title and k not in tracked)]:
        del pool[key]

    # Creator baseline for the strongest discoveries (one channel listing each).
    top = sorted([i for i in pool.values() if i.platform == "youtube" and not i.channel_median and i.channel_url],
                 key=lambda i: i.per_day or 0, reverse=True)[:15]
    if top:
        _log(f"baseline: {len(top)} creators", quiet)
    seen_ch = {}
    for it in top:
        if it.channel_url not in seen_ch:
            recent = youtube.channel_recent(it.channel_url, 30, [])
            seen_ch[it.channel_url] = (youtube.median_views(recent), [r.views for r in recent])
        it.channel_median, vs = seen_ch[it.channel_url]
        it.creator_pct = youtube.percentile(it.views, vs)

    # 7. Velocity, then transcripts for the posts that make the report, then history.
    for it in pool.values():
        store.add_rise(it)
    sec = report.sections(list(pool.values()), tracked, watched, cfg["report"]["top"])
    chosen = []
    for group in ("rising", "outliers", "by_day", "seeds"):
        for it in sec[group]:
            if it not in chosen:
                chosen.append(it)
    chosen = chosen[: cfg["report"].get("transcripts", 40)]
    fetched, captions_ok, limited = 0, True, False
    for it in chosen:
        cached = store.text(it.key)
        if cached and cached[1]:                 # only a real transcript is final; fallbacks are retried
            it.hook, it.transcript = cached[0] or "", cached[1]
            it.description = cached[2] or it.description
            it.cta, it.wpm = cached[3] or "", cached[4]
            continue
        if it.platform == "youtube" and not it.caption_url and captions_ok:
            youtube.enrich(it, errors)       # API finds come without caption links
        try:
            transcripts.fill(it, errors, captions=captions_ok)
        except transcripts.RateLimited:
            captions_ok, limited = False, True
            transcripts.fill(it, errors, captions=False)
        fetched += 1
        if it.caption_url and captions_ok:
            time.sleep(2.0)                  # be gentle: YouTube rate-limits caption downloads
    if limited:
        skipped.append("Some transcripts: YouTube rate-limited caption downloads (HTTP 429). "
                       "Captions are retried next run; the post caption is shown meanwhile.")
    if fetched:
        _log(f"transcripts: {fetched} posts", quiet)

    # Local Whisper for posts with no captions (Instagram/TikTok audio first), if enabled and installed.
    tcfg = cfg.get("transcribe") or {}
    if tcfg.get("whisper"):
        if whisper.available():
            todo = [i for i in chosen if not i.transcript and i.platform != "youtube"]
            todo += [i for i in chosen if not i.transcript and i.platform == "youtube" and captions_ok]
            todo = todo[: tcfg.get("max_per_run", 8)]
            if todo:
                _log(f"whisper: transcribing {len(todo)} posts locally", quiet)
            for it in todo:
                whisper.transcribe(it, cfg, errors)
        else:
            skipped.append("Local transcription: transcribe.whisper is on but faster-whisper isn't installed "
                           "(pip install faster-whisper).")

    # Local copies of thumbnails for on-screen text (read by the skill).
    for it in chosen[: cfg["report"].get("frames", 30)]:
        frames.fetch(cfg, it, errors)

    new_keys = set()
    for it in pool.values():
        if not store.seen_before(it.key):
            new_keys.add(it.key)
        store.save(it, tracked=it.key in tracked)
        if it.hook or it.transcript:
            store.save_text(it)
    store.commit()

    creators = Counter(i.channel for i in pool.values() if i.channel and i.key not in watched and i.key not in tracked)
    result = {
        "items": list(pool.values()), "tracked": tracked, "watched": watched, "new": new_keys,
        "errors": errors, "skipped": skipped, "repeat_creators": [c for c, n in creators.most_common(15) if n >= 2],
    }
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    result["usage"] = usage.snapshot()
    result["budget"] = usage.warnings(
        cfg,
        store.usage_since(now.strftime("%Y-%m-%dT00:00:00"), "youtube_api_units") + usage.COUNTS["youtube_api_units"],
        store.usage_since(now.strftime("%Y-%m-01T00:00:00"), "apify_items") + usage.COUNTS["apify_items"])
    paths = report.write(cfg, result)
    if cfg.get("alerts"):
        if alerts.available(cfg):
            hits = alerts.pick(cfg, list(pool.values()), store)
            if alerts.send(cfg, hits, paths[0], errors):
                for it, _ in hits:
                    store.flag(it.key, "alerted")
                store.commit()
                _log(f"alerts: sent {len(hits)}", quiet)
        else:
            _log("alerts: skipped (no TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)", quiet)
    store.log_run(cfg["name"], {"items": len(pool), "errors": len(errors), "report": paths[0],
                                "usage": usage.snapshot()})
    try:                                   # keep the web dashboard's data fresh
        from .export import export_all
        export_all([cfg["name"]])
    except Exception as err:               # never fail a run over the dashboard
        _log(f"export for the dashboard failed: {err}", quiet)
    return result, paths


def save(cfg, refs, note=""):
    """Save posts (id, key or URL) to the swipe file with fresh numbers and transcript; keep tracking them."""
    store = Store(cfg["db"])
    errors, out = [], []
    for ref in refs:
        row = store.find(ref)
        url = row[1] if row else ref
        if not url.startswith("http"):
            errors.append(f"{ref}: not found in history; pass the post URL instead")
            continue
        it = links.fetch(url, "saved", errors)
        if not it:
            continue
        cached = store.text(it.key)
        if cached and cached[1]:
            it.hook, it.transcript = cached[0] or "", cached[1]
        try:
            transcripts.fill(it, errors)
        except transcripts.RateLimited:
            errors.append(f"{ref}: YouTube rate-limited captions; saved without transcript (run save again later)")
            transcripts.fill(it, errors, captions=False)
        if it.platform == "youtube":
            it.channel_median = youtube.median_views(youtube.channel_recent(it.channel_url, 30, [])) if it.channel_url else None
        store.save(it, tracked=True)
        store.save_text(it)
        store.flag(it.key, "saved")
        out.append(swipe.write(cfg, it, note))
    store.commit()
    return out, errors


def dismiss(cfg, refs):
    store = Store(cfg["db"])
    done, missing = [], []
    for ref in refs:
        row = store.find(ref)
        if row:
            store.flag(row[0], "dismissed")
            done.append(row[0])
        else:
            missing.append(ref)
    store.commit()
    return done, missing


def add_seeds(cfg, urls):
    store = Store(cfg["db"])
    errors, out = [], []
    for u in urls:
        it = links.fetch(u, "seed", errors)
        if it:
            store.save(it, tracked=True)
            out.append(it)
    store.commit()
    return out, errors
