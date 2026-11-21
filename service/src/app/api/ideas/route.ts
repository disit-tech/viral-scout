import { z } from "zod";
import { apiSecret, config, crmSecretOf, hasPacks, PLATFORMS, projectSlugs, REASONS } from "@/lib/config";
import { prisma } from "@/lib/db";
import { bearer, safeEqual } from "@/lib/auth";
import { logFeedback, postIdea, postPack, postScript, refreshIdeaMessage, repostIdea, requestPack, setStage } from "@/lib/idea-bot";
import { FINAL, PACK_KIND, platformList, STAGE, tooLongSection } from "@/lib/ui";
import { recentStorms } from "@/lib/storms";

/**
 * Ideas API for the local generator (the solar site's scripts/ideas.mjs) and the CRM pages. Same contract as the solar
 * site's /api/ideas: same bodies, same answers. Full access: "Authorization: Bearer <IDEAS_API_SECRET>".
 * A project with crmSecretEnv in projects.json also accepts that key, for its own ideas and the CRM steps only.
 *   GET    ?project=… (default: defaultProject) every idea with its feedback; ?packs=1 includes stored content packs
 *   POST   { batch, project?, ideas: [...] } store + post
 *   PATCH  tracked · repost · script · stage · pack · rate · comment · requestPack · remove · platforms
 */

export const dynamic = "force-dynamic";

const full = (req: Request) => safeEqual(bearer(req), apiSecret());
/** Projects whose CRM key this request carries. */
const crmProjects = (req: Request) => {
  const key = bearer(req);
  return key ? projectSlugs().filter((p) => safeEqual(key, crmSecretOf(p))) : [];
};

const text = (max: number) => z.string().trim().min(1).max(max);
const projectEnum = () => z.enum(projectSlugs() as [string, ...string[]]);
const platformEnum = () => z.enum(Object.keys(PLATFORMS()) as [string, ...string[]]);

function schemas() {
  const Idea = z.object({
    title: text(200),
    rubric: text(80).optional(),
    hookType: text(40).optional(),
    hook: text(300),
    angle: text(600).optional(),
    fact: text(600).optional(),
    source: text(400).optional(),
    visual: text(600).optional(),
    cta: text(200).optional(),
    score: z.number().int().min(0).max(50).optional(),
    platforms: z.array(platformEnum()).max(12).optional(),
    why: text(300).optional(),
    replaces: z.number().int().positive().optional(),
    variantOf: z.number().int().positive().optional(),
  });
  const PROJECTS = projectEnum();
  const Body = z.object({ batch: text(60), project: PROJECTS.default(config().defaultProject), ideas: z.array(Idea).min(1).max(20) });
  const PackSection = z.object({
    title: text(80),
    parts: z.array(z.object({ label: text(80).optional(), note: text(600).optional(), text: text(3500) })).min(1).max(10),
  });
  const id = z.number().int().positive();
  const Patch = z.union([
    z.object({ ids: z.array(id).min(1), status: z.enum(["tracked"]) }),
    z.object({ ids: z.array(id).min(1).max(50), repost: z.literal(true) }),
    z.object({ id, script: z.string().trim().min(20).max(3500) }),
    z.object({ id, stage: z.enum(Object.keys(STAGE) as [string, ...string[]]), draftPath: z.string().max(400).optional() }),
    z.object({ id, project: PROJECTS, pack: z.array(PackSection).min(1).max(15), note: z.string().max(300).optional(), send: z.boolean().optional() }),
    z.object({ id, project: PROJECTS, rate: z.enum(["sent", "good", "bad", "redo", "approved"]) }),
    z.object({ id, project: PROJECTS, comment: z.string().trim().min(1).max(2000) }),
    z.object({ id, project: PROJECTS, requestPack: z.literal(true) }),
    z.object({ id, project: PROJECTS, remove: z.literal(true) }),
    z.object({ id, project: PROJECTS, platforms: z.array(platformEnum()).max(12) }),
  ]);
  return { Body, Patch };
}

