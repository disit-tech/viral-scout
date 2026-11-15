import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setConfig } from "@/lib/config";
import { ENV, fakeDb, fakeTelegram, idea } from "./helpers";

const state = vi.hoisted(() => ({ db: null as unknown }));
vi.mock("@/lib/db", () => ({ prisma: new Proxy({}, { get: (_t, p) => (state.db as Record<string | symbol, unknown>)[p] }) }));

const ideas = await import("@/app/api/ideas/route");

const req = (method: string, key: string | null, body?: unknown, query = "") =>
  new Request(`http://svc/api/ideas${query}`, {
    method,
    headers: { ...(key ? { authorization: `Bearer ${key}` } : {}), "content-type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });

let db: ReturnType<typeof fakeDb>;
let tg: ReturnType<typeof fakeTelegram>;
beforeEach(() => {
  setConfig(null, ENV);
  db = fakeDb([idea({ id: 1, tags: "hk" }), idea({ id: 2, project: "homes", tgMessageId: 51 })]);
  // findMany for GET includes feedback rows
  db.db.videoIdea.findMany = vi.fn(async ({ where }: { where?: { project?: string } } = {}) =>
    [...db.ideas.values()].filter((r) => !where?.project || r.project === where.project).map((r) => ({ ...r, feedback: [{ id: 1, createdAt: new Date(0), kind: "pack", value: '{"sections":[{"title":"LinkedIn"}]}' }] })),
  ) as never;
  state.db = db.db;
  tg = fakeTelegram();
});
afterEach(() => vi.unstubAllGlobals());

describe("/api/ideas auth", () => {
  it("no key or a wrong key gives 401", async () => {
    expect((await ideas.GET(req("GET", null))).status).toBe(401);
    expect((await ideas.GET(req("GET", "nope"))).status).toBe(401);
    expect((await ideas.POST(req("POST", "nf-secret", {}))).status).toBe(401);
  });
  it("the CRM key reads only its own project", async () => {
    expect((await ideas.GET(req("GET", "nf-secret", undefined, "?project=homes"))).status).toBe(200);
    expect((await ideas.GET(req("GET", "nf-secret", undefined, "?project=solar"))).status).toBe(401);
    expect((await ideas.GET(req("GET", "nf-secret"))).status).toBe(401); // default project is solar
  });
  it("the CRM key may rate its own ideas but not stage them or touch others", async () => {
    expect((await ideas.PATCH(req("PATCH", "nf-secret", { id: 2, project: "homes", rate: "good" }))).status).toBe(200);
    expect(db.ideas.get(2)!.status).toBe("good");
    expect((await ideas.PATCH(req("PATCH", "nf-secret", { id: 1, project: "solar", rate: "good" }))).status).toBe(401);
    expect((await ideas.PATCH(req("PATCH", "nf-secret", { id: 2, stage: "posted" }))).status).toBe(401);
  });
});

describe("/api/ideas contract", () => {
  it("GET returns labels, platform arrays, short pack lines and storms", async () => {
    const res = await ideas.GET(req("GET", "api-secret"));
    const body = (await res.json()) as { ideas: { id: number; tags: string[]; platforms: string[]; feedback: { value: string }[] }[]; storms: unknown[] };
    expect(body.ideas.map((i) => i.id)).toEqual([1]);
    expect(body.ideas[0].tags).toEqual(["🪝 Сильний хук"]);
    expect(body.ideas[0].platforms).toEqual([]);
    expect(body.ideas[0].feedback[0].value).toBe("stored: LinkedIn");
    expect(body.storms).toEqual([]);
  });
  it("unknown project gives 400", async () => {
    expect((await ideas.GET(req("GET", "api-secret", undefined, "?project=nope"))).status).toBe(400);
  });
  it("POST stores and posts through the project's bot", async () => {
    const res = await ideas.POST(req("POST", "api-secret", { batch: "b1", project: "agency", ideas: [{ title: "T", hook: "H", platforms: ["linkedin", "linkedin"] }] }));
    expect(await res.json()).toEqual({ created: [3] });
    expect(db.ideas.get(3)!).toMatchObject({ project: "agency", platforms: "linkedin", tgMessageId: expect.any(Number) });
    expect(tg.method("sendMessage")[0].token).toBe("222:agency");
  });
  it("POST validates the body", async () => {
    expect((await ideas.POST(req("POST", "api-secret", { batch: "b1", ideas: [] }))).status).toBe(400);
    expect((await ideas.POST(req("POST", "api-secret", { batch: "b1", ideas: [{ title: "T", hook: "H", platforms: ["myspace"] }] }))).status).toBe(400);
  });
  it("PATCH pack: only pack projects, and long sections are refused", async () => {
    const pack = (n: number) => [{ title: "LinkedIn", parts: [{ text: "x".repeat(n) }] }];
    expect((await ideas.PATCH(req("PATCH", "api-secret", { id: 1, project: "solar", pack: pack(10) }))).status).toBe(400);
    const long = await ideas.PATCH(req("PATCH", "api-secret", { id: 2, project: "homes", pack: [...pack(10), { title: "Big", parts: [{ text: "x".repeat(3500) }, { text: "x".repeat(500) }] }] }));
    expect(long.status).toBe(400);
    expect(await long.json()).toEqual({ error: 'section "Big" is too long for one Telegram message; split it' });
    const ok = await ideas.PATCH(req("PATCH", "api-secret", { id: 2, project: "homes", pack: pack(10) }));
    expect(await ok.json()).toMatchObject({ ok: true, stage: "pack_sent", messages: 2, dryRun: false, stored: true });
    expect(tg.method("sendMessage").every((c) => c.token === "333:homes" && (c.body.reply_parameters as { message_id: number }).message_id === 51)).toBe(true);
  });
});
