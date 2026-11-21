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
  const plain = db.db.videoIdea.findMany;
  db.db.videoIdea.findMany = vi.fn(async (args: Parameters<typeof plain>[0] = {}) =>
    (await plain(args)).map((r) => ({ ...r, feedback: [{ id: 1, createdAt: new Date(0), kind: "pack", value: '{"sections":[{"title":"LinkedIn"}]}' }] })),
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
    expect(await res.json()).toEqual({ created: [3], reused: [], messages: { 3: expect.any(Number) } });
    expect(db.ideas.get(3)!).toMatchObject({ project: "agency", platforms: "linkedin", tgMessageId: expect.any(Number) });
    expect(tg.method("sendMessage")[0].token).toBe("222:agency");
  });
  it("POST of the same batch again (a client retry after a timeout) posts no second card", async () => {
    const batch = { batch: "nf-b", project: "agency", ideas: [{ title: "A", hook: "H" }, { title: "B", hook: "H" }] };
    // The first try stored A and B, but only A got its Telegram message before the client gave up.
    await ideas.POST(req("POST", "api-secret", batch));
    db.ideas.get(4)!.tgMessageId = null;
    const before = tg.method("sendMessage").length;
    const res = await ideas.POST(req("POST", "api-secret", { ...batch, ideas: [...batch.ideas, { title: "C", hook: "H" }] }));
    const body = (await res.json()) as { created: number[]; reused: number[]; messages: Record<string, number | null> };
    expect(body.created).toEqual([3, 4, 5]);
    expect(body.reused).toEqual([3, 4]);
    expect(Object.values(body.messages).every((m) => typeof m === "number")).toBe(true);
    expect(tg.method("sendMessage").length - before).toBe(2); // B (never posted) and the new C; not A again
    expect([...db.ideas.values()].filter((i) => i.batch === "nf-b")).toHaveLength(3);
  });
  it("a Telegram call that hangs or fails comes back as not ok instead of throwing", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new DOMException("The operation was aborted due to timeout", "TimeoutError"); }));
    const res = await ideas.POST(req("POST", "api-secret", { batch: "b9", project: "agency", ideas: [{ title: "T", hook: "H" }] }));
    expect(res.status).toBe(200);
    expect(((await res.json()) as { messages: Record<string, unknown> }).messages).toEqual({ 3: null });
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
