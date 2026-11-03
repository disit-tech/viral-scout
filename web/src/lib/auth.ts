/**
 * Single-password gate for the published (read-only) dashboard. No paid auth service.
 * Cookie = "<expiresAt>.<HMAC-SHA256(expiresAt)>" signed with SESSION_SECRET (Web Crypto: works in proxy + routes).
 * Locally (no SITE_PASSWORD) the gate is off. On Vercel without SITE_PASSWORD everything is locked (fail closed).
 */
export const SESSION_COOKIE = "vs_session";
const DAY = 86_400_000;

/** Public demo deployments (sample data only) skip the login: VIRAL_SCOUT_PUBLIC_DEMO=1. */
export const isPublicDemo = process.env.VIRAL_SCOUT_PUBLIC_DEMO === "1";

export function authRequired(): boolean {
  if (isPublicDemo) return false;
  return Boolean(process.env.SITE_PASSWORD) || Boolean(process.env.VERCEL);
}

function secret(): string {
  const s = process.env.SESSION_SECRET;
  if (!s || s.length < 24) throw new Error("SESSION_SECRET must be set (24+ random characters)");
  return s;
}

async function hmac(data: string): Promise<string> {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret()),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(data)));
  let s = "";
  for (const b of sig) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function same(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

export async function createSession(days = 30): Promise<{ token: string; expires: Date }> {
  const expires = new Date(Date.now() + days * DAY);
  const payload = String(expires.getTime());
  return { token: `${payload}.${await hmac(payload)}`, expires };
}

export async function verifySession(token: string | undefined): Promise<boolean> {
  if (!token) return false;
  const [payload, sig] = token.split(".");
  if (!payload || !sig || Number(payload) < Date.now()) return false;
  try {
    return same(await hmac(payload), sig);
  } catch {
    return false;
  }
}

export function passwordOk(input: string): boolean {
  const p = process.env.SITE_PASSWORD;
  return Boolean(p) && same(input, p!);
}
