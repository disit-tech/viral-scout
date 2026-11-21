import { createHmac } from "node:crypto";
import { apiSecret, allowedChats, config, labelOf, noteBotsFor, noteProjectOf, projectSlugs, tokenOf, videoBotOf } from "@/lib/config";
import { prisma } from "@/lib/db";
import { bearer, safeEqual } from "@/lib/auth";
import { api } from "@/lib/telegram";
import { tagsLine } from "@/lib/ui";

/**
 * Owner notes for the unattended jobs (client: viral-scout's `python -m viral_scout notes`, see viral_scout/notes.py).
 * Notes are ClaudeNote rows, stored per bot. A project reads the notes of the video bot (shared by every project:
 * a note belongs to the project whose header label starts the message it replies to, else to defaultProject) and of
 * its own older bot (projects.<slug>.bot). Files go out through the video bot, headed with the project's label.
 * Auth: "Authorization: Bearer <IDEAS_API_SECRET>" (full access only, no CRM keys).
 *   GET   ?project=…&status=new|all[&limit=20]  → {notes: [{id, created_at, from, kind, status, text, about, file_url, result}]}
 *   GET   ?project=…&pending=1                 → {pending: n}: new notes, plus blog guides approved with ✅ for the
 *                                                blog bot (like solar's notes.mjs pending)
 *   GET   ?file=<id>&sig=<hmac>                → the note's Telegram file, proxied (no auth header; the signed link is the key)
 *   PATCH {id, project, status: done|skipped|open, result?, reply?}   reply = answer in the note's thread
 *   POST  multipart: project, caption, tags?, reply_to?, file → {message_id}  (caption ends with the hashtags: business, file kind, tags)  (sent to the project bot's first allowed chat)
 *   POST  JSON {project, prepare: true, name, caption?, tags?, reply_to?} → {bot_id, chat_id, method, field, caption, reply_parameters?}
 *         the same send planned, nothing sent: the PC uploads files over Vercel's ~4.5 MB body limit to the Bot API itself
 * The bot token never leaves the service: file links point back here with an HMAC of the note id.
 */

export const dynamic = "force-dynamic";

const full = (req: Request) => safeEqual(bearer(req), apiSecret());
const json = (body: unknown, status = 200) => Response.json(body, { status });
const botsFor = noteBotsFor;
const noteProject = noteProjectOf;
const sigOf = (id: number) => createHmac("sha256", apiSecret() ?? "").update(`note-file:${id}`).digest("hex").slice(0, 32);

type Note = {
  id: number; createdAt: Date; bot: string; chatId: string; messageId: number; fromName: string | null; kind: string;
  text: string | null; fileId: string | null; replyToText: string | null; status: string; result: string | null;
};

const shape = (n: Note, origin: string) => ({
  id: n.id,
  created_at: n.createdAt.toISOString(),
  from: n.fromName,
  kind: n.kind,
  status: n.status,
  text: n.text,
  about: n.replyToText,
  file_url: n.fileId ? `${origin}/api/notes?file=${n.id}&sig=${sigOf(n.id)}` : null,
  result: n.result,
});

export async function GET(req: Request) {
  const url = new URL(req.url);
  const fileId = url.searchParams.get("file");
  if (fileId) return file(Number(fileId), url.searchParams.get("sig"));
  if (!full(req)) return json({ error: "unauthorized" }, 401);
  const project = url.searchParams.get("project");
  const bots = botsFor(project);
  if (!bots) return json({ error: `project must be one of ${projectSlugs().join(", ")}` }, 400);
  const mine = (rows: Note[]) => rows.filter((n) => noteProject(n) === project);
  if (url.searchParams.get("pending")) {
    const fresh = mine((await prisma.claudeNote.findMany({ where: { bot: { in: bots }, status: "new" }, take: 500 })) as Note[]);
    // Approved blog guides wait for the blog job of the default project (the blog is the solar site's).
    const blog = project === config().defaultProject && config().blog ? await prisma.blogReview.count({ where: { status: "approved" } }) : 0;
    return json({ pending: fresh.length + blog });
  }
  const all = url.searchParams.get("status") === "all";
  const limit = Math.min(Math.max(Number(url.searchParams.get("limit")) || (all ? 20 : 100), 1), 200);
  const notes = mine((await prisma.claudeNote.findMany({
    where: all ? { bot: { in: bots } } : { bot: { in: bots }, status: "new" },
    orderBy: { id: all ? "desc" : "asc" },
    take: 500,
  })) as Note[]).slice(0, limit);
  return json({ notes: notes.map((n) => shape(n, url.origin)) });
}

