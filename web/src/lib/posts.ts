// Shared post helpers: scan times and labels. Used by the post card and the posts board.
import type { Item } from "./types";

export const PLATFORM: Record<string, string> = { youtube: "YouTube", instagram: "Instagram", tiktok: "TikTok" };

/** When viral-scout last measured the post: the newest snapshot, else the run date. */
export const lastScanned = (i: Item, fallback?: string | null): string | null =>
  i.history.length ? i.history[i.history.length - 1][0] : fallback ?? null;

/** When viral-scout first saw the post. */
export const firstSeen = (i: Item): string | null => i.first_seen ?? (i.history.length ? i.history[0][0] : null);

export const creatorName = (i: Item) => i.channel || "Unknown creator";

export const foundLabel = (x: string) =>
  x === "re-check" ? "re-check (tracked/watched)" : x.replace(/^youtube /, "YouTube ").replace(/^tiktok /, "TikTok ").replace(/^instagram /, "Instagram ");

export const reach = (i: Item) => i.views ?? i.likes;
