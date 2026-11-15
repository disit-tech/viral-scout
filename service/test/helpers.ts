import { vi } from "vitest";
import type { VideoIdea } from "@/lib/db";

/** A full VideoIdea row with defaults. */
export function idea(over: Partial<VideoIdea> = {}): VideoIdea {
  return {
    id: 7,
    createdAt: new Date("2026-11-01T10:00:00Z"),
    updatedAt: new Date("2026-11-01T10:00:00Z"),
    batch: "2026-11-01-a",
    project: "solar",
    title: "Generator <vs> battery",
    rubric: null,
    hookType: null,
    hook: "Your fridge dies in 4 hours",
    angle: null,
    fact: null,
    source: null,
    visual: null,
    cta: null,
    score: null,
    platforms: null,
    why: null,
    status: "sent",
    comment: null,
    tags: null,
    askMessageId: null,
    askedAt: null,
    parentId: null,
    version: 1,
    tgChatId: "-100",
    tgMessageId: 50,
    stage: null,
    stageAt: null,
    script: null,
    scriptMessageId: null,
    draftPath: null,
    ...over,
  };
}

type Where = Record<string, unknown>;
const matches = (row: Record<string, unknown>, where: Where): boolean =>
  Object.entries(where).every(([k, v]) => {
    if (k === "OR") return (v as Where[]).some((w) => matches(row, w));
    if (v && typeof v === "object" && !(v instanceof Date)) {
      const o = v as { in?: unknown[]; notIn?: unknown[]; gte?: Date };
      if (o.in) return o.in.includes(row[k]);
      if (o.notIn) return !o.notIn.includes(row[k]);
      if (o.gte) return row[k] instanceof Date && (row[k] as Date) >= o.gte;
    }
    return row[k] === v;
  });

/** A tiny in-memory stand-in for the Prisma calls the bot makes. */
export function fakeDb(rows: VideoIdea[] = []) {
  const ideas = new Map(rows.map((r) => [r.id, { ...r }]));
  const feedback: { ideaId: number; kind: string; value: string | null }[] = [];
  const notes: Record<string, unknown>[] = [];
  const blog = new Map<number, Record<string, unknown>>();
  const db = {
    videoIdea: {
      findUnique: vi.fn(async ({ where }: { where: Where }) => { const r = [...ideas.values()].find((x) => matches(x, where)); return r ? { ...r } : null; }),
      findFirst: vi.fn(async ({ where }: { where: Where }) => { const r = [...ideas.values()].find((x) => matches(x, where)); return r ? { ...r } : null; }),
      findMany: vi.fn(async ({ where }: { where?: Where } = {}) => [...ideas.values()].filter((r) => matches(r, where ?? {}))),
      update: vi.fn(async ({ where, data }: { where: { id: number }; data: Partial<VideoIdea> }) => {
        const r = ideas.get(where.id);
        if (!r) throw new Error("not found");
        Object.assign(r, data);
        return { ...r };
      }),
      create: vi.fn(async ({ data }: { data: Partial<VideoIdea> }) => {
        const id = Math.max(0, ...ideas.keys()) + 1;
        const r = idea({ id, tgChatId: null, tgMessageId: null, ...data });
        ideas.set(id, r);
        return { ...r };
      }),
    },
    ideaFeedback: { create: vi.fn(async ({ data }: { data: (typeof feedback)[number] }) => (feedback.push(data), data)) },
    claudeNote: { upsert: vi.fn(async ({ create }: { create: Record<string, unknown> }) => (notes.push(create), create)) },
    blogReview: {
      findUnique: vi.fn(async ({ where }: { where: { id: number } }) => blog.get(where.id) ?? null),
      findMany: vi.fn(async () => []),
      update: vi.fn(async ({ where, data }: { where: { id: number }; data: object }) => Object.assign(blog.get(where.id)!, data)),
      create: vi.fn(),
    },
    stormAlert: { findMany: vi.fn(async () => []) },
  };
  return { db, ideas, feedback, notes, blog };
}

export type Call = { token: string; method: string; body: Record<string, unknown> };

/** Replaces fetch: records every Telegram call, answers ok with increasing message ids. */
export function fakeTelegram() {
  const calls: Call[] = [];
  let next = 1000;
  const fetchMock = vi.fn(async (url: string, init?: { body?: string }) => {
    const m = /bot([^/]+)\/(\w+)$/.exec(String(url));
    calls.push({ token: m?.[1] ?? "", method: m?.[2] ?? "", body: init?.body ? JSON.parse(init.body) : {} });
    return new Response(JSON.stringify({ ok: true, result: { message_id: next++ } }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, method: (name: string) => calls.filter((c) => c.method === name) };
}

export const ENV = {
  TELEGRAM_CHAT_ID: "-100",
  TELEGRAM_IDEAS_BOT_TOKEN: "111:ideas",
  TELEGRAM_AGENCY_IDEAS_BOT_TOKEN: "222:agency",
  TELEGRAM_HOMES_IDEAS_BOT_TOKEN: "333:homes",
  TELEGRAM_WEBHOOK_SECRET: "hook-secret",
  HOMES_FORWARD_SECRET: "nf-secret",
  IDEAS_API_SECRET: "api-secret",
};
