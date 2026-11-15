# Publishing and unattended jobs

The last part of the studio: scout → ideas → script → video → **publish → measure**, plus the jobs that run it while nobody watches.

- **Publish** plans the week, sends the owner a morning post pack, and posts one approved video through official APIs. Only where the profile opts in.
- **Jobs** run Claude Code headless on a schedule: ideas, script, notes, film, blog. One job at a time, narrow permissions, a log per job.
- **Notes** carry the owner's replies (Telegram) back to the notes job, which makes new versions.
- **Scheduling** is one script the owner runs once. Claude never registers tasks.

## Safety rules

1. Nothing is posted unattended. No job is allowed `publish … post`, whatever the profile adds to its tools.
2. `publish post` sends only to platforms with `auto_post: true`. The default is false everywhere, so the default is a queue for posting by hand.
3. TikTok and every platform without an official publishing API are always posted by hand. TikTok's API keeps posts private until TikTok audits the app. Browser-automation posters are never used: they break the platforms' terms.
4. Jobs never spend money, contact leads, change a live website or delete data. A note that asks for that is answered "needs a live session".
5. Delivering drafts to the owner (Telegram, the vault) is fine. Posting is the owner's decision.
6. Tokens live in the env file named by the profile. They never go in the profile, a prompt or a log.

## Profile blocks

The shared `studio:` block (brand, vault folder, instructions note, compliance note, CTA) is read by every studio command. See `profiles/_template.yaml` for all keys with comments.

### `publish:`

| Key | Default | What |
|---|---|---|
| `platforms` | tiktok, instagram, youtube, facebook | where each video goes |
| `handles` | `{}` | account per platform, shown in the plan |
| `timezone` | America/Springfield | for slots and `--at` |
| `slots` | 18:00 / 18:30 / 18:30 / 19:30 | local posting time per platform |
| `utm` | medium social, campaign `{slug}` | `sources` renames utm_source per platform (e.g. `instagram_story`) |
| `auto_post` | all false | per platform; only instagram, facebook, youtube can be true |
| `env_file` | none | file with the tokens |
| `tokens` | standard names | map a standard name to yours, e.g. `youtube: {YOUTUBE_REFRESH_TOKEN: MYBIZ_YT}` |
| `youtube` | category 27, en, public | upload settings |
| `queue` | `<vault_dir>/05 Marketing/Video Studio/ready-to-post.md` | the ready-to-post table |
| `morning_pack` | off, 9:00, delivery none | `enabled`, `hour`, `delivery: telegram\|none`, `env_file`, `token_env`, `chat_env` |

Standard token names: `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`, `FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_TOKEN`, `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.

### `jobs:`

| Key | Default | What |
|---|---|---|
| `ideas` | off, 08:00 daily, `count: 5` | runs the `/studio-ideas` skill |
| `script` | off, 08:30 daily | one script for the best approved idea, sent for ✅ |
| `notes` | off, every 15 min | starts Claude only when a note waits |
| `film` | off, 06:00 daily, hourly until 22:00, `max_tries: 2`, `buffer: 4` | one finished film a day |
| `blog` | off, Monday 08:45 | one blog draft a week, sent for ✅ |
| `owner`, `language` | "the owner", English | how prompts name and talk to the approver |
| `delivery` | none | `telegram` (through the ideas API / service) or `none` |
| `api` | `IDEAS_SITE_URL`, `IDEAS_API_SECRET`, project = profile name | env var names for the notes/ideas API; falls back to an `ideas:` block |
| `notes_command` | none | use a notes CLI with the same verbs instead of the API |
| `cwd`, `add_dirs` | this repo, none | where Claude runs and which folders it may touch (the vault is always added) |
| `allowed_tools` | none | extras per job (`film: ["Bash(npx hyperframes:*)"]`) or for `all` |
| `instructions` | none | extra lines per job, on top of the instructions note |
| `permission_mode`, `lock_hours`, `time_limit_hours` | acceptEdits, 3, 3 | |

Each job also takes `enabled`, `at`, `days` (daily, a weekday, or a list), `retry_until`, `max_tries`. Write `enabled:`, not `on:`: YAML reads a bare `on` as true.

## Commands

```
python -m viral_scout publish <profile> plan [--days 7] [--json]       queued films → slot, UTM link, auto or manual per platform
python -m viral_scout publish <profile> today [--dry-run] [--force]    morning post pack (video, still, POST.md blocks)
python -m viral_scout publish <profile> post <video.mp4> --caption <c.md> [--only youtube] [--at "2026-11-16 18:30"] [--dry-run]

