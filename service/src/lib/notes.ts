import { allowedChats, botConfig, tokenOf } from "./config";
import { prisma } from "./db";

/**
 * Notes for Claude from the Telegram group (ported from the solar site's src/lib/claude-notes.ts).
 * Stored: a reply to any message of this bot, or (only the bot with notes "replies+call") a message starting with
 * "Claude" / "Клод" / "#claude". Claude Code reads them on the PC with `npm run notes` (site/scripts/notes.mjs), which
 * picks the token by ClaudeNote.bot: keep the bot slugs ("ideas", "agency") as they are.
 */

export type Msg = {
  message_id: number;
  chat: { id: number };
  from?: { first_name?: string; username?: string; is_bot?: boolean };
  text?: string;
  caption?: string;
  voice?: { file_id: string };
  audio?: { file_id: string };
  photo?: { file_id: string }[];
  video?: { file_id: string };
  document?: { file_id: string };
  reply_to_message?: { message_id: number; from?: { id: number }; text?: string; caption?: string };
};

export const CALL_CLAUDE = /^\s*(#?claude|клод)\b[\s,:-]*/i;

/** Should this bot keep the message as a note? Pure, for tests. */
export function noteDecision(bot: string, m: Msg | undefined, token: string | undefined, chats: string[]) {
  const mode = botConfig(bot)?.notes ?? "off";
  if (mode === "off" || !m || !token || m.from?.is_bot || !chats.includes(String(m.chat.id))) return null;
  const body = m.text ?? m.caption ?? "";
  const botId = Number(token.split(":")[0]);
  const reply = m.reply_to_message;
  const toThisBot = reply?.from?.id === botId;
  // A plain "Claude …" message: only one bot stores it, or it would be saved twice.
  if (!toThisBot && !(mode === "replies+call" && !reply && CALL_CLAUDE.test(body))) return null;
  if (body.startsWith("/")) return null;
  const file = m.voice ?? m.audio ?? m.video ?? m.document ?? m.photo?.at(-1);
  const kind = m.voice ? "voice" : m.audio ? "audio" : m.video ? "video" : m.document ? "document" : m.photo ? "photo" : "text";
  if (!body && !file) return null;
  return {
    bot,
    chatId: String(m.chat.id),
    messageId: m.message_id,
    fromName: m.from?.username ? `@${m.from.username}` : (m.from?.first_name ?? null),
    kind,
    text: toThisBot ? body || null : body.replace(CALL_CLAUDE, "") || null,
    fileId: file?.file_id ?? null,
    replyToMessageId: reply?.message_id ?? null,
    replyToText: (reply?.text ?? reply?.caption ?? "").slice(0, 1000) || null,
  };
}

/** True when the message was saved as a note. The bot puts 👀 on it so the owner sees it was saved. */
export async function captureNote(bot: string, m: Msg | undefined): Promise<boolean> {
  const token = tokenOf(bot);
  const data = noteDecision(bot, m, token, allowedChats(bot));
  if (!data || !m) return false;
  await prisma.claudeNote.upsert({
    where: { chatId_messageId: { chatId: data.chatId, messageId: data.messageId } },
    update: {},
    create: data,
  });
  await fetch(`https://api.telegram.org/bot${token}/setMessageReaction`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: m.chat.id, message_id: m.message_id, reaction: [{ type: "emoji", emoji: "👀" }] }),
  }).catch(() => undefined);
  return true;
}
