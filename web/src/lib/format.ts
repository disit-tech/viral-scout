/** A number from data that may hold "" or "12.5" (note front matter, CSV imports): null when there's no number. */
export function toNum(v: unknown): number | null {
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v.trim().replace(/[,×x]$/i, "").replace(/,/g, ""));
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export function num(raw: number | string | null | undefined): string {
  const v = toNum(raw);
  if (v === null) return "—";
  const a = Math.abs(v);
  if (a >= 1e9) return `${(v / 1e9).toFixed(1).replace(/\.0$/, "")}B`;
  if (a >= 1e6) return `${(v / 1e6).toFixed(1).replace(/\.0$/, "")}M`;
  if (a >= 1e3) return `${(v / 1e3).toFixed(1).replace(/\.0$/, "")}K`;
  return `${Math.round(v)}`;
}

export function times(raw: number | string | null | undefined): string {
  const v = toNum(raw);
  return v === null ? "—" : `${v >= 10 ? Math.round(v) : v.toFixed(1)}×`;
}

export function age(iso: string | null): string {
  if (!iso) return "—";
  const h = (Date.now() - new Date(iso).getTime()) / 36e5;
  if (h < 24) return `${Math.max(1, Math.round(h))}h`;
  const d = h / 24;
  return d < 60 ? `${Math.round(d)}d` : `${Math.round(d / 30)}mo`;
}

export function when(iso: string | null): string {
  if (!iso) return "never";
  const d = new Date(iso);
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

/** When a past event happened, with the day: "today 11:29 PM", "yesterday 9:05 AM", "Sat Nov 21, 11:29 PM" (+ year if not this year). */
export function stamp(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const clock = d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  const dayStart = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const days = Math.round((dayStart(now) - dayStart(d)) / 864e5);
  if (days === 0) return `today ${clock}`;
  if (days === 1) return `yesterday ${clock}`;
  const wd = d.toLocaleDateString("en-US", { weekday: "short" });
  const md = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const year = d.getFullYear() !== now.getFullYear() ? ` ${d.getFullYear()}` : "";
  return `${wd} ${md}${year}, ${clock}`;
}

export function tier(outlier: number | null | undefined): "mega" | "viral" | "above" | null {
  if (!outlier) return null;
  if (outlier >= 10) return "mega";
  if (outlier >= 3) return "viral";
  if (outlier >= 1.5) return "above";
  return null;
}

/** Obsidian markdown → plain markdown for the web: wikilinks to text, callout markers to quotes. */
export function deObsidian(md: string): string {
  return md
    .replace(/!\[\[[^\]]+\]\]/g, "")
    .replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, "$2")
    .replace(/\[\[([^\]]+)\]\]/g, (_, p: string) => p.split("/").pop() ?? p)
    .replace(/^>\s*\[!(\w+)\][-+]?\s*(.*)$/gm, "> **$2**");
}

/** "3h ago", "2d ago": how long since a scan. */
export function ago(iso: string | null | undefined): string {
  if (!iso) return "never";
  const m = (Date.now() - new Date(iso).getTime()) / 6e4;
  if (m < 1) return "just now";
  if (m < 60) return `${Math.round(m)}m ago`;
  const h = m / 60;
  if (h < 24) return `${Math.round(h)}h ago`;
  const d = h / 24;
  return d < 60 ? `${Math.round(d)}d ago` : `${Math.round(d / 30)}mo ago`;
}
