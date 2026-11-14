export function num(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const a = Math.abs(v);
  if (a >= 1e9) return `${(v / 1e9).toFixed(1).replace(/\.0$/, "")}B`;
  if (a >= 1e6) return `${(v / 1e6).toFixed(1).replace(/\.0$/, "")}M`;
  if (a >= 1e3) return `${(v / 1e3).toFixed(1).replace(/\.0$/, "")}K`;
  return `${Math.round(v)}`;
}

export function times(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : `${v >= 10 ? Math.round(v) : v.toFixed(1)}×`;
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
