import type { BlogReview, VideoIdea } from "./db";
import { config, hasPacks, labelOf, PLATFORMS, REASONS, reasonsFor } from "./config";
import { esc } from "./telegram";

/**
 * Everything the bot shows: message texts, keyboards and callback data. Pure functions (no DB, no Telegram), ported
 * 1:1 from the solar site's src/lib/idea-bot.ts; the per-project parts (header label, reasons, packs, platforms) come
 * from projects.json.
 *
 * Callback data: i:<id>:<action> rate/request · m:<id>:<more|back|del|delyes> menu · t:<id>:<reason|done|undo|tored>
 * "why?" question · p:<id>:req content pack · s:<id>:<ok|edit> scenario · b:<id>:<ok|edit> blog review
 */

export const STATUS: Record<string, string> = {
  sent: "⏳ чекає оцінки",
  good: "👍 Норм",
  bad: "👎 Погано",
  redo: "🔁 Переробити (при наступній генерації)",
  approved: "✅ У трекер (додам при наступній генерації)",
  expand: "📝 Розгорнути (при наступній генерації)",
  variants: "🧬 3 варіації (при наступній генерації)",
  replaced: "♻️ Замінено новою версією",
  varied: "🧬 Варіації надіслано",
  tracked: "📋 У трекері",
  deleted: "🗑 Видалено",
};
export const ACTIONS: Record<string, string> = { g: "good", b: "bad", r: "redo", a: "approved", x: "expand", v: "variants" };
/** Statuses after which the idea message has no buttons any more. */
export const FINAL = ["replaced", "varied", "tracked", "deleted"];
/** Production stages after an idea is approved (VideoIdea.stage). */
export const STAGE: Record<string, string> = {
  script: "📝 сценарій чекає на тебе",
  script_ok: "✅ сценарій затверджено, Claude робить відео",
  making: "⚙️ відео в роботі",
  draft: "🎞 чернетка відео в групі",
  posted: "📤 опубліковано",
  pack: "📝 пости: Claude підготує при наступному запуску",
  pack_sent: "📝 пости надіслано (відповіді під ідеєю)",
};

export const platformList = (i: { platforms?: string | null }) =>
  i.platforms ? i.platforms.split(",").filter((k) => PLATFORMS()[k]) : [];

/** ✅ on a pack project also means "write the posts". */
export const statusLabel = (i: Pick<VideoIdea, "project" | "status">) =>
  hasPacks(i) && i.status === "approved" ? "✅ У трекер + 📝 пости (при наступній генерації)" : (STATUS[i.status] ?? i.status);

const QUESTION: Record<string, string> = {
  good: "Що сподобалось?",
  approved: "Що сподобалось?",
  bad: "Відкинуто: схожого більше не буде. Чому ідея не жива?",
  redo: "Основа ок, міняємо виконання. Що змінити?",
  expand: "Що додати?",
  variants: "Які варіації?",
};
/** 👎 → 🔁 right in the question, when the idea turns out to be worth saving. */
export const SWITCH: Record<string, { code: string; text: string }> = {
  bad: { code: "tored", text: "🔁 Ні, краще переробити" },
};
/** Plain text (not a reply) within this window after a "why?" question goes to that idea. */
export const ASK_WINDOW_MS = 60 * 60 * 1000;

export const tagList = (i: Pick<VideoIdea, "tags">) => (i.tags ? i.tags.split(",").filter((t) => REASONS()[t]) : []);

export type Button = { text: string; callback_data: string };
export type Keyboard = { inline_keyboard: Button[][] };

