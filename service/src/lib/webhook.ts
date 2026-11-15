import { botConfig, forwardSecretOf, webhookSecretOf } from "./config";
import { safeEqual, TELEGRAM_SECRET_HEADER, verifyForward } from "./auth";
import { handleIdeasUpdate, type Update } from "./idea-bot";

export type Route = { ok: true; bot: string } | { ok: false; status: 401 | 404; error: string };

/** A Telegram webhook call for /api/telegram/<bot>: the bot must exist and own its webhook here (webhookSecretEnv set). */
export function routeWebhook(bot: string, headers: Headers): Route {
  if (!botConfig(bot)) return { ok: false, status: 404, error: "unknown bot" };
  const secret = webhookSecretOf(bot);
  if (!secret || !safeEqual(headers.get(TELEGRAM_SECRET_HEADER), secret)) return { ok: false, status: 401, error: "Unauthorized" };
  return { ok: true, bot };
}

/** A forward from a CRM site that owns the bot's webhook (/api/forward?bot=<bot>): checked with forwardSecretEnv. */
export function routeForward(bot: string | null, headers: Headers, body: string): Route {
  if (!bot || !botConfig(bot)) return { ok: false, status: 404, error: "unknown bot" };
  if (!verifyForward(headers, body, forwardSecretOf(bot))) return { ok: false, status: 401, error: "Unauthorized" };
  return { ok: true, bot };
}

/**
 * Handles the update and always answers 200 once authorised: Telegram retries anything else, and a retried button
 * press would toggle a reason twice.
 */
export async function runUpdate(route: Route, raw: string) {
  if (!route.ok) return new Response(route.error, { status: route.status });
  let update: Update | null = null;
  try {
    update = JSON.parse(raw) as Update;
  } catch {}
  if (update) await handleIdeasUpdate(update, route.bot).catch((e) => console.error(`${route.bot} ideas update`, e));
  return Response.json({ ok: true });
}
