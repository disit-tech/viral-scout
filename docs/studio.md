# Content studio

viral-scout started as the research step. It now covers the whole loop for each business:

```
scout ──► ideas ──► ratings ──► script ──► video ──► publish ──► measure
run/ads/   /studio-   Telegram    /studio-   video     publish    perf, check
demand     ideas      service     video      ...       ...
```

Every step reads the same profile (`profiles/<name>.yaml`). Other repos (a business's website, CRM, or vault project) don't hold the tools. They only trigger them: a ten-line skill that calls `/studio-ideas <profile>`, or a scheduled task that runs `python -m viral_scout jobs <profile> run <job>`.

## Two layers of instructions

| Layer | Where | What | In git |
|---|---|---|---|
| Core | `.claude/skills/studio-*/SKILL.md`, `viral_scout/jobs/prompts/*.md` | The method: how to read feedback, score ideas, write a script, cut, render, check, the content pack format, and the hard rules | yes (public) |
| Profile | `profiles/<name>.yaml`: `studio:`, `ideas:`, `video:`, `publish:`, `jobs:` | Settings: project slug, rubrics and score criteria, brand colors and voice, platforms and slots, which jobs run | no (`profiles/` is git-ignored) |
| Profile, free text | the note in `studio.instructions` (in the vault) | Everything a business does differently: tone, compliance, banned words, the "never show" list, CTA, budgets | vault |

The profile overrides the core defaults. It never overrides the hard rules: no one else's footage or wording, every number has a source, compliance before approval, and no unattended job may post, spend money or contact anyone.

## The parts

| Part | Doc | Commands |
|---|---|---|
| Ideas, ratings, content packs | [ideas.md](ideas.md) | `/studio-ideas`, `python -m viral_scout ideas <p> info \| pull \| push \| pack …` |
| Telegram bot (buttons, reasons, comments, notes) | [telegram-service.md](telegram-service.md) | `service/`, deployed once to Vercel, shared by every profile |
| Video generation | [video.md](video.md) | `/studio-video`, `python -m viral_scout video <p> cut \| make \| render \| voice \| film \| still …` |
| Publishing, unattended jobs, schedule | [publish-and-jobs.md](publish-and-jobs.md) | `python -m viral_scout publish \| jobs \| notes <p> …`, `scripts/schedule-studio.ps1` |

## Where things run

- **The PC** does the heavy work: Claude Code on the subscription writes ideas and scripts, WhisperX and Chatterbox run on the GPU, HyperFrames renders films. Nothing here has to be online.
- **The service** (Vercel) answers Telegram instantly: a tap on 👍 👎 🔁 ✅ updates the message and asks "why?" even when the PC is off. Taps and replies are stored in the database and the PC reads them on its next run.
- **The database** is the existing Turso database (tables `VideoIdea`, `IdeaFeedback`, `BlogReview`, `ClaudeNote`), unchanged. The CRM pages that list ideas keep working.

## Optional installs

Research-only users need none of this. Each part says what is missing and exits with code 3, it never crashes.

| For | Install |
|---|---|
| Video (WhisperX, CUDA) | `scripts/setup-video.ps1` creates `.venv-video` |
| Voice clone (Chatterbox) | `scripts/setup-video.ps1 -Voice` creates `.venv-voice` (separate: it needs other torch and numpy versions) |
| Cards and films | `scripts/setup-video.ps1 -Node` (Playwright, HyperFrames) |
| Telegram service | `cd service && npm ci`, then deploy (see `service/README.md`) |

`python -m viral_scout video doctor` shows what is installed.

## Adding a business

1. A viral-scout profile (`python -m viral_scout new …`), as before.
2. A `studio:` block and the instructions note in the vault. The ideas doc has a template.
3. The blocks for the parts you want: `ideas:` (plus the project in the service config, `STUDIO_CONFIG_JSON` or `service/projects.json`, and its bot), `video:`, `publish:`, `jobs:`.
4. In the business's own repo, a trigger skill (see `docs/examples/trigger-skill.md`), if you want `/ideas` to work there.
5. `python -m viral_scout jobs <p> install-plan` prints the schedule command for the owner to run.

## Moving an existing repo over

Each part's doc has the step list. The order that keeps everything working:

1. Ideas: point the repo's ideas skill at `/studio-ideas` (the HTTP contract is the same as the old `ideas.mjs`, so nothing else changes).
2. Video: render one existing video through `viral_scout video` and compare it with the old output before switching.
3. Telegram: deploy the service, then move one bot at a time (Homeworks, Acme Agency, solar). Each bot can be pointed back to the old webhook.
4. Jobs: replace the repo's runner and scheduled tasks with `schedule-studio.ps1`.
5. Remove the old copies once a week of runs looks right.
