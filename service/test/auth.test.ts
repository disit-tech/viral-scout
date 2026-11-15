import { beforeEach, describe, expect, it } from "vitest";
import { safeEqual, sign, verifyForward } from "@/lib/auth";
import { setConfig } from "@/lib/config";
import { routeForward, routeWebhook } from "@/lib/webhook";
import { ENV } from "./helpers";

beforeEach(() => setConfig(null, ENV));

const h = (o: Record<string, string>) => new Headers(o);

describe("forward signature", () => {
  const body = '{"update_id":1}';
  it("accepts the secret header the Homeworks site sends today", () => {
    expect(verifyForward(h({ "x-telegram-bot-api-secret-token": "nf-secret" }), body, "nf-secret")).toBe(true);
  });
  it("accepts an HMAC of the body", () => {
    expect(verifyForward(h({ "x-studio-signature": sign("nf-secret", body) }), body, "nf-secret")).toBe(true);
  });
  it("rejects a wrong secret, a tampered body, or no secret configured", () => {
    expect(verifyForward(h({ "x-telegram-bot-api-secret-token": "nope" }), body, "nf-secret")).toBe(false);
    expect(verifyForward(h({ "x-studio-signature": sign("nf-secret", body) }), body + " ", "nf-secret")).toBe(false);
    expect(verifyForward(h({ "x-telegram-bot-api-secret-token": "" }), body, undefined)).toBe(false);
    expect(verifyForward(h({}), body, "nf-secret")).toBe(false);
  });
  it("safeEqual never matches empty values", () => {
    expect(safeEqual("", "")).toBe(false);
    expect(safeEqual(null, undefined)).toBe(false);
    expect(safeEqual("a", "ab")).toBe(false);
  });
});

describe("webhook routing", () => {
  const ok = h({ "x-telegram-bot-api-secret-token": "hook-secret" });
  it("routes a known bot with the right secret_token", () => {
    expect(routeWebhook("ideas", ok)).toEqual({ ok: true, bot: "ideas" });
    expect(routeWebhook("agency", ok)).toEqual({ ok: true, bot: "agency" });
  });
  it("unknown bot gives 404, wrong secret gives 401", () => {
    expect(routeWebhook("nope", ok)).toMatchObject({ ok: false, status: 404 });
    expect(routeWebhook("ideas", h({ "x-telegram-bot-api-secret-token": "x" }))).toMatchObject({ ok: false, status: 401 });
    expect(routeWebhook("ideas", h({}))).toMatchObject({ ok: false, status: 401 });
  });
  it("a bot whose webhook lives elsewhere has no webhook here", () => {
    expect(routeWebhook("homes", ok)).toMatchObject({ ok: false, status: 401 });
  });
  it("an unset secret env never lets anyone in", () => {
    setConfig(null, { ...ENV, TELEGRAM_WEBHOOK_SECRET: "" });
    expect(routeWebhook("ideas", h({ "x-telegram-bot-api-secret-token": "" }))).toMatchObject({ ok: false, status: 401 });
  });
  it("forwards need the bot's forward secret", () => {
    expect(routeForward("homes", h({ "x-telegram-bot-api-secret-token": "nf-secret" }), "{}")).toEqual({ ok: true, bot: "homes" });
    expect(routeForward("homes", ok, "{}")).toMatchObject({ ok: false, status: 401 });
    expect(routeForward("ideas", h({ "x-telegram-bot-api-secret-token": "nf-secret" }), "{}")).toMatchObject({ ok: false, status: 401 });
    expect(routeForward(null, ok, "{}")).toMatchObject({ ok: false, status: 404 });
  });
});
