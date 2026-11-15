import { readFileSync } from "node:fs";
import { join } from "node:path";
import { z } from "zod";
import example from "../../projects.example.json";

/**
 * Projects and bots come from config, not code. In order: the whole JSON in the STUDIO_CONFIG_JSON env var (use this
 * on Vercel, so a deploy can change bots without a commit), else projects.json in the service root (git-ignored: your
 * real projects), else projects.example.json (placeholders). Tests always use the example. Secrets are env var names only.
 */
function rawConfig(e: Record<string, string | undefined>): unknown {
  if (e.STUDIO_CONFIG_JSON) return JSON.parse(e.STUDIO_CONFIG_JSON);
  if (process.env.VITEST) return example;
  try {
    return JSON.parse(readFileSync(join(process.cwd(), "projects.json"), "utf8"));
  } catch {
    return example;
  }
}

const envName = z.string().regex(/^[A-Z][A-Z0-9_]*$/, "an env var name (A-Z, 0-9, _)");
const slug = z.string().regex(/^[a-z][a-z0-9_-]{0,30}$/);

const Bot = z.object({
  /** Env var with the bot token from @BotFather. */
  tokenEnv: envName,
  /** Env var with the secret_token this bot's webhook was set with. Unset = its webhook is not this service. */
  webhookSecretEnv: envName.optional(),
  /** Env var with the shared secret a CRM site uses to forward this bot's idea updates to /api/forward. */
  forwardSecretEnv: envName.optional(),
  /** Env var with the allowed chat ids (comma-separated); defaults to the top-level chatsEnv. */
  chatsEnv: envName.optional(),
  /**
   * Notes for Claude (ClaudeNote rows, read on the PC by notes.mjs):
   * off = never (a CRM bot) · replies = replies to this bot's messages · replies+call = also plain "Claude, …" messages
   * (give "replies+call" to one bot only, or such a message is stored twice).
   */
  notes: z.enum(["off", "replies", "replies+call"]).default("replies"),
});

const Project = z.object({
  /** The bot that posts (and so edits) this project's ideas. Falls back to defaultBot while its token is unset. */
  bot: slug,
  /** Header in front of every idea message, so brands sharing a group don't mix (e.g. "🔨 Homeworks · "). */
  label: z.string().default(""),
  /** Which entry of reasonSets offers the "why?" chips. */
  reasonSet: z.string().min(1),
  /** Approved ideas get a content pack (📝 Пости): one ready-to-post text per platform. */
  packs: z.boolean().default(false),
  /** Platform keys this project offers (a subset of platforms); unset = all. */
  platforms: z.array(z.string()).optional(),
  /** Env var with a limited key for this project's CRM page: read its ideas and rate/comment/📝/🗑/platforms only. */
  crmSecretEnv: envName.optional(),
});

const ReasonSet = z.record(z.string(), z.array(z.string()));

export const ConfigSchema = z
  .object({
    $comment: z.string().optional(),
    defaultProject: slug,
    defaultBot: slug,
    chatsEnv: envName,
    /** Bot that sends scenarios (✅ / ✏️). */
    scriptsBot: slug,
    blog: z.object({ bot: slug, publicUrl: z.string().url() }).optional(),
    bots: z.record(slug, Bot),
    projects: z.record(slug, Project),
    platforms: z.record(z.string(), z.string()),
    reasons: z.record(z.string(), z.string()),
    reasonSets: z.record(z.string(), ReasonSet),
  })
  .superRefine((c, ctx) => {
    const bad = (message: string) => ctx.addIssue({ code: "custom", message });
    if (!c.projects[c.defaultProject]) bad(`defaultProject "${c.defaultProject}" is not in projects`);
    if (!c.bots[c.defaultBot]) bad(`defaultBot "${c.defaultBot}" is not in bots`);
    if (!c.bots[c.scriptsBot]) bad(`scriptsBot "${c.scriptsBot}" is not in bots`);
    if (c.blog && !c.bots[c.blog.bot]) bad(`blog.bot "${c.blog.bot}" is not in bots`);
    for (const [p, v] of Object.entries(c.projects)) {
      if (!c.bots[v.bot]) bad(`project ${p}: bot "${v.bot}" is not in bots`);
      if (!c.reasonSets[v.reasonSet]) bad(`project ${p}: reasonSet "${v.reasonSet}" is not in reasonSets`);
      for (const k of v.platforms ?? []) if (!c.platforms[k]) bad(`project ${p}: platform "${k}" is not in platforms`);
    }
    for (const [name, set] of Object.entries(c.reasonSets))
      for (const codes of Object.values(set)) for (const code of codes) if (!c.reasons[code]) bad(`reasonSet ${name}: reason "${code}" is not in reasons`);
    if (Object.values(c.bots).filter((b) => b.notes === "replies+call").length > 1) bad(`only one bot may have notes "replies+call"`);
  });

