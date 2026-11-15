import { allowedChats, blogBotOf, botConfig, botOf, botSlugs, config, hasPacks, ideaScopeOf, legacyBotOf, REASONS, tokenOf, videoBotOf } from "./config";
import { prisma, type BlogReview, type VideoIdea } from "./db";
import { captureNote, type Msg } from "./notes";
import { api } from "./telegram";
import {
  ASK_WINDOW_MS,
  askKeyboard,
  askText,
  BLOG_STATUS,
  blogKeyboard,
  blogStatusText,
  blogText,
  FINAL,
  HELP,
  ideaText,
  keyboard,
  PACK_KIND,
  packMessages,
  parseCallback,
  scriptKeyboard,
  scriptText,
  STAGE,
  STATUS,
  statusLabel,
  tagList,
  toggleTag,
  type PackSection,
} from "./ui";

/**
 * The ideas bot's actions: store, post, redraw, and handle every button and reply. Ported from the solar site's
 * src/lib/idea-bot.ts; projects and bots come from projects.json (see ./config.ts). The ideas themselves are written
 * on the PC by Claude Code and pushed in through /api/ideas.
 */

/** Appends to the feedback history (IdeaFeedback): every step is kept, VideoIdea only holds the current state. */
export async function logFeedback(ideaId: number, kind: string, value?: string | null) {
  await prisma.ideaFeedback.create({ data: { ideaId, kind, value: value ?? null } }).catch((e) => console.error("Idea feedback log", e));
}

const firstChat = (bot: string) => allowedChats(bot)[0];

/** Queues a content pack for the next Claude run (Telegram 📝 button and the CRM). */
export async function requestPack(idea: VideoIdea): Promise<"queued" | "already" | "refused"> {
  if (!hasPacks(idea) || idea.status === "deleted" || idea.status === "replaced") return "refused";
  if (idea.stage === "pack") return "already";
  await setStage(idea, "pack");
  return "queued";
}

const POSTED = /^(?:re)?posted by the (\S+) bot/;

/**
 * The bot that posted the idea's current message (so the only one that can edit it). Read from the feedback log
 * ("posted by the X bot"); ideas posted before that log existed belong to their project's old bot.
 */
export async function posterOf(i: VideoIdea): Promise<string> {
  const rows = await prisma.ideaFeedback.findMany({ where: { ideaId: i.id, kind: "system" }, orderBy: { id: "desc" }, take: 20 });
  for (const r of rows) {
    const m = POSTED.exec(r.value ?? "");
    if (m && botConfig(m[1])) return m[1];
  }
  return legacyBotOf(i);
}

/**
 * Sends a content pack as replies under the idea and stores it (feedback kind "pack").
 * send = false only stores it (backfill of a pack that already went to Telegram); the stage is left as it is.
 */
export async function postPack(i: VideoIdea, sections: PackSection[], notePath?: string, send = true) {
  await logFeedback(i.id, PACK_KIND, JSON.stringify({ sections, note: notePath ?? null }));
  if (!send) return { idea: i, messages: [] as string[], dryRun: true };
  // Replies go under the idea, so they come from the bot that posted it (message ids are per bot in a basic group).
  const bot = i.tgMessageId ? await posterOf(i) : botOf(i);
  const chat_id = i.tgChatId ?? firstChat(bot);
  const messages = packMessages(i, sections, notePath);
  const dryRun = !tokenOf(bot) || !chat_id;
  if (dryRun) {
    console.info(`[ideas bot skipped: not configured] pack for #${i.id}\n` + messages.map((m) => m.replace(/<[^>]+>/g, "")).join("\n\n────────\n\n"));
  } else {
    for (const text of messages) {
      await api("sendMessage", {
        chat_id,
        text,
        parse_mode: "HTML",
        link_preview_options: { is_disabled: true },
        ...(i.tgMessageId ? { reply_parameters: { message_id: i.tgMessageId, allow_sending_without_reply: true } } : {}),
      }, bot);
    }
  }
  await logFeedback(i.id, "system", `pack sent: ${sections.map((s) => s.title).join(" · ")}${notePath ? ` (${notePath})` : ""}`);
  const done = await setStage(i, "pack_sent");
  return { idea: done, messages, dryRun };
}

