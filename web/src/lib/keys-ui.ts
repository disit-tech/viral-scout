// Tiers and price labels for the API keys (tier/price come from viral_scout/keys.py). Shared by both Setup pages.

export const TIERS: { id: string; title: string; text: string }[] = [
  { id: "essential", title: "Start here", text: "Videos, ads and search demand run on these." },
  { id: "recommended", title: "Recommended", text: "Your own posts' and ads' numbers, and alerts on your phone." },
  { id: "optional", title: "Optional", text: "Only for specific cases: local competitors, TikTok ads, EU-only ad libraries." },
  { id: "advanced", title: "Advanced", text: "Settings you rarely change." },
];

export const PRICE: Record<string, { label: string; cls: string; title: string }> = {
  free: { label: "free", cls: "border-above/50 bg-above/10 text-above", title: "No charge (some need an account or an application)" },
  free_tier: { label: "free tier, then paid", cls: "border-rise/50 bg-rise/10 text-rise", title: "A free monthly allowance, then billed" },
  paid: { label: "paid", cls: "border-viral/60 bg-viral/10 text-viral", title: "Every run costs money (Apify bills per result)" },
  control: { label: "spend control", cls: "border-line bg-panel-2 text-muted", title: "A spending setting, not a source" },
};

export const tierOf = (k: { tier?: string }) => k.tier ?? "optional";
/** The price label, or null when the catalog doesn't say (never guess "free": the full cost text shows instead). */
export const priceOf = (k: { price?: string }) => (k.price && PRICE[k.price]) || null;

/** Keys grouped by tier (in TIERS order), then by provider group (in catalog order). */
export function byTier<T extends { tier?: string; group: string }>(keys: T[]) {
  return TIERS.map((t) => {
    const inTier = keys.filter((k) => tierOf(k) === t.id);
    const groups = Array.from(new Set(inTier.map((k) => k.group)));
    return { ...t, keys: inTier, groups: groups.map((g) => ({ group: g, keys: inTier.filter((k) => k.group === g) })) };
  }).filter((t) => t.keys.length);
}

/** The cost text minus what the price badge already says: "free" → "", "free (10,000 units/day)" → "10,000 units/day",
 *  "paid per result" → "per result". */
export function costDetail(k: { cost?: string; price?: string }): string {
  const cost = (k.cost ?? "").trim();
  const p = priceOf(k);
  if (!p) return cost;
  const word = p.label.split(/[ ,]/)[0];                    // "free", "paid", "spend"
  const rest = cost.toLowerCase().startsWith(word) ? cost.slice(word.length).replace(/^[\s,:]+/, "") : cost;
  return rest.replace(/^\((.*)\)$/, "$1").trim();
}

/** What a key is for (uses from viral_scout/keys.py), in filter order. */
export const USES: { id: string; label: string }[] = [
  { id: "videos", label: "🎬 videos" }, { id: "ads", label: "📢 ads" }, { id: "demand", label: "🔎 search demand" },
  { id: "performance", label: "📊 your performance" }, { id: "local", label: "📍 local competitors" },
  { id: "alerts", label: "🔔 alerts" }, { id: "tools", label: "🛠 tools" },
];
export const useLabel = (id: string) => USES.find((u) => u.id === id)?.label ?? id;
