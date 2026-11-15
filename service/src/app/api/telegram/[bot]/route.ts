import { routeWebhook, runUpdate } from "@/lib/webhook";

/**
 * Telegram webhook of one bot: /api/telegram/<bot slug from projects.json>.
 * Telegram sends the secret_token given to setWebhook in x-telegram-bot-api-secret-token; it must match the bot's
 * webhookSecretEnv. See service/README.md for setWebhook.
 */
export async function POST(req: Request, ctx: { params: Promise<{ bot: string }> }) {
  const { bot } = await ctx.params;
  const route = routeWebhook(bot, req.headers);
  return runUpdate(route, route.ok ? await req.text() : "");
}
