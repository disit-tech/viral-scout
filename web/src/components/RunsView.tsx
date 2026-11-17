"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { Profile } from "@/lib/types";
import { num, when } from "@/lib/format";

// The Runs tab of a business: what each run (videos, ads, search demand) did, what it couldn't do and why,
// and, for videos, the hashtags and creators worth adding.

export type AdsRun = { date: string; ads: number; advertisers: number; coverage: string[]; skipped: string[]; errors: string[]; usage?: Record<string, number>; budget?: string[] } | null;
export type DemandRun = { date: string; fetched: string; terms: number; geo: string; skipped: string[]; errors: string[]; usage?: Record<string, number> } | null;

const USAGE: Record<string, (v: number) => string> = {
  youtube_api_units: (v) => `${num(v)} YouTube API units (of 10,000 free a day)`,
  page_requests: (v) => `${num(v)} public page loads`,
  apify_items: (v) => `${num(v)} Apify results (paid)`,
  apify_runs: (v) => `${num(v)} Apify actor runs`,
  whisper_seconds: (v) => `${Math.max(1, Math.round(v / 60))} min of local transcription`,
};
const usageText = (u?: Record<string, number>) =>
  Object.entries(u ?? {}).filter(([, v]) => v).map(([k, v]) => (USAGE[k] ? USAGE[k](v) : `${num(v)} ${k.replace(/_/g, " ")}`));
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;

type Kind = { title: string; tag: string; cls: string; note: string; needsSetup?: boolean; key?: string };
const KEYISH = /\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b/g;     // APIFY_TOKEN, META_AD_LIBRARY_TOKEN, …

/** Plain-language reading of a "skipped" line. setKeys: keys set now (local dashboard), to spot ones added since. */
function classify(s: string, setKeys: Set<string> | null): Kind {
  const keys = Array.from(new Set(s.match(KEYISH) ?? [])).filter((k) => !/^HTTP_/.test(k));
  const title = /bot check/i.test(s) ? "Video details (likes, titles) for part of the videos"
    : /caption|transcript/i.test(s) ? "Some transcripts" : s.split(":")[0];
  if (/free run/i.test(s)) return { title, tag: "expected", cls: "border-line text-muted", note: "Run now is YouTube-only to stay free; the Monday run includes this." };
  if (keys.length && setKeys && keys.every((k) => setKeys.has(k)))
    return { title, tag: "key added since", cls: "border-above/50 text-above", note: `${keys.join(" and ")} ${keys.length > 1 ? "are" : "is"} set now, so the next run includes this.` };
  if (keys.length && /\bEU\b|\bEEA\b/.test(s))
    return { title, tag: "optional", cls: "border-line text-muted", note: "Only covers ads shown in the EU. Not needed while this business targets the US.", needsSetup: true, key: keys[0] };
  if (keys.length) return { title, tag: "needs a key", cls: "border-viral/60 text-viral", note: `Add ${keys.join(" and ")} on the Setup page to turn this on.`, needsSetup: true, key: keys[0] };
  if (/429|rate.?limit|bot check/i.test(s))
    return { title, tag: "temporary", cls: "border-rise/50 text-rise", note: "The platform slowed this kind of request down for a while. Nothing to fix; it is retried on the next run." };
  return { title, tag: "note", cls: "border-line text-muted", note: "" };
}

