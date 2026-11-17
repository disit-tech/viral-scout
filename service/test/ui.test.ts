import { beforeEach, describe, expect, it } from "vitest";
import file from "../projects.example.json";
import { parseConfig, setConfig } from "@/lib/config";
import {
  askKeyboard,
  askText,
  businessTag,
  hashtag,
  ideaText,
  keyboard,
  packMessage,
  packMessages,
  PACK_MESSAGE_MAX,
  parseCallback,
  platformOfTitle,
  scriptText,
  tagsLine,
  tooLongSection,
  toggleTag,
} from "@/lib/ui";
import { ENV, idea } from "./helpers";

const data = (kb: { inline_keyboard: { callback_data: string }[][] }) => kb.inline_keyboard.map((r) => r.map((b) => b.callback_data));
const texts = (kb: { inline_keyboard: { text: string }[][] }) => kb.inline_keyboard.map((r) => r.map((b) => b.text));

beforeEach(() => setConfig(null, ENV));

describe("idea keyboard", () => {
  it("main view: 2+2 rating buttons and the menu", () => {
    expect(data(keyboard(idea()))).toEqual([["i:7:g", "i:7:b"], ["i:7:r", "i:7:a"], ["m:7:more"]]);
  });
  it("marks the current rating", () => {
    expect(texts(keyboard(idea({ status: "bad" })))[0]).toEqual(["👍 Норм", "• 👎 Погано •"]);
  });
  it("shows a pending expand/variants request on the menu button", () => {
    expect(texts(keyboard(idea({ status: "expand" })))[2]).toEqual(["⋯ Ще (📝 Розгорнути)"]);
  });
  it("more and delete-confirm views", () => {
    expect(data(keyboard(idea(), "more"))).toEqual([["i:7:x", "i:7:v"], ["m:7:del"], ["m:7:back"]]);
    expect(data(keyboard(idea(), "del"))).toEqual([["m:7:delyes", "m:7:back"]]);
  });
  it("final statuses have no buttons", () => {
    for (const status of ["replaced", "varied", "tracked", "deleted"]) expect(keyboard(idea({ status })).inline_keyboard).toEqual([]);
  });
  it("a tracked idea of a pack project keeps the 📝 button, by stage", () => {
    const nf = idea({ project: "homes", status: "tracked" });
    expect(texts(keyboard(nf))).toEqual([["📝 Пости"]]);
    expect(texts(keyboard({ ...nf, stage: "pack" }))).toEqual([["📝 Пости: в черзі"]]);
    expect(texts(keyboard({ ...nf, stage: "pack_sent" }))).toEqual([["📝 Пости ще раз"]]);
    expect(data(keyboard(nf))).toEqual([["p:7:req"]]);
  });
});

describe("idea text", () => {
  it("escapes HTML and has no label for solar", () => {
    const t = ideaText(idea());
    expect(t.startsWith("💡 <b>Ідея #7</b>")).toBe(true);
    expect(t).toContain("Generator &lt;vs&gt; battery");
  });
  it("puts the project label in front", () => {
    expect(ideaText(idea({ project: "homes" }))).toMatch(/^🔨 Homeworks · 💡/);
    expect(ideaText(idea({ project: "agency", status: "deleted" }))).toBe("🗑 <s>🏢 Acme Agency · Ідея #7: Generator &lt;vs&gt; battery</s>");
  });
  it("lists platforms, reasons and the pack-aware ✅ label", () => {
    const t = ideaText(idea({ project: "homes", status: "approved", platforms: "facebook,bogus,nextdoor", tags: "hk,zz" }));
    expect(t).toContain("📲 Де постити: Facebook page · Nextdoor");
    expect(t).toContain("🏷 🪝 Сильний хук");
    expect(t).toContain("✅ У трекер + 📝 пости");
    expect(ideaText(idea({ status: "approved" }))).toContain("✅ У трекер (додам при наступній генерації)");
  });
});

