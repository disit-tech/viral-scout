import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setConfig } from "@/lib/config";
import { ENV, fakeDb, fakeTelegram, idea } from "./helpers";

// The DB is mocked: these tests never open a database.
const state = vi.hoisted(() => ({ db: null as unknown }));
vi.mock("@/lib/db", () => ({ prisma: new Proxy({}, { get: (_t, p) => (state.db as Record<string | symbol, unknown>)[p] }) }));

const { handleIdeasUpdate } = await import("@/lib/idea-bot");
const { routeForward, runUpdate } = await import("@/lib/webhook");

const press = (data: string, chat = -100) => ({ callback_query: { id: "q1", data, message: { message_id: 50, chat: { id: chat } } } });
const text = (t: string, reply?: number) => ({
  message: { message_id: 77, chat: { id: -100 }, from: { first_name: "A" }, text: t, ...(reply ? { reply_to_message: { message_id: reply } } : {}) },
});

let db: ReturnType<typeof fakeDb>;
let tg: ReturnType<typeof fakeTelegram>;

function setup(rows = [idea()]) {
  db = fakeDb(rows);
  state.db = db.db;
  tg = fakeTelegram();
}

beforeEach(() => setConfig(null, ENV));
afterEach(() => vi.unstubAllGlobals());

describe("rating buttons", () => {
  it("👍 stores the rating, redraws the idea and asks why", async () => {
    setup();
    await handleIdeasUpdate(press("i:7:g"), "ideas");
    expect(db.ideas.get(7)!.status).toBe("good");
    expect(db.feedback).toContainEqual({ ideaId: 7, kind: "rating", value: "good" });
    expect(tg.method("answerCallbackQuery")[0].body).toMatchObject({ callback_query_id: "q1", text: "👍 Норм" });
    expect(tg.method("editMessageText")[0].body).toMatchObject({ chat_id: "-100", message_id: 50 });
    const ask = tg.method("sendMessage")[0];
    expect(ask.body.text).toContain("Що сподобалось?");
    expect(db.ideas.get(7)!.askMessageId).toBeGreaterThan(0);
    expect(tg.calls.every((c) => c.token === "111:ideas")).toBe(true);
  });
  it("a new rating clears the old reasons; the same rating logs nothing", async () => {
    setup([idea({ status: "good", tags: "hk" })]);
    await handleIdeasUpdate(press("i:7:g"), "ideas");
    expect(db.feedback).toHaveLength(0);
    await handleIdeasUpdate(press("i:7:b"), "ideas");
    expect(db.ideas.get(7)!).toMatchObject({ status: "bad", tags: null });
  });
  it("refuses chats that are not allowed", async () => {
    setup();
    await handleIdeasUpdate(press("i:7:g", -999), "ideas");
    expect(db.ideas.get(7)!.status).toBe("sent");
    expect(tg.calls).toHaveLength(1);
    expect(tg.calls[0].body).toMatchObject({ text: "⛔ Немає доступу", show_alert: true });
  });
  it("final ideas only answer their status", async () => {
    setup([idea({ status: "tracked" })]);
    await handleIdeasUpdate(press("i:7:g"), "ideas");
    expect(tg.calls.map((c) => c.method)).toEqual(["answerCallbackQuery"]);
    expect(tg.calls[0].body.text).toBe("📋 У трекері");
  });
  it("unknown idea and junk data", async () => {
    setup();
    await handleIdeasUpdate(press("i:99:g"), "ideas");
    await handleIdeasUpdate(press("zz"), "ideas");
    expect(tg.calls.map((c) => c.body.text)).toEqual(["Ідею не знайдено", "Ідею не знайдено"]);
  });
});

describe("why? reasons", () => {
  it("toggles a reason and logs tag / untag", async () => {
    setup([idea({ status: "good" })]);
    await handleIdeasUpdate(press("t:7:hk"), "ideas");
    expect(db.ideas.get(7)!.tags).toBe("hk");
    await handleIdeasUpdate(press("t:7:hk"), "ideas");
    expect(db.ideas.get(7)!.tags).toBeNull();
    expect(db.feedback.map((f) => f.kind)).toEqual(["tag", "untag"]);
  });
  it("ignores unknown reason codes", async () => {
    setup([idea({ status: "good" })]);
    await handleIdeasUpdate(press("t:7:zz"), "ideas");
    expect(tg.calls).toHaveLength(0);
  });
  it("↩️ undo resets the rating but keeps comments", async () => {
    setup([idea({ status: "bad", tags: "nt", comment: "meh", askMessageId: 60 })]);
    await handleIdeasUpdate(press("t:7:undo"), "ideas");
    expect(db.ideas.get(7)!).toMatchObject({ status: "sent", tags: null, comment: "meh", askMessageId: null });
    expect(db.feedback).toContainEqual({ ideaId: 7, kind: "undo", value: "bad" });
    expect(tg.method("deleteMessage")).toHaveLength(1);
  });
  it("👎 → 🔁 switch", async () => {
    setup([idea({ status: "bad", tags: "nt" })]);
    await handleIdeasUpdate(press("t:7:tored"), "ideas");
    expect(db.ideas.get(7)!).toMatchObject({ status: "redo", tags: null });
  });
});

