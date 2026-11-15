import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { parseConfig, setConfig } from "@/lib/config";
import file from "../projects.example.json";
import { ENV } from "./helpers";

const state = vi.hoisted(() => ({ db: null as unknown }));
vi.mock("@/lib/db", () => ({ prisma: new Proxy({}, { get: (_t, p) => (state.db as Record<string | symbol, unknown>)[p] }) }));

const status = await import("@/app/api/status/route");

const GENERIC = {
  ...file,
  ideasBot: "studio-ideas",
  videoBot: "studio-video",
  bots: {
    ...file.bots,
    ideas: { ...file.bots.ideas, notes: "replies" },
    "studio-ideas": { tokenEnv: "TELEGRAM_STUDIO_IDEAS_BOT_TOKEN", webhookSecretEnv: "TELEGRAM_WEBHOOK_SECRET", notes: "off" },
    "studio-video": { tokenEnv: "TELEGRAM_STUDIO_VIDEO_BOT_TOKEN", webhookSecretEnv: "TELEGRAM_WEBHOOK_SECRET", notes: "replies+call" },
  },
  projects: { ...file.projects, solar: { ...file.projects.solar, label: "☀️ Bright Solar · " } },
};
const GENV = { ...ENV, TELEGRAM_STUDIO_IDEAS_BOT_TOKEN: "444:si", TELEGRAM_STUDIO_VIDEO_BOT_TOKEN: "555:sv" };

/** Telegram: getMe → a username per token; getWebhookInfo → the studio bots point at the service, homes at its site. */
function fakeTelegram() {
  const sent: { token: string; method: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: { body?: string }) => {
    const [, token, method] = /bot([^/]+)\/(\w+)$/.exec(String(url)) ?? [];
    const body = init?.body ? JSON.parse(init.body) : {};
    sent.push({ token, method, body });
    const name = { "444:si": "studio_ideas_bot", "555:sv": "studio_video_bot", "333:homes": "homes_crm_bot" }[token] ?? "other_bot";
    const hook = token === "333:homes" ? "https://homes.example.com/api/telegram/webhook"
      : token === "222:agency" ? "" : `http://svc/api/telegram/${name}`;
    const result = method === "getMe" ? { username: name }
      : method === "getWebhookInfo" ? { url: hook, pending_update_count: 0, ...(token === "555:sv" ? { last_error_message: "Read timeout expired", last_error_date: 1763200000 } : {}) }
      : { message_id: 4242 };
    return new Response(JSON.stringify({ ok: true, result }));
  }));
  return sent;
}

const db = {
  videoIdea: {
    findFirst: vi.fn(async ({ where }: { where: { project: string } }) => (where.project === "homes" ? { id: 12, createdAt: new Date("2026-11-15T13:00:00Z") } : null)),
    count: vi.fn(async ({ where }: { where: { project: string } }) => (where.project === "homes" ? 3 : 0)),
  },
  ideaFeedback: {
    findFirst: vi.fn(async ({ where }: { where: { kind: unknown; idea: { project: string } } }) =>
      where.idea.project === "homes" ? { createdAt: new Date("2026-11-15T14:00:00Z"), kind: "rating", value: "good", ideaId: 12 } : null),
  },
  claudeNote: {
    findMany: vi.fn(async () => [
      { id: 5, createdAt: new Date("2026-11-15T15:00:00Z"), bot: "studio-video", chatId: "-100", messageId: 9, fromName: "O", kind: "text", text: "louder", fileId: null, replyToText: "🔨 Homeworks · 📝 Сценарій", status: "new", result: null },
    ]),
  },
};

const get = (q = "", key = GENV.IDEAS_API_SECRET) =>
  status.GET(new Request(`http://svc/api/status${q}`, { headers: key ? { authorization: `Bearer ${key}` } : {} }));

beforeEach(() => {
  setConfig(parseConfig(GENERIC), GENV);
  state.db = db;
});
afterEach(() => vi.unstubAllGlobals());

describe("/api/status", () => {
  it("needs the full API secret", async () => {
    fakeTelegram();
    expect((await get("", "")).status).toBe(401);
    expect((await get("", "nf-secret")).status).toBe(401);
    expect((await get("?project=nope")).status).toBe(400);
  });

  it("shows one business's bots, where their updates go, and its latest activity, without tokens", async () => {
    fakeTelegram();
    const r = await get("?project=homes");
    const text = await r.text();
    expect(text).not.toContain("444:si");
    expect(text).not.toContain("333:homes");
    const p = (JSON.parse(text) as { projects: Record<string, any>[] }).projects[0];
    expect(p.label).toBe("🔨 Homeworks · ");
    expect(p.ideas).toMatchObject({ slug: "studio-ideas", token: true, where: "service", username: "studio_ideas_bot", shared: true });
    expect(p.video).toMatchObject({ slug: "studio-video", where: "service", lastError: "Read timeout expired", shared: true });
    expect(p.oldBot).toMatchObject({ slug: "homes", where: "forward" });
    expect(p.activity).toMatchObject({ lastIdeaPosted: { id: 12 }, waitingForRating: 3, lastTap: { id: 12, kind: "rating" }, openNotes: 1 });
  });

  it("lists every business, asking Telegram once per bot", async () => {
    const sent = fakeTelegram();
    const r = (await (await get()).json()) as { projects: { project: string }[] };
    expect(r.projects.map((p) => p.project)).toEqual(["solar", "homes", "agency"]);
    const infoCalls = sent.filter((c) => c.method === "getWebhookInfo").map((c) => c.token);
    expect(new Set(infoCalls).size).toBe(infoCalls.length);
  });

  it("sends a test message through the business's ideas or video bot, headed with its label", async () => {
    const sent = fakeTelegram();
    const post = (body: unknown) => status.POST(new Request("http://svc/api/status", {
      method: "POST", headers: { authorization: `Bearer ${GENV.IDEAS_API_SECRET}`, "content-type": "application/json" }, body: JSON.stringify(body),
    }));
    expect((await post({ project: "homes", role: "nope" })).status).toBe(400);
    expect(await (await post({ project: "homes", role: "video" })).json()).toMatchObject({ ok: true, bot: "studio-video", message_id: 4242 });
    const msg = sent.find((c) => c.method === "sendMessage")!;
    expect(msg.token).toBe("555:sv");
    expect(String(msg.body.text)).toMatch(/^🔨 Homeworks · 🧪/);
  });
});