python -m viral_scout jobs <profile> list                              jobs on/off, today's marker and tries, the lock
python -m viral_scout jobs <profile> prompt film                       the assembled prompt and tools (runs nothing)
python -m viral_scout jobs <profile> run film [--dry-run] [--force]    one run (Task Scheduler does this)
python -m viral_scout jobs <profile> install-plan [--json]             the tasks, and the command to register them

python -m viral_scout notes <profile> [list | all | pending]
python -m viral_scout notes <profile> done|skip|reply <id> "text"
python -m viral_scout notes <profile> send <file> "caption" [--reply <id>]
```

The caption file for `post`: optional `ai: true` and `title:` lines at the top, then the default caption, then optional `## Instagram`, `## Facebook`, `## YouTube`, `## TikTok` sections that replace it for one platform. With `ai: true`, YouTube gets its synthetic-media flag; Instagram has no API flag, so the caption must say it.

The API publisher is `viral_scout/publish/node/publish.mjs` (plain `fetch`, no dependencies, Node 22+). Run `node --test viral_scout/publish/node/test.mjs` for its tests. YouTube needs a refresh token once: `node viral_scout/publish/node/youtube-auth.mjs` with `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET` set. While the Google consent screen is in Testing, the token expires after 7 days. Videos from an unaudited API project stay private.

## How a job runs

1. Off, or already done this day (week for blog)? Exit.
2. The lock `data/jobs/claude.lock` is held by a live job? Exit. One Claude job runs on the PC at a time, for all profiles. A lock older than 3 h is stale and taken over.
3. Notes only: nothing waiting? Exit without starting Claude.
4. Tries used up (2 a day)? Exit until tomorrow.
5. `claude -p` with the prompt on stdin, `--permission-mode acceptEdits`, the job's `--allowedTools`, `--add-dir <vault>`. Output goes to `data/logs/studio/<profile>-<job>-<date>.log`.
6. Exit 0 → `data/jobs/<profile>/<job>-<date>.done`. The film job is the exception: Claude writes the marker itself as the last step, only when a film was delivered. A run that broke halfway is retried next hour.

The prompt is the header (unattended rules, paths, CTA, compliance note), the core prompt `viral_scout/jobs/prompts/<job>.md` (generic), the profile's `studio.instructions` note and `jobs.instructions.<job>`, and the footer (the "never" list). Business specifics belong in the instructions note: the reference film, voice, sources, what never to show, which repo to commit to.

## Notes API

`notes` talks to the ideas API / service with `Authorization: Bearer <secret>` and `?project=<project>`:

| Call | Answer |
|---|---|
| `GET /api/notes?status=new` (or `status=all&limit=20`) | `{notes: [{id, created_at, from, kind, status, text, about, file_url, result}]}` |
| `GET /api/notes?pending=1` | `{pending: n}` (new notes plus approved items waiting for the job) |
| `PATCH /api/notes {id, project, status: done\|skipped\|open, result, reply}` | closes or answers a note in its thread |
| `POST /api/notes` multipart `file`, `caption`, `project`, `reply_to` | `{message_id}` |

Until the service has these endpoints, set `jobs.notes_command` to a CLI with the same verbs (solar: `node D:/repo/solar-site/site/scripts/notes.mjs`).

## Install the schedule

Claude may not register scheduled tasks. The owner runs it once:

```
python -m viral_scout jobs myhomes install-plan
pwsh -NoProfile -ExecutionPolicy Bypass -File "D:/repo/viral-scout/scripts/schedule-studio.ps1" -Profile myhomes [-Paused]
```

Tasks are named `viral-scout <profile>.<job>` and run `scripts/studio.ps1`. Built in: the full pwsh.exe path, hidden window, runs on battery, StartWhenAvailable, wake to run, a 3 h limit, IgnoreNew, and an hourly repeat for daily jobs (daily triggers miss days when the PC sleeps). The PC must be on or asleep with wake timers allowed. Remove them with `-Remove`.

