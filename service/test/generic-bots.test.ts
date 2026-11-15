import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { botOf, parseConfig, projectOfText, setConfig, videoBotOf } from "@/lib/config";
import file from "../projects.example.json";
import { ENV, fakeDb, fakeTelegram, idea } from "./helpers";

// Two generic bots: "studio-ideas" posts every project's ideas, "studio-video" sends scenarios, files and takes notes.
// The old per-project bots stay configured, so the messages they posted earlier keep working.
const state = vi.hoisted(() => ({ db: null as unknown }));
vi.mock("@/lib/db", () => ({ prisma: new Proxy({}, { get: (_t, p) => (state.db as Record<string | symbol, unknown>)[p] }) }));

const { handleIdeasUpdate, postIdea, refreshIdeaMessage, postScript, posterOf } = await import("@/lib/idea-bot");
const notes = await import("@/app/api/notes/route");

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

let db: ReturnType<typeof fakeDb>;
let tg: ReturnType<typeof fakeTelegram>;
const tokenOfCall = (c: { token: string }) => c.token;

beforeEach(() => setConfig(parseConfig(GENERIC), GENV));
afterEach(() => vi.unstubAllGlobals());

describe("generic bots", () => {
  it("config: ideas of every project go through the ideas bot, production through the video bot", () => {
    expect(botOf({ project: "homes" })).toBe("studio-ideas");
    expect(botOf({ project: "agency" })).toBe("studio-ideas");
    expect(videoBotOf()).toBe("studio-video");
    expect(projectOfText("🔨 Homeworks · 💡 Ідея #3")).toBe("homes");
    expect(projectOfText("☀️ Bright Solar · 📝 Сценарій")).toBe("solar");
  });

  it("a project may drop its own bot once ideasBot is set; without both the config is refused", () => {
    const { bot: _drop, ...rest } = GENERIC.projects.homes;
    expect(() => parseConfig({ ...GENERIC, projects: { ...GENERIC.projects, homes: rest } })).not.toThrow();
    const { ideasBot: _i, ...noShared } = GENERIC;
    expect(() => parseConfig({ ...noShared, projects: { ...GENERIC.projects, homes: rest } })).toThrow(/ideasBot/);
  });

  it("a new idea is posted by the ideas bot and remembered as its poster", async () => {
    db = fakeDb([idea({ id: 9, project: "homes", tgChatId: null, tgMessageId: null })]);
    state.db = db.db;
    tg = fakeTelegram();
    await postIdea(db.ideas.get(9)!);
    expect(tg.method("sendMessage").map(tokenOfCall)).toEqual(["444:si"]);
    expect(db.feedback).toContainEqual({ ideaId: 9, kind: "system", value: "posted by the studio-ideas bot" });
    expect(await posterOf(db.ideas.get(9)!)).toBe("studio-ideas");
  });

  it("an idea posted before the switch is still edited by its old bot", async () => {
    db = fakeDb([idea({ id: 2, project: "homes", tgMessageId: 51 })]);
    state.db = db.db;
    tg = fakeTelegram();
    await refreshIdeaMessage(db.ideas.get(2)!);
    expect(tg.method("editMessageText").map(tokenOfCall)).toEqual(["333:homes"]);
  });

  it("the same message number from another bot never lands on the wrong idea", async () => {
    // Idea 1 was posted by the old homes bot as message 50; idea 3 by the ideas bot, also as message 50 (basic group).
    db = fakeDb([idea({ id: 1, project: "homes", tgMessageId: 50 }), idea({ id: 3, project: "agency", tgMessageId: 50 })]);
    db.feedback.push({ ideaId: 3, kind: "system", value: "posted by the studio-ideas bot" });
    state.db = db.db;
    tg = fakeTelegram();
    const reply = (t: string) => ({ message: { message_id: 90, chat: { id: -100 }, from: { first_name: "A" }, text: t, reply_to_message: { message_id: 50 } } });
    await handleIdeasUpdate(reply("shorter hook"), "studio-ideas");
    expect(db.ideas.get(3)!.comment).toBe("shorter hook");
    expect(db.ideas.get(1)!.comment).toBeNull();
    await handleIdeasUpdate(reply("more local"), "homes");
    expect(db.ideas.get(1)!.comment).toBe("more local");
  });

  it("scenarios go out through the video bot, headed with the project", async () => {
    db = fakeDb([idea({ id: 4, project: "homes", status: "approved" })]);
    state.db = db.db;
    tg = fakeTelegram();
    await postScript(db.ideas.get(4)!, "Hook: gutters full of leaves. Body: one bucket. CTA: text a photo.");
    const sent = tg.method("sendMessage");
    expect(sent.map(tokenOfCall)).toEqual(["555:sv"]);
    expect(String(sent[0].body.text)).toMatch(/^🔨 Homeworks · 📝/);
  });

  it("notes of the shared video bot are split by project", async () => {
    const rows = [
      { id: 1, createdAt: new Date(0), bot: "studio-video", chatId: "-100", messageId: 5, fromName: "O", kind: "text", text: "redo", fileId: null, replyToText: "🔨 Homeworks · 📝 Сценарій", status: "new", result: null },
      { id: 2, createdAt: new Date(0), bot: "studio-video", chatId: "-100", messageId: 6, fromName: "O", kind: "text", text: "louder", fileId: null, replyToText: "☀️ Bright Solar · film.mp4", status: "new", result: null },
    ];
    state.db = {
      claudeNote: { findMany: vi.fn(async ({ where }: { where: { bot: { in: string[] } } }) => rows.filter((r) => where.bot.in.includes(r.bot))) },
      blogReview: { count: vi.fn(async () => 0) },
    };
    const get = (project: string) => notes.GET(new Request(`http://svc/api/notes?project=${project}`, { headers: { authorization: `Bearer ${GENV.IDEAS_API_SECRET}` } }));
    expect(((await (await get("homes")).json()) as { notes: { id: number }[] }).notes.map((n) => n.id)).toEqual([1]);
    expect(((await (await get("solar")).json()) as { notes: { id: number }[] }).notes.map((n) => n.id)).toEqual([2]);
  });
});

describe("before the generic bots have tokens", () => {
  it("everything stays on the old bots", () => {
    setConfig(parseConfig(GENERIC), ENV);
    expect(botOf({ project: "homes" })).toBe("homes");
    expect(botOf({ project: "solar" })).toBe("ideas");
    expect(videoBotOf()).toBe("ideas");
  });
});