export function ideaText(i: VideoIdea) {
  const label = labelOf(i.project);
  if (i.status === "deleted") return `🗑 <s>${label}Ідея #${i.id}: ${esc(i.title)}</s>`;
  const platforms = platformList(i);
  return [
    `${label}💡 <b>Ідея #${i.id}</b>${i.rubric ? ` · ${esc(i.rubric)}` : ""}${i.version > 1 ? ` · v${i.version} (замість #${i.parentId})` : ""}${i.version === 1 && i.parentId ? ` · 🧬 варіація #${i.parentId}` : ""}`,
    `🎬 <b>${esc(i.title)}</b>`,
    `🪝 ${i.hookType ? `<i>${esc(i.hookType)}</i>: ` : ""}"${esc(i.hook)}"`,
    i.angle ? `🎯 ${esc(i.angle)}` : null,
    i.fact ? `📊 ${esc(i.fact)}${i.source ? ` (${esc(i.source)})` : ""}` : null,
    i.visual ? `🎞️ ${esc(i.visual)}` : null,
    i.cta ? `📣 ${esc(i.cta)}` : null,
    i.why ? `🕐 Чому зараз: ${esc(i.why)}` : null,
    platforms.length ? `📲 Де постити: ${platforms.map((k) => PLATFORMS()[k]).join(" · ")}` : null,
    i.score != null ? `⭐ Самооцінка: ${i.score}/50` : null,
    "",
    `Оцінка: <b>${statusLabel(i)}</b>`,
    i.stage ? `🎬 Виробництво: <b>${STAGE[i.stage] ?? i.stage}</b>` : null,
    tagList(i).length ? `🏷 ${tagList(i).map((t) => REASONS()[t]).join(" · ")}` : null,
    i.comment ? `💬 ${esc(i.comment)}` : `<i>Коментар: відповідай на це повідомлення текстом.</i>`,
  ]
    .filter((l) => l !== null)
    .join("\n");
}

export function packButton(i: Pick<VideoIdea, "id" | "stage">): Button {
  const text = i.stage === "pack" ? "📝 Пости: в черзі" : i.stage === "pack_sent" ? "📝 Пости ще раз" : "📝 Пости";
  return { text, callback_data: `p:${i.id}:req` };
}

/** Idea message buttons. view: main (rating) · more (expand / variants / delete) · del (confirm delete). */
export function keyboard(i: VideoIdea, view: "main" | "more" | "del" = "main"): Keyboard {
  // A tracked idea of a pack project keeps one button: ask for (more) posts.
  if (i.status === "tracked" && hasPacks(i)) return { inline_keyboard: [[packButton(i)]] };
  if (FINAL.includes(i.status)) return { inline_keyboard: [] };
  const mark = (a: string, label: string): Button => ({
    text: ACTIONS[a] === i.status ? `• ${label} •` : label,
    callback_data: `i:${i.id}:${a}`,
  });
  const menu = (a: string, label: string): Button => ({ text: label, callback_data: `m:${i.id}:${a}` });
  if (view === "del") return { inline_keyboard: [[menu("delyes", "🗑 Так, видалити"), menu("back", "⬅️ Ні, назад")]] };
  if (view === "more")
    return {
      inline_keyboard: [
        [mark("x", "📝 Розгорнути"), mark("v", "🧬 3 варіації")],
        [menu("del", "🗑 Видалити")],
        [menu("back", "⬅️ Назад")],
      ],
    };
  return {
    inline_keyboard: [
      [mark("g", "👍 Норм"), mark("b", "👎 Погано")],
      [mark("r", "🔁 Переробити"), mark("a", "✅ У трекер")],
      [menu("more", i.status === "expand" || i.status === "variants" ? `⋯ Ще (${STATUS[i.status].split(" (")[0]})` : "⋯ Ще")],
    ],
  };
}

export function askText(i: VideoIdea, done = false) {
  const tags = tagList(i).map((t) => REASONS()[t]);
  return [
    `${done ? "✔️" : "❓"} <b>Ідея #${i.id}</b> «${esc(i.title)}» → ${STATUS[i.status] ?? i.status}`,
    done
      ? tags.length || i.comment
        ? "Записав. Врахую при наступній генерації."
        : "Без деталей: врахую лише оцінку."
      : `<b>${QUESTION[i.status] ?? "Чому?"}</b> Обери кілька пунктів і/або просто напиши текстом: що завгодно, кількома повідомленнями, протягом години.`,
    tags.length ? `🏷 ${tags.join(" · ")}` : null,
  ]
    .filter((l) => l !== null)
    .join("\n");
}

/** "Why?" chips for the idea's status (two per row, from the project's reason set), then switch / undo / done. */
export function askKeyboard(i: VideoIdea): Keyboard {
  const picked = tagList(i);
  const reasons = REASONS();
  const rows: Button[][] = [];
  reasonsFor(i.project, i.status).forEach((c, n) => {
    const btn = { text: picked.includes(c) ? `✓ ${reasons[c]}` : reasons[c], callback_data: `t:${i.id}:${c}` };
    if (n % 2 === 0) rows.push([btn]);
    else rows[rows.length - 1].push(btn);
  });
  const sw = SWITCH[i.status];
  if (sw) rows.push([{ text: sw.text, callback_data: `t:${i.id}:${sw.code}` }]);
  rows.push([
    { text: "↩️ Скасувати оцінку", callback_data: `t:${i.id}:undo` },
    { text: "✔️ Готово", callback_data: `t:${i.id}:done` },
  ]);
  return { inline_keyboard: rows };
}

/** Next reason tags after a tap: a picked code is removed, a new one appended. */
export const toggleTag = (tags: string[], code: string) => (tags.includes(code) ? tags.filter((t) => t !== code) : [...tags, code]);

export const scriptText = (i: VideoIdea) =>
  [
    `📝 <b>Сценарій · ідея #${i.id}</b>: ${esc(i.title)}`,
    "",
    esc((i.script ?? "").slice(0, 3500)),
    "",
    i.stage === "script"
      ? "<i>✅ = Claude робить відео (поки ПК увімкнений). Правки: відповідай (reply) на це повідомлення текстом або голосом.</i>"
      : `🎬 <b>${STAGE[i.stage ?? ""] ?? i.stage}</b>`,
  ].join("\n");

export const scriptKeyboard = (i: VideoIdea): Keyboard =>
  i.stage === "script"
    ? { inline_keyboard: [[{ text: "✅ Затвердити сценарій", callback_data: `s:${i.id}:ok` }, { text: "✏️ Правки", callback_data: `s:${i.id}:edit` }]] }
    : { inline_keyboard: [] };

export const BLOG_STATUS: Record<string, string> = {
  waiting: "⏳ чекає на тебе",
  approved: "✅ затверджено, Claude публікує (до ~15 хв, коли ПК увімкнений)",
  published: "📤 опубліковано",
  replaced: "♻️ замінено новою версією",
};

export const blogText = (b: BlogReview, summary: string) =>
  [
    `📰 <b>Гайд для блогу</b>: ${esc(b.title)}`,
    `<code>${esc(b.slug)}</code>`,
    "",
    esc(summary.slice(0, 3000)),
    "",
    `Статус: <b>${BLOG_STATUS[b.status] ?? b.status}</b>`,
    b.status === "waiting" ? "<i>Повний текст: файл нижче. ✅ = публікація на сайті. Правки: відповідай (reply) на це повідомлення.</i>" : null,
  ]
    .filter((l) => l !== null)
    .join("\n");

export const blogKeyboard = (b: BlogReview): Keyboard =>
  b.status === "waiting"
    ? { inline_keyboard: [[{ text: "✅ Опублікувати", callback_data: `b:${b.id}:ok` }, { text: "✏️ Правки", callback_data: `b:${b.id}:edit` }]] }
    : { inline_keyboard: [] };

export const blogStatusText = (b: BlogReview, status: string) =>
  `📰 ${esc(b.title)}: <b>${BLOG_STATUS[status] ?? status}</b>${status === "published" && config().blog ? `\n${config().blog!.publicUrl}${b.slug}` : ""}`;

// ───────────── Content packs ─────────────

/** One message of a content pack: a platform header, optional notes for the owner, and each text in its own copyable block. */
export type PackPart = { label?: string; note?: string; text: string };
export type PackSection = { title: string; parts: PackPart[] };
/** Feedback kind that stores a whole pack (JSON { sections, note }), so a CRM can show and copy it. */
export const PACK_KIND = "pack";
/** Telegram caps a message at 4096 characters; leave room for the HTML tags and escaping. */
export const PACK_MESSAGE_MAX = 3900;

export const packMessage = (s: PackSection) =>
  [
    `<b>${esc(s.title)}</b>`,
    ...s.parts.map((p) =>
      [p.label ? `<b>${esc(p.label)}</b>` : null, p.note ? `<i>${esc(p.note)}</i>` : null, `<pre>${esc(p.text)}</pre>`]
        .filter((l) => l !== null)
        .join("\n"),
    ),
  ].join("\n\n");

/** The first section too long for one Telegram message (same estimate as the solar site), if any. */
export const tooLongSection = (sections: PackSection[]) =>
  sections.find((s) => s.title.length + s.parts.reduce((n, p) => n + p.text.length + (p.label?.length ?? 0) + (p.note?.length ?? 0) + 40, 0) > PACK_MESSAGE_MAX);

/** The messages of a pack: a short header, then one message per platform section. */
export function packMessages(i: Pick<VideoIdea, "id" | "title">, sections: PackSection[], notePath?: string) {
  const head = [
    `📝 <b>Пости · ідея #${i.id}</b>: ${esc(i.title)}`,
    `${sections.length} повідомлень, по одному на платформу. Текст у сірому блоці копіюється натиском.`,
    notePath ? `<i>Нотатка: ${esc(notePath)}</i>` : null,
  ]
    .filter((l) => l !== null)
    .join("\n");
  return [head, ...sections.map(packMessage)];
}

// ───────────── Callback data ─────────────

export type Callback =
  | { kind: "i"; id: number; action: string; status: string }
  | { kind: "m"; id: number; action: "more" | "back" | "del" | "delyes" }
  | { kind: "t"; id: number; code: string }
  | { kind: "p"; id: number }
  | { kind: "s"; id: number; action: "ok" | "edit" }
  | { kind: "b"; id: number; action: "ok" | "edit" };

/**
 * Parses button data. Unknown kinds or a bad id give null. An unknown i: action keeps kind "i" with status "" (the
 * handler then just answers the tap, as before).
 */
export function parseCallback(data: string | undefined | null): Callback | null {
  if (!data) return null;
  const [kind, idRaw, a = ""] = data.split(":");
  const id = Number(idRaw);
  if (!Number.isInteger(id) || id <= 0) return null;
  switch (kind) {
    case "i":
      return { kind, id, action: a, status: ACTIONS[a] ?? "" };
    case "m":
      return { kind, id, action: a === "more" || a === "del" || a === "delyes" ? a : "back" };
    case "t":
      return { kind, id, code: a };
    case "p":
      return { kind, id };
    case "s":
    case "b":
      return { kind, id, action: a === "edit" ? "edit" : "ok" };
    default:
      return null;
  }
}

export const HELP = [
  "💡 <b>Бот ідей для відео</b>",
  "Ідеї пише генератор (<code>/video-ideas</code> у Claude Code) на основі playbook, банку хуків, трекера і новин.",
  "",
  "Під кожною ідеєю: 👍 Норм · 👎 Погано · 🔁 Переробити · ✅ У трекер.",
  "⋯ Ще: 📝 Розгорнути (детальніша версія) · 🧬 3 варіації · 🗑 Видалити · ⬅️ Назад.",
  "Після вибору бот спитає «чому?» / «що змінити?»: обери пункти і/або напиши текстом (протягом години можна просто писати в чат). ↩️ Скасувати оцінку повертає ідею як була.",
  "Пізніше: відповідай (reply) на повідомлення з ідеєю, щоб додати коментар.",
  "Наступна генерація враховує все це.",
].join("\n");
