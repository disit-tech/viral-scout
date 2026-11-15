# Ideas

The ideas step of the content studio: scout → **ideas** → ratings → script → video → publish → measure.

Claude writes ideas for a business from everything the vault knows plus viral-scout's market data, pushes them to the ideas API, and the owner rates each one in Telegram (👍 👎 🔁 ✅, reasons, comments). The next run reads the ratings first and learns from them. Approved ideas can get a content pack: ready-to-post texts per platform.

Three parts:

| Part | Where | What |
|---|---|---|
| Skill | `.claude/skills/studio-ideas/SKILL.md` + `packs.md` | the method, the same for every business |
| Instructions note | the vault, `studio.instructions` in the profile | everything specific to one business: audience, rubrics, compliance, voice, phone, platforms |
| CLI | `python -m viral_scout ideas <profile> …` | talks to the ideas API; the project comes from the profile |

The method behind it: `shared/playbooks/05 Marketing/idea-generator-telegram.md` in the vault.

## Profile blocks

Two blocks in `profiles/<name>.yaml`. `${OBSIDIAN_VAULT}` and other `${VARS}` are expanded in every value, nested ones too.

```yaml
studio:                     # shared by every studio step
  brand: "Homeworks"
  vault_dir: ${OBSIDIAN_VAULT}/projects/myhomes      # relative note paths below are taken from here
  instructions: ${OBSIDIAN_VAULT}/projects/myhomes/05 Marketing/studio-instructions.md
  compliance: ${OBSIDIAN_VAULT}/projects/myhomes/07 Jurisdiction/2026-10-22-fall-work-compliance.md
  cta: {text: "Text a photo to (555) 010-0000", link: "https://example.com"}

ideas:
  project: homes
  api: {env_file: "D:/repo/solar-site/site/.env.local", url_env: IDEAS_SITE_URL, secret_env: IDEAS_API_SECRET}
  header: "🔨 Homeworks"
  rubrics: [Short video, Before/after post, Offer, Local outreach, Channel, Newsletter / email, Trust]
  score: {criteria: [Hook, Clarity, Lead potential, Effort, Fit], threshold: 38}
  experiment_share: 0.2
  sources: [README.md, "06 Sales & Partners/offer-menu.md"]
  tracker: 05 Marketing/idea-tracker.md
  # taste_note: defaults to the profile's top-level taste_note
  market_data: {min_share: 0.5, max_age_days: 14}
  packs:
    enabled: true
    platforms: [facebook, fb_groups, instagram, tiktok, youtube, nextdoor, google, linkedin, threads, yelp, email, print]
    limits: {threads: {per_part: 500}, google: {total: 1500}, linkedin: {total: 3000, hashtags: [3, 8]}}
    banned_words:
      - {pattern: '\b(insured|bonded)\b', why: "not true while site.insured is false"}
      - crew
  daily: {count: 5, at: "08:15"}
```

