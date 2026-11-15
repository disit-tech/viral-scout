# viral-scout

Python tool that finds viral posts on a topic per business profile. See README.md.

- Run: `PYTHONIOENCODING=utf-8 python -m viral_scout run <profile>`. Test runs: set `OBSIDIAN_VAULT` to a scratch folder so the report doesn't land in the real vault, and delete `data/<profile>.sqlite` afterwards (it holds the snapshot history).
- yt-dlp comes from `$VIRAL_SCOUT_YTDLP` (the `D:\repo\yt-dlp` clone, set in `.env`).
- New platform = a module in `viral_scout/sources/` returning `Item`s; wire it into `run.scout`. Keep optional sources optional: no key → add a line to `skipped`, never fail the run.
- Legitimate access only: yt-dlp on public pages, official APIs (YouTube Data API, Instagram Graph), or Apify. No private APIs, header spoofing or hidden logins.
- `.env`, `data/`, `reports/` are git-ignored. Keys never go in profiles.

## Deployments (Vercel): read before any deploy, link or delete

Exactly two Vercel projects belong to this repo. Both are in the Vercel team **`disit`** and both build from GitHub on every push to `main`:

| Project | Root Directory | What it is | Rule |
|---|---|---|---|
| `viral-scout-demo` | `web` | the dashboard with **sample data**, public (`VIRAL_SCOUT_PUBLIC_DEMO=1`), https://viral-scout-demo.vercel.app | the only online dashboard |
| `studio-ideas-service` | `service` | the **live Telegram bot backend** for every business (ideas, buttons, notes, films), https://studio-ideas-service.vercel.app | never delete or rename it; real projects come from the `STUDIO_CONFIG_JSON` env var |

- The two projects are not duplicates: same repo, different folders. Deleting `studio-ideas-service` stops every business's bot.
- **No private dashboard online** (owner's decision, 2026-11-15): don't run `scripts/publish.ps1`, don't turn on the `viral-scout publish` task, don't create a `viral-scout` project. The owner's real data stays on the local dashboard (`cd web && npm run dev`).
- Don't create Vercel projects. `vercel link` creates one when the name doesn't exist and connects it to GitHub on its own; check `vercel project ls` first, and never link `web/` or `service/` to a new name.
- Before any Vercel CLI command, run `npx vercel whoami`: it must be the account that owns the `disit` team. The CLI on the owner's PC is sometimes logged in to another account, whose team holds the business sites, not these projects.
- Deploys come from `git push` to `main`. A CLI deploy of the service runs from the repo root (the project's Root Directory is `service`). After changing `STUDIO_CONFIG_JSON`, redeploy the latest production deployment so it takes effect.
- The businesses' own websites are other repos and other Vercel projects; they don't belong here.