export default function RunsView({ profile, ads, demand, local }: { profile: Profile | null; ads: AdsRun; demand: DemandRun; local: boolean }) {
  const [setKeys, setSetKeys] = useState<Set<string> | null>(null);
  useEffect(() => {                       // which keys are set now (local dashboard only)
    if (!local) return;
    fetch("/api/keys").then((r) => r.json()).then((d) => {
      if (d?.ok) setSetKeys(new Set((d.keys as { name: string; set: boolean }[]).filter((k) => k.set).map((k) => k.name)));
    }).catch(() => undefined);
  }, [local]);
  const name = profile?.name ?? "";

  return (
    <div className="space-y-8">
      <p className="max-w-3xl text-sm text-muted">
        What each run did: the weekly videos run, the weekly ads run and the search demand refresh. For each: when it ran,
        what it couldn&apos;t do and why (most of it is expected or fixes itself), errors, and what it used.
      </p>
      <nav className="flex flex-wrap gap-2 text-sm">
        {[["videos", "🎬 Videos run", profile?.runs[0]?.ts ?? profile?.date], ["ads", "📢 Ads run", ads?.date], ["demand", "🔎 Search demand", demand?.fetched]].map(([id, label, ts]) => (
          <a key={id} href={`#run-${id}`} className="rounded-full border border-line px-3 py-1 text-muted hover:text-text">
            {label} <span className="text-xs">· {ts ? when(ts) : "not run"}</span>
          </a>
        ))}
      </nav>

      <Section id="videos" title="🎬 Videos run" when_={profile?.runs[0]?.ts ?? profile?.date ?? null}
        summary={profile ? `${num(profile.runs[0]?.items ?? profile.items.length)} posts kept · ${plural(profile.runs[0]?.errors ?? profile.errors.length, "error")}` : "No videos run yet."}
        usage={profile?.usage} budget={profile?.budget} link={profile ? { href: `/p/${name}/videos`, label: "Open videos →" } : undefined}>
        {profile && <VideoRun profile={profile} local={local} setKeys={setKeys} />}
      </Section>

      <Section id="ads" title="📢 Ads run" when_={ads?.date ?? null}
        summary={ads ? `${num(ads.ads)} ads from ${num(ads.advertisers)} advertisers · ${plural(ads.errors.length, "error")}` : "No ads run yet."}
        usage={ads?.usage} budget={ads?.budget} link={ads ? { href: `/p/${name}/ads`, label: "Open ads →" } : undefined}>
        {ads && (
          <div className="grid gap-4 lg:grid-cols-2">
            <Skipped lines={ads.skipped} setKeys={setKeys} text="Ad libraries the run couldn't read, and why." />
            {ads.coverage.length > 0 && (
              <Panel title="What it read" text="Each ad library this run used, and how many ads came from it.">
                <ul className="list-disc space-y-1.5 pl-5">{ads.coverage.map((c) => <li key={c}>{c}</li>)}</ul>
              </Panel>
            )}
            <Errors errors={ads.errors} />
          </div>
        )}
      </Section>

      <Section id="demand" title="🔎 Search demand" when_={demand?.fetched ?? null}
        summary={demand ? `${plural(demand.terms, "term")} from Google Trends for ${demand.geo || "the area"} · ${plural(demand.errors.length, "error")}` : "Not fetched yet."}
        usage={demand?.usage} link={demand ? { href: `/p/${name}/demand`, label: "Open search demand →" } : undefined}>
        {demand && (demand.skipped.length > 0 || demand.errors.length > 0) && (
          <div className="grid gap-4 lg:grid-cols-2">
            {demand.skipped.length > 0 && <Skipped lines={demand.skipped} setKeys={setKeys} text="Parts of the refresh that were left out." />}
            <Errors errors={demand.errors} />
          </div>
        )}
      </Section>
    </div>
  );
}

function Section({ id, title, when_, summary, usage, budget, link, children }: {
  id: string; title: string; when_: string | null; summary: string; usage?: Record<string, number>; budget?: string[];
  link?: { href: string; label: string }; children?: React.ReactNode;
}) {
  return (
    <section id={`run-${id}`} className="scroll-mt-20 space-y-3">
      <div className="rounded-2xl border border-line bg-panel p-4 text-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-semibold">{title}</h2>
          {link && <Link href={link.href} className="text-xs text-muted hover:text-text">{link.label}</Link>}
        </div>
        <p className="mt-1 text-muted"><span className="text-text">{when_ ? when(when_) : "never"}</span> · {summary}</p>
        {usageText(usage).length > 0 && <p className="mt-1 text-xs text-muted">Used: {usageText(usage).join(" · ")}</p>}
        {budget?.map((b) => <p key={b} className="mt-2 text-viral">⚠️ {b}</p>)}
      </div>
      {children}
    </section>
  );
}

function Skipped({ lines, setKeys, text }: { lines: string[]; setKeys: Set<string> | null; text: string }) {
  return (
    <Panel title="What didn't run, and why" text={text}>
      {lines.length ? (
        <ul className="space-y-3">
          {lines.map((s) => {
            const k = classify(s, setKeys);
            return (
              <li key={s}>
                <div className="flex flex-wrap items-start gap-2">
                  <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] ${k.cls}`}>{k.tag}</span>
                  <span className="text-text">{k.title}</span>
                </div>
                {k.note && <p className="mt-0.5 text-xs">{k.note}{k.needsSetup && <> <Link href={k.key ? `/setup#key-${k.key}` : "/setup"} className="whitespace-nowrap rounded border border-line px-2 py-0.5 text-rise hover:bg-panel-2">Set {k.key ?? "the key"} →</Link></>}</p>}
                <p className="mt-0.5 text-[11px] text-muted/80">{s}</p>
              </li>
            );
          })}
        </ul>
      ) : <p>Everything ran.</p>}
    </Panel>
  );
}

function Errors({ errors }: { errors: string[] }) {
  if (!errors.length) return null;
  return (
    <Panel title={`Errors (${errors.length})`} text="Individual requests that failed. A few are normal (a deleted video, a timeout); many in a row usually mean a missing or expired key.">
      <ul className="max-h-64 space-y-1 overflow-auto font-mono text-[11px]">{errors.slice(0, 40).map((e, i) => <li key={i} className="break-all">{e}</li>)}</ul>
    </Panel>
  );
}

