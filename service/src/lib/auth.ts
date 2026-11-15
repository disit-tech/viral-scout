import { createHmac, timingSafeEqual } from "node:crypto";

/** Constant-time string compare (false when either side is empty). */
export function safeEqual(a: string | null | undefined, b: string | null | undefined) {
  if (!a || !b) return false;
  const x = Buffer.from(a);
  const y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}

export const bearer = (req: Request) => {
  const h = req.headers.get("authorization") ?? "";
  return h.startsWith("Bearer ") ? h.slice(7) : null;
};

export const TELEGRAM_SECRET_HEADER = "x-telegram-bot-api-secret-token";
export const SIGNATURE_HEADER = "x-studio-signature";

export const sign = (secret: string, body: string) => "sha256=" + createHmac("sha256", secret).update(body).digest("hex");

/**
 * A forwarded update is genuine when it carries the bot's forward secret, either the way the Homeworks site sends it
 * today (the secret itself in x-telegram-bot-api-secret-token) or as an HMAC of the body (x-studio-signature: sha256=…),
 * which never puts the secret on the wire.
 */
export function verifyForward(headers: Headers, body: string, secret: string | undefined) {
  if (!secret) return false;
  if (safeEqual(headers.get(TELEGRAM_SECRET_HEADER), secret)) return true;
  return safeEqual(headers.get(SIGNATURE_HEADER), sign(secret, body));
}
