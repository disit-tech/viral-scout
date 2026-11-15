import { tokenOf } from "./config";

export const esc = (s: unknown) =>
  String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

export type TgResult = { ok?: boolean; description?: string; result?: { message_id?: number } };

/** One Bot API call through the given bot. No token = skipped (returns null), like the solar site. */
export async function api(method: string, body: Record<string, unknown>, bot: string): Promise<TgResult | null> {
  const token = tokenOf(bot);
  if (!token) return null;
  const r = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const json = (await r.json().catch(() => ({}))) as TgResult;
  if (!json.ok && !/message is not modified/.test(json.description ?? "")) {
    console.error("Ideas bot error", bot, method, r.status, json.description);
  }
  return json;
}
