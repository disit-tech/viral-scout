import { routeForward, runUpdate } from "@/lib/webhook";

/**
 * Idea updates forwarded by a site that owns a bot's webhook (the Homeworks CRM bot's webhook is homes.example.com,
 * which forwards idea buttons and replies). POST /api/forward?bot=<bot slug>, body = the Telegram update as received.
 * Auth: the bot's forwardSecretEnv, either as x-telegram-bot-api-secret-token (what the Homeworks site sends today)
 * or as x-studio-signature: sha256=<HMAC-SHA256 of the body>.
 */
export async function POST(req: Request) {
  const raw = await req.text();
  const bot = new URL(req.url).searchParams.get("bot");
  return runUpdate(routeForward(bot, req.headers, raw), raw);
}
