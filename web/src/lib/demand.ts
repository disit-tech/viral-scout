// Search demand (Google Trends): types and loader for web/data/demand/<profile>.json (python -m viral_scout demand).
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

const DATA = path.join(/*turbopackIgnore: true*/ process.cwd(), process.env.VIRAL_SCOUT_DATA_DIR || "data", "demand");

export type DemandQuery = { query: string; value: string | number; buyer?: boolean };
export type DemandSeason = {
  rise_week: number; peak_week: number; end_week: number; height: number; in_season: boolean;
  rise_date: string; peak_date: string; end_date: string; start_by: string; next_rise: string; label: string;
};
export type DemandTerm = {
  term: string; status: "ok" | "no data"; note?: string; weeks?: number; low_volume?: boolean; zero_share?: number;
  shape?: string; strength?: number; season_index?: number[]; month_index?: (number | null)[]; seasons?: DemandSeason[];
  peak_week?: number; low_week?: number; in_season?: boolean; now?: number;
  vs_last_year_pct?: number | null; vs_normal_pct?: number | null; trend_pct?: number | null;
  series?: [string, number][]; start_by?: string; rise_date?: string; peak_date?: string; end_date?: string;
  related?: { rising: DemandQuery[]; top: DemandQuery[]; rising_topics: DemandQuery[]; places: { name: string; value: number }[] };
  trends_url?: string;
};
export type DemandCalendarRow = {
  term: string; label: string; start_by: string; rise: string; peak: string; end: string; in_season: boolean;
  next_rise: string; shape: string; low_volume: boolean;
};
export type DemandData = {
  profile: string; date: string; fetched: string; geo: string; time: string; lead_weeks: number;
  terms: DemandTerm[]; calendar: DemandCalendarRow[];
  compare: { terms: string[]; rows: { term: string; avg: number; share_pct: number; vs_top: number }[]; trends_url: string } | null;
  errors: string[]; skipped: string[];
};

export async function loadDemand(name: string): Promise<DemandData | null> {
  if (!/^[\w.-]+$/.test(name)) return null;
  try {
    return JSON.parse(await readFile(path.join(DATA, `${name}.json`), "utf-8"));
  } catch {
    return null;
  }
}

export async function demandNames(): Promise<string[]> {
  try {
    return (await readdir(DATA)).filter((f) => f.endsWith(".json")).map((f) => f.slice(0, -5));
  } catch {
    return [];
  }
}

/** "Chicago metro" style labels for the geo codes people use most. */
export function geoLabel(geo: string) {
  const metros: Record<string, string> = { "US-IL-602": "Chicago metro", "US-NY-501": "New York metro", "US-CA-803": "Los Angeles metro" };
  if (metros[geo]) return metros[geo];
  if (/^US-[A-Z]{2}$/.test(geo)) return `${geo.slice(3)} (state)`;
  return geo || "Worldwide";
}