export async function GET(req: Request) {
  const params = new URL(req.url).searchParams;
  const project = params.get("project") ?? config().defaultProject;
  if (!full(req) && !crmProjects(req).includes(project)) return new Response("Unauthorized", { status: 401 });
  const withPacks = params.get("packs") === "1";
  if (!projectSlugs().includes(project)) return Response.json({ error: "unknown project" }, { status: 400 });
  const rows = await prisma.videoIdea.findMany({
    where: { project },
    orderBy: { id: "asc" },
    omit: { askMessageId: true, askedAt: true },
    include: { feedback: { orderBy: { id: "asc" }, omit: { ideaId: true } } },
  });
  const reasons = REASONS();
  const packLine = (v: string | null) => {
    try {
      const p = JSON.parse(v ?? "") as { sections: { title: string }[] };
      return `stored: ${p.sections.map((s) => s.title).join(" · ")}`;
    } catch {
      return "stored";
    }
  };
  const label = (k: string, v: string | null) =>
    k === PACK_KIND && !withPacks ? packLine(v) : v && (k === "tag" || k === "untag") ? (reasons[v] ?? v) : v;
  const ideas = rows.map((i) => ({
    ...i,
    tags: i.tags ? i.tags.split(",").map((t) => reasons[t] ?? t) : [],
    platforms: platformList(i),
    feedback: i.feedback.map((f) => ({ ...f, value: label(f.kind, f.value) })),
  }));
  // NWS warnings from the last 72 h: the generator opens with a storm-response idea when there are any.
  return Response.json({ ideas, storms: await recentStorms() });
}

export async function POST(req: Request) {
  if (!full(req)) return new Response("Unauthorized", { status: 401 });
  const parsed = schemas().Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: z.flattenError(parsed.error) }, { status: 400 });

  const created: number[] = [];
  const varied = new Set<number>();
  const { project } = parsed.data;
  // A push the client gave up on (timeout) may have stored and posted part of the batch. Sending the same batch again
  // must not post a second card: an idea of this batch with the same title is the same idea. It is only posted
  // when it never got its Telegram message.
  const earlier = await prisma.videoIdea.findMany({ where: { project, batch: parsed.data.batch } });
  const reused: number[] = [];
  const messages: Record<number, number | null> = {};
  for (const { replaces, variantOf, platforms, ...data } of parsed.data.ideas) {
    const same = earlier.find((e) => e.title === data.title);
    if (same) {
      if (!same.tgMessageId && same.status === "sent") await postIdea(same);
      reused.push(same.id);
      created.push(same.id);
      continue;
    }
    // replaces: a new version (redo / expand) → the old one turns ♻️; variantOf: a sibling → the original turns 🧬 once all are posted
    const parent = replaces ? await prisma.videoIdea.findUnique({ where: { id: replaces, project } }) : null;
    const origin = !parent && variantOf ? await prisma.videoIdea.findUnique({ where: { id: variantOf, project } }) : null;
    const idea = await prisma.videoIdea.create({
      data: {
        ...data,
        platforms: platforms?.length ? [...new Set(platforms)].join(",") : null,
        batch: parsed.data.batch,
        project,
        parentId: parent?.id ?? origin?.id,
        version: parent ? parent.version + 1 : 1,
      },
    });
    if (parent) {
      await refreshIdeaMessage(await prisma.videoIdea.update({ where: { id: parent.id }, data: { status: "replaced" } }));
      await logFeedback(parent.id, "system", `replaced by #${idea.id}`);
    }
    if (origin) varied.add(origin.id);
    await postIdea(idea);
    created.push(idea.id);
  }
  for (const id of varied) {
    await refreshIdeaMessage(await prisma.videoIdea.update({ where: { id }, data: { status: "varied" } }));
    await logFeedback(id, "system", "varied");
  }
  // The Telegram message of every idea of the batch (null = not posted: the bot couldn't send it).
  for (const i of await prisma.videoIdea.findMany({ where: { id: { in: created } }, select: { id: true, tgMessageId: true } })) {
    messages[i.id] = i.tgMessageId ?? null;
  }
  return Response.json({ created, reused, messages });
}

