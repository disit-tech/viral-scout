"""Ad sources. Legitimate access only: official APIs, or paid providers (Apify) that handle the platform themselves.

No page scraping here: no private APIs, no header spoofing, no logins, no bot-check bypassing. For anything
without an API, the report adds plain links to the public libraries so a person can look (see lookup_links).
"""
import json
import os
import re
import time
from datetime import timedelta
from urllib.parse import quote_plus

import requests

from .. import usage
from .model import Ad, now, parse_count, parse_when, unwrap
from . import extract

# Meta: commercial ads are in the API only when they reached the EU (ads_archive, ad_reached_countries note).
EU = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU",
      "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"}
# TikTok Commercial Content API: EEA country codes (UK and Switzerland aren't in the API's list).
EEA = EU | {"IS", "LI", "NO"}

GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v26.0")
META_FIELDS = ("id,page_id,page_name,ad_creation_time,ad_delivery_start_time,ad_delivery_stop_time,"
               "ad_creative_bodies,ad_creative_link_titles,ad_creative_link_captions,ad_creative_link_descriptions,"
               "ad_snapshot_url,publisher_platforms,eu_total_reach,languages")
TIKTOK_FIELDS = ("ad.id,ad.first_shown_date,ad.last_shown_date,ad.status,ad.videos,ad.image_urls,ad.reach,"
                 "advertiser.business_id,advertiser.business_name")

SOURCES = ["meta_api", "tiktok_api", "apify_meta", "apify_tiktok_top", "apify_google"]

NEEDS = {
    "meta_api": (["META_AD_LIBRARY_TOKEN"], "Meta Ad Library API: no META_AD_LIBRARY_TOKEN (free; identity-verified "
                 "Meta developer account). Covers ads delivered in the EU plus political/issue ads; not US commercial ads."),
    "tiktok_api": (["TIKTOK_RESEARCH_CLIENT_KEY", "TIKTOK_RESEARCH_CLIENT_SECRET"],
                   "TikTok Commercial Content API: no TIKTOK_RESEARCH_CLIENT_KEY / TIKTOK_RESEARCH_CLIENT_SECRET "
                   "(free after TikTok approves a research application). Covers ads shown in the EEA."),
    "apify_meta": (["APIFY_TOKEN", "APIFY_ADS_ACTOR"], "Meta Ad Library via Apify (US and everywhere else): needs "
                   "APIFY_TOKEN + APIFY_ADS_ACTOR (paid per ad, e.g. apify~facebook-ads-scraper)."),
    "apify_tiktok_top": (["APIFY_TOKEN", "APIFY_TIKTOK_ADS_ACTOR"], "TikTok Creative Center Top Ads via Apify: needs "
                         "APIFY_TOKEN + APIFY_TIKTOK_ADS_ACTOR (paid; Creative Center has no public API)."),
    "apify_google": (["APIFY_TOKEN", "APIFY_GOOGLE_ADS_ACTOR"], "Google Ads Transparency Center via Apify: needs "
                     "APIFY_TOKEN + APIFY_GOOGLE_ADS_ACTOR (paid; the Transparency Center has no public API)."),
}


def available(source):
    return all(os.environ.get(k) for k in NEEDS[source][0])


def pick(d, *paths, default=None):
    """First non-empty value among dot paths ('snapshot.body.text', 'cards.0.title') in a loosely shaped dict."""
    for p in paths:
        cur = d
        for part in p.split("."):
            if isinstance(cur, dict):
                cur = cur.get(part)
            elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
                cur = cur[int(part)]
            else:
                cur = None
            if cur is None:
                break
        if cur not in (None, "", [], {}):
            return cur
    return default


def _text(v):
    if isinstance(v, list):
        v = next((x for x in v if isinstance(x, str) and x.strip()), "")
    if isinstance(v, dict):
        v = v.get("text") or (v.get("markup") or {}).get("__html") or ""
    s = re.sub(r"<[^>]+>", " ", str(v or ""))
    s = s.replace("&amp;", "&").replace("&nbsp;", " ").replace("&#039;", "'").replace("&quot;", '"')
    return re.sub(r"[ \t]+", " ", s).strip()


