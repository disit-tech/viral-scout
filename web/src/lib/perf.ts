import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

/** Own performance data: web/data/perf/<profile>.json, written by `python -m viral_scout perf` / export. */
const DIR = path.join(/*turbopackIgnore: true*/ process.cwd(), process.env.VIRAL_SCOUT_DATA_DIR || "data", "perf");

export type Kpi = { value: number; num: number | null; den: number | null; denominator: string | null; n?: number };
export type KpiDef = { id: string; group: string; label: string; unit: string; better: string | null; formula: string; note: string };
export type Test = { test: string; status: "pass" | "warn" | "fail" | "n/a"; metric: string | null; value: number | null; benchmark: number | null; basis: string };
export type Finding = { rule: string; title: string; severity: number; score: number; evidence: string; investigate: string[] };
export type Curve = { source: "retention" | "quartiles"; points: [number, number][]; drops: { from: number; to: number; drop: number; seconds?: [number, number] }[]; peak: number; end: number };
export type Medians = { all: Record<string, number>; n: Record<string, number>; bands: Record<string, Record<string, number>> };

export type PerfRecord = {
  key: string;
  source: string;
  platform: string;
  kind: "organic" | "paid";
  id: string;
  title: string | null;
  url: string | null;
  thumbnail: string | null;
  campaign: string | null;
  duration: number | null;
  published: string | null;
  date_start: string | null;
  date_stop: string | null;
  views: number | null;
  impressions: number | null;
  spend: number | null;
  view_definition: string | null;
  notes: string[];
  kpis: Record<string, Kpi>;
  curve: Curve | null;
  curve_summary: string;
  band: string | null;
  tests: Test[];
  diagnosis: { problem: Finding | null; findings: Finding[]; caveats: string[] };
  fatigue: { detected: boolean; frequency: [number, number]; ctr: [number, number]; from: string; to: string } | null;
  trend?: Record<string, [number | null, number | null]>;
};

export type Perf = {
  name: string;
  date: string;
  goal: string;
  days: number;
  economics: Record<string, number>;
  unit_economics: Record<string, { value: number; formula: string; note: string }>;
  sources: { pulled: Record<string, number>; skipped: string[]; errors: string[]; stored: Record<string, { records: number; updated: string }> };
  records: PerfRecord[];
  medians: { organic: Medians; paid: Medians };
  account: Partial<Record<"organic" | "paid", { records: number; kpis: Record<string, Kpi>; mer?: { value: number; basis: string } }>>;
  priorities: { organic: { what: string; why: string }[]; paid: { what: string; why: string }[]; goal: string };
  kpi_defs: KpiDef[];
  groups: Record<string, string>;
  platform_differences: [string, string][];
};

export async function loadPerf(name: string): Promise<Perf | null> {
  if (!/^[\w.-]+$/.test(name)) return null;
  try {
    return JSON.parse(await readFile(path.join(DIR, `${name}.json`), "utf-8"));
  } catch {
    return null;
  }
}

export async function perfNames(): Promise<string[]> {
  try {
    return (await readdir(DIR)).filter((f) => f.endsWith(".json")).map((f) => f.slice(0, -5));
  } catch {
    return [];
  }
}

export { fmtKpi } from "./perf-format";
