# Profiles

Each business has one YAML file in `profiles/`. Business profiles are **git-ignored**: only `_template.yaml` and `example-*.yaml` are committed, so your keywords, watch lists and business description stay on your machine.

Start from `profiles/_template.yaml`. `${ENV_VAR}` is expanded, which is handy for `${OBSIDIAN_VAULT}`.

## Fields

| Field | What | Tips |
|---|---|---|
| `name` | profile id | file name without `.yaml` |
| `business` | who the ideas are for: audience, offer, who films, language, tone, liked formats, hard rules | the skill adapts every idea to this, so be specific |
| `taste_note` | path to a likes/dislikes note | optional; the skill respects it |
| `output_dir` | where reports go | default `reports/<name>/` |
| `swipe_dir` | where saved posts go | default `<output_dir>/swipe` |
| `discover.youtube.keywords` | search terms | needs `YOUTUBE_API_KEY` for Shorts. Mix **formats** ("how native speakers say") with **customer situations** ("english at the doctor") |
| `discover.youtube.languages` | keyword → ISO code | e.g. `английский идиомы: ru`, so the API favours that language |
| `discover.youtube.region` | ISO country | optional |
| `discover.youtube.hashtags` | hashtag feeds | free; noisy, so `must_match` matters |
| `discover.youtube.window` | hour, today, week, month, year | `month` with per-day ranking works well |
| `discover.youtube.shorts` | under 4 minutes | `true` for short-form |
| `discover.tiktok.*` | hashtags and keywords | needs `APIFY_TOKEN` |
| `watch.youtube` | `@handle`, channel URL or `UC…` id | creators you want to follow |
| `watch.instagram` | usernames | needs the Graph API, professional accounts only |
| `watch.tiktok` | usernames | needs Apify |
| `seeds` | post URLs to track | the posts people send you, and your own posts |
| `filters.min_views` | ignore smaller posts | 5,000 is a good start |
| `filters.max_age_days` | ignore older discoveries | 30–60 |
| `filters.must_match` | regex the title (hashtags removed) + channel must match | your topic words, in every language |
| `filters.exclude` | regex on title + channel | competitors' niches you don't serve, kids' content, news, live streams |
| `enrich_top` | YouTube videos opened per run for full stats | 60–90 |
| `recheck` | re-measure recent posts | `{max_age_days: 30, limit: 60}` |
| `report` | `top` rows per section, `hooks` shown, `transcripts` fetched | `{top: 25, hooks: 20, transcripts: 40}` |
| `alerts` | Telegram thresholds | see below |

### Alerts

```yaml
alerts:
  min_outlier: 20          # ≥20× the creator's usual…
  min_baseline: 5000       # …and the creator normally gets 5K+ (avoids tiny-channel flukes)
  min_rise_per_day: 100000 # or growing 100K+/day between runs
  min_per_day: ""          # optional
  max: 3                   # per run
  # env_file / token_env / chat_env: reuse another app's bot (see setup.md)
```

Start strict and loosen it later. Each post alerts only once.

## Tuning loop

1. **Run it:** `python -m viral_scout run <name>`.
2. **Open "Fastest new posts".** For each off-topic hit, ask why it got in:
   - Title off-topic but channel name matches (e.g. "… English" news channels) → add the channel's words to `exclude`.
   - Matched only through a hashtag → that's already ignored; check that `must_match` isn't too broad (`word` alone matches a lot).
   - Wrong audience (exams, kids) → add to `exclude`.
3. **Too few results:**
   - Add keywords and the API key.
   - Add the hashtags listed under **Suggested hashtags**.
   - Widen `window`, or lower `min_views`.
4. **Dismiss** the leftovers: `python -m viral_scout dismiss <name> <ID> ...`.

## Example

`profiles/example-language-school.yaml` is a working profile for an online English school. Copy it as a starting point.
