import type { Item, Profile } from "./types";
import { num, times } from "./format";

/** Plain-language reasons this post is worth studying, from its numbers. */
export function whyNotable(i: Item): string[] {
  const out: string[] = [];
  const reach = i.views ?? i.likes;
  if (i.outlier && i.outlier >= 3) {
    out.push(`${times(i.outlier)} the creator's usual ${i.views != null ? "views" : "likes"}: the format worked, not just the account${i.outlier >= 10 ? " (🔥 mega outlier)" : ""}.`);
  } else if (i.outlier && i.outlier >= 1.5) {
    out.push(`${times(i.outlier)} the creator's usual: above their normal, not a breakout.`);
  } else if (i.outlier) {
    out.push(`Around the creator's normal (${times(i.outlier)}): a big account doing what it always does. Study the series, not this one post.`);
  }
  if (i.creator_pct != null && i.creator_pct >= 90) out.push(`Beats ${Math.round(i.creator_pct)}% of this creator's recent posts.`);
  if (i.vs_pace && i.vs_pace >= 2) out.push(`${times(i.vs_pace)} the creator's usual views per day, compared at a similar age.`);
  if (i.vs_topic && i.vs_topic >= 2) out.push(`${times(i.vs_topic)} the niche median views per day in this run.`);
  if (i.rise_per_day) out.push(`Still growing: +${num(i.rise_per_day)} per day since the previous run.`);
  if (i.per_day && reach) out.push(`${num(reach)} ${i.views != null ? "views" : "likes"} in ${ageWords(i.published)}, about ${num(i.per_day)} a day.`);
  if (i.emerging) out.push(`🌱 Small creator (${num(i.followers)} followers): a format that works without a big audience.`);
  if (i.engagement && i.engagement >= 0.05) out.push(`High engagement: ${(i.engagement * 100).toFixed(1)}% of viewers liked or commented.`);
  if (i.questions?.length) out.push(`Viewers are asking questions in the comments (${i.questions.length}): ready-made follow-up ideas.`);
  if (i.early) out.push("⏳ Under 6 hours old: numbers are still settling.");
  return out;
}

function ageWords(iso: string | null): string {
  if (!iso) return "an unknown time";
  const d = (Date.now() - new Date(iso).getTime()) / 864e5;
  return d < 1 ? `${Math.max(1, Math.round(d * 24))} hours` : d < 60 ? `${Math.round(d)} days` : `${Math.round(d / 30)} months`;
}

/** Official embed URL (YouTube no-cookie, Instagram, TikTok), or null. */
export function embedUrl(i: Item): string | null {
  if (i.platform === "youtube") return `https://www.youtube-nocookie.com/embed/${i.id}?rel=0`;
  if (i.platform === "instagram") {
    const code = i.url.match(/instagram\.com\/(?:reel|p)\/([\w-]+)/)?.[1];
    return code ? `https://www.instagram.com/reel/${code}/embed` : null;
  }
  if (i.platform === "tiktok") return `https://www.tiktok.com/embed/v2/${i.id}`;
  return null;
}

/** Bits of the AI ideas notes that mention this post: breakdown rows and the ideas that borrow from it. */
export function aiMentions(i: Item, ideas: Profile["ideas"]): { date: string; lines: string[] }[] {
  const keys = [i.id, i.url].filter(Boolean);
  const out: { date: string; lines: string[] }[] = [];
  for (const note of ideas) {
    const lines: string[] = [];
    const md = note.markdown.split("\n");
    md.forEach((line, idx) => {
      if (!keys.some((k) => line.includes(k))) return;
      if (line.trim().startsWith("|")) {
        const cells = line.split("|").map((c) => c.trim()).filter(Boolean);
        const header = md.slice(0, idx).reverse().find((l) => l.trim().startsWith("|") && !/^\|\s*-/.test(l.trim()) && !keys.some((k) => l.includes(k)));
        const names = header?.split("|").map((c) => c.trim()).filter(Boolean) ?? [];
        lines.push(cells.slice(1).map((c, n) => `**${names[n + 1] ?? ""}:** ${c}`).join(" · "));
      } else {
        // An idea that borrows from this post: take its heading and the few lines around.
        const start = md.slice(0, idx + 1).map((l, n) => [l, n] as const).reverse().find(([l]) => /^#{2,4}\s/.test(l))?.[1] ?? idx;
        const block = md.slice(start, Math.min(md.length, idx + 6)).filter((l) => l.trim()).join("\n");
        if (!lines.includes(block)) lines.push(block);
      }
    });
    if (lines.length) out.push({ date: note.date, lines });
  }
  return out;
}
