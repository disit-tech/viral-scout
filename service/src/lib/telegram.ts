import { tokenOf } from "./config";

export const esc = (s: unknown) =>
  String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

export type TgResult = { ok?: boolean; description?: string; result?: { message_id?: number } };

/** How long one Bot API call may take. A hung call used to hold the whole request until the client gave up. */
export const TG_TIMEOUT_MS = 15_000;

/** One Bot API call through the given bot. No token = skipped (returns null), like the solar site. A network error or
 * a timeout comes back as {ok: false} (logged), so one failed message doesn't stop the rest of a batch. */
export async function api(method: string, body: Record<string, unknown>, bot: string): Promise<TgResult | null> {
  const token = tokenOf(bot);
  if (!token) return null;
  let r: Response;
  try {
    r = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(TG_TIMEOUT_MS),
    });
  } catch (e) {
    const description = e instanceof Error ? `${e.name}: ${e.message}` : String(e);
    console.error("Ideas bot error", bot, method, description);
    return { ok: false, description };
  }
  const json = (await r.json().catch(() => ({}))) as TgResult;
  if (!json.ok && !/message is not modified/.test(json.description ?? "")) {
    console.error("Ideas bot error", bot, method, r.status, json.description);
  }
  return json;
}
