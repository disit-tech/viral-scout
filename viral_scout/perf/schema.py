"""The normalized record. Every source (API or CSV) produces dicts with these fields; anything unknown stays None.

Counts are absolute numbers for the reporting period; times are seconds; money is in the account currency.
Platform-provided rates (e.g. YouTube's averageViewPercentage) are kept separately with a `_given` suffix so the
KPI layer can prefer computing from counts and fall back to the platform's own number.
"""

FIELDS = {
    # identity
    "key": "source:id, unique per record",
    "source": "instagram | youtube | meta_ads | tiktok_ads | csv:meta | csv:tiktok | csv:youtube | csv:generic",
    "platform": "instagram | youtube | facebook | tiktok | other",
    "kind": "organic | paid",
    "id": "post / video / ad id",
    "title": "caption first line, video title or ad name",
    "url": "permalink, if known",
    "thumbnail": "thumbnail URL, if known",
    "creative_id": "ad creative id (paid)",
    "campaign": "campaign name (paid)",
    "published": "ISO date the post went live (organic)",
    "date_start": "reporting period start (YYYY-MM-DD)",
    "date_stop": "reporting period end (YYYY-MM-DD)",
    "duration": "video length in seconds",
    # A. attention
    "impressions": "times the video/ad was shown",
    "reach": "unique accounts that saw it",
    "frequency": "impressions ÷ reach, as reported",
    "views": "the platform's own view/play count (definition differs per platform, see view_definition)",
    "video_starts": "video plays started (Meta video_play_actions, TikTok video_play_actions)",
    "views_2s": "2-second views (TikTok video_watched_2s; Meta 2-second continuous plays)",
    "views_3s": "3-second views (Meta 'video_view' action)",
    "views_6s": "6-second views (TikTok video_watched_6s)",
    "thruplays": "Meta ThruPlays: played to completion, or 15 s for longer videos",
    "engaged_views": "YouTube engagedViews",
    "skip_rate_given": "Instagram reels_skip_rate, % of plays skipped in the first 3 s",
    "stayed_pct_given": "YouTube Studio 'Stayed to watch' % for Shorts (vs swiped away)",
    # B. retention
    "p25": "plays reaching 25% of the length", "p50": "plays reaching 50%", "p75": "plays reaching 75%",
    "p100": "plays reaching 100% (completed)",
    "avg_watch_time": "average seconds watched per play",
    "avg_pct_viewed_given": "platform-reported average % viewed (YouTube averageViewPercentage)",
    "total_watch_time": "total seconds watched",
    "retention": "[[elapsed ratio 0–1, audience watch ratio, relative performance or None], ...]",
    # C. engagement
    "likes": "", "comments": "", "shares": "", "saves": "", "reposts": "",
    "follows": "follows / subscribers gained from this video",
    "profile_visits": "", "total_interactions": "as reported by Instagram",
    "comment_texts": "own comments (text only) for the sentiment lexicon",
    # D. traffic
    "clicks": "all clicks", "link_clicks": "clicks to the destination (Meta inline link clicks, TikTok clicks)",
    "landing_page_views": "Meta landing_page_view action",
    "spend": "amount spent",
    # E. conversion
    "conversions": "the optimization event / results (platform-defined)",
    "leads": "", "purchases": "orders", "revenue": "attributed revenue (purchase value)",
    "daily": "[{date, impressions, reach, frequency, clicks, link_clicks, spend}] for fatigue",
    "view_definition": "what 'views' means for this record's platform",
    "notes": "list of caveats added by the source (missing metrics, deprecations)",
}

NUMERIC = [k for k in FIELDS if k not in {
    "key", "source", "platform", "kind", "id", "title", "url", "thumbnail", "creative_id", "campaign",
    "published", "date_start", "date_stop", "retention", "comment_texts", "daily", "view_definition", "notes"}]

VIEW_DEFINITIONS = {
    "instagram": "Instagram 'views': every time the reel starts playing, replays included (no minimum time).",
    "youtube": "YouTube 'views': for Shorts, since 31 Mar 2025 every start or replay counts; engagedViews keeps the "
               "older stricter count. For long-form, a view is counted after a few seconds of real watching.",
    "facebook": "Meta: 3-second video plays (the 'video_view' action); ThruPlay = completed or ≥15 s; "
                "video_play_actions = starts (no minimum).",
    "tiktok": "TikTok ads: video views = starts (replays excluded); 2-s and 6-s views are within one impression "
              "session; average play time includes replays.",
}


def blank(source, kind, id_, **kw):
    r = {k: None for k in FIELDS}
    r.update(source=source, kind=kind, id=str(id_), key=f"{source}:{id_}", notes=[], retention=None,
             comment_texts=None, daily=None)
    r.update({k: v for k, v in kw.items() if k in FIELDS})
    if not r.get("view_definition") and r.get("platform") in VIEW_DEFINITIONS:
        r["view_definition"] = VIEW_DEFINITIONS[r["platform"]]
    return r