def _advertiser_entries(cfg_ads):
    """advertisers: ["Sunrun", "123456789", {name, page_id, match, domain}] → list of dicts."""
    out = []
    for a in cfg_ads.get("advertisers") or []:
        if isinstance(a, dict):
            out.append({"name": str(a.get("name") or a.get("page_id") or ""), "page_id": str(a.get("page_id") or ""),
                        "match": a.get("match") or "", "domain": a.get("domain") or ""})
        elif str(a).strip().isdigit():
            out.append({"name": str(a).strip(), "page_id": str(a).strip(), "match": "", "domain": ""})
        elif str(a).strip():
            out.append({"name": str(a).strip(), "page_id": "", "match": "", "domain": ""})
    return out


def _matches(adv, page_name):
    pat = adv["match"] or re.escape(adv["name"])
    try:
        return bool(re.search(pat, page_name or "", re.I))
    except re.error:
        return adv["name"].lower() in (page_name or "").lower()


# ---------- Meta Ad Library API (official) ----------

def meta_countries(cfg_ads):
    explicit = [c.upper() for c in cfg_ads.get("meta_countries") or []]
    return explicit or [c.upper() for c in cfg_ads.get("countries") or [] if c.upper() in EU]


def _meta_get(url, params, label, errors, state):
    if state.get("stop"):
        return None
    try:
        r = requests.get(url, params=params, timeout=60)
        usage.add("meta_ad_library_requests")
        d = r.json()
    except (requests.RequestException, ValueError) as err:
        errors.append(f"{label}: {err}")
        return None
    if "error" in d:
        e = d["error"]
        msg = e.get("message", "")[:200]
        if e.get("code") in (4, 17, 613, 80004) or "rate" in msg.lower():
            state["stop"] = True
            errors.append(f"Meta Ad Library API rate limit ({e.get('code')}): stopped Meta for this run. {msg}")
        elif e.get("code") == 190:
            state["stop"] = True
            errors.append(f"Meta Ad Library API: access token invalid or expired (190). {msg}")
        else:
            errors.append(f"{label}: Meta error {e.get('code')}: {msg}")
        return None
    return d


def _meta_ad(d, found_by, countries):
    bodies = d.get("ad_creative_bodies") or []
    titles = d.get("ad_creative_link_titles") or []
    caps = d.get("ad_creative_link_captions") or []
    cards = max(len(bodies), len(titles), 1)
    return Ad(
        source="meta_api", id=str(d.get("id")), advertiser=d.get("page_name") or "", advertiser_id=str(d.get("page_id") or ""),
        url=f"https://www.facebook.com/ads/library/?id={d.get('id')}", snapshot_url=d.get("ad_snapshot_url") or "",
        body=_text(bodies), title=_text(titles), link_caption=_text(caps),
        format="carousel" if cards > 1 else "",
        platforms=[str(p).lower() for p in d.get("publisher_platforms") or []], countries=countries,
        start=parse_when(d.get("ad_delivery_start_time")), stop=parse_when(d.get("ad_delivery_stop_time")),
        reach=parse_count(d.get("eu_total_reach")), reach_label="EU reach" if d.get("eu_total_reach") else "",
        found_by=[found_by],
    )


