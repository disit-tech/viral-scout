// Shared ad helpers: labels, "worth studying", copy breakdown, similar ads. Used by the ads board and the ad page.
import type { AdItem } from "./types";

export const OFFER: Record<string, string> = {
  price: "price shown", free_trial: "free trial / lesson", free_quote: "free quote", free: "\"free\" claim",
  discount: "discount", guarantee: "guarantee", financing: "financing", incentive: "tax credit / rebate",
  urgency: "urgency", social_proof: "social proof",
};
export const SOURCE: Record<string, string> = {
  meta_api: "Meta API", tiktok_api: "TikTok API", apify_meta: "Facebook / Instagram",
  apify_tiktok_top: "TikTok Top Ads", apify_google: "Google",
};
export const SOURCE_SHORT: Record<string, string> = { meta_api: "FB", tiktok_api: "TT", apify_meta: "FB", apify_tiktok_top: "TT", apify_google: "G" };

export const advName = (a: AdItem) => a.advertiser || "Unknown advertiser";
export const competitorSearch = (a: AdItem) => a.found_by.some((x) => x.includes("advertiser") || x.includes("google"));
export const queryLabel = (x: string) =>
  x.replace(/^apify meta advertiser /, "competitor: ").replace(/^meta advertiser /, "competitor: ")
    .replace(/^apify meta keyword /, "keyword: ").replace(/^meta keyword /, "keyword: ")
    .replace(/^tiktok keyword /, "TikTok keyword: ").replace(/^apify google transparency.*/, "Google: competitor domains/names")
    .replace(/^apify tiktok top ads/, "TikTok Top Ads (industry)");

export const adHref = (profile: string, a: AdItem) => `/p/${profile}/a/${encodeURIComponent(a.key)}`;

/** The ads worth a closer look: long runs that are still live, very long runs, or several variants (a paid test). */
export function worthStudying(a: AdItem) {
  const d = a.days_running ?? 0;
  return d >= 60 || (a.active && d >= 30) || a.variants >= 3;
}

export function median(xs: number[]) {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

// ---------- copy breakdown (deterministic: regexes, no AI) ----------

const uniq = (xs: string[]) => Array.from(new Set(xs.map((x) => x.trim().toLowerCase()))).slice(0, 8);
const hits = (re: RegExp, s: string) => uniq(s.match(re) ?? []);

const PROBLEM = /\b(clogged|clogs?|leak\w*|damage\w*|broken|tired of|worried|struggl\w*|costly|expensive|dangerous|overflow\w*|mold|rot\w*|pests?|ice dams?|stress\w*|hassle|ladders?|drafty|outdated|ugly|falling|unsafe|emergency|storm)\b/gi;
const PROOF = /(\d[\d,.]*\+?\s*(?:\w+\s)?(?:reviews?|stars?|years?|customers?|homes?|homeowners|families|clients|projects|installs?|installations)\b|\d(?:\.\d)?\s*★|\brated\b|\baward[- ]?\w*|\bbbb\b|\ba\+|\blicensed\b|\binsured\b|\bcertified\b|\bwarrant\w*|\bguarantee\w*|\bsince (?:19|20)\d\d\b|\bfamily[- ]owned\b|#1\b|\btrusted\b)/gi;
const URGENCY = /\b(today|now|limited|ends?|only|last chance|hurry|this week|deadline|while supplies last|book (?:now|today)|spots?|before)\b/gi;
const MONEY = /(\$\s?\d[\d,]*(?:\.\d+)?|\d+\s?%\s?off|\bfree\b|\$0 down|\b0% (?:apr|interest)|financing)/gi;
const EMOJI = /\p{Extended_Pictographic}/gu;

export type CopyBreakdown = {
  text: string; chars: number; words: number; visible: string; cut: string; visibleLimit: number; limitLabel: string;
  hookFits: boolean | null; problem: string[]; proof: string[]; urgency: string[]; money: string[];
  questions: number; emoji: number; firstPerson: boolean; youCount: number;
};

/** What the copy does, line by line. Meta shows about 125 characters of primary text before "See more";
 *  Google text ads cap headlines at 30 and descriptions at 90 characters. */
export function copyBreakdown(a: AdItem): CopyBreakdown {
  const text = [a.body, a.title].filter(Boolean).join("\n").trim();
  const primary = (a.body || a.title || "").trim();
  const google = a.source === "apify_google";
  const limit = google ? 90 : 125;
  const hook = (a.hook || "").trim();
  return {
    text, chars: text.length, words: text ? text.split(/\s+/).length : 0,
    visible: primary.slice(0, limit), cut: primary.slice(limit), visibleLimit: limit,
    limitLabel: google ? "a Google description shows up to 90 characters" : "Facebook/Instagram show about 125 characters before \"See more\"",
    hookFits: hook ? hook.length <= limit : null,
    problem: hits(PROBLEM, text), proof: hits(PROOF, text), urgency: hits(URGENCY, text), money: hits(MONEY, text),
    questions: (text.match(/\?/g) ?? []).length, emoji: (text.match(EMOJI) ?? []).length,
    firstPerson: /\b(we|our|us)\b/i.test(text), youCount: (text.match(/\byou(r|'re)?\b/gi) ?? []).length,
  };
}

// ---------- similar ads elsewhere (token overlap, other advertisers) ----------

const STOP = new Set(("that this with your from have will more what when they them their there about just than then " +
  "into over only also been were each make like very much some most such here home homes today call free").split(" "));
const tokens = (a: AdItem) => new Set(`${a.hook} ${a.title ?? ""} ${a.body ?? ""}`.toLowerCase().match(/[a-z]{4,}/g)?.filter((w) => !STOP.has(w)) ?? []);

export function similarAds(ad: AdItem, all: AdItem[], n = 6) {
  const mine = tokens(ad);
  const myOffers = new Set(ad.offers);
  const out: { ad: AdItem; sim: number; sharedOffers: string[]; sharedWords: string[] }[] = [];
  for (const b of all) {
    if (b.key === ad.key || advName(b) === advName(ad)) continue;
    const t = tokens(b);
    const shared = [...t].filter((w) => mine.has(w));
    const sim = mine.size && t.size ? shared.length / (mine.size + t.size - shared.length) : 0;
    const sharedOffers = b.offers.filter((o) => myOffers.has(o));
    const score = sim + (sharedOffers.length ? 0.08 * sharedOffers.length : 0);
    if (sim >= 0.12 || (sharedOffers.length && sim >= 0.05)) out.push({ ad: b, sim: score, sharedOffers, sharedWords: shared.slice(0, 6) });
  }
  return out.sort((x, y) => y.sim - x.sim || y.ad.ad_score - x.ad.ad_score).slice(0, n);
}
