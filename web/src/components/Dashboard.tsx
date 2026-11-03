"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { Item, Profile } from "@/lib/types";
import { num, when } from "@/lib/format";
import PostCard from "./PostCard";
import SwipeBoard from "./SwipeBoard";
import PerformanceLink from "./perf/PerformanceLink";

type Tab = "outliers" | "by_day" | "rising" | "seeds" | "own" | "ideas" | "swipe" | "health";

const TABS: { id: Tab; label: string; hint: string }[] = [
  { id: "outliers", label: "Outliers", hint: "Far above the creator's usual. The format worked, not just the account." },
  { id: "by_day", label: "Fastest", hint: "Independent search: newest posts on the topic, by views per day." },
  { id: "rising", label: "Rising now", hint: "Growth since the previous run: what is taking off right now." },
  { id: "seeds", label: "Tracked", hint: "Links you sent or saved, re-measured every run." },
  { id: "own", label: "Your posts", hint: "Your own posts against your own usual (profile: own.youtube / own.urls)." },
  { id: "ideas", label: "Ideas", hint: "AI breakdowns and ideas adapted to this business." },
  { id: "swipe", label: "Swipe file", hint: "Saved references, from idea to posted." },
  { id: "health", label: "Sources", hint: "What ran, what was skipped, and suggestions for the profile." },
];

