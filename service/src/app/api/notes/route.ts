import { createHmac } from "node:crypto";
import { apiSecret, allowedChats, config, projectOf, projectSlugs, tokenOf } from "@/lib/config";
import { prisma } from "@/lib/db";
import { bearer, safeEqual } from "@/lib/auth";
import { api } from "@/lib/telegram";

/**
 * Owner notes for the unattended jobs (client: viral-scout's `python -m viral_scout notes`, see viral_scout/notes.py).
 * Notes are ClaudeNote rows, stored per bot; a project reads the notes of its own bot (projects.<slug>.bot).
 * Auth: "Authorization: Bearer <IDEAS_API_SECRET>" (full access only, no CRM keys).
 *   GET   ?project=…&status=new|all[&limit=20]  → {notes: [{id, created_at, from, kind, status, text, about, file_url, result}]}
 *   GET   ?project=…&pending=1                 → {pending: n}: new notes, plus blog guides approved with ✅ for the
 *                                                blog bot (like solar's notes.mjs pending)
 *   GET   ?file=<id>&sig=<hmac>                → the note's Telegram file, proxied (no auth header; the signed link is the key)
 *   PATCH {id, project, status: done|skipped|open, result?, reply?}   reply = answer in the note's thread
 *   POST  multipart: project, caption, reply_to?, file → {message_id}  (sent to the project bot's first allowed chat)
 * The bot token never leaves the service: file links point back here with an HMAC of the note id.
 */

export const dynamic = "force-dynamic";

const full = (req: Request) => safeEqual(bearer(req), apiSecret());
const json = (body: unknown, status = 200) => Response.json(body, { status });
const botFor = (project: string | null) => (project && projectOf(project) ? projectOf(project)!.bot : null);
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
  const bot = botFor(url.searchParams.get("project"));
  if (!bot) return json({ error: `project must be one of ${projectSlugs().join(", ")}` }, 400);
  if (url.searchParams.get("pending")) {
    const notes = await prisma.claudeNote.count({ where: { bot, status: "new" } });
    const blog = config().blog?.bot === bot ? await prisma.blogReview.count({ where: { status: "approved" } }) : 0;
    return json({ pending: notes + blog });
  }
  const all = url.searchParams.get("status") === "all";
  const limit = Math.min(Math.max(Number(url.searchParams.get("limit")) || (all ? 20 : 100), 1), 200);
  const notes = (await prisma.claudeNote.findMany({
    where: all ? { bot } : { bot, status: "new" },
    orderBy: { id: all ? "desc" : "asc" },
    take: limit,
  })) as Note[];
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
  const bot = botFor(b?.project ?? null);
  if (!b || !bot || !Number.isInteger(b.id) || !["done", "skipped", "open"].includes(b.status ?? "")) {
    return json({ error: "body: {id, project, status: done|skipped|open, result?, reply?}" }, 400);
  }
  const n = (await prisma.claudeNote.findUnique({ where: { id: b.id } })) as Note | null;
  if (!n || n.bot !== bot) return json({ error: "no such note for this project" }, 404);
  const status = b.status === "open" ? "new" : b.status!;
  await prisma.claudeNote.update({
    where: { id: n.id },
    data: { status, doneAt: status === "new" ? null : new Date(), result: b.result?.slice(0, 2000) ?? n.result },
  });
  if (b.reply?.trim()) {
    await api("sendMessage", { chat_id: n.chatId, text: b.reply.slice(0, 3900), reply_parameters: { message_id: n.messageId } }, bot);
  }
  return json({ ok: true });
}

export async function POST(req: Request) {
  if (!full(req)) return json({ error: "unauthorized" }, 401);
  const form = await req.formData().catch(() => null);
  const bot = botFor((form?.get("project") as string | null) ?? null);
  const f = form?.get("file");
  if (!form || !bot || !(f instanceof Blob)) return json({ error: "multipart: project, file, caption?, reply_to?" }, 400);
  const token = tokenOf(bot);
  const chat = allowedChats(bot)[0];
  if (!token || !chat) return json({ error: `bot ${bot} has no token or chat configured` }, 503);
  const out = new FormData();
  out.set("chat_id", chat);
  out.set("document", f, (f as File).name || "file");
  const caption = String(form.get("caption") ?? "").slice(0, 1024);
  if (caption) out.set("caption", caption);
  const replyTo = Number(form.get("reply_to"));
  if (Number.isInteger(replyTo) && replyTo > 0) {
    const n = (await prisma.claudeNote.findUnique({ where: { id: replyTo } })) as Note | null;
    if (n && n.bot === bot) out.set("reply_parameters", JSON.stringify({ message_id: n.messageId }));
  }
  const r = await fetch(`https://api.telegram.org/bot${token}/sendDocument`, { method: "POST", body: out });
  const res = (await r.json().catch(() => ({}))) as { ok?: boolean; description?: string; result?: { message_id?: number } };
  if (!res.ok) return json({ error: res.description ?? `Telegram ${r.status}` }, 502);
  return json({ message_id: res.result?.message_id });
}