The dashboard's Schedule page lists them under "Studio jobs": pause, resume, run now, stop, remove, last log. Times are changed in the profile, then the install script is run again.

### The idea generator from the dashboard

The `ideas` job has its own section on the Schedule page, **Idea generator**, with one card per profile that has an `ideas:` block. There, without editing YAML or running the install script:
- **Set up (paused)** writes `jobs.ideas` into the profile (`enabled: true`, `at`, `days`, `count`) and registers `viral-scout <profile>.ideas`, paused. Until it's set up, the card suggests the time and count of the older daily run (`ideas.daily.at` / `count`).
- **Days** (every day, or any weekdays), **time** and **ideas per run**: **Save** edits the profile (comments kept, a backup in `data/profile-backups/`) and re-registers the task. A paused task stays paused, an on one stays on.
- **Turn on / Pause**, **Run now** (asks first: it starts the Claude CLI), **Stop**, **last log**.
- **Remove** sets `jobs.ideas.enabled: false` and removes the task; the other settings stay in the profile.

The job gets the same extra folders as the older daily run: when `jobs.add_dirs` is empty, `ideas.daily.add_dirs` is used.

The same from the CLI:
```
python -m viral_scout jobs --overview                                       # profiles with ideas: and their jobs.ideas
python -m viral_scout jobs myhomes schedule ideas --enabled 1 --at 08:15 --days Monday,Thursday --count 5
pwsh -NoProfile -File scripts/tasks.ps1 studio-sync -Profile myhomes        # register/update/remove the profile's studio tasks
```

The section **Older idea and content tasks** lists tasks the business sites registered before the move (any task that runs an `ideas-daily.ps1` or a site's `scripts/jobs/run.ps1`): pause, turn on, run now, stop or remove, not reschedule. Once a business's idea generator is set up here, pause or remove its older task so ideas aren't made twice.

## Moving solar's jobs here (steps)

1. Write `profiles/mysolar.yaml` blocks: `studio:` (vault `projects/mysolar`, CTA solar.example.com/checklist), `publish:` (the four slots, handles, `env_file: D:/repo/solar-site/site/.env.local`, `morning_pack` with `delivery: telegram`, `token_env: TELEGRAM_IDEAS_BOT_TOKEN`), `jobs:` (owner Alex, language Ukrainian, `cwd: D:/repo/solar-site`, `notes_command` as above, `api.project: solar`).
2. Move the solar-only parts of `site/scripts/jobs/{film,script,notes,blog}.md` into the vault note `05 Marketing/studio-instructions.md`: the reference film `tools/video/films/nov17-grid-truth/`, the voice command and `refB.wav`, the official sources, the never-show list, the blog's one allowed website change, commit and push rules.
3. Add the film tools to `jobs.allowed_tools.film` (npx hyperframes, ffmpeg, the voice venv, git add/commit/push in that repo).
4. Compare `jobs mysolar prompt film` with the old `film.md`. Then do one watched run: `jobs mysolar run film --force`.
5. The owner removes the old tasks (`site/scripts/jobs/schedule.ps1 -Remove`) and runs `schedule-studio.ps1 -Profile mysolar`.
6. Keep `post-today.mjs` until a `publish mysolar today --dry-run` matches its `--dry` output for a queued day.

## What was moved from solar, and what was not

- Moved and made generic: `tools/publish` (now `viral_scout/publish/node`), `post-today.mjs` (`publish today`), `notes.mjs` (`notes`, through the API), `jobs/run.ps1` (`jobs run`), `jobs/schedule.ps1` (`schedule-studio.ps1`), the job prompts (core prompts plus the instructions note), `ideas-daily.ps1` of solar and homes (the `ideas` job).
- Not moved: `tools/ad-spy` is replaced by `python -m viral_scout ads` (official Meta and TikTok APIs plus Apify, scored, weekly). `tools/carousel`, `tools/postcards` and `tools/social` render solar's own brand templates (fonts, art, the founder photo), so they stay in solar. A generic carousel or card renderer belongs in `video … cards`.