export async function PATCH(req: Request) {
  const isFull = full(req);
  const crm = isFull ? [] : crmProjects(req);
  if (!isFull && crm.length === 0) return new Response("Unauthorized", { status: 401 });
  const parsed = schemas().Patch.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: z.flattenError(parsed.error) }, { status: 400 });
  const body = parsed.data;
  // A CRM key: only the CRM steps (rate / comment / 📝 / delete / platforms) on its own project's ideas.
  const crmStep = "rate" in body || "comment" in body || "requestPack" in body || "remove" in body || "platforms" in body;
  if (!isFull && !(crmStep && "project" in body && crm.includes(body.project))) return new Response("Unauthorized", { status: 401 });
  if ("pack" in body) {
    const idea = await prisma.videoIdea.findUnique({ where: { id: body.id, project: body.project } });
    if (!idea) return Response.json({ error: `idea #${body.id} not found in project ${body.project}` }, { status: 404 });
    if (!hasPacks(idea)) return Response.json({ error: `no content packs for project ${idea.project}` }, { status: 400 });
    const long = tooLongSection(body.pack);
    if (long) return Response.json({ error: `section "${long.title}" is too long for one Telegram message; split it` }, { status: 400 });
    const { idea: done, messages, dryRun } = await postPack(idea, body.pack, body.note, body.send ?? true);
    return Response.json({ ok: true, stage: done.stage, messages: messages.length, dryRun, stored: true });
  }
  if (crmStep) {
    // Same steps as the Telegram buttons and the CRM pages: same rows, and the Telegram message is redrawn.
    const idea = await prisma.videoIdea.findUnique({ where: { id: body.id, project: body.project } });
    if (!idea) return Response.json({ error: `idea #${body.id} not found in project ${body.project}` }, { status: 404 });
    if ("platforms" in body) {
      const platforms = [...new Set(body.platforms)].join(",") || null;
      await refreshIdeaMessage(await prisma.videoIdea.update({ where: { id: idea.id }, data: { platforms } }));
      await logFeedback(idea.id, "system", `platforms ${platforms ?? "none"}`);
      return Response.json({ ok: true });
    }
    if ("requestPack" in body) {
      const result = await requestPack(idea);
      if (result === "refused") return Response.json({ error: "no content packs for this idea" }, { status: 400 });
      return Response.json({ ok: true, result });
    }
    if ("comment" in body) {
      const comment = (idea.comment ? `${idea.comment}\n${body.comment}` : body.comment).slice(-2000);
      await refreshIdeaMessage(await prisma.videoIdea.update({ where: { id: idea.id }, data: { comment } }));
      await logFeedback(idea.id, "comment", body.comment);
      return Response.json({ ok: true });
    }
    if (FINAL.includes(idea.status)) return Response.json({ error: `idea #${idea.id} is ${idea.status}` }, { status: 409 });
    if ("remove" in body) {
      await refreshIdeaMessage(await prisma.videoIdea.update({ where: { id: idea.id }, data: { status: "deleted" } }));
      await logFeedback(idea.id, "delete", idea.status);
      return Response.json({ ok: true });
    }
    if (body.rate !== idea.status) {
      // A new rating starts with no reasons (they described the old one).
      await refreshIdeaMessage(await prisma.videoIdea.update({ where: { id: idea.id }, data: { status: body.rate, tags: null } }));
      await logFeedback(idea.id, body.rate === "sent" ? "undo" : "rating", body.rate === "sent" ? idea.status : body.rate);
    }
    return Response.json({ ok: true });
  }
  if ("id" in body) {
    const idea = await prisma.videoIdea.findUnique({ where: { id: body.id } });
    if (!idea) return Response.json({ error: "idea not found" }, { status: 404 });
    const done = "script" in body ? await postScript(idea, body.script) : await setStage(idea, body.stage, body.draftPath);
    return Response.json({ ok: true, stage: done.stage, scriptMessageId: done.scriptMessageId });
  }
  if ("repost" in body) {
    for (const idea of await prisma.videoIdea.findMany({ where: { id: { in: body.ids } }, orderBy: { id: "asc" } })) await repostIdea(idea);
    return Response.json({ ok: true });
  }
  for (const id of body.ids) {
    const idea = await prisma.videoIdea.update({ where: { id }, data: { status: body.status } }).catch(() => null);
    if (idea) {
      await refreshIdeaMessage(idea);
      await logFeedback(id, "system", body.status);
    }
  }
  return Response.json({ ok: true });
}
