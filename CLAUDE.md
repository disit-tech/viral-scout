# viral-scout

Python tool that finds viral posts on a topic per business profile. See README.md.

- Run: `PYTHONIOENCODING=utf-8 python -m viral_scout run <profile>`. Test runs: set `OBSIDIAN_VAULT` to a scratch folder so the report doesn't land in the real vault, and delete `data/<profile>.sqlite` afterwards (it holds the snapshot history).
- yt-dlp comes from `$VIRAL_SCOUT_YTDLP` (the `D:\repo\yt-dlp` clone, set in `.env`).
- New platform = a module in `viral_scout/sources/` returning `Item`s; wire it into `run.scout`. Keep optional sources optional: no key → add a line to `skipped`, never fail the run.
- Legitimate access only: yt-dlp on public pages, official APIs (YouTube Data API, Instagram Graph), or Apify. No private APIs, header spoofing or hidden logins.
- `.env`, `data/`, `reports/` are git-ignored. Keys never go in profiles.