def meta_api(cfg_ads, errors, log=print):
    countries = meta_countries(cfg_ads)
    token = os.environ["META_AD_LIBRARY_TOKEN"]
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/ads_archive"
    since = (now() - timedelta(days=int(cfg_ads.get("days", 180)))).strftime("%Y-%m-%d")
    per_query = int(cfg_ads.get("per_query", 50))
    base = {"access_token": token, "ad_type": "ALL", "ad_active_status": "ALL", "fields": META_FIELDS,
            "ad_reached_countries": json.dumps(countries), "ad_delivery_date_min": since, "limit": min(per_query, 100)}
    state, out = {}, {}

    def collect(params, label, keep=None, media=None):
        p = dict(base, **params)
        if media:
            p["media_type"] = media
        got, next_url, first = 0, url, True
        while next_url and got < per_query and not state.get("stop"):
            d = _meta_get(next_url, p if first else None, label, errors, state)
            first = False
            if not d:
                break
            for row in d.get("data") or []:
                ad = _meta_ad(row, label, countries)
                if keep and not keep(ad):
                    continue
                got += 1
                if ad.key in out:
                    out[ad.key].found_by = sorted(set(out[ad.key].found_by + ad.found_by))
                    if media == "VIDEO":
                        out[ad.key].format = "video"
                else:
                    if media == "VIDEO":
                        ad.format = "video"
                    out[ad.key] = ad
            next_url = (d.get("paging") or {}).get("next")
            time.sleep(1.0)
        return got

    advs = _advertiser_entries(cfg_ads)
    ids = [a["page_id"] for a in advs if a["page_id"]]
    queries = []
    for i in range(0, len(ids), 10):                 # search_page_ids takes up to 10 Page IDs
        queries.append(({"search_page_ids": json.dumps(ids[i:i + 10])}, "meta pages " + ",".join(ids[i:i + 10]), None))
    for a in advs:
        if not a["page_id"]:
            queries.append(({"search_terms": a["name"][:100], "search_type": "KEYWORD_EXACT_PHRASE"},
                            f"meta advertiser {a['name']}", (lambda ad, a=a: _matches(a, ad.advertiser))))
    for k in cfg_ads.get("keywords") or []:
        queries.append(({"search_terms": str(k)[:100], "search_type": "KEYWORD_UNORDERED"}, f"meta keyword {k}", None))
    video_pass = cfg_ads.get("meta_video_pass", True)
    for params, label, keep in queries:
        if video_pass:
            collect(params, label, keep, media="VIDEO")      # tags video ads (the API has no format field)
        n = collect(params, label, keep)
        log(f"  {label}: {n} ads")
    for ad in out.values():
        if not ad.format:
            ad.format = "image/other"
    return list(out.values())


# ---------- TikTok Commercial Content API (official, EEA) ----------

def _tiktok_token(errors):
    try:
        r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", timeout=30,
                          headers={"Content-Type": "application/x-www-form-urlencoded"},
                          data={"client_key": os.environ["TIKTOK_RESEARCH_CLIENT_KEY"],
                                "client_secret": os.environ["TIKTOK_RESEARCH_CLIENT_SECRET"],
                                "grant_type": "client_credentials"})
        usage.add("tiktok_research_requests")
        d = r.json()
    except (requests.RequestException, ValueError) as err:
        errors.append(f"TikTok token: {err}")
        return None
    if not d.get("access_token"):
        errors.append(f"TikTok token: {d.get('error_description') or d.get('error') or str(d)[:150]}")
    return d.get("access_token")


def _tiktok_ad(row, found_by):
    ad, adv = row.get("ad") or {}, row.get("advertiser") or {}
    vids = ad.get("videos") or []
    imgs = ad.get("image_urls") or []
    status = str(ad.get("status") or "").lower()
    stop = parse_when(ad.get("last_shown_date"))
    active = True if status == "active" else False if status == "inactive" else None
    if active:
        stop = None
    return Ad(
        source="tiktok_api", id=str(ad.get("id")), advertiser=adv.get("business_name") or "",
        advertiser_id=str(adv.get("business_id") or adv.get("buisness_id") or ""),
        url=f"https://library.tiktok.com/ads/detail/?ad_id={ad.get('id')}",
        image=imgs[0] if imgs else (vids[0].get("cover_image_url", "") if vids and isinstance(vids[0], dict) else ""),
        video=vids[0].get("url", "") if vids and isinstance(vids[0], dict) else "",
        format=extract.norm_format("", has_video=bool(vids), has_images=len(imgs), cards=len(imgs)),
        platforms=["tiktok"], start=parse_when(ad.get("first_shown_date")), stop=stop, active=active,
        reach=parse_count((ad.get("reach") or {}).get("unique_users_seen")),
        reach_label="unique users seen (EEA)", found_by=[found_by],
    )


