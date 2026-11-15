import { beforeEach, describe, expect, it, vi } from "vitest";
import { setConfig } from "@/lib/config";
import { ENV } from "./helpers";

const state = vi.hoisted(() => ({ db: null as unknown }));
vi.mock("@/lib/db", () => ({ prisma: new Proxy({}, { get: (_t, p) => (state.db as Record<string | symbol, unknown>)[p] }) }));

const notes = await import("@/app/api/notes/route");
const SECRET = ENV.IDEAS_API_SECRET as string;

const row = (over: Record<string, unknown> = {}) => ({
  id: 1, createdAt: new Date("2026-11-15T08:00:00Z"), bot: "ideas", chatId: "-100", messageId: 9, fromName: "Owner",
  kind: "text", text: "shorter hook", fileId: null, replyToText: "Idea #3", status: "new", result: null, ...over,
});

let rows: ReturnType<typeof row>[];
beforeEach(() => {
  setConfig(null, ENV);
  rows = [row(), row({ id: 2, bot: "agency" }), row({ id: 3, fileId: "F1", kind: "voice" })];
  state.db = {
    blogReview: { count: vi.fn(async () => 2) },
    claudeNote: {
      findMany: vi.fn(async ({ where }: { where: { bot: string; status?: string } }) =>
        rows.filter((r) => r.bot === where.bot && (!where.status || r.status === where.status))),
      count: vi.fn(async ({ where }: { where: { bot: string; status: string } }) =>
        rows.filter((r) => r.bot === where.bot && r.status === where.status).length),
      findUnique: vi.fn(async ({ where }: { where: { id: number } }) => rows.find((r) => r.id === where.id) ?? null),
      update: vi.fn(async ({ where, data }: { where: { id: number }; data: Record<string, unknown> }) =>
        Object.assign(rows.find((r) => r.id === where.id)!, data)),
    },
  };
});

const req = (method: string, key: string | null, query = "", body?: unknown) =>
  new Request(`http://svc/api/notes${query}`, {
    method,
    headers: { ...(key ? { authorization: `Bearer ${key}` } : {}), "content-type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });

describe("/api/notes", () => {
  it("needs the full API secret", async () => {
    expect((await notes.GET(req("GET", null, "?project=solar"))).status).toBe(401);
    expect((await notes.GET(req("GET", "nf-secret", "?project=homes"))).status).toBe(401);
  });
  it("lists only the project bot's new notes, with a signed file link and no token", async () => {
    const r = await notes.GET(req("GET", SECRET, "?project=solar"));
    const { notes: list } = (await r.json()) as { notes: { id: number; file_url: string | null; about: string }[] };
    expect(list.map((n) => n.id)).toEqual([1, 3]);
    expect(list[0].about).toBe("Idea #3");
    expect(list[1].file_url).toMatch(/^http:\/\/svc\/api\/notes\?file=3&sig=[0-9a-f]{32}$/);
    expect(JSON.stringify(list)).not.toContain(ENV.TELEGRAM_IDEAS_BOT_TOKEN ?? "no-token-in-env");
  });
  it("counts pending notes and refuses unknown projects", async () => {
    expect(await (await notes.GET(req("GET", SECRET, "?project=agency&pending=1"))).json()).toEqual({ pending: 1 });
    // solar's bot is the blog bot: 2 new notes + 2 approved blog guides
    expect(await (await notes.GET(req("GET", SECRET, "?project=solar&pending=1"))).json()).toEqual({ pending: 4 });
    expect((await notes.GET(req("GET", SECRET, "?project=nope"))).status).toBe(400);
  });
  it("closes a note of its own project only", async () => {
    expect((await notes.PATCH(req("PATCH", SECRET, "", { id: 2, project: "solar", status: "done" }))).status).toBe(404);
    expect((await notes.PATCH(req("PATCH", SECRET, "", { id: 1, project: "solar", status: "done", result: "v2 sent" }))).status).toBe(200);
    expect(rows[0].status).toBe("done");
    expect(rows[0].result).toBe("v2 sent");
  });
  it("rejects a file link with a wrong signature", async () => {
    expect((await notes.GET(new Request("http://svc/api/notes?file=3&sig=00"))).status).toBe(401);
  });
});