/** Posts an idea to every allowed chat and remembers the first message (for edits and reply-comments). */
export async function postIdea(i: VideoIdea) {
  const bot = botOf(i);
  const chats = allowedChats(bot);
  if (!tokenOf(bot) || chats.length === 0) {
    console.info("[ideas bot skipped: not configured]\n" + ideaText(i).replace(/<[^>]+>/g, ""));
    return;
  }
  for (const chat_id of chats) {
    const res = await api("sendMessage", {
      chat_id,
      text: ideaText(i),
      parse_mode: "HTML",
      link_preview_options: { is_disabled: true },
      reply_markup: keyboard(i),
    }, bot);
    const message_id = res?.result?.message_id;
    if (message_id && !i.tgMessageId) {
      i = await prisma.videoIdea.update({ where: { id: i.id }, data: { tgChatId: String(chat_id), tgMessageId: message_id } });
      await logFeedback(i.id, "system", `posted by the ${bot} bot`);
    }
  }
}

/** Posts the idea again, e.g. after its project got its own bot: the old message is deleted by whichever bot sent it. */
export async function repostIdea(i: VideoIdea) {
  if (i.tgChatId && i.tgMessageId) {
    const target = { chat_id: i.tgChatId, message_id: i.tgMessageId };
    // The bot that posted it first, then the others in config order.
    const first = await posterOf(i);
    const order = [first, ...botSlugs().filter((b) => b !== first)];
    for (const bot of order) {
      if (!tokenOf(bot)) continue;
      const del = await api("deleteMessage", target, bot);
      if (del?.ok) break;
    }
  }
  i = await prisma.videoIdea.update({ where: { id: i.id }, data: { tgChatId: null, tgMessageId: null, askMessageId: null, askedAt: null } });
  await postIdea(i);
  await logFeedback(i.id, "system", `reposted by the ${botOf(i)} bot`);
}

/** Sends a (new version of the) scenario for an approved idea to the group, with ✅ / ✏️ buttons. */
export async function postScript(i: VideoIdea, script: string) {
  const bot = videoBotOf();
  const chat_id = firstChat(bot);
  if (!tokenOf(bot) || !chat_id) return i;
  if (i.scriptMessageId) {
    // The old version loses its buttons: only the newest scenario can be approved.
    await api("editMessageReplyMarkup", { chat_id: i.tgChatId ?? chat_id, message_id: i.scriptMessageId, reply_markup: { inline_keyboard: [] } }, bot);
  }
  i = await prisma.videoIdea.update({ where: { id: i.id }, data: { script, stage: "script", stageAt: new Date() } });
  const res = await api("sendMessage", { chat_id, text: scriptText(i), parse_mode: "HTML", reply_markup: scriptKeyboard(i) }, bot);
  const message_id = res?.result?.message_id;
  if (message_id) i = await prisma.videoIdea.update({ where: { id: i.id }, data: { scriptMessageId: message_id } });
  await logFeedback(i.id, "system", "script sent");
  await refreshIdeaMessage(i);
  return i;
}

/** Moves an idea to another production stage (Claude's jobs) and redraws its messages. */
export async function setStage(i: VideoIdea, stage: string, draftPath?: string) {
  i = await prisma.videoIdea.update({ where: { id: i.id }, data: { stage, stageAt: new Date(), ...(draftPath ? { draftPath } : {}) } });
  await logFeedback(i.id, "system", `stage ${stage}`);
  await refreshIdeaMessage(i);
  if (i.scriptMessageId) {
    const bot = videoBotOf();
    await api("editMessageText", {
      chat_id: firstChat(bot),
      message_id: i.scriptMessageId,
      text: scriptText(i),
      parse_mode: "HTML",
      reply_markup: scriptKeyboard(i),
    }, bot);
  }
  return i;
}

/** Redraws the idea message after a change (status, reasons, comment, replaced, tracked). */
export async function refreshIdeaMessage(i: VideoIdea) {
  if (!i.tgChatId || !i.tgMessageId) return;
  await api("editMessageText", {
    chat_id: i.tgChatId,
    message_id: i.tgMessageId,
    text: ideaText(i),
    parse_mode: "HTML",
    link_preview_options: { is_disabled: true },
    reply_markup: keyboard(i),
  }, await posterOf(i));
}

// ───────────── Blog guides: ✅ Publish / ✏️ Changes ─────────────

const blogBot = () => blogBotOf();

