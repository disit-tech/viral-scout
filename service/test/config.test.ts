import { beforeEach, describe, expect, it } from "vitest";
import file from "../projects.example.json";
import { allowedChats, botOf, config, hasPacks, ideaScopeOf, parseConfig, reasonsFor, setConfig } from "@/lib/config";
import { ENV } from "./helpers";

beforeEach(() => setConfig(null, ENV));

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const clone = (): any => structuredClone(file);

describe("example config", () => {
  it("is valid and mirrors the solar site", () => {
    const c = config();
    expect(Object.keys(c.projects)).toEqual(["solar", "homes", "agency"]);
    expect(c.defaultProject).toBe("solar");
    expect(Object.entries(c.projects).filter(([, p]) => p.packs).map(([k]) => k)).toEqual(["homes"]);
    expect(c.projects.homes.label).toBe("🔨 Homeworks · ");
    expect(c.projects.agency.label).toBe("🏢 Acme Agency · ");
    expect(c.bots.homes.notes).toBe("off");
    expect(c.bots.ideas.notes).toBe("replies+call");
    expect(Object.keys(c.reasons)).toHaveLength(44);
    expect(Object.keys(c.platforms)).toHaveLength(12);
  });
  it("names env vars only, never values", () => {
    const json = JSON.stringify(file);
    expect(json).not.toMatch(/\d{6,}:[A-Za-z0-9_-]{20,}/); // no bot token
    expect(json).not.toMatch(/libsql:\/\//);
  });
});

describe("routing", () => {
  it("each project posts through its own bot once the token is set", () => {
    expect(botOf({ project: "solar" })).toBe("ideas");
    expect(botOf({ project: "homes" })).toBe("homes");
    expect(botOf({ project: "agency" })).toBe("agency");
    expect(botOf({ project: "unknown" })).toBe("ideas");
  });
  it("falls back to the default bot without a token", () => {
    setConfig(null, { ...ENV, TELEGRAM_AGENCY_IDEAS_BOT_TOKEN: "" });
    expect(botOf({ project: "agency" })).toBe("ideas");
  });
  it("scopes message-id lookups to the bot's own ideas", () => {
    expect(ideaScopeOf("homes")).toEqual({ project: { in: ["homes"] } });
    expect(ideaScopeOf("ideas")).toEqual({ project: { notIn: ["homes", "agency"] } });
    setConfig(null, { ...ENV, TELEGRAM_AGENCY_IDEAS_BOT_TOKEN: undefined, TELEGRAM_HOMES_IDEAS_BOT_TOKEN: undefined });
    expect(ideaScopeOf("ideas")).toEqual({});
  });
  it("chats come from the env, per bot when set", () => {
    expect(allowedChats("ideas")).toEqual(["-100"]);
    const c = clone();
    c.bots.agency.chatsEnv = "AGENCY_CHATS";
    setConfig(parseConfig(c), { ...ENV, AGENCY_CHATS: " -5, -6 " });
    expect(allowedChats("agency")).toEqual(["-5", "-6"]);
    expect(allowedChats("ideas")).toEqual(["-100"]);
  });
  it("packs and reasons per project", () => {
    expect(hasPacks({ project: "homes" })).toBe(true);
    expect(hasPacks({ project: "solar" })).toBe(false);
    expect(reasonsFor("agency", "bad")).toEqual(["nt", "au", "dp", "rk", "ns", "sl", "st", "cl"]);
    expect(reasonsFor("unknown", "good")).toContain("hk");
  });
  it("STUDIO_CONFIG_JSON overrides the file", () => {
    const c = clone();
    c.defaultProject = "agency";
    setConfig(null, { ...ENV, STUDIO_CONFIG_JSON: JSON.stringify(c) });
    expect(config().defaultProject).toBe("agency");
  });
});

describe("validation", () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const broken = (f: (c: any) => void) => {
    const c = clone();
    f(c);
    return () => parseConfig(c);
  };
  it("rejects dangling references", () => {
    expect(broken((c) => (c.projects.solar.bot = "nope"))).toThrow(/bot "nope"/);
    expect(broken((c) => (c.projects.solar.reasonSet = "nope"))).toThrow(/reasonSet "nope"/);
    expect(broken((c) => c.reasonSets.video.good.push("zz"))).toThrow(/reason "zz"/);
    expect(broken((c) => (c.defaultBot = "nope"))).toThrow(/defaultBot/);
    expect(broken((c) => (c.projects.solar.platforms = ["myspace"]))).toThrow(/platform "myspace"/);
  });
  it("rejects a secret value where an env name belongs", () => {
    expect(broken((c) => (c.bots.ideas.tokenEnv = "123456:abc"))).toThrow(/env var name/);
  });
  it("allows only one bot to catch plain 'Claude' messages", () => {
    expect(broken((c) => (c.bots.agency.notes = "replies+call"))).toThrow(/only one bot/);
  });
});