async function file(id: number, sig: string | null) {
  if (!Number.isInteger(id) || id <= 0 || !apiSecret() || !safeEqual(sig, sigOf(id))) return json({ error: "unauthorized" }, 401);
  const n = (await prisma.claudeNote.findUnique({ where: { id } })) as Note | null;
  const token = n && tokenOf(n.bot);
  if (!n?.fileId || !token) return json({ error: "no file" }, 404);
  const meta = await api("getFile", { file_id: n.fileId }, n.bot);
  const path = (meta?.result as { file_path?: string } | undefined)?.file_path;
  if (!path) return json({ error: "file not available (Telegram keeps bot files for a limited time)" }, 404);
  const r = await fetch(`https://api.telegram.org/file/bot${token}/${path}`);
  if (!r.ok || !r.body) return json({ error: `download failed: ${r.status}` }, 502);
  const name = path.split("/").pop() ?? `note-${id}`;
  return new Response(r.body, {
    headers: { "Content-Type": r.headers.get("content-type") ?? "application/octet-stream", "Content-Disposition": `attachment; filename="${name}"` },
  });
}

export async function PATCH(req: Request) {
  if (!full(req)) return json({ error: "unauthorized" }, 401);
  const b = (await req.json().catch(() => null)) as
    | { id?: number; project?: string; status?: string; result?: string; reply?: string }
    | null;
  const bots = botsFor(b?.project ?? null);
  if (!b || !bots || !Number.isInteger(b.id) || !["done", "skipped", "open"].includes(b.status ?? "")) {
    return json({ error: "body: {id, project, status: done|skipped|open, result?, reply?}" }, 400);
  }
  const n = (await prisma.claudeNote.findUnique({ where: { id: b.id } })) as Note | null;
  if (!n || !bots.includes(n.bot) || noteProject(n) !== b.project) return json({ error: "no such note for this project" }, 404);
  const bot = n.bot; // answer in the note's thread, through the bot that received it
  const status = b.status === "open" ? "new" : b.status!;
  await prisma.claudeNote.update({
    where: { id: n.id },
    data: { status, doneAt: status === "new" ? null : new Date(), result: b.result?.slice(0, 2000) ?? n.result },
  });
  if (b.reply?.trim()) {
    const tags = tagsLine(b.project, ["reply"]);
    await api("sendMessage", { chat_id: n.chatId, text: `${b.reply.trim().slice(0, 3800)}\n\n${tags}`, reply_parameters: { message_id: n.messageId } }, bot);
  }
  return json({ ok: true });
}

