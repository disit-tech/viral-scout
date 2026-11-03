import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import type { AdsData, IndexEntry, Profile } from "./types";

const DATA = path.join(/*turbopackIgnore: true*/ process.cwd(), process.env.VIRAL_SCOUT_DATA_DIR || "data");

export async function loadIndex(): Promise<{ exported: string | null; profiles: IndexEntry[] }> {
  try {
    return JSON.parse(await readFile(path.join(DATA, "index.json"), "utf-8"));
  } catch {
    return { exported: null, profiles: [] };
  }
}

export async function loadProfile(name: string): Promise<Profile | null> {
  if (!/^[\w.-]+$/.test(name)) return null;
  try {
    return JSON.parse(await readFile(path.join(DATA, `${name}.json`), "utf-8"));
  } catch {
    return null;
  }
}

export async function profileNames(): Promise<string[]> {
  try {
    return (await readdir(DATA)).filter((f) => f.endsWith(".json") && f !== "index.json").map((f) => f.slice(0, -5));
  } catch {
    return [];
  }
}

/** Ads scout data for one profile (web/data/ads/<name>.json), written by `python -m viral_scout ads|export`. */
export async function loadAds(name: string): Promise<AdsData | null> {
  if (!/^[\w.-]+$/.test(name)) return null;
  try {
    return JSON.parse(await readFile(path.join(DATA, "ads", `${name}.json`), "utf-8"));
  } catch {
    return null;
  }
}

export async function adsNames(): Promise<string[]> {
  try {
    return (await readdir(path.join(DATA, "ads"))).filter((f) => f.endsWith(".json")).map((f) => f.slice(0, -5));
  } catch {
    return [];
  }
}

/** Local = running on the owner's PC: actions (save, dismiss, status) call the Python CLI. */
export const isLocal = !process.env.VERCEL && process.env.VIRAL_SCOUT_READONLY !== "1";