/** Sends a blog draft for review; an older waiting version of the same guide loses its buttons. */
export async function postBlogReview(slug: string, title: string, summary: string) {
  const bot = blogBot();
  const chat_id = firstChat(bot);
  for (const old of await prisma.blogReview.findMany({ where: { slug, status: "waiting" } })) {
    const o = await prisma.blogReview.update({ where: { id: old.id }, data: { status: "replaced" } });
    if (o.messageId) await api("editMessageReplyMarkup", { chat_id, message_id: o.messageId, reply_markup: { inline_keyboard: [] } }, bot);
  }
  let b = await prisma.blogReview.create({ data: { slug, title } });
  if (!tokenOf(bot) || !chat_id) return b;
  const res = await api("sendMessage", { chat_id, text: blogText(b, summary), parse_mode: "HTML", reply_markup: blogKeyboard(b) }, bot);
  if (res?.result?.message_id) b = await prisma.blogReview.update({ where: { id: b.id }, data: { messageId: res.result.message_id } });
  return b;
}

/** Status change from Claude's job (published) or the ✅ button; the message keeps its text, the status line is appended. */
export async function setBlogStatus(b: BlogReview, status: string) {
  const bot = blogBot();
  b = await prisma.blogReview.update({ where: { id: b.id }, data: { status, decidedAt: new Date() } });
  if (b.messageId) {
    await api("editMessageReplyMarkup", { chat_id: firstChat(bot), message_id: b.messageId, reply_markup: blogKeyboard(b) }, bot);
    await api("sendMessage", {
      chat_id: firstChat(bot),
      text: blogStatusText(b, status),
      parse_mode: "HTML",
      reply_parameters: { message_id: b.messageId, allow_sending_without_reply: true },
    }, bot);
  }
  return b;
}

/** A plain message to the default bot's chats (e.g. storm alerts). Skipped when that bot isn't configured. */
export async function notifyIdeasChat(text: string) {
  const bot = config().defaultBot;
  const chats = allowedChats(bot);
  if (!tokenOf(bot) || chats.length === 0) {
    console.info("[ideas bot skipped: not configured]\n" + text.replace(/<[^>]+>/g, ""));
    return;
  }
  await Promise.allSettled(chats.map((chat_id) => api("sendMessage", { chat_id, text, parse_mode: "HTML", link_preview_options: { is_disabled: true } }, bot)));
}

// ───────────── Button handlers ─────────────

type Query = { id: string; data?: string; message?: { message_id: number; chat: { id: number } } };
export type Update = { callback_query?: Query; message?: Msg };

const answer = (bot: string, q: Query, text?: string, show_alert?: boolean) =>
  api("answerCallbackQuery", { callback_query_id: q.id, ...(text !== undefined ? { text } : {}), ...(show_alert ? { show_alert } : {}) }, bot);

/** 📝 Пости: queue a content pack for the next Claude run (the texts are written on the PC, not here). */
async function handlePack(q: Query, idea: VideoIdea) {
  const bot = await posterOf(idea);
  if (!hasPacks(idea) || idea.status === "deleted" || idea.status === "replaced") return answer(bot, q, "Для цієї ідеї пости не робимо");
  if ((await requestPack(idea)) === "already") return answer(bot, q, "📝 Вже в черзі");
  await answer(bot, q, "📝 Claude напише пости при наступному запуску (щодня о 8:15, коли ПК увімкнений) і надішле їх відповідями під ідеєю.", true);
}

async function handleScript(q: Query, idea: VideoIdea, a: "ok" | "edit") {
  const bot = videoBotOf();
  if (idea.stage !== "script") return answer(bot, q, STAGE[idea.stage ?? ""] ?? "Сценарій вже не активний");
  if (a === "edit")
    return answer(bot, q, "Відповідай (reply) на сценарій: що змінити (текстом або голосом). Claude перепише й надішле нову версію.", true);
  await logFeedback(idea.id, "rating", "script approved");
  await setStage(idea, "script_ok");
  await answer(bot, q, "✅ Claude візьме в роботу (коли ПК увімкнений)");
}

async function handleBlog(q: Query, id: number, a: "ok" | "edit") {
  const bot = blogBot();
  const b = await prisma.blogReview.findUnique({ where: { id } });
  if (!b || b.status !== "waiting") return answer(bot, q, b ? (BLOG_STATUS[b.status] ?? b.status) : "Не знайдено");
  if (a === "edit")
    return answer(bot, q, "Відповідай (reply) на це повідомлення: що змінити (текстом або голосом). Claude перепише й надішле нову версію.", true);
  await setBlogStatus(b, "approved");
  await answer(bot, q, "✅ Claude опублікує (коли ПК увімкнений)");
}

