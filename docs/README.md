# viral-scout docs

New here? Read them in this order: **Setup and keys → Profiles → Marketing workflow**, then the feature you need.

## Get started

| Doc | For |
|---|---|
| [Setup and keys](setup.md) | Install, the Obsidian vault, every key (YouTube, Instagram, Apify, ads, Telegram…), scheduling, the MCP server |
| [Profiles](profiles.md) | Writing a profile for a new business: fields, optional blocks (ads, search demand, performance, alerts), tuning filters |
| [Marketing workflow](marketing-workflow.md) | Using it every week: from "what's viral" on Monday to a filmed video |

## Features

| Doc | For |
|---|---|
| [Dashboard](dashboard.md) | The web UI: every page, local with actions, or published read-only on Vercel |
| [Ads scout](ads-scout.md) | The paid side: long-running competitor ads, offers and hooks (Meta, TikTok, Google), coverage per region, scoring, costs |
| [Search demand](search-demand.md) | Google Trends for the business's area: when each service rises and peaks, and which words people use |
| [Your performance](performance.md) | Your own videos and ads: hook rate, retention, CTR, CPA, ROAS from official APIs or your exports; diagnostics |

## Making better videos

| Doc | For |
|---|---|
| [Video quality framework](video-quality-framework.md) | The 5 tests, 20 criteria and the 100-point scorecard, structure, production standards, testing |
| [Originality and duplicate detection](originality-and-duplicate-detection.md) | How Instagram, TikTok and YouTube detect reposts and copies, and how to stay original |

## Content studio

Optional: the same profile drives ideas, ratings, scripts, videos, publishing and the daily jobs. Other repos only trigger it.

| Doc | For |
|---|---|
| [Content studio](studio.md) | Overview: scout → ideas → ratings → script → video → publish → measure, core vs per-profile instructions, what runs where, adding a business |
| [Ideas](ideas.md) | The `/studio-ideas` skill, the `ideas:` profile block, `python -m viral_scout ideas` commands, daily run, migration |
| [Video generation](video.md) | Recording + script → captioned 1080×1920 master, brand cards, voice clone, HyperFrames films, stills; the `video:` block and `/studio-video` |
| [Telegram ideas service](telegram-service.md) | The always-on bot for idea buttons, reasons, comments and content packs (`service/`, Vercel); config and cutover |
| [Publishing and jobs](publish-and-jobs.md) | Posting plan, morning post pack, opt-in API posting, the unattended Claude jobs and their schedule |

## Under the hood

| Doc | For |
|---|---|
| [How it works](how-it-works.md) | Pipeline, sources, scoring formulas, data model, code map, limits |
| [Similar tools](similar-tools.md) | How other viral/outlier tools work and what viral-scout took from them |
| [References](references.md) | Every competitor, API, library, policy and fact source, with links |