export default function Dashboard({ profile, ideas, local }: {
  profile: Profile; ideas: { date: string; file: string; html: string }[]; local: boolean;
}) {
  const [tab, setTab] = useState<Tab>(profile.sections.outliers.length ? "outliers" : "by_day");
  const [items, setItems] = useState<Item[]>(profile.items);
  const [platform, setPlatform] = useState("all");
  const [q, setQ] = useState("");
  const [hideSaved, setHideSaved] = useState(false);
  const [ideaIdx, setIdeaIdx] = useState(0);

  const byKey = useMemo(() => new Map(items.map((i) => [i.key, i])), [items]);
  const platforms = useMemo(() => Array.from(new Set(items.map((i) => i.platform))), [items]);

  const list = useMemo(() => {
    if (!["outliers", "by_day", "rising", "seeds", "own"].includes(tab)) return [];
    const keys = profile.sections[tab as keyof Profile["sections"]] ?? [];
    const needle = q.trim().toLowerCase();
    return keys
      .map((k) => byKey.get(k))
      .filter((i): i is Item => Boolean(i))
      .filter((i) => tab === "seeds" || tab === "own" || !i.dismissed)
      .filter((i) => platform === "all" || i.platform === platform)
      .filter((i) => !hideSaved || !i.saved)
      .filter((i) => !needle || `${i.title} ${i.channel} ${i.hook ?? ""}`.toLowerCase().includes(needle));
  }, [tab, profile.sections, byKey, platform, hideSaved, q]);

  const counts: Partial<Record<Tab, number>> = {
    outliers: profile.sections.outliers.length,
    by_day: profile.sections.by_day.length,
    rising: profile.sections.rising.length,
    seeds: profile.sections.seeds.length,
    own: profile.sections.own?.length ?? 0,
    ideas: ideas.length,
    swipe: profile.swipe.length,
  };

  function patch(key: string, p: Partial<Item>) {
    setItems((all) => all.map((i) => (i.key === key ? { ...i, ...p } : i)));
  }

  const current = TABS.find((t) => t.id === tab)!;

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link href="/" className="text-xs text-muted hover:text-text">← All businesses</Link>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">{profile.name}</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">{profile.business}</p>
        </div>
        <div className="text-right text-xs text-muted">
          <div>Last run {when(profile.date)}</div>
          <div>{num(items.filter((i) => !i.dismissed).length)} posts · {profile.sources.hashtags} hashtags · {profile.sources.keywords} keywords · {profile.sources.watch} watched</div>
          <Link href={`/p/${profile.name}/ads`}
            className="mt-2 inline-block rounded-lg border border-line bg-panel px-2.5 py-1 text-sm text-text hover:border-accent">
            Ads{profile.ads_summary ? ` · ${num(profile.ads_summary.ads)}` : ""} →
          </Link>
          <PerformanceLink name={profile.name} className="ml-2 mt-2" />
        </div>
      </div>

      <nav className="mb-4 flex gap-1 overflow-x-auto border-b border-line">
        {TABS.filter((t) => t.id !== "own" || (profile.sections.own?.length ?? 0) > 0).map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm transition ${tab === t.id ? "border-accent text-text" : "border-transparent text-muted hover:text-text"}`}>
            {t.label}
            {counts[t.id] !== undefined && <span className="ml-1.5 rounded-full bg-panel-2 px-1.5 text-[11px] text-muted">{counts[t.id]}</span>}
          </button>
        ))}
      </nav>
      <p className="mb-4 text-sm text-muted">{current.hint}</p>

      {["outliers", "by_day", "rising", "seeds", "own"].includes(tab) && (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search title, creator, hook…"
              className="w-64 rounded-lg border border-line bg-panel px-3 py-1.5 text-sm outline-none focus:border-accent" />
            <select value={platform} onChange={(e) => setPlatform(e.target.value)}
              className="rounded-lg border border-line bg-panel px-2 py-1.5 text-sm">
              <option value="all">All platforms</option>
              {platforms.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <label className="flex items-center gap-1.5 text-sm text-muted">
              <input type="checkbox" checked={hideSaved} onChange={(e) => setHideSaved(e.target.checked)} /> Hide saved
            </label>
            {!local && <span className="text-xs text-muted">Read-only: buttons copy the command to run on your PC.</span>}
          </div>
          {list.length === 0 ? (
            <Empty tab={tab} />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {list.map((i) => <PostCard key={i.key} item={i} profile={profile.name} local={local} onChange={patch} />)}
            </div>
          )}
        </>
      )}

      {tab === "ideas" && (
        ideas.length === 0 ? (
          <div className="rounded-xl border border-dashed border-line p-8 text-center text-muted">
            No ideas notes yet. In Claude Code run <code className="text-text">/viral-scout {profile.name}</code>.
          </div>
        ) : (
          <div className="grid gap-6 lg:grid-cols-[180px_1fr]">
            <aside className="flex gap-1 overflow-x-auto lg:flex-col">
              {ideas.map((d, i) => (
                <button key={d.file} onClick={() => setIdeaIdx(i)}
                  className={`rounded-lg px-3 py-1.5 text-left text-sm ${i === ideaIdx ? "bg-panel-2 text-text" : "text-muted hover:text-text"}`}>
                  {d.date}
                </button>
              ))}
            </aside>
            <article className="prose-dark min-w-0 rounded-2xl border border-line bg-panel p-5 sm:p-7"
              dangerouslySetInnerHTML={{ __html: ideas[ideaIdx]?.html ?? "" }} />
          </div>
        )
      )}

      {tab === "swipe" && <SwipeBoard notes={profile.swipe} profile={profile.name} local={local} />}

      {tab === "health" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title="Skipped sources">
            {profile.skipped.length ? <ul className="list-disc space-y-1.5 pl-5">{profile.skipped.map((s) => <li key={s}>{s}</li>)}</ul> : <p>Everything ran.</p>}
          </Panel>
          <Panel title="Suggested hashtags (not in the profile yet)">
            {profile.suggested_hashtags.length ? (
              <div className="flex flex-wrap gap-1.5">{profile.suggested_hashtags.map((h) => <span key={h} className="rounded-full bg-panel-2 px-2 py-0.5 text-xs">{h}</span>)}</div>
            ) : <p>None this run.</p>}
          </Panel>
          <Panel title="Creators who keep showing up">
            {profile.repeat_creators.length ? <p>{profile.repeat_creators.join(", ")}</p> : <p>None this run.</p>}
          </Panel>
          <Panel title={`Errors (${profile.errors.length})`}>
            {profile.errors.length ? (
              <ul className="max-h-64 space-y-1 overflow-auto font-mono text-[11px]">{profile.errors.slice(0, 40).map((e, i) => <li key={i} className="break-all">{e}</li>)}</ul>
            ) : <p>None.</p>}
          </Panel>
          <Panel title="Usage (last run)">
            {profile.usage && Object.keys(profile.usage).length ? (
              <ul className="space-y-1 text-xs">{Object.entries(profile.usage).map(([k, v]) => <li key={k}>{k.replace(/_/g, " ")}: <b className="text-text">{num(v)}</b></li>)}</ul>
            ) : <p>Not counted in this run.</p>}
            {profile.budget?.map((b) => <p key={b} className="mt-2 text-viral">⚠️ {b}</p>)}
          </Panel>
          {profile.trends && profile.trends.length > 0 && (
            <Panel title="Trending hashtags (TikTok)">
              <div className="flex flex-wrap gap-1.5">{profile.trends.slice(0, 30).map((t) => (
                <span key={t.hashtag} className={`rounded-full px-2 py-0.5 text-xs ${t.on_topic ? "bg-above text-ink" : "bg-panel-2"}`}>#{t.hashtag} {t.views ? num(t.views) : ""}</span>
              ))}</div>
            </Panel>
          )}
          <Panel title="Recent runs">
            <ul className="space-y-1 text-xs">{profile.runs.slice(0, 10).map((r) => <li key={r.ts}>{when(r.ts)} · {r.items ?? "?"} posts · {r.errors ?? 0} errors</li>)}</ul>
          </Panel>
        </div>
      )}
    </div>
  );
}

function Empty({ tab }: { tab: Tab }) {
  const text: Partial<Record<Tab, string>> = {
    rising: "Needs two runs at least an hour apart (ideally a day) to measure growth.",
    seeds: "No tracked links. Add some with `python -m viral_scout add <profile> <url>` or the Track button.",
  };
  return <div className="rounded-xl border border-dashed border-line p-8 text-center text-muted">{text[tab] ?? "Nothing matches."}</div>;
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-panel p-4 text-sm text-muted">
      <h3 className="mb-2 font-semibold text-text">{title}</h3>
      {children}
    </section>
  );
}
