import { z } from "zod";
import { allowedChats, apiSecret, labelOf, projectSlugs, REASONS, reasonsFor, videoBotOf } from "@/lib/config";
import { prisma } from "@/lib/db";
import { bearer, safeEqual } from "@/lib/auth";
import { logFeedback, refreshIdeaMessage } from "@/lib/idea-bot";
import { FINAL, PACK_KIND, platformList, STAGE } from "@/lib/ui";

/**
 * The ideas board: one admin page (disit.tech/admin/ideas) for every project's ideas and daily films.
 * Full access only: "Authorization: Bearer <IDEAS_API_SECRET>". /api/ideas stays as it is for the CLI and CRM pages.
 *   GET    every project's ideas + films (raw reason codes), the projects, reasons per status, stages
 *   PATCH  { ids, op, value? }: rate · remove · tag · comment · note · posted. Same rows, same feedback log, and the
 *          Telegram message is redrawn, like the buttons there.
 */

export const dynamic = "force-dynamic";

const RATINGS = ["sent", "good", "bad", "redo", "approved", "expand", "variants"] as const;
const STATUSES = [...RATINGS, "review", "tracked", "replaced", "varied", "deleted"];

/** A film waiting for you is "review", never "sent" (the bots auto-post "sent" rows that have no Telegram message). */
const waitingOf = (i: { kind: string }, status: string) => (i.kind === "film" && status === "sent" ? "review" : status);

export async function GET(req: Request) {
  if (!safeEqual(bearer(req), apiSecret())) return new Response("Unauthorized", { status: 401 });
  const projects = projectSlugs();
  const rows = await prisma.videoIdea.findMany({
    where: { project: { in: projects } },
    orderBy: { id: "desc" },
    omit: { askMessageId: true, askedAt: true },
    include: { feedback: { orderBy: { id: "asc" }, omit: { ideaId: true } } },
  });
  const ideas = rows.map((i) => ({
    ...i,
    tags: i.tags ? i.tags.split(",").filter(Boolean) : [],
    platforms: platformList(i),
    // A stored content pack is long JSON: the board only needs to know there is one.
    feedback: i.feedback.map((f) => (f.kind === PACK_KIND ? { ...f, value: "content pack stored" } : f)),
  }));
  const reasonsForAll = Object.fromEntries(
    projects.map((p) => [p, Object.fromEntries(STATUSES.map((s) => [s, reasonsFor(p, s)]).filter(([, v]) => v.length))]),
  );
  return Response.json({
    projects: projects.map((slug) => ({ slug, label: labelOf(slug).replace(/[\s·:|-]+$/, "").trim() || slug })),
    reasons: REASONS(),
    reasonsFor: reasonsForAll,
    stages: STAGE,
    final: FINAL,
    ideas,
  });
}

const Patch = z.object({
  ids: z.array(z.number().int().positive()).min(1).max(100),
  op: z.enum(["rate", "remove", "tag", "comment", "note", "posted"]),
  value: z.string().trim().max(2000).optional(),
});

export async function PATCH(req: Request) {
  if (!safeEqual(bearer(req), apiSecret())) return new Response("Unauthorized", { status: 401 });
  const parsed = Patch.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: z.flattenError(parsed.error) }, { status: 400 });
  const { ids, op, value = "" } = parsed.data;
  if (op === "rate" && !(RATINGS as readonly string[]).includes(value)) return Response.json({ error: "unknown rating" }, { status: 400 });
  if ((op === "tag" || op === "comment" || op === "note") && !value) return Response.json({ error: `${op} needs a value` }, { status: 400 });
  if ((op === "tag" || op === "note") && ids.length > 1) return Response.json({ error: `${op} is for one idea at a time` }, { status: 400 });

  const found = await prisma.videoIdea.findMany({ where: { id: { in: ids }, project: { in: projectSlugs() } } });
  let changed = 0;
  // A few at a time: each one may redraw a Telegram message.
  for (let k = 0; k < found.length; k += 5) {
    await Promise.all(
      found.slice(k, k + 5).map(async (i) => {
        if (op === "comment") {
          const comment = (i.comment ? `${i.comment}\n${value}` : value).slice(-2000);
          await refreshIdeaMessage(await prisma.videoIdea.update({ where: { id: i.id }, data: { comment } }));
          await logFeedback(i.id, "comment", value);
          changed++;
          return;
        }
        if (op === "note") {
          const about =
            i.stage === "script" || i.stage === "script_ok"
              ? `📝 Сценарій · ідея #${i.id}: ${i.title}`
              : i.stage === "draft"
                ? `🎬 ${i.kind === "film" ? "Фільм" : "Чернетка відео"} · ідея #${i.id}: ${i.title}${i.draftPath ? ` (${i.draftPath})` : ""}`
                : `💡 Ідея #${i.id}: ${i.title}`;
          const bot = videoBotOf();
          await prisma.claudeNote.create({
            data: {
              bot,
              chatId: allowedChats(bot)[0] ?? "crm",
              // Negative = from a CRM page (no Telegram message to reply to).
              messageId: -Math.floor(Date.now() / 1000),
              fromName: "disit.tech board",
              text: value,
              replyToMessageId: i.stage === "script" ? i.scriptMessageId : null,
              // The label in front lets the notes reader file it under the right project.
              replyToText: `${labelOf(i.project)}${about}`,
            },
          });
          await logFeedback(i.id, "comment", `note for Claude: ${value}`);
          changed++;
          return;
        }
        if (FINAL.includes(i.status)) return;
        if (op === "posted") {
          if (i.kind !== "film") return;
          const posted = i.stage !== "posted";
          await prisma.videoIdea.update({ where: { id: i.id }, data: { stage: posted ? "posted" : "draft", stageAt: new Date() } });
          await logFeedback(i.id, "stage", posted ? "posted" : "not posted");
          changed++;
          return;
        }
        if (op === "remove") {
          await refreshIdeaMessage(await prisma.videoIdea.update({ where: { id: i.id }, data: { status: "deleted" } }));
          await logFeedback(i.id, "delete", i.status);
          changed++;
          return;
        }
        if (op === "tag") {
          if (!reasonsFor(i.project, i.status).includes(value)) return;
          const tags = (i.tags ?? "").split(",").filter(Boolean);
          const on = tags.includes(value);
          const next = on ? tags.filter((t) => t !== value) : [...tags, value];
          await refreshIdeaMessage(await prisma.videoIdea.update({ where: { id: i.id }, data: { tags: next.join(",") || null } }));
          await logFeedback(i.id, on ? "untag" : "tag", value);
          changed++;
          return;
        }
        // rate: a new rating starts with no reasons (they described the old one)
        const status = waitingOf(i, value);
        if (status === i.status) return;
        const undo = status === "sent" || status === "review";
        await refreshIdeaMessage(await prisma.videoIdea.update({ where: { id: i.id }, data: { status, tags: null } }));
        await logFeedback(i.id, undo ? "undo" : "rating", undo ? i.status : status);
        changed++;
      }),
    );
  }
  return Response.json({ ok: true, changed });
}
