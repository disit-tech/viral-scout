# Dashboard

A Next.js app in `web/` that shows every business profile: outliers, fastest posts, rising posts and tracked links as cards (thumbnail, labels, metrics, growth sparkline, hook, transcript), plus the AI ideas notes, a swipe-file board and source health.

It runs in two modes:

| | Local (your PC) | Published (Vercel, free Hobby plan) |
|---|---|---|
| Start | `cd web && npm install && npm run dev` → http://localhost:3210 | `scripts/publish.ps1` |
| Data | `web/data/*.json`, refreshed after every run | a snapshot uploaded with each deploy |
| Save / Track / Dismiss / swipe status | run the Python CLI and update the vault | read-only; the buttons copy the CLI command |
| Login | none (unless `SITE_PASSWORD` is set) | password (`SITE_PASSWORD`); locked if it's missing |

Nothing runs in the cloud. Collection stays on your PC (home IP, yt-dlp, the scheduled task). Vercel only hosts the pages.

## Data flow

```
python -m viral_scout run <profile>      → data/<profile>-latest.json + SQLite
   └─ export (automatic after each run)  → web/data/<profile>.json, web/data/index.json
python -m viral_scout export [profiles]  → the same, by hand
scripts/publish.ps1                      → export + vercel deploy --prod (uploads web/ incl. data/)
```

`web/data/` is git-ignored, so the public repo never contains business data. The deploy uploads it straight from your PC: `web/.vercelignore` deliberately doesn't exclude it.

## Publish to Vercel

One-time setup:
```powershell
npx vercel login                       # once per PC
scripts/publish.ps1 -SetPassword       # links project "viral-scout", asks for a password, deploys
```

Afterwards:
```powershell
scripts/publish.ps1                    # export + production deploy
scripts/publish.ps1 -Preview           # preview URL instead
```

To publish automatically after the daily run, add a line to your scheduled task after `run-daily.ps1`:
`pwsh -File scripts/publish.ps1`.

**Free plan notes:**
- Vercel Hobby is meant for personal, non-commercial use. If the dashboard becomes a client deliverable, move it to Pro.
- Vercel's own "Password Protection" is a paid feature, so this app has its own login: an HMAC-signed cookie, valid 30 days. It runs in `src/proxy.ts`, Next 16's replacement for middleware.
- Every page is pre-rendered at build time. The only server code that runs is the login check, which fits comfortably in the free limits.

## Pages

- `/`: one card per business, with posts, outliers, 🔥 mega, saved, and the top thumbnails.
- `/p/<profile>` has these tabs:
  - **Outliers**, **Fastest**, **Rising now**, **Tracked**: card grids with search, a platform filter and "hide saved".
  - **Ideas**: the `<date>-viral-ideas.md` notes written by the `/viral-scout` skill, rendered as HTML.
  - **Swipe file**: a board with idea → scripted → filmed → posted → skip columns. Changing a card's status locally edits the note's `status:` in the vault.
  - **Sources**: skipped sources, suggested hashtags, creators who keep showing up, errors and recent runs.

## Security

- Local actions only accept requests whose host is `localhost` or `127.0.0.1`. The Python CLI is called with fixed arguments, never through a shell.
- On Vercel (`VERCEL` is set) actions are switched off, and the API answers 403.
- Pages send `X-Robots-Tag: noindex` and set `robots: noindex`.