/** After a rating or request: ask "why?" with reason buttons; the previous question for this idea is removed. */
async function askWhy(i: VideoIdea, chat_id: number) {
  const bot = await posterOf(i);
  if (i.askMessageId) await api("deleteMessage", { chat_id, message_id: i.askMessageId }, bot);
  const res = await api("sendMessage", { chat_id, text: askText(i), parse_mode: "HTML", reply_markup: askKeyboard(i) }, bot);
  const message_id = res?.result?.message_id;
  if (message_id) await prisma.videoIdea.update({ where: { id: i.id }, data: { askMessageId: message_id, askedAt: new Date() } });
}

async function handleTag(q: Query, idea: VideoIdea, code: string) {
  const bot = await posterOf(idea);
  const id = idea.id;
  const target = { chat_id: q.message!.chat.id, message_id: q.message!.message_id, parse_mode: "HTML" };
  if (code === "undo") {
    // Back to "waiting": rating and reasons go, comments stay.
    const updated = await prisma.videoIdea.update({ where: { id }, data: { status: "sent", tags: null, askedAt: null, askMessageId: null } });
    await logFeedback(id, "undo", idea.status);
    await Promise.all([
      answer(bot, q, "↩️ Оцінку скасовано"),
      api("deleteMessage", { chat_id: target.chat_id, message_id: target.message_id }, bot),
      refreshIdeaMessage(updated),
    ]);
    return;
  }
  if (code === "tored") {
    const status = "redo";
    const updated = await prisma.videoIdea.update({ where: { id }, data: { status, tags: null, askedAt: new Date() } });
    await logFeedback(id, "rating", status);
    await Promise.all([
      answer(bot, q, STATUS[status]),
      api("editMessageText", { ...target, text: askText(updated), reply_markup: askKeyboard(updated) }, bot),
      refreshIdeaMessage(updated),
    ]);
    return;
  }
  if (code === "done") {
    const updated = await prisma.videoIdea.update({ where: { id }, data: { askedAt: null } });
    await Promise.all([
      answer(bot, q, "✔️ Записав"),
      api("editMessageText", { ...target, text: askText(updated, true), reply_markup: { inline_keyboard: [] } }, bot),
    ]);
    return;
  }
  const reasons = REASONS();
  if (!reasons[code]) return;
  const next = toggleTag(tagList(idea), code);
  const updated = await prisma.videoIdea.update({ where: { id }, data: { tags: next.length ? next.join(",") : null, askedAt: new Date() } });
  await logFeedback(id, next.includes(code) ? "tag" : "untag", code);
  await Promise.all([
    answer(bot, q, next.includes(code) ? `✓ ${reasons[code]}` : "Прибрав"),
    api("editMessageText", { ...target, text: askText(updated), reply_markup: askKeyboard(updated) }, bot),
    refreshIdeaMessage(updated),
  ]);
}

async function handleMenu(q: Query, idea: VideoIdea, action: "more" | "back" | "del" | "delyes") {
  const bot = await posterOf(idea);
  const target = { chat_id: q.message!.chat.id, message_id: q.message!.message_id };
  if (action === "delyes") {
    const updated = await prisma.videoIdea.update({ where: { id: idea.id }, data: { status: "deleted", askedAt: null } });
    await logFeedback(idea.id, "delete", idea.status);
    await answer(bot, q, "🗑 Видалено");
    if (idea.askMessageId) await api("deleteMessage", { chat_id: target.chat_id, message_id: idea.askMessageId }, bot);
    // Bots can delete their own messages for 48 h; after that the message is struck through instead.
    const del = await api("deleteMessage", target, bot);
    if (!del?.ok) await refreshIdeaMessage(updated);
    return;
  }
  const view = action === "more" ? "more" : action === "del" ? "del" : "main";
  await Promise.all([
    answer(bot, q, action === "del" ? "Точно видалити?" : undefined),
    api("editMessageReplyMarkup", { ...target, reply_markup: keyboard(idea, view) }, bot),
  ]);
}

