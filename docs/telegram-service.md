# Telegram ideas service

The ideas bot as a small always-on service, in [`service/`](../service/README.md). It answers Telegram buttons at once, so rating an idea never waits for the PC.

## Who does what

| Part | Runs on | Does |
|---|---|---|
| Generation | your PC (Claude Code, daily task) | reads the vault and viral-scout reports, writes ideas, scenarios, content packs, blog drafts |
| Rendering | your PC | films and edits videos, writes files |
| Ideas CLI | your PC (`site/scripts/ideas.mjs`) | pushes ideas and packs to `/api/ideas`, pulls ratings back |
| **Service** | Vercel | stores ideas, posts them, handles every button and reply, keeps the feedback log |
| CRM pages | homes.example.com/admin/ideas, solar.example.com/admin/ideas | read and rate the same rows |

```
PC: Claude writes ideas ──► /api/ideas ──► Turso DB (VideoIdea, IdeaFeedback, BlogReview, ClaudeNote)
                                 │                     ▲            ▲
                                 ▼                     │            │
                        Telegram group ◄── bots ── service    CRM /admin/ideas
                           │ 👍 👎 🔁 ✅ replies       ▲
                           └── webhook /api/telegram/<bot>
                               or forward /api/forward?bot=<bot> (a CRM bot whose webhook is its own site)
```

The PC only needs to be on for generation and rendering. Ratings, reasons, comments, undo, 📝 requests and approvals land in the database right away, and the next PC run reads them.

## Database

The service uses the solar site's Turso database as it is. Its Prisma schema copies five models with the same names and columns: `VideoIdea`, `IdeaFeedback`, `BlogReview`, `ClaudeNote` (replies for Claude: read by `site/scripts/notes.mjs` today, and through the service's `/api/notes` by `python -m viral_scout notes`; contract in [publish-and-jobs.md](publish-and-jobs.md)) and `StormAlert` (read only). It never migrates. The solar site's schema stays the source of truth.

**What the CRM pages need: nothing.** They read the same rows. The Homeworks page talks to `/api/ideas` with its own limited key, and the service accepts that key the same way the solar site does.

## Routes

| Route | Auth | For |
|---|---|---|
| `GET POST PATCH /api/ideas` | `Bearer IDEAS_API_SECRET`, or a project's CRM key | the ideas CLI and the CRM pages. Same bodies and answers as the solar site |
| `GET POST PATCH /api/blog-review` | `Bearer IDEAS_API_SECRET` | the weekly blog job |
| `POST /api/telegram/<bot>` | `x-telegram-bot-api-secret-token` = the bot's `webhookSecretEnv` | a bot whose webhook is this service |
| `POST /api/forward?bot=<bot>` | the bot's `forwardSecretEnv`, as `x-telegram-bot-api-secret-token` or `x-studio-signature: sha256=<HMAC of the body>` | a bot whose webhook is another site |
| `GET /api/health` | none | which bots have a token and secret (true/false only); `?db=1` pings the DB |

Webhook and forward routes answer 200 once the request is authorised, even if handling fails. Telegram retries anything else, and a retried tap would toggle a reason twice.

## Config reference

`STUDIO_CONFIG_JSON` (env var, use it on Vercel), else `service/projects.json` (git-ignored: your real projects), else `service/projects.example.json` (placeholders, committed). Secrets never go in it: every `*Env` field names an env var. The service checks the file at start and refuses broken references.