def tiktok_api(cfg_ads, errors, log=print):
    token = _tiktok_token(errors)
    if not token:
        return []
    days = min(int(cfg_ads.get("days", 180)), 364)
    filters = {"ad_published_date_range": {"min": (now() - timedelta(days=days)).strftime("%Y%m%d"),
                                           "max": now().strftime("%Y%m%d")}}
    eea = [c.upper() for c in cfg_ads.get("countries") or [] if c.upper() in EEA]
    if cfg_ads.get("tiktok_country"):
        filters["country_code"] = str(cfg_ads["tiktok_country"]).upper()
    elif len(eea) == 1:
        filters["country_code"] = eea[0]
    per_query = int(cfg_ads.get("per_query", 50))
    out = {}
    terms = [(a["name"], f"tiktok advertiser {a['name']}", a) for a in _advertiser_entries(cfg_ads) if not a["page_id"]]
    terms += [(k, f"tiktok keyword {k}", None) for k in cfg_ads.get("keywords") or []]
    for term, label, adv in terms:
        search_id, got = None, 0
        while got < per_query:
            body = {"filters": filters, "search_term": str(term)[:50], "max_count": 10}
            if search_id:
                body["search_id"] = search_id
            try:
                r = requests.post("https://open.tiktokapis.com/v2/research/adlib/ad/query/",
                                  params={"fields": TIKTOK_FIELDS}, json=body, timeout=60,
                                  headers={"Authorization": f"Bearer {token}"})
                usage.add("tiktok_research_requests")
                d = r.json()
            except (requests.RequestException, ValueError) as err:
                errors.append(f"{label}: {err}")
                break
            err = d.get("error") or {}
            if err.get("code") not in (None, "", "ok"):
                errors.append(f"{label}: TikTok {err.get('code')}: {str(err.get('message'))[:200]}")
                break
            data = d.get("data") or {}
            rows = data.get("ads") or []
            for row in rows:
                ad = _tiktok_ad(row, label)
                if adv and not _matches(adv, ad.advertiser):
                    continue
                got += 1
                out.setdefault(ad.key, ad)
            search_id = data.get("search_id")
            if not rows or str(data.get("has_more")).lower() not in ("true", "1"):
                break
            time.sleep(1.0)
        log(f"  {label}: {got} ads")
    return list(out.values())


# ---------- Apify (paid providers; actors differ, so fields are read loosely) ----------

def _apify(actor, payload, label, errors):
    try:
        r = requests.post(f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items",
                          params={"token": os.environ["APIFY_TOKEN"]}, json=payload, timeout=300)
        if r.status_code >= 400:
            errors.append(f"{label}: Apify HTTP {r.status_code} {r.text[:200]}")
            return []
        rows = r.json()
    except (requests.RequestException, ValueError) as err:
        errors.append(f"{label}: {err}")
        return []
    rows = rows if isinstance(rows, list) else []
    usage.add("apify_items", len(rows))
    usage.add("apify_runs")
    return [r for r in rows if isinstance(r, dict)]


def library_url(country, keyword=None, page_id=None, exact=False):
    """Public Meta Ad Library search page (for people to open, and as Apify actor input)."""
    c = (country or "ALL").upper()
    if page_id:
        return (f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country={c}"
                f"&view_all_page_id={page_id}&search_type=page&media_type=all")
    st = "keyword_exact_phrase" if exact else "keyword_unordered"
    return (f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country={c}"
            f"&q={quote_plus(str(keyword or ''))}&search_type={st}&media_type=all")


