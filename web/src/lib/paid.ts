import { readFile } from "node:fs/promises";
import path from "node:path";
import type { Paid } from "./paid-format";

/** Paid ads (your own ad accounts): web/data/paid/<profile>.json, written by `python -m viral_scout paid <p> pull` / export. */
const DIR = path.join(/*turbopackIgnore: true*/ process.cwd(), process.env.VIRAL_SCOUT_DATA_DIR || "data", "paid");

export async function loadPaid(name: string): Promise<Paid | null> {
  if (!/^[\w.-]+$/.test(name)) return null;
  try {
    return JSON.parse(await readFile(path.join(DIR, `${name}.json`), "utf-8"));
  } catch {
    return null;
  }
}

export * from "./paid-format";