export type Config = z.infer<typeof ConfigSchema>;
export type BotConfig = z.infer<typeof Bot>;
export type ProjectConfig = z.infer<typeof Project>;

export function parseConfig(raw: unknown): Config {
  const r = ConfigSchema.safeParse(raw);
  if (!r.success) throw new Error(`Invalid ideas service config: ${r.error.issues.map((i) => `${i.path.join(".")} ${i.message}`).join("; ")}`);
  return r.data;
}

let current: Config | null = null;
let env: Record<string, string | undefined> = process.env;

export function config(): Config {
  if (!current) current = parseConfig(rawConfig(env));
  return current;
}

/** Tests: swap the config and/or the env. */
export function setConfig(c: Config | null, e: Record<string, string | undefined> = process.env) {
  current = c;
  env = e;
}

const read = (name?: string) => (name ? env[name]?.trim() || undefined : undefined);

export const projectSlugs = () => Object.keys(config().projects);
export const botSlugs = () => Object.keys(config().bots);
export const projectOf = (slug: string): ProjectConfig | undefined => config().projects[slug];
export const botConfig = (slug: string): BotConfig | undefined => config().bots[slug];

export const tokenOf = (bot: string) => read(botConfig(bot)?.tokenEnv);
export const webhookSecretOf = (bot: string) => read(botConfig(bot)?.webhookSecretEnv);
export const forwardSecretOf = (bot: string) => read(botConfig(bot)?.forwardSecretEnv);
export const crmSecretOf = (project: string) => read(projectOf(project)?.crmSecretEnv);
export const apiSecret = () => read("IDEAS_API_SECRET");

/** Allowed chat ids for a bot (defaults to the top-level chatsEnv, e.g. TELEGRAM_CHAT_ID). */
export const allowedChats = (bot?: string) =>
  (read((bot && botConfig(bot)?.chatsEnv) || config().chatsEnv) ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

/**
 * The bot that posts (and so edits) an idea: the project's own bot once its token is set, else the default bot.
 * Unknown projects use the default bot.
 */
export const botOf = (i: { project: string }): string => {
  const own = projectOf(i.project)?.bot;
  return own && tokenOf(own) ? own : config().defaultBot;
};

/** Which ideas a bot may look up by message id: in a basic group every bot numbers its messages on its own. */
export function ideaScopeOf(bot: string): { project?: string | { in: string[] } | { notIn: string[] } } {
  const c = config();
  if (bot !== c.defaultBot) return { project: { in: projectSlugs().filter((p) => c.projects[p].bot === bot) } };
  const own = projectSlugs().filter((p) => c.projects[p].bot !== c.defaultBot && botOf({ project: p }) !== c.defaultBot);
  return own.length ? { project: { notIn: own } } : {};
}

export const hasPacks = (i: { project: string }) => Boolean(projectOf(i.project)?.packs);
export const REASONS = () => config().reasons;
export const PLATFORMS = () => config().platforms;
/** Reason codes offered for a status in this project ("why?" chips). */
export const reasonsFor = (project: string, status: string): string[] => {
  const set = config().reasonSets[projectOf(project)?.reasonSet ?? ""] ?? config().reasonSets[projectOf(config().defaultProject)!.reasonSet];
  return set?.[status] ?? [];
};
export const labelOf = (project: string) => projectOf(project)?.label ?? "";