def _meta_apify_ad(row, found_by, country):
    snap = row.get("snapshot") if isinstance(row.get("snapshot"), dict) else {}
    cards = snap.get("cards") or row.get("cards") or []
    card = cards[0] if cards and isinstance(cards[0], dict) else {}
    videos = snap.get("videos") or row.get("videos") or []
    images = snap.get("images") or row.get("images") or []
    vid0 = videos[0] if videos and isinstance(videos[0], dict) else {}
    img0 = images[0] if images and isinstance(images[0], dict) else {}
    aid = str(pick(row, "adArchiveID", "adArchiveId", "ad_archive_id", "adId", "ad_id", "id", default=""))
    body = _text(pick(row, "snapshot.body.text", "snapshot.body", "body", "adText", "ad_creative_bodies", "text")
                 or card.get("body"))
    start = parse_when(pick(row, "startDate", "start_date", "startDateFormatted", "ad_delivery_start_time"))
    stop = parse_when(pick(row, "endDate", "end_date", "endDateFormatted", "ad_delivery_stop_time"))
    active = pick(row, "isActive", "is_active", "active")
    if isinstance(active, str):
        active = active.lower() in ("true", "active", "1")
    if active and stop and stop > now() - timedelta(days=1):
        stop = None                                  # some actors set endDate = today for running ads
    if not start:                                    # apify~facebook-ads-scraper also gives totalActiveTime (seconds)
        secs = parse_count(pick(row, "totalActiveTime", "total_active_time"))
        if secs:
            start = (stop or now()) - timedelta(seconds=secs)
    plats = pick(row, "publisherPlatform", "publisher_platform", "publisherPlatforms", "publisher_platforms", default=[])
    if isinstance(plats, str):
        plats = [plats]
    return Ad(
        source="apify_meta", id=aid, advertiser=_text(pick(row, "pageName", "page_name", "snapshot.pageName",
                                                          "snapshot.page_name", "advertiser")),
        advertiser_id=str(pick(row, "pageID", "pageId", "page_id", "snapshot.pageId", default="")),
        url=pick(row, "adLibraryURL", "ad_library_url", "url", default="")
        if "ads/library" in str(pick(row, "adLibraryURL", "ad_library_url", "url", default=""))
        else (f"https://www.facebook.com/ads/library/?id={aid}" if aid else ""),
        image=str(pick(img0, "originalImageUrl", "resizedImageUrl", "url", default="")
                  or pick(vid0, "videoPreviewImageUrl", default="")
                  or pick(card, "originalImageUrl", "resizedImageUrl", "videoPreviewImageUrl", default="")
                  or pick(row, "imageUrl", "image", "thumbnail", default="")),
        video=str(pick(vid0, "videoHdUrl", "videoSdUrl", default="") or pick(card, "videoHdUrl", "videoSdUrl", default="")),
        body=body,
        title=_text(pick(row, "snapshot.title", "title", "ad_creative_link_titles") or card.get("title")),
        link_caption=_text(pick(row, "snapshot.caption", "caption", "ad_creative_link_captions") or card.get("caption")),
        link_url=unwrap(str(pick(row, "snapshot.linkUrl", "linkUrl", "link_url", default="") or card.get("linkUrl") or "")),
        cta_text=_text(pick(row, "snapshot.ctaText", "ctaText", "cta_text") or card.get("ctaText")),
        format=extract.norm_format(pick(row, "snapshot.displayFormat", "displayFormat", "display_format", "format"),
                                   has_video=bool(vid0), has_images=len(images), cards=len(cards)),
        platforms=[str(p).lower() for p in plats], countries=[country] if country else [],
        start=start, stop=stop, active=active if isinstance(active, bool) else None,
        reach=parse_count(pick(row, "euTotalReach", "eu_total_reach", "reachEstimate", "reach")),
        reach_label="EU reach" if pick(row, "euTotalReach", "eu_total_reach") else ("reach" if pick(row, "reachEstimate", "reach") else ""),
        variants_reported=parse_count(pick(row, "collationCount", "collation_count")),
        found_by=[found_by],
    )