function VideoRun({ profile, local, setKeys }: { profile: Profile; local: boolean; setKeys: Set<string> | null }) {
  const [added, setAdded] = useState<Record<string, "busy" | "ok" | string>>({});

  async function addHashtag(tag: string) {
    setAdded((a) => ({ ...a, [tag]: "busy" }));
    const cur = await fetch(`/api/profile?profile=${encodeURIComponent(profile.name)}`).then((r) => r.json()).catch(() => null);
    if (!cur?.ok) { setAdded((a) => ({ ...a, [tag]: cur?.error ?? "could not read the profile" })); return; }
    const list: string[] = (cur.fields?.["discover.youtube.hashtags"] as string[]) ?? [];
    if (list.map((x) => x.toLowerCase()).includes(tag)) { setAdded((a) => ({ ...a, [tag]: "ok" })); return; }
    const r = await fetch("/api/profile", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ profile: profile.name, base: cur.base, set: { "discover.youtube.hashtags": [...list, tag] } }),
    }).then((x) => x.json()).catch(() => ({ ok: false, error: "request failed" }));
    setAdded((a) => ({ ...a, [tag]: r.ok ? "ok" : r.error ?? "not saved" }));
  }

  const suggested = profile.suggested_hashtags.map((h) => {
    const m = h.match(/^#?(\S+?)(?:\s*\((\d+)\))?$/);
    return { tag: (m?.[1] ?? h).replace(/^#/, "").toLowerCase(), n: m?.[2] ? Number(m[2]) : null };
  });

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Skipped lines={profile.skipped} setKeys={setKeys} text="Parts of the search the run had to leave out. Most are expected or fix themselves." />

      <Panel title="Hashtags to add" text="These keep appearing on the posts this run found, but they're not in your search list. Add the ones that fit your business; the next run searches them too. The number is how many found posts used it.">
        {suggested.length ? (
          <div className="flex flex-wrap gap-1.5">
            {suggested.map(({ tag, n }) => {
              const st = added[tag];
              return (
                <span key={tag} className="inline-flex items-center gap-1 rounded-full border border-line bg-panel-2 py-0.5 pl-2 pr-1 text-xs text-text">
                  #{tag}{n !== null && <span className="text-muted">{n}</span>}
                  {local ? (
                    st === "ok" ? <span className="px-1 text-above" title="Added to Settings → Videos → YouTube hashtags">✓</span>
                      : <button disabled={st === "busy"} onClick={() => addHashtag(tag)} title="Add to YouTube hashtags"
                          className="rounded-full px-1.5 text-accent hover:bg-accent/15 disabled:opacity-50">{st === "busy" ? "…" : "＋"}</button>
                  ) : null}
                </span>
              );
            })}
          </div>
        ) : <p>None this run.</p>}
        {Object.entries(added).filter(([, v]) => !["ok", "busy"].includes(v)).map(([t, v]) => <p key={t} className="mt-2 text-xs text-mega">#{t}: {v}</p>)}
        <p className="mt-2 text-xs"><Link href={`/p/${profile.name}/settings#videos`} className="text-rise hover:underline">All search settings →</Link></p>
      </Panel>

      <Panel title="Creators who keep showing up" text="Accounts this run found more than once. If they fit, add them to your watch list: every run then checks their newest posts against their own usual.">
        {profile.repeat_creators.length ? (
          <>
            <div className="flex flex-wrap gap-1.5">
              {profile.repeat_creators.map((c) => <span key={c} className="rounded-full bg-panel-2 px-2 py-0.5 text-xs text-text">{c}</span>)}
            </div>
            <p className="mt-2 text-xs"><Link href={`/p/${profile.name}/settings#videos`} className="text-rise hover:underline">Add to the watch list in Settings →</Link></p>
          </>
        ) : <p>None this run.</p>}
      </Panel>

      <Errors errors={profile.errors} />

      {profile.trends && profile.trends.length > 0 && (
        <Panel title="Trending on TikTok" text="TikTok's trending hashtags this week. Highlighted ones match your topic.">
          <div className="flex flex-wrap gap-1.5">{profile.trends.slice(0, 30).map((t) => (
            <span key={t.hashtag} className={`rounded-full px-2 py-0.5 text-xs ${t.on_topic ? "bg-above text-ink" : "bg-panel-2"}`}>#{t.hashtag} {t.views ? num(t.views) : ""}</span>
          ))}</div>
        </Panel>
      )}

      <Panel title="Recent videos runs" text="One line per run: when, how many posts it kept, errors, and what it used.">
        <ul className="space-y-1.5 text-xs">
          {profile.runs.slice(0, 10).map((r) => (
            <li key={r.ts}>
              <span className="text-text">{when(r.ts)}</span> · {r.items ?? "?"} posts · <span className={r.errors ? "text-mega" : ""}>{plural(r.errors ?? 0, "error")}</span>
              {usageText(r.usage).length > 0 && <div className="text-[11px] text-muted/80">{usageText(r.usage).join(" · ")}</div>}
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

function Panel({ title, text, children }: { title: string; text: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-panel p-4 text-sm text-muted">
      <h3 className="font-semibold text-text">{title}</h3>
      <p className="mb-3 mt-0.5 text-xs">{text}</p>
      {children}
    </section>
  );
}
