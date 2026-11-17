/** Paid ads types and formatting, safe for client components (no fs). Loader: lib/paid.ts. */
export type PaidPlatform = "meta" | "google" | "tiktok";
export const PLATFORM_NAMES: Record<PaidPlatform, string> = { meta: "Meta (Facebook + Instagram)", google: "Google Ads", tiktok: "TikTok Ads" };

export type Campaign = {
  id: string; name: string; status: string; running: boolean; objective?: string | null;
  daily_budget: number | null; budget_remaining: number | null; budget_level: string;
  start?: string | null; stop?: string | null; month_spend: number; impressions: number; clicks: number;
  results: number | null; cost_per_result: number | null;
};
export type Account = {
  ok: boolean; account?: string; name?: string; currency?: string; account_status?: string | number; month_spend?: number;
  result_label?: string; campaigns: Campaign[]; manage_url?: string; error?: string; missing?: "account" | "key";
};
export type LogRow = { at: string; by: string; action: string; platform: string; campaign: string; amount_usd: number | null; text: string };
export type Brief = { goal?: string; daily_budget_usd?: number; geo?: string; audience?: string; offer?: string; landing?: string; notes?: string };
export type Paid = {
  profile: string; cap: number; platforms: PaidPlatform[]; accounts: Partial<Record<PaidPlatform, string>>; brief: Brief;
  snapshot: { pulled: string; platforms: Partial<Record<PaidPlatform, Account>> } | null;
  month: { spent: number; running: number; projected: number; days_left: number; check: string;
    rows: { platform: string; campaign: string; id: string; to_spend: number }[] };
  log: LogRow[];
};

export const usd = (v: number | null | undefined, digits = 0) =>
  v == null ? "—" : `$${v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