/** One Telegram update for `bot` (a button press or a message), from its webhook or a forward. */
export async function handleIdeasUpdate(update: Update, bot: string) {
  const q = update.callback_query;
  if (q?.data && q.message) {
    if (!allowedChats(bot).includes(String(q.message.chat.id))) return answer(bot, q, "⛔ Немає доступу", true);
    const cb = parseCallback(q.data);
    if (!cb) return answer(bot, q, q.data.startsWith("b:") ? "Не знайдено" : "Ідею не знайдено", !q.data.startsWith("b:"));
    if (cb.kind === "b") return handleBlog(q, cb.id, cb.action); // blog guide review, not an idea
    const idea = await prisma.videoIdea.findUnique({ where: { id: cb.id } });
    if (!idea) return answer(bot, q, "Ідею не знайдено", true);
    if (cb.kind === "s") return handleScript(q, idea, cb.action); // the scenario of an approved (often already "tracked") idea
    if (cb.kind === "p") return handlePack(q, idea); // content pack request (often on a "tracked" idea)
    if (FINAL.includes(idea.status)) return answer(bot, q, STATUS[idea.status]);
    if (cb.kind === "t") return handleTag(q, idea, cb.code);
    if (cb.kind === "m") return handleMenu(q, idea, cb.action);
    const status = cb.status;
    if (!status) return answer(bot, q);
    // A new rating gets its own reasons (old tags described the old rating); comments stay.
    const updated = await prisma.videoIdea.update({ where: { id: idea.id }, data: status === idea.status ? {} : { status, tags: null } });
    if (status !== idea.status) await logFeedback(idea.id, "rating", status);
    await Promise.all([answer(bot, q, statusLabel(updated)), refreshIdeaMessage(updated), askWhy(updated, q.message.chat.id)]);
    return;
  }

  const m = update.message;
  if (!m || !allowedChats(bot).includes(String(m.chat.id))) return;
  const note = (msg: Msg) => captureNote(bot, msg); // a bot with notes "off" (a CRM bot) keeps nothing
  if (!m.text) {
    await note(m); // voice / photo / video replies for Claude
    return;
  }
  if (m.text.startsWith("/")) {
    await api("sendMessage", { chat_id: m.chat.id, text: HELP, parse_mode: "HTML" }, bot);
    // Ideas pushed before the first /start couldn't be delivered (a bot can't message first): post them now.
    const waiting = await prisma.videoIdea.findMany({ where: { status: "sent", tgMessageId: null }, orderBy: { id: "asc" } });
    for (const idea of waiting.filter((i) => botOf(i) === bot)) await postIdea(idea);
    return;
  }
  // Which idea: a reply to the idea or to its "why?" question; otherwise the idea asked about in the last hour.
  // Only this bot's ideas: in a basic group every bot numbers messages on its own, so message ids repeat across bots.
  // The candidates are narrowed to the ideas whose current message this bot posted (posterOf).
  const mine = ideaScopeOf(bot);
  const replyTo = m.reply_to_message?.message_id;
  const candidates = replyTo
    ? await prisma.videoIdea.findMany({ where: { ...mine, OR: [{ tgChatId: String(m.chat.id), tgMessageId: replyTo }, { askMessageId: replyTo }] }, orderBy: { id: "desc" }, take: 10 })
    : await prisma.videoIdea.findMany({ where: { ...mine, askedAt: { gte: new Date(Date.now() - ASK_WINDOW_MS) } }, orderBy: { askedAt: "desc" }, take: 10 });
  let idea: VideoIdea | null = null;
  for (const c of candidates) if ((await posterOf(c)) === bot) { idea = c; break; }
  // Not about an idea: a reply to another message of this bot (e.g. a video) or "Claude, …" → a note for Claude.
  // Anything else in the group is people talking: stay quiet.
  if (!idea || idea.status === "deleted" || (!replyTo && /^\s*(#?claude|клод)\b/i.test(m.text))) {
    await note(m);
    return;
  }
  const comment = idea.comment ? `${idea.comment}\n${m.text}` : m.text;
  const updated = await prisma.videoIdea.update({
    where: { id: idea.id },
    // The message shows the latest 2000 characters; the full text of every comment is in the feedback log.
    data: { comment: comment.slice(-2000), ...(idea.askedAt ? { askedAt: new Date() } : {}) },
  });
  await logFeedback(idea.id, "comment", m.text);
  await Promise.all([
    refreshIdeaMessage(updated),
    api("sendMessage", { chat_id: m.chat.id, text: `💬 Записав до ідеї #${idea.id}. Можеш дописати ще або натиснути «✔️ Готово».`, reply_to_message_id: m.message_id }, bot),
  ]);
}