describe("menu", () => {
  it("⋯ opens the more view", async () => {
    setup();
    await handleIdeasUpdate(press("m:7:more"), "ideas");
    const kb = tg.method("editMessageReplyMarkup")[0].body.reply_markup as { inline_keyboard: { callback_data: string }[][] };
    expect(kb.inline_keyboard[0].map((b) => b.callback_data)).toEqual(["i:7:x", "i:7:v"]);
  });
  it("🗑 confirmed marks deleted", async () => {
    setup();
    await handleIdeasUpdate(press("m:7:delyes"), "ideas");
    expect(db.ideas.get(7)!.status).toBe("deleted");
    expect(db.feedback).toContainEqual({ ideaId: 7, kind: "delete", value: "sent" });
  });
});

describe("content pack button", () => {
  it("queues a pack on a Homeworks idea through the Homeworks bot", async () => {
    setup([idea({ project: "homes", status: "tracked" })]);
    await handleIdeasUpdate(press("p:7:req"), "homes");
    expect(db.ideas.get(7)!.stage).toBe("pack");
    expect(tg.calls.every((c) => c.token === "333:homes")).toBe(true);
    expect(tg.method("answerCallbackQuery")[0].body).toMatchObject({ show_alert: true });
  });
  it("refuses packs for solar", async () => {
    setup([idea({ status: "tracked" })]);
    await handleIdeasUpdate(press("p:7:req"), "ideas");
    expect(db.ideas.get(7)!.stage).toBeNull();
    expect(tg.calls[0].body.text).toBe("Для цієї ідеї пости не робимо");
  });
});

describe("scenario buttons", () => {
  it("✅ approves the scenario", async () => {
    setup([idea({ status: "tracked", stage: "script", scriptMessageId: 80 })]);
    await handleIdeasUpdate(press("s:7:ok"), "ideas");
    expect(db.ideas.get(7)!.stage).toBe("script_ok");
    expect(db.feedback).toContainEqual({ ideaId: 7, kind: "rating", value: "script approved" });
  });
});

describe("replies and comments", () => {
  it("a reply to the idea becomes a comment", async () => {
    setup();
    await handleIdeasUpdate(text("More about batteries", 50), "ideas");
    expect(db.ideas.get(7)!.comment).toBe("More about batteries");
    expect(db.feedback).toContainEqual({ ideaId: 7, kind: "comment", value: "More about batteries" });
    expect(tg.method("sendMessage")[0].body.text).toContain("Записав до ідеї #7");
  });
  it("plain text within an hour of the question goes to that idea", async () => {
    setup([idea({ status: "good", askedAt: new Date() })]);
    await handleIdeasUpdate(text("love it"), "ideas");
    expect(db.ideas.get(7)!.comment).toBe("love it");
  });
  it("only the bot that owns the idea records it", async () => {
    setup([idea({ project: "agency" })]);
    await handleIdeasUpdate(text("hi", 50), "ideas");
    expect(db.ideas.get(7)!.comment).toBeNull();
    await handleIdeasUpdate(text("hi", 50), "agency");
    expect(db.ideas.get(7)!.comment).toBe("hi");
  });
  it("'Claude, …' goes to notes for the bot with replies+call, never for a CRM bot", async () => {
    setup([]);
    await handleIdeasUpdate(text("Claude, redo the video"), "ideas");
    expect(db.notes).toHaveLength(1);
    expect(db.notes[0]).toMatchObject({ bot: "ideas", text: "redo the video" });
    await handleIdeasUpdate(text("Claude, hi"), "homes");
    expect(db.notes).toHaveLength(1);
  });
});

describe("forwarded updates", () => {
  it("a signed forward from the Homeworks site runs as the Homeworks bot", async () => {
    setup([idea({ project: "homes" })]);
    const raw = JSON.stringify(press("i:7:a"));
    const route = routeForward("homes", new Headers({ "x-telegram-bot-api-secret-token": "nf-secret" }), raw);
    const res = await runUpdate(route, raw);
    expect(res.status).toBe(200);
    expect(db.ideas.get(7)!.status).toBe("approved");
    expect(tg.calls.every((c) => c.token === "333:homes")).toBe(true);
    expect(tg.method("answerCallbackQuery")[0].body.text).toBe("✅ У трекер + 📝 пости (при наступній генерації)");
  });
  it("a bad signature changes nothing", async () => {
    setup([idea({ project: "homes" })]);
    const raw = JSON.stringify(press("i:7:a"));
    const res = await runUpdate(routeForward("homes", new Headers({ "x-telegram-bot-api-secret-token": "x" }), raw), raw);
    expect(res.status).toBe(401);
    expect(db.ideas.get(7)!.status).toBe("sent");
    expect(tg.calls).toHaveLength(0);
  });
});