| Key | Meaning |
|---|---|
| `defaultProject` | project used when `/api/ideas` gets no `project` (solar) |
| `defaultBot` | bot for projects whose own bot has no token yet, and for plain notifications |
| `chatsEnv` | env var with the allowed chat ids, comma-separated |
| `scriptsBot` | bot that sends scenarios with ✅ / ✏️ |
| `blog.bot`, `blog.publicUrl` | bot for blog reviews; link shown after publishing (`publicUrl` + slug) |
| `bots.<slug>.tokenEnv` | env var with the bot token |
| `bots.<slug>.webhookSecretEnv` | env var with the `secret_token` set on its webhook. Leave out when the webhook lives elsewhere |
| `bots.<slug>.forwardSecretEnv` | env var with the secret a CRM site forwards this bot's updates with |
| `bots.<slug>.chatsEnv` | optional, overrides the top-level `chatsEnv` |
| `bots.<slug>.notes` | `off` (CRM bot), `replies` (replies to the bot become notes for Claude), `replies+call` (also plain "Claude, ..." messages; one bot only) |
| `projects.<slug>.bot` | the bot that posts this project's ideas |
| `projects.<slug>.label` | header in front of each idea, e.g. `🔨 Homeworks · ` |
| `projects.<slug>.reasonSet` | which entry of `reasonSets` gives the "why?" chips |
| `projects.<slug>.packs` | approved ideas get a content pack (📝 Пости) |
| `projects.<slug>.platforms` | optional subset of `platforms` |
| `projects.<slug>.crmSecretEnv` | env var with a limited key for the project's CRM page: read its ideas, rate, comment, 📝, 🗑, platforms |
| `platforms` | key → label of where an idea can be posted |
| `reasons` | code → label of every reason chip. Codes are stored in `VideoIdea.tags`, so never reuse a code for a new meaning |
| `reasonSets.<name>.<status>` | the codes offered after that rating (`good`, `approved`, `bad`, `redo`, `expand`, `variants`) |

**Adding a project:** add a bot (or reuse one), add the project with its label and reason set, set the env vars, deploy, then set the webhook. Bot slugs end up in `ClaudeNote.bot`, which `notes.mjs` uses to pick the token: keep existing slugs (`ideas`, `agency`) as they are.

**A different reason set:** add the codes to `reasons`, add a set under `reasonSets`, point the project at it. The example ships one set (`video`) for all three projects, because that is what the solar site does today.

## Cutover plan

One bot at a time, in this order. Each step has its own rollback. Commands are in [service/README.md](../service/README.md).

1. **Deploy** the service with every env var. Check `/api/health?db=1`. Nothing reaches it yet.
2. **myhomes.** On the Homeworks site set `IDEAS_FORWARD_URL=https://<service>/api/forward?bot=homes` and redeploy. Its webhook stays where it is. Tap a few buttons on a Homeworks idea and check the CRM page. Rollback: set it back to `https://solar.example.com/api/telegram/ideas-homes`.
3. **Acme Agency.** `setWebhook` for the Acme Agency bot to `https://<service>/api/telegram/agency` with `secret_token`. Rate an idea, reply to one, check a note lands for Claude. Rollback: `setWebhook` back to `https://solar.example.com/api/telegram/ideas-agency` with the solar site's secret.
4. **Solar.** Same for the ideas bot, `/api/telegram/ideas`. Also try a scenario ✅ and a blog ✅. Rollback: `setWebhook` back to `https://solar.example.com/api/telegram/ideas`.
5. **Later, optional:** move the ideas CLI (`IDEAS_SITE_URL`) to the service, then drop the bot code from the solar site.

A rollback never touches the database: both apps read and write the same rows.

## What changed from the solar site

Ported 1:1: every text, button, callback format (`i: m: t: p: s: b:`), status, stage, the feedback log, the one-hour "why?" window, comment handling, the per-bot message-id scoping, content packs, scenarios, blog reviews, notes for Claude, and the `/api/ideas` and `/api/blog-review` contracts.

Changed:

- Projects, bots, labels, reasons, packs and platforms come from `projects.json` instead of constants.
- One webhook route per bot slug instead of one file per bot. A bot without `webhookSecretEnv` can't be reached there.
- The forward route accepts an HMAC signature as well as the shared secret header.
- The Homeworks CRM key is `crmSecretEnv` per project, instead of the solar site's webhook secret.
- Secrets are compared in constant time.
- If the `StormAlert` read fails, `/api/ideas` returns `storms: []` instead of an error.