/** How a file goes to the group: the video bot's first chat, the project's header first and the tags last. */
async function planFor(project: string, name: string, captionIn: string, tagsIn: string, replyToIn: unknown) {
  const bot = videoBotOf();
  const token = tokenOf(bot);
  const chat = allowedChats(bot)[0];
  if (!token || !chat) return null;
  // Like the old notes.mjs: videos play in the chat, images show inline, anything else is a file.
  const kind = /\.(mp4|mov|m4v)$/i.test(name) ? "video" : /\.(jpe?g|png|webp)$/i.test(name) ? "photo" : "document";
  const method = { video: "sendVideo", photo: "sendPhoto", document: "sendDocument" }[kind];
  // The project's header goes first, so a reply to the file is a note for that project.
  // Tags last (business, file kind, and any extra words the job passed in `tags`, e.g. "film tiktok idea92"), kept whole
  // when the caption has to be cut to Telegram's 1024 characters.
  const extra = tagsIn.split(/[\s,]+/).filter(Boolean);
  const tags = tagsLine(project, [{ video: "video", photo: "image", document: "file" }[kind]!, ...extra]);
  const body = `${labelOf(project)}${captionIn}`.trim();
  const caption = `${body.slice(0, 1024 - tags.length - 2)}\n\n${tags}`.trim();
  let reply_parameters: { message_id: number } | undefined;
  const replyTo = Number(replyToIn);
  if (Number.isInteger(replyTo) && replyTo > 0) {
    const n = (await prisma.claudeNote.findUnique({ where: { id: replyTo } })) as Note | null;
    if (n && n.bot === bot) reply_parameters = { message_id: n.messageId };
  }
  return { bot, token, chat, kind, method, caption, reply_parameters };
}

/**
 * POST multipart (file ≤ ~4.5 MB, Vercel's request body limit) → sent here. POST JSON {project, prepare: true, name,
 * caption?, tags?, reply_to?} → the plan only, so the PC can upload a bigger file (Telegram: 50 MB) straight to the
 * Bot API with the same bot, chat, caption and reply target. The plan carries the bot's numeric id (public, the part
 * of the token before ":") so the client can check its token is this bot's; never the token.
 */
export async function POST(req: Request) {
  if (!full(req)) return json({ error: "unauthorized" }, 401);
  if ((req.headers.get("content-type") ?? "").includes("application/json")) {
    const b = (await req.json().catch(() => null)) as
      | { project?: string; prepare?: boolean; name?: string; caption?: string; tags?: string; reply_to?: number }
      | null;
    if (!b?.prepare || !botsFor(b.project ?? null) || !b.name) return json({ error: "JSON: {project, prepare: true, name, caption?, tags?, reply_to?}" }, 400);
    const p = await planFor(b.project!, b.name, String(b.caption ?? ""), String(b.tags ?? ""), b.reply_to);
    if (!p) return json({ error: `bot ${videoBotOf()} has no token or chat configured` }, 503);
    return json({
      bot_id: p.token.split(":")[0], chat_id: p.chat, method: p.method, field: p.kind, caption: p.caption,
      ...(p.reply_parameters ? { reply_parameters: p.reply_parameters } : {}),
    });
  }
  const form = await req.formData().catch(() => null);
  const project = (form?.get("project") as string | null) ?? null;
  const bots = botsFor(project);
  const f = form?.get("file");
  if (!form || !bots || !(f instanceof Blob)) return json({ error: "multipart: project, file, caption?, reply_to?" }, 400);
  const name = (f as File).name || "file";
  const p = await planFor(project!, name, String(form.get("caption") ?? ""), String(form.get("tags") ?? ""), form.get("reply_to"));
  if (!p) return json({ error: `bot ${videoBotOf()} has no token or chat configured` }, 503);
  const out = new FormData();
  out.set("chat_id", p.chat);
  out.set(p.kind, f, name);
  if (p.kind === "video") out.set("supports_streaming", "true");
  if (p.caption) out.set("caption", p.caption);
  if (p.reply_parameters) out.set("reply_parameters", JSON.stringify(p.reply_parameters));
  const r = await fetch(`https://api.telegram.org/bot${p.token}/${p.method}`, { method: "POST", body: out });
  const res = (await r.json().catch(() => ({}))) as { ok?: boolean; description?: string; result?: { message_id?: number } };
  if (!res.ok) return json({ error: res.description ?? `Telegram ${r.status}` }, 502);
  return json({ message_id: res.result?.message_id });
}