def apify_meta(cfg_ads, errors, log=print):
    country = (cfg_ads.get("countries") or ["US"])[0].upper()
    urls = []
    for a in _advertiser_entries(cfg_ads):
        urls.append((library_url(country, page_id=a["page_id"]) if a["page_id"]
                     else library_url(country, a["name"], exact=True), f"apify meta advertiser {a['name']}", a))
    for k in cfg_ads.get("keywords") or []:
        urls.append((library_url(country, k), f"apify meta keyword {k}", None))
    if not urls:
        return []
    per_query = int(cfg_ads.get("per_query", 50))
    out = {}
    for u, label, adv in urls:                     # one run per URL, so each result knows which query found it
        payload = {"startUrls": [{"url": u}], "resultsLimit": per_query}
        payload.update(cfg_ads.get("apify_input") or {})
        rows = _apify(os.environ["APIFY_ADS_ACTOR"], payload, label, errors)
        n = 0
        for row in rows:
            ad = _meta_apify_ad(row, label, country)
            if not ad.id or (adv and not adv["page_id"] and not _matches(adv, ad.advertiser)):
                continue
            n += 1
            if ad.key in out:
                out[ad.key].found_by = sorted(set(out[ad.key].found_by + ad.found_by))
            else:
                out[ad.key] = ad
        log(f"  {label}: {n} ads")
    return list(out.values())


def apify_tiktok_top(cfg_ads, errors, log=print):
    country = (cfg_ads.get("countries") or ["US"])[0].upper()
    kws = list(cfg_ads.get("keywords") or [])
    payload = {"keywords": kws, "keyword": kws[0] if kws else "", "country": country, "region": country,
               "period": 30, "maxItems": int(cfg_ads.get("per_query", 50))}
    payload.update(cfg_ads.get("tiktok_top_input") or {})
    rows = _apify(os.environ["APIFY_TIKTOK_ADS_ACTOR"], payload, "apify tiktok top ads", errors)
    out = []
    for row in rows:
        aid = str(pick(row, "id", "ad_id", "adId", "material_id", "materialId", default=""))
        if not aid:
            continue
        title = _text(pick(row, "ad_title", "adTitle", "title", "caption", "text", "description"))
        url = pick(row, "url", "detailUrl", "detail_url", "link", default="")
        out.append(Ad(
            source="apify_tiktok_top", id=aid, advertiser=_text(pick(row, "brand_name", "brandName", "advertiser",
                                                                     "advertiser_name", "advertiserName")),
            url=url or f"https://ads.tiktok.com/business/creativecenter/topads/{aid}/pc/en",
            image=str(pick(row, "video_info.cover", "videoInfo.cover", "cover", "coverUrl", "cover_url", "thumbnail", default="")),
            body=title, title="", format="video", platforms=["tiktok"], countries=[country],
            likes=parse_count(pick(row, "like", "likes", "likeCount", "like_count", "diggCount")),
            reach=parse_count(pick(row, "views", "play_count", "playCount", "impression", "impressions")),
            reach_label="views" if pick(row, "views", "play_count", "playCount") else (
                "impressions" if pick(row, "impression", "impressions") else ""),
            start=parse_when(pick(row, "first_shown", "firstShown", "start_date", "startDate", "create_time")),
            cta_text=_text(pick(row, "cta", "cta_text", "ctaText", "call_to_action")),
            found_by=["apify tiktok top ads"],
        ))
    log(f"  apify tiktok top ads: {len(out)} ads")
    return out