describe("hashtags", () => {
  it("business tag from the label, else the slug; only letters, digits and _", () => {
    expect(businessTag("homes")).toBe("#Homeworks");
    expect(businessTag("agency")).toBe("#AcmeAgency");
    expect(businessTag("solar")).toBe("#solar"); // no label in the example
    expect(hashtag("YouTube Shorts")).toBe("#YouTubeShorts");
    expect(hashtag("2026")).toBe(""); // Telegram doesn't link a tag without a letter
  });
  it("a hashtag set in projects.json wins", () => {
    const c = JSON.parse(JSON.stringify(file));
    c.projects.solar.hashtag = "LightsOn";
    setConfig(parseConfig(c), ENV);
    expect(businessTag("solar")).toBe("#LightsOn");
  });
  it("finds the platform a section title names", () => {
    expect(platformOfTitle("▶ YouTube Shorts")).toBe("youtube");
    expect(platformOfTitle("Facebook groups")).toBe("fb_groups");
    expect(platformOfTitle("Facebook page")).toBe("facebook");
    expect(platformOfTitle("▶ TIKTOK (відео)")).toBe("tiktok");
    expect(platformOfTitle("Intro")).toBeUndefined();
  });
  it("ends idea and script messages with business, kind, platforms and the idea id", () => {
    const t = ideaText(idea({ project: "homes", platforms: "facebook,nextdoor" }));
    expect(t.split("\n").at(-1)).toBe("#Homeworks #idea #facebook #nextdoor #idea7");
    expect(scriptText(idea({ project: "agency", stage: "script" })).split("\n").at(-1)).toBe("#AcmeAgency #script #idea7");
    expect(ideaText(idea({ status: "deleted" }))).not.toContain("#idea");
    expect(tagsLine("homes", ["idea", "idea"], ["tiktok", "tiktok"])).toBe("#Homeworks #idea #tiktok");
  });
});

describe("why? question", () => {
  it("offers the status's reasons two per row, then undo/done", () => {
    const kb = askKeyboard(idea({ status: "good", tags: "tp" }));
    expect(kb.inline_keyboard.slice(0, 4).every((r) => r.length === 2)).toBe(true);
    expect(texts(kb)[0]).toEqual(["🪝 Сильний хук", "✓ 💡 Свіжа тема"]);
    expect(data(kb).at(-1)).toEqual(["t:7:undo", "t:7:done"]);
  });
  it("👎 also offers switching to 🔁", () => {
    expect(data(askKeyboard(idea({ status: "bad" }))).at(-2)).toEqual(["t:7:tored"]);
  });
  it("odd counts leave a single button in the last row", () => {
    const kb = askKeyboard(idea({ status: "variants" }));
    expect(kb.inline_keyboard[2]).toHaveLength(1);
  });
  it("reason sets are per project", () => {
    const c = structuredClone(file) as unknown as {
      projects: Record<string, { reasonSet: string }>;
      reasonSets: Record<string, Record<string, string[]>>;
      reasons: Record<string, string>;
    };
    c.reasons.lp = "📞 Lead potential";
    c.reasonSets.marketing = { good: ["lp", "hk"] };
    c.projects.homes.reasonSet = "marketing";
    setConfig(parseConfig(c), ENV);
    expect(data(askKeyboard(idea({ project: "homes", status: "good" })))[0]).toEqual(["t:7:lp", "t:7:hk"]);
    expect(data(askKeyboard(idea({ project: "solar", status: "good" })))[0]).toEqual(["t:7:hk", "t:7:tp"]);
    expect(askKeyboard(idea({ project: "homes", status: "bad" })).inline_keyboard).toHaveLength(2); // only switch + undo/done
  });
  it("texts for asking and done", () => {
    expect(askText(idea({ status: "redo" }))).toContain("Що змінити?");
    expect(askText(idea({ status: "good" }), true)).toContain("Без деталей");
    expect(askText(idea({ status: "good", tags: "hk" }), true)).toContain("Записав.");
  });
  it("toggles a reason", () => {
    expect(toggleTag(["hk"], "tp")).toEqual(["hk", "tp"]);
    expect(toggleTag(["hk", "tp"], "hk")).toEqual(["tp"]);
  });
});

