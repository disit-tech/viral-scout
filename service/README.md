# Telegram ideas service

The always-on half of the content studio. Your PC writes and renders ideas; this small Next.js app on Vercel handles the Telegram buttons (👍 👎 🔁 ✅, ⋯ menu, "why?" chips, ↩️ undo, replies as comments, 📝 Пости, scenario ✅/✏️, blog ✅/✏️) so they answer at once, even when the PC is off.

It uses the database the CRM sites already use (the solar site's Turso DB). Same tables, same columns, no migrations. Architecture, config reference and the cutover plan: [docs/telegram-service.md](../docs/telegram-service.md).

## Layout

```
service/
  projects.example.json    projects and bots, placeholders (copy to projects.json, git-ignored, or put the JSON in STUDIO_CONFIG_JSON)
  .env.example             every env var
  prisma/schema.prisma     copy of the VideoIdea, IdeaFeedback, BlogReview, ClaudeNote, StormAlert models
  src/lib/config.ts        loads and checks the config (STUDIO_CONFIG_JSON, projects.json or the example), picks the bot for a project
  src/lib/ui.ts            message texts, keyboards, callback data (pure)
  src/lib/idea-bot.ts      post, redraw, button and reply handlers
  src/lib/notes.ts         replies for Claude (ClaudeNote rows)
  src/lib/webhook.ts       webhook and forward routing
  src/app/api/ideas              same contract as the solar site's /api/ideas
  src/app/api/blog-review        same contract as the solar site's /api/blog-review
  src/app/api/telegram/[bot]     one webhook per bot slug
  src/app/api/forward            ?bot=<slug>: updates forwarded by a CRM site
  src/app/api/health             config check (true/false only), ?db=1 pings the DB
  test/                    vitest, Telegram and DB mocked
```

## Local

```sh
cd service
npm install          # also runs prisma generate
npm test
npx tsc --noEmit
npm run dev          # http://localhost:3220/api/health
```

With `DATABASE_URL` empty it uses a scratch file `data/local.db`. Don't point a local run at the production DB.

## Deploy (Vercel)

1. New Vercel project from this repo. **Root Directory: `service`**. Framework: Next.js. Pick the region closest to the Turso database.
2. Environment variables: everything in `.env.example`. Copy the values from the solar site's Vercel project:
   `DATABASE_URL`, `DATABASE_AUTH_TOKEN`, `IDEAS_API_SECRET`, `TELEGRAM_CHAT_ID`, the three bot tokens, `TELEGRAM_WEBHOOK_SECRET`.
   `HOMES_FORWARD_SECRET` = the Homeworks site's `IDEAS_FORWARD_SECRET`.
3. Deploy. Open `https://<service>/api/health?db=1`: every bot should show `token: true`, and `db` should be `ok`.

Deploying changes nothing in Telegram. Until a webhook points here, the service gets no updates.

## Generic bots

One ideas bot and one video bot for every business: `ideasBot` and `videoBot` in the config. Setup and behaviour: [docs/telegram-service.md](../docs/telegram-service.md#generic-bots-one-for-ideas-one-for-videos).

## Switch one bot at a time

Each step is reversible on its own. Do one, use the bot for a day, then do the next.

**1. Homeworks (CRM bot, webhook stays on homes.example.com).** In the Homeworks (homes) Vercel project set
`IDEAS_FORWARD_URL=https://<service>/api/forward?bot=homes` and redeploy. No Telegram call. Note: the Homeworks CRM page also takes its `/api/ideas` base from that URL's origin, so it now reads through the service too (same DB, same answers). Set `IDEAS_API_URL=https://solar.example.com` there if you want to keep it on the solar site for now.

**2. Acme Agency bot.** Point its webhook here:

```sh
curl -s "https://api.telegram.org/bot<AGENCY_TOKEN>/setWebhook" \
  -d url="https://<service>/api/telegram/agency" \
  -d secret_token="<TELEGRAM_WEBHOOK_SECRET>" \
  -d allowed_updates='["message","callback_query"]'
curl -s "https://api.telegram.org/bot<AGENCY_TOKEN>/getWebhookInfo"
```

**3. Solar ideas bot.** Same, with the ideas bot's token and `url=https://<service>/api/telegram/ideas`.

The ideas CLI (`site/scripts/ideas.mjs`) can keep talking to the solar site: both apps write the same rows. To move it too, set `IDEAS_SITE_URL=https://<service>` in `site/.env.local`.

## Roll back

Point the webhook back at the solar site. Nothing in the database has to change.

| Bot | Roll back |
|---|---|
| Homeworks | `IDEAS_FORWARD_URL=https://solar.example.com/api/telegram/ideas-homes` on the Homeworks project, redeploy |
| Acme Agency | `setWebhook url=https://solar.example.com/api/telegram/ideas-agency secret_token=<solar TELEGRAM_WEBHOOK_SECRET>` |
| Solar | `setWebhook url=https://solar.example.com/api/telegram/ideas secret_token=<solar TELEGRAM_WEBHOOK_SECRET>` |

## Keep in sync

The solar site still has its own copy of the bot code (it posts ideas from `/api/ideas` and storm alerts). If you change a button, a text or a reason there, change it here too, or move the CLI and the CRM pages to the service and retire the copy. The Prisma models here are a copy: the solar site's schema is the source of truth.