def apify_google(cfg_ads, errors, log=print):
    country = (cfg_ads.get("countries") or ["US"])[0].upper()
    domains = list(cfg_ads.get("domains") or []) + [a["domain"] for a in _advertiser_entries(cfg_ads) if a["domain"]]
    names = [a["name"] for a in _advertiser_entries(cfg_ads) if not a["page_id"]]
    if not (domains or names):
        return []
    payload = {"domains": domains, "searchTerms": domains + names, "region": country,
               "maxItems": int(cfg_ads.get("per_query", 50))}
    payload.update(cfg_ads.get("google_input") or {})
    rows = _apify(os.environ["APIFY_GOOGLE_ADS_ACTOR"], payload, "apify google transparency", errors)
    out = []
    for row in rows:
        cid = str(pick(row, "creativeId", "creative_id", "adId", "ad_id", "id", default=""))
        if not cid:
            continue
        adv_id = str(pick(row, "advertiserId", "advertiser_id", default=""))
        stop = parse_when(pick(row, "lastShown", "last_shown", "lastShownDate", "last_shown_date", "endDate"))
        active = pick(row, "isActive", "is_active")
        if active is None and stop:
            active = stop >= now() - timedelta(days=3)       # "last shown" yesterday = still running
        if active and stop and stop >= now() - timedelta(days=3):
            stop = None
        url = pick(row, "url", "adUrl", "creativeUrl", "link", "previewUrl", default="")
        if not url or "adstransparency" not in str(url):
            url = (f"https://adstransparency.google.com/advertiser/{adv_id}/creative/{cid}?region={country}"
                   if adv_id else str(url))
        out.append(Ad(
            source="apify_google", id=cid, advertiser=_text(pick(row, "advertiserName", "advertiser_name", "advertiser")),
            advertiser_id=adv_id, url=url,
            image=str(pick(row, "imageUrl", "image", "previewImage", "preview_image", "thumbnail", default="")),
            title=_text(pick(row, "headline", "title")), body=_text(pick(row, "description", "text", "body")),
            link_url=str(pick(row, "landingPage", "landing_page", "destinationUrl", "targetDomain", default="")),
            format=extract.norm_format(pick(row, "format", "adFormat", "ad_format", "type")),
            platforms=[str(p).lower() for p in (pick(row, "platforms", "surfaces", default=[]) or [])] or ["google"],
            countries=[country], start=parse_when(pick(row, "firstShown", "first_shown", "firstShownDate",
                                                       "first_shown_date", "startDate")),
            stop=stop, active=active if isinstance(active, bool) else None,
            reach=parse_count(pick(row, "impressions", "timesShown", "times_shown")),
            reach_label="times shown (range)" if pick(row, "impressions", "timesShown", "times_shown") else "",
            found_by=["apify google transparency"],
        ))
    log(f"  apify google transparency: {len(out)} ads")
    return out


RUNNERS = {"meta_api": meta_api, "tiktok_api": tiktok_api, "apify_meta": apify_meta,
           "apify_tiktok_top": apify_tiktok_top, "apify_google": apify_google}


def lookup_links(cfg_ads):
    """Plain links to the public libraries, for a person to open in a browser (no fetching by the tool)."""
    country = (cfg_ads.get("countries") or ["US"])[0].upper()
    rows = []
    for a in _advertiser_entries(cfg_ads):
        links = {"Meta Ad Library": library_url(country, page_id=a["page_id"]) if a["page_id"]
                 else library_url(country, a["name"], exact=True)}
        if a["domain"]:
            links["Google Ads Transparency"] = f"https://adstransparency.google.com/?region={country}&domain={a['domain']}"
        rows.append({"label": a["name"], "kind": "advertiser", "links": links})
    for d in cfg_ads.get("domains") or []:
        rows.append({"label": d, "kind": "domain",
                     "links": {"Google Ads Transparency": f"https://adstransparency.google.com/?region={country}&domain={d}"}})
    for k in cfg_ads.get("keywords") or []:
        rows.append({"label": k, "kind": "keyword", "links": {
            "Meta Ad Library": library_url(country, k),
            "TikTok Creative Center Top Ads": "https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en",
        }})
    return rows