| Key | Default | Meaning |
|---|---|---|
| `studio.brand` | | the business name the texts use |
| `studio.vault_dir` | | the project's vault folder. Relative paths in `ideas.sources` and `ideas.tracker` start here (else at the vault root) |
| `studio.instructions` | | the per-business note. It overrides the skill's defaults, never its hard rules |
| `studio.compliance` | | the compliance note every idea is checked against |
| `studio.cta` | | default call to action: `text` and `link` (UTM links are built on it) |
| `ideas.project` | required | the project slug on the ideas API (`solar`, `homes`, `agency` today). Lowercase letters, digits and `-` only. Every call is scoped to it |
| `ideas.api.env_file` | | a KEY=VALUE file with the credentials (e.g. the solar site's `.env.local`). A real environment variable wins |
| `ideas.api.url_env` | `IDEAS_SITE_URL` | the variable with the API's base URL (unset: `http://localhost:3000`) |
| `ideas.api.secret_env` | `IDEAS_API_SECRET` | the variable with the bearer secret |
| `ideas.header` | | how the bot heads this project's messages (for the report) |
| `ideas.rubrics` | `[]` | the idea types to mix |
| `ideas.score` | Hook, Clarity, Proof, Call-out, Fit; 38 | the self-score criteria (1–10 each) and the threshold. `push` refuses ideas under it |
| `ideas.experiment_share` | `0.2` | the share of each batch that is a labelled experiment |
| `ideas.sources` | `[]` | notes read on every run (season plan, offer menu, playbook, hook bank…) |
| `ideas.tracker` | | where ✅ ideas become rows |
| `ideas.taste_note` | top-level `taste_note` | the taste profile the run reads and updates |
| `ideas.market_data` | `output_dir`; 0.5; 14 | `dir` with viral-scout's reports, the share of the batch that builds on fresh ones, and how old "fresh" can be |
| `ideas.packs.enabled` | `false` | content packs on or off (the API only takes packs for `homes` today) |
| `ideas.packs.platforms` | all 12 API keys | the platform keys ideas may use, and the pack sections |
| `ideas.packs.limits` | `{}` | per platform: `per_part`, `total`, `hashtags: [min, max]`. The key matches a word in the section title |
| `ideas.packs.banned_words` | `[]` | a plain string = a whole word, any case. Or `{pattern, why, level: error / warning, case: true}`. Errors block a pack and are warnings on `push`. An em dash is always a warning |
| `ideas.blog` | `false` | allows the `blog*` commands (the solar site's blog review) |
| `ideas.batch_dir` | `data/ideas/<profile>/` | where the skill writes batch files |
| `ideas.daily` | 5; `08:15`; `[]` | `count` per daily run, `at` for the scheduled task, `add_dirs` for extra `--add-dir` folders |

Credentials never go in the profile.

## Commands

Run from the repo root with `PYTHONIOENCODING=utf-8`.

```
python -m viral_scout ideas <profile> info                                  resolved settings, notes to read, newest market data (no network)
python -m viral_scout ideas <profile> pull                                  every idea of the project, with ratings, tags, comments, feedback (JSON)
python -m viral_scout ideas <profile> push <batch.json> [--dry-run]         store and post a batch to the ideas bot
python -m viral_scout ideas <profile> tracked <id> [<id> ...]               mark ideas as added to the tracker
python -m viral_scout ideas <profile> repost <id> [<id> ...]                post again through the project's current bot
python -m viral_scout ideas <profile> script <id> <file.md>                 send a scenario for approval
python -m viral_scout ideas <profile> stage <id> <stage> [--draft <path>]   making | draft | posted (and the API's other stages)
python -m viral_scout ideas <profile> pack <id> <note.md> [--dry-run] [--store-only]
python -m viral_scout ideas <profile> blog <slug> "<title>" <summary.txt> | blog-list | blog-published <id>
```

What the CLI checks before it sends anything:
- **push:** the API's field limits (title 200, hook 300, why 300, cta 200, source 400, rubric 80, hookType 40, angle / fact / visual 600; 1–20 ideas; batch name ≤ 60), `score` against the threshold, `platforms` against `packs.platforms`, `replaces` / `variantOf`. `--dry-run` only checks.
- **pack:** parses the note (every `## Platform` is one message, every `### Label` a block, `>` lines are owner notes, Checks / Notes sections are skipped), then the profile's limits, the API's limits (15 sections, 10 blocks, 3,500 chars per block, one Telegram message per section) and the banned words. `--dry-run` prints the messages and sends nothing.
- **tracked / repost / script / stage:** the API body has no project, so the CLI first pulls the project's ideas and refuses ids that aren't in it.

Project safety: there is no `--project` flag and `IDEAS_PROJECT` is ignored. A batch file that names another project is refused.

The requests are the same as `solar-site/site/scripts/ideas.mjs` sends (paths, methods, headers, JSON bodies), so the CLI works against today's solar site and any service that keeps the `/api/ideas` contract. A live `pull` for `homes` returned the same JSON as `ideas.mjs` on 2026-11-15.

MCP: `ideas_pull(profile)` is the read-only version of `pull`. Writes stay in the CLI.

## Daily run

`scripts/ideas-daily.ps1 -Profile <name> [-Count N] [-Topic "…"] [-PostsOnly]` checks that the API answers, then runs `/studio-ideas` headless with a narrow allowlist: Read, Glob, Grep, Edit, Write, WebSearch, WebFetch and only `python -m viral_scout ideas <name> …` in the shell, with `--add-dir $env:OBSIDIAN_VAULT` (plus `ideas.daily.add_dirs`). `-PostsOnly` exits without starting Claude when no idea is ✅ or waiting for a pack. Logs: `data/logs/ideas-<name>-<date>.log`.

Schedule it (Claude's auto mode blocks registering tasks, so the owner runs this):
```powershell
$a = New-ScheduledTaskAction -Execute "<full path to pwsh.exe>" -Argument '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "D:\repo\viral-scout\scripts\ideas-daily.ps1" -Profile myhomes'
$t = New-ScheduledTaskTrigger -Daily -At 08:15
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask "Homeworks Ideas" -Action $a -Trigger $t -Settings $s
```

## Trigger from another repo

A project repo keeps a thin skill that calls this one: see [examples/trigger-skill.md](examples/trigger-skill.md). For `/studio-ideas` to work outside this repo, junction the skill folder into `~/.claude/skills/` like `/viral-scout`:
```powershell
New-Item -ItemType Junction -Path "$HOME\.claude\skills\studio-ideas" -Target "D:\repo\viral-scout\.claude\skills\studio-ideas"
```
The CLI runs from `D:\repo\viral-scout` (`cd` there once in the session).

## Migration (per repo, not done yet)

The drafts are in [examples/](examples/): one instructions note per business, with the profile blocks at the top.

**Homeworks (homes)**
1. Add the `studio:` and `ideas:` blocks from the draft instructions note in the vault (`projects/myhomes/05 Marketing/studio-instructions.md`; it opens with the blocks) to `profiles/myhomes.yaml`.
2. Put the rest of that file in the vault at `projects/myhomes/05 Marketing/studio-instructions.md`.
3. `python -m viral_scout ideas myhomes info`, then `pull`: it should list the same ideas as `node …/ideas.mjs --project homes pull`.
4. Replace `homes/.claude/skills/ideas/SKILL.md` with the trigger (`examples/trigger-skill.md`) and delete `posts.md` there.
5. Point the "Homeworks Ideas" task at `viral-scout/scripts/ideas-daily.ps1 -Profile myhomes`, retire `homes/scripts/ideas-daily.ps1`.

**Solar (mysolar)**
1. Profile blocks and the instructions note from the vault draft `projects/mysolar/05 Marketing/Video Studio/studio-instructions.md` (check the brand name, header and CTA link).
2. The new runner doesn't start the local dev server or the Telegram poller and doesn't run the storm cron, as `site/scripts/ideas-daily.ps1` does. Keep `IDEAS_SITE_URL` on the live site (the cron runs there), or keep the old runner until the ideas service replaces the site.
3. `solar-site/.claude/skills/video-ideas/SKILL.md` → a trigger calling `/studio-ideas mysolar`.
4. `site/scripts/ideas.mjs` can stay for the site's own npm scripts; the skill no longer needs it.

**Acme Agency**
The old skill lives in the vault: `projects/agency/.claude/skills/agency-ideas/SKILL.md`, runner `projects/agency/.claude/scripts/ideas-daily.ps1`.
1. Create `profiles/agency.yaml` (Acme Agency has no viral-scout profile yet) with the blocks from the vault draft `projects/agency/ideas/studio-instructions.md`.
2. The instructions note goes to `projects/agency/ideas/studio-instructions.md`.
3. The vault skill becomes a trigger calling `/studio-ideas agency`; the "Acme Agency Ideas" task runs `ideas-daily.ps1 -Profile agency` (`daily.add_dirs` keeps the BeHuman folder).

What stayed per business (now in the instructions notes): rubrics and tracks (Acme Agency's 3 growth + 2 content), score criteria, the storm-first idea (solar only), platforms and packs (Homeworks only), the BeHuman pass (Acme Agency content only), compliance rules, language and voice, tracker table and where ✅ rows go, batch name prefix, budget per idea, and the reason-tag reading notes.
