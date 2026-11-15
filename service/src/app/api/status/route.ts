import {
  apiSecret, allowedChats, botConfig, botOf, config, forwardSecretOf, labelOf, legacyBotOf, noteBotsFor, noteProjectOf,
  projectOf, projectSlugs, tokenOf, videoBotOf, webhookSecretOf,
} from "@/lib/config";
import { prisma } from "@/lib/db";
import { bearer, safeEqual } from "@/lib/auth";
import { api } from "@/lib/telegram";

/**
 * Are a business's bots connected and working? For the dashboard's Bots page (`python -m viral_scout ideas <p> status`).
 * Auth: "Authorization: Bearer <IDEAS_API_SECRET>". Tokens never leave the service.
 *   GET   ?project=…            → one project: its ideas bot and video bot, each bot's webhook as Telegram reports it,
 *                                  and the latest activity (idea posted, button tap, comment, note).
 *   GET   (no project)          → every project.
 *   POST  {project, role: "ideas"|"video"}  → a short test message through that bot to the group → {message_id}
 */

export const dynamic = "force-dynamic";

const full = (req: Request) => safeEqual(bearer(req), apiSecret());
const json = (body: unknown, status = 200) => Response.json(body, { status });

type Hook = { url?: string; pending_update_count?: number; last_error_message?: string; last_error_date?: number };

/** One bot as the dashboard shows it. `where`: service = its webhook is this service; forward = its own site forwards
 * idea updates here; elsewhere = updates don't reach this service; none = no webhook; unknown = no token. */
async function botStatus(slug: string, origin: string, cache: Map<string, unknown>) {
  if (cache.has(slug)) return cache.get(slug);
  const b = botConfig(slug);
  const token = Boolean(tokenOf(slug));
  let out: Record<string, unknown> = { slug, token, where: "unknown" };
  if (b && token) {
    const [me, info] = await Promise.all([api("getMe", {}, slug), api("getWebhookInfo", {}, slug)]);
    const hook = (info?.result ?? {}) as Hook;
    const url = hook.url ?? "";
    const here = url.startsWith(`${origin}/api/telegram/`) || url.startsWith(`${origin.replace(/\/$/, "")}/api/telegram/`);
    // "forward" only when the service can check the forwards (its forward secret is set); else they go elsewhere.
    const where = !url ? "none" : here ? "service" : b.forwardSecretEnv && forwardSecretOf(slug) ? "forward" : "elsewhere";
    out = {
      slug,
      token,
      username: (me?.result as { username?: string } | undefined)?.username ?? null,
      where,
      webhook: url ? url.replace(/^https?:\/\//, "").replace(/\?.*$/, "") : null,
      pending: hook.pending_update_count ?? 0,
      lastError: hook.last_error_message ?? null,
      lastErrorAt: hook.last_error_date ? new Date(hook.last_error_date * 1000).toISOString() : null,
      secretSet: Boolean(webhookSecretOf(slug)),
      forwardSecretSet: Boolean(forwardSecretOf(slug)),
      chats: allowedChats(slug).length,
    };
  }
  cache.set(slug, out);
  return out;
}

const iso = (d: Date | null | undefined) => (d ? new Date(d).toISOString() : null);

async function projectStatus(project: string, origin: string, cache: Map<string, unknown>) {
  const c = config();
  const ideasBot = botOf({ project });
  const oldBot = legacyBotOf({ project });
  const videoBot = videoBotOf();
  const [lastIdea, waiting, lastTap, lastComment, notes] = await Promise.all([
    prisma.videoIdea.findFirst({ where: { project, tgMessageId: { not: null } }, orderBy: { createdAt: "desc" }, select: { id: true, createdAt: true } }),
    prisma.videoIdea.count({ where: { project, status: "sent" } }),
    prisma.ideaFeedback.findFirst({
      where: { kind: { in: ["rating", "tag", "untag", "undo", "delete"] }, idea: { project } },
      orderBy: { id: "desc" }, select: { createdAt: true, kind: true, value: true, ideaId: true },
    }),
    prisma.ideaFeedback.findFirst({ where: { kind: "comment", idea: { project } }, orderBy: { id: "desc" }, select: { createdAt: true, ideaId: true } }),
    prisma.claudeNote.findMany({ where: { bot: { in: noteBotsFor(project) ?? [] } }, orderBy: { id: "desc" }, take: 200 }),
  ]);
  const mine = notes.filter((n) => noteProjectOf(n) === project);
  return {
    project,
    label: labelOf(project),
    ideas: { ...(await botStatus(ideasBot, origin, cache) as object), shared: ideasBot === c.ideasBot },
    video: { ...(await botStatus(videoBot, origin, cache) as object), shared: videoBot === c.videoBot },
    // The project's own bot from before the generic bots: it still answers its old messages.
    oldBot: oldBot !== ideasBot ? await botStatus(oldBot, origin, cache) : null,
    sharedConfigured: { ideas: c.ideasBot ?? null, video: c.videoBot ?? null },
    activity: {
      lastIdeaPosted: lastIdea ? { id: lastIdea.id, at: iso(lastIdea.createdAt) } : null,
      waitingForRating: waiting,
      lastTap: lastTap ? { id: lastTap.ideaId, at: iso(lastTap.createdAt), kind: lastTap.kind, value: lastTap.value } : null,
      lastComment: lastComment ? { id: lastComment.ideaId, at: iso(lastComment.createdAt) } : null,
      lastNote: mine[0] ? { id: mine[0].id, at: iso(mine[0].createdAt), status: mine[0].status } : null,
      openNotes: mine.filter((n) => n.status === "new").length,
    },
  };
}

export async function GET(req: Request) {
  if (!full(req)) return json({ error: "unauthorized" }, 401);
  const url = new URL(req.url);
  const one = url.searchParams.get("project");
  if (one && !projectOf(one)) return json({ error: `project must be one of ${projectSlugs().join(", ")}` }, 400);
  const cache = new Map<string, unknown>();
  const list = one ? [one] : projectSlugs();
  const projects = [];
  for (const p of list) projects.push(await projectStatus(p, url.origin, cache));
  return json({ service: url.origin, checkedAt: new Date().toISOString(), projects });
}

export async function POST(req: Request) {
  if (!full(req)) return json({ error: "unauthorized" }, 401);
  const b = (await req.json().catch(() => null)) as { project?: string; role?: string } | null;
  if (!b?.project || !projectOf(b.project) || !["ideas", "video"].includes(b.role ?? "")) {
    return json({ error: "body: {project, role: ideas|video}" }, 400);
  }
  const bot = b.role === "ideas" ? botOf({ project: b.project }) : videoBotOf();
  const chat_id = allowedChats(bot)[0];
  if (!tokenOf(bot) || !chat_id) return json({ error: `bot ${bot} has no token or chat` }, 503);
  const what = b.role === "ideas" ? "ideas bot" : "video bot";
  const res = await api("sendMessage", {
    chat_id,
    text: `${labelOf(b.project)}🧪 Test from the viral-scout dashboard: the ${what} can post here.`,
  }, bot);
  if (!res?.ok) return json({ error: res?.description ?? "Telegram did not accept the message" }, 502);
  return json({ ok: true, bot, message_id: res.result?.message_id });
}