describe("callback data", () => {
  it("parses every kind", () => {
    expect(parseCallback("i:12:g")).toEqual({ kind: "i", id: 12, action: "g", status: "good" });
    expect(parseCallback("i:12:zz")).toEqual({ kind: "i", id: 12, action: "zz", status: "" });
    expect(parseCallback("m:3:delyes")).toEqual({ kind: "m", id: 3, action: "delyes" });
    expect(parseCallback("m:3:whatever")).toEqual({ kind: "m", id: 3, action: "back" });
    expect(parseCallback("t:3:hk")).toEqual({ kind: "t", id: 3, code: "hk" });
    expect(parseCallback("p:3:req")).toEqual({ kind: "p", id: 3 });
    expect(parseCallback("s:3:edit")).toEqual({ kind: "s", id: 3, action: "edit" });
    expect(parseCallback("b:3:ok")).toEqual({ kind: "b", id: 3, action: "ok" });
  });
  it("rejects junk", () => {
    for (const d of ["", "x:1:a", "i:abc:g", "i:-1:g", "i:1.5:g", "n:4:new"]) expect(parseCallback(d)).toBeNull();
    expect(parseCallback(undefined)).toBeNull();
  });
  it("every button the UI draws parses back and fits Telegram's 64 bytes", () => {
    const all = [
      ...data(keyboard(idea({ id: 123456 }))),
      ...data(keyboard(idea({ id: 123456 }), "more")),
      ...data(keyboard(idea({ id: 123456 }), "del")),
      ...data(askKeyboard(idea({ id: 123456, status: "bad" }))),
      ...data(askKeyboard(idea({ id: 123456, status: "redo" }))),
    ].flat();
    for (const d of all) expect(parseCallback(d), d).not.toBeNull();
    for (const d of all) expect(new TextEncoder().encode(d).length).toBeLessThanOrEqual(64);
  });
});

describe("content packs", () => {
  const section = (n: number) => ({ title: "LinkedIn", parts: [{ label: "Post", note: "for <you>", text: "x".repeat(n) }] });
  it("one message per section, header first, texts in <pre>", () => {
    const msgs = packMessages(idea({ title: "A&B" }), [section(10), { title: "Threads", parts: [{ text: "hi" }] }], "05 Marketing/p.md");
    expect(msgs).toHaveLength(3);
    expect(msgs[0]).toContain("📝 <b>Пости · ідея #7</b>: A&amp;B");
    expect(msgs[0]).toContain("2 повідомлень");
    expect(msgs[0]).toContain("<i>Нотатка: 05 Marketing/p.md</i>");
    expect(msgs[0]).toContain("#solar #posts #linkedin #threads #idea7");
    expect(msgs[1]).toBe("<b>LinkedIn</b>\n\n<b>Post</b>\n<i>for &lt;you&gt;</i>\n<pre>xxxxxxxxxx</pre>\n\n#solar #posts #linkedin #idea7");
    expect(msgs[2]).toBe("<b>Threads</b>\n\n<pre>hi</pre>\n\n#solar #posts #threads #idea7");
  });
  it("flags a section too long for one Telegram message", () => {
    const fits = PACK_MESSAGE_MAX - "LinkedIn".length - "Post".length - "for <you>".length - 40;
    expect(tooLongSection([section(fits)])).toBeUndefined();
    expect(tooLongSection([section(10), section(fits + 1)])?.title).toBe("LinkedIn");
    expect(packMessage(section(fits)).length).toBeLessThan(4096);
  });
});
