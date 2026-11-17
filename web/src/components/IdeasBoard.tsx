"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ago, when } from "@/lib/format";

type Feedback = { id: number; createdAt: string; kind: string; value: string | null };
type Idea = {
  id: number; createdAt: string; updatedAt?: string; batch?: string | null; project: string; kind: "idea" | "film";
  title: string; rubric?: string | null; hookType?: string | null; hook?: string | null; angle?: string | null;
  fact?: string | null; source?: string | null; visual?: string | null; cta?: string | null; score?: number | null;
  platforms: string[]; why?: string | null; status: string; comment?: string | null; tags: string[];
  parentId?: number | null; version?: number; stage?: string | null; script?: string | null; draftPath?: string | null;
  postDate?: string | null; feedback?: Feedback[];
};
type Board = {
  source: "board" | "ideas"; can: string[]; error?: string;
  projects: { slug: string; label: string; display: string; profile?: string }[];
  reasons: Record<string, string>; reasonsFor: Record<string, Record<string, string[]>>;
  stages: Record<string, string>; final: string[]; ideas: Idea[];
};

const STATUS: Record<string, [string, string]> = {
  sent: ["⏳ waiting", "border-line text-muted"],
  review: ["👀 film to review", "border-rise/50 text-rise"],
  good: ["👍 good", "border-above/50 text-above"],
  bad: ["👎 bad", "border-mega/50 text-mega"],
  redo: ["🔁 redo", "border-viral/50 text-viral"],
  approved: ["✅ to tracker", "border-above/60 text-above"],
  expand: ["📝 expand", "border-viral/50 text-viral"],
  variants: ["🧬 variants", "border-viral/50 text-viral"],
  tracked: ["📋 in tracker", "border-above/40 text-above"],
  replaced: ["♻️ replaced", "border-line text-muted"],
  varied: ["🧬 varied", "border-line text-muted"],
  deleted: ["🗑 deleted", "border-line text-muted"],
};
const RATE = [["good", "👍"], ["bad", "👎"], ["redo", "🔁"], ["approved", "✅"], ["expand", "📝"], ["variants", "🧬"]] as const;
const FALLBACK_RATE = ["good", "bad", "redo", "approved"];
const OPEN = ["sent", "review"];

export default function IdeasBoard({ initialProject }: { initialProject: string }) {
  const [data, setData] = useState<Board | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [project, setProject] = useState(initialProject);
  const [kind, setKind] = useState<"" | "idea" | "film">("");
  const [status, setStatus] = useState("open");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"new" | "score">("new");
  const [picked, setPicked] = useState<number[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await fetch("/api/ideas-board").then((x) => x.json()).catch(() => ({ error: "request failed" }));
    setLoading(false);
    if (r.error) setErr(String(r.error));
    else {
      setErr("");
      setData(r);
      // ?project= takes the bot project slug (solar) or the viral-scout profile name (nfSolarPanels)
      const hit = (r as Board).projects.find((p) => p.profile === initialProject);
      if (hit) setProject((cur) => (cur === initialProject ? hit.slug : cur));
    }
  }, [initialProject]);
  useEffect(() => { load(); }, [load]);

  async function act(ids: number[], op: string, value = "", proj?: string) {
    setMsg(null);
    const first = data?.ideas.find((i) => i.id === ids[0]);
    const r = await fetch("/api/ideas-board", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ ids, op, value, project: proj ?? first?.project }) }).then((x) => x.json()).catch(() => ({ error: "request failed" }));
    setMsg(r.error ? { ok: false, text: String(r.error) } : { ok: true, text: `Done (${r.changed ?? ids.length} changed). The Telegram message is updated too.` });
    if (!r.error) { setPicked([]); await load(); }
  }

  const label = useMemo(() => Object.fromEntries((data?.projects ?? []).map((p) => [p.slug, p.display])), [data]);
  const ideas = useMemo(() => {
    if (!data) return [];
    const s = q.trim().toLowerCase();
    const list = data.ideas.filter((i) =>
      (!project || i.project === project) && (!kind || i.kind === kind) &&
      (status === "all" ? i.status !== "deleted" : status === "open" ? OPEN.includes(i.status) : i.status === status) &&
      (!s || [i.title, i.hook, i.angle, i.fact, i.visual, i.cta, i.why, i.comment, i.rubric, `#${i.id}`].some((x) => x?.toLowerCase().includes(s))));
    return sort === "score" ? [...list].sort((a, b) => (b.score ?? -1) - (a.score ?? -1)) : list;
  }, [data, project, kind, status, q, sort]);

  if (err && !data) {
    const btn = "rounded border border-line px-2 py-0.5 text-xs text-rise hover:bg-panel-2";
    return (
      <div className="space-y-3">
        <h1 className="text-2xl font-semibold">Ideas</h1>
        <p className="text-mega">{err}</p>
        <section className="rounded-2xl border border-viral/50 bg-panel p-4 text-sm">
          <h2 className="font-semibold">To see the ideas here</h2>
          <ul className="mt-2 divide-y divide-line">
            <li className="flex flex-wrap items-center gap-3 py-1.5"><span>The bot service&apos;s address (<code>STUDIO_SERVICE_URL</code>)</span><Link href="/setup?use=ideas#key-STUDIO_SERVICE_URL" className={`ml-auto ${btn}`}>Set the key →</Link></li>
            <li className="flex flex-wrap items-center gap-3 py-1.5"><span>The ideas API secret (<code>IDEAS_API_SECRET</code>), the same as on the service</span><Link href="/setup?use=ideas#key-IDEAS_API_SECRET" className={`ml-auto ${btn}`}>Set the key →</Link></li>
            <li className="flex flex-wrap items-center gap-3 py-1.5"><span>At least one business with the idea generator set up</span><Link href="/schedule" className={`ml-auto ${btn}`}>Open Schedule →</Link></li>
          </ul>
        </section>
        <button onClick={load} className="rounded-lg border border-line px-3 py-1.5 text-sm">Try again</button>
      </div>
    );
  }
  if (!data) return <div><h1 className="text-2xl font-semibold">Ideas</h1><p className="mt-3 text-muted">Loading every business&apos;s ideas…</p></div>;

  const count = (f: (i: Idea) => boolean) => data.ideas.filter((i) => (!project || i.project === project) && f(i)).length;
  const statuses = ["open", "all", ...Object.keys(STATUS)].filter((s) => s === "open" || s === "all" || count((i) => i.status === s));
  const chip = (on: boolean) => `rounded-full border px-3 py-1 text-xs ${on ? "border-accent bg-accent/15 text-accent" : "border-line text-muted hover:text-text"}`;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">Ideas</h1>
        <span className="text-sm text-muted">{data.ideas.length} ideas and films from {data.projects.length} businesses</span>
        <button onClick={load} disabled={loading} className="ml-auto rounded-lg border border-line px-3 py-1.5 text-sm hover:bg-panel-2 disabled:opacity-40">{loading ? "Loading…" : "↻ Refresh"}</button>
      </div>
      {data.source === "ideas" && (
        <p className="rounded-lg border border-viral/40 bg-viral/5 px-3 py-2 text-xs text-muted">
          Reading through the per-business ideas API: rate (👍 👎 🔁 ✅), comment and remove work. Reason tags, notes for Claude,
          📝 expand, 🧬 variants and &ldquo;posted&rdquo; for films switch on once the bot service&apos;s <code>/api/board</code> is deployed.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-1.5">
        <button onClick={() => setProject("")} className={chip(!project)}>all businesses <span className="opacity-70">{data.ideas.length}</span></button>
        {data.projects.map((p) => (
          <button key={p.slug} onClick={() => setProject(p.slug)} className={chip(project === p.slug)}>
            {p.display} <span className="opacity-70">{data.ideas.filter((i) => i.project === p.slug).length}</span>
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {(["", "idea", "film"] as const).map((k) => (
          <button key={k || "any"} onClick={() => setKind(k)} className={chip(kind === k)}>
            {k === "" ? "ideas + films" : k === "idea" ? "💡 ideas" : "🎬 films"} <span className="opacity-70">{count((i) => !k || i.kind === k)}</span>
          </button>
        ))}
        <span className="mx-1 text-line">|</span>
        {statuses.map((s) => (
          <button key={s} onClick={() => setStatus(s)} className={chip(status === s)}>
            {s === "open" ? "needs a rating" : s === "all" ? "everything" : STATUS[s][0]}{" "}
            <span className="opacity-70">{s === "open" ? count((i) => OPEN.includes(i.status)) : s === "all" ? count((i) => i.status !== "deleted") : count((i) => i.status === s)}</span>
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search titles, hooks, comments, #id…"
          className="w-full max-w-sm rounded-lg border border-line bg-panel px-3 py-1.5 text-sm" />
        <select value={sort} onChange={(e) => setSort(e.target.value as "new" | "score")} className="rounded-lg border border-line bg-panel px-2 py-1.5 text-sm">
          <option value="new">newest first</option><option value="score">best score first</option>
        </select>
        <span className="text-xs text-muted">{ideas.length} shown</span>
        {picked.length > 0 && (
          <span className="ml-auto flex flex-wrap items-center gap-1.5 text-xs">
            {picked.length} picked:
            {RATE.filter(([r]) => data.source === "board" || FALLBACK_RATE.includes(r)).map(([r, e]) => (
              <button key={r} onClick={() => act(picked, "rate", r)} className="rounded border border-line px-2 py-0.5 hover:bg-panel-2" title={STATUS[r][0]}>{e}</button>
            ))}
            <button onClick={() => confirm(`Delete ${picked.length} ideas?`) && act(picked, "remove")} className="rounded border border-line px-2 py-0.5 hover:bg-panel-2">🗑</button>
            <button onClick={() => setPicked([])} className="text-muted hover:text-text">✕</button>
          </span>
        )}
      </div>
      {msg && <p className={`text-sm ${msg.ok ? "text-above" : "text-mega"}`}>{msg.text}</p>}

      <div className="grid gap-3 lg:grid-cols-2">
        {ideas.map((i) => (
          <Card key={i.id} i={i} board={data} business={label[i.project] ?? i.project} showBusiness={!project}
            picked={picked.includes(i.id)} onPick={(on) => setPicked(on ? [...picked, i.id] : picked.filter((x) => x !== i.id))} act={act} />
        ))}
      </div>
      {ideas.length === 0 && <p className="text-muted">Nothing here with these filters.</p>}
    </div>
  );
}

function Card({ i, board, business, showBusiness, picked, onPick, act }: {
  i: Idea; board: Board; business: string; showBusiness: boolean; picked: boolean; onPick: (on: boolean) => void;
  act: (ids: number[], op: string, value?: string, project?: string) => Promise<void>;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const done = board.final.includes(i.status);
  const isBoard = board.source === "board";
  const tagCodes = isBoard ? board.reasonsFor[i.project]?.[i.status] ?? [] : [];
  const [st, cls] = STATUS[i.status] ?? [i.status, "border-line text-muted"];
  const run = async (op: string, value = "") => { setBusy(true); await act([i.id], op, value, i.project); setBusy(false); };
  const rates = RATE.filter(([r]) => isBoard || FALLBACK_RATE.includes(r));

  return (
    <article className={`flex flex-col gap-2 rounded-2xl border bg-panel p-4 text-sm ${picked ? "border-accent" : "border-line"}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <input type="checkbox" checked={picked} onChange={(e) => onPick(e.target.checked)} aria-label={`pick #${i.id}`} />
        {showBusiness && <span className="rounded-full bg-panel-2 px-2 py-0.5 font-medium">{business}</span>}
        <span className="text-muted">{i.kind === "film" ? "🎬 film" : "💡 idea"} #{i.id}</span>
        {i.rubric && <span className="text-muted">· {i.rubric}</span>}
        {i.version && i.version > 1 ? <span className="text-muted">· v{i.version} (replaces #{i.parentId})</span> : i.parentId ? <span className="text-muted">· variant of #{i.parentId}</span> : null}
        <span className={`rounded-full border px-2 py-0.5 ${cls}`}>{st}</span>
        {i.stage && <span className="rounded-full border border-line px-2 py-0.5 text-muted">🎬 {board.stages[i.stage] ?? i.stage}</span>}
        {i.score != null && <span className="ml-auto font-semibold" title="the generator's own score, out of 50">⭐ {i.score}/50</span>}
      </div>
      <h3 className="text-base font-semibold">{i.title}</h3>
      {i.hook && <p>🪝 {i.hookType ? <i className="text-muted">{i.hookType}: </i> : null}&ldquo;{i.hook}&rdquo;</p>}
      {i.angle && <p className="text-muted">🎯 {i.angle}</p>}
      {i.fact && <p className="text-muted">📊 {i.fact}{i.source && !i.source.startsWith("film:") ? ` (${i.source})` : ""}</p>}
      {i.visual && <p className="text-muted">🎞️ {i.visual}</p>}
      {i.cta && <p className="text-muted">📣 {i.cta}</p>}
      {i.why && <p className="text-muted">🕐 {i.why}</p>}
      {i.platforms.length > 0 && <p className="text-xs text-muted">📲 {i.platforms.join(" · ")}</p>}
      {i.kind === "film" && i.draftPath && <p className="truncate text-xs text-muted" title={i.draftPath}>🎞 {i.draftPath}{i.postDate ? ` · post ${i.postDate.slice(0, 10)}` : ""}</p>}
      {i.tags.length > 0 && <p className="text-xs">🏷 {i.tags.map((t) => board.reasons[t] ?? t).join(" · ")}</p>}
      {i.comment && <p className="whitespace-pre-line rounded-lg bg-panel-2 px-2 py-1.5 text-xs">💬 {i.comment}</p>}

      {!done && (
        <div className="flex flex-wrap items-center gap-1.5">
          {rates.map(([r, e]) => (
            <button key={r} disabled={busy} onClick={() => run("rate", i.status === r ? "sent" : r)}
              title={i.status === r ? "Click again to undo" : STATUS[r][0]}
              className={`rounded-lg border px-2 py-1 text-sm disabled:opacity-40 ${i.status === r ? "border-accent bg-accent/15" : "border-line hover:bg-panel-2"}`}>{e}</button>
          ))}
          {isBoard && i.kind === "film" && (
            <button disabled={busy} onClick={() => run("posted")} className={`rounded-lg border px-2 py-1 text-xs disabled:opacity-40 ${i.stage === "posted" ? "border-above text-above" : "border-line hover:bg-panel-2"}`}>
              {i.stage === "posted" ? "📤 posted ✓" : "📤 mark posted"}
            </button>
          )}
          <button disabled={busy} onClick={() => confirm(`Delete #${i.id} "${i.title}"?`) && run("remove")} className="ml-auto rounded-lg border border-line px-2 py-1 text-xs text-muted hover:text-mega disabled:opacity-40">🗑 delete</button>
        </div>
      )}
      {tagCodes.length > 0 && !done && (
        <div className="flex flex-wrap gap-1">
          {tagCodes.map((c) => (
            <button key={c} disabled={busy} onClick={() => run("tag", c)}
              className={`rounded-full border px-2 py-0.5 text-[11px] disabled:opacity-40 ${i.tags.includes(c) ? "border-accent bg-accent/15 text-accent" : "border-line text-muted hover:text-text"}`}>
              {i.tags.includes(c) ? "✓ " : ""}{board.reasons[c] ?? c}
            </button>
          ))}
        </div>
      )}
      <div className="flex gap-1.5">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder={isBoard ? "Comment, or a note for Claude…" : "Comment…"}
          className="min-w-0 flex-1 rounded-lg border border-line bg-panel-2 px-2 py-1 text-xs" />
        <button disabled={busy || !text.trim()} onClick={async () => { await run("comment", text.trim()); setText(""); }}
          className="rounded-lg border border-line px-2 py-1 text-xs hover:bg-panel-2 disabled:opacity-40" title="Saved on the idea; the next generation reads it">💬</button>
        {isBoard && (
          <button disabled={busy || !text.trim()} onClick={async () => { await run("note", text.trim()); setText(""); }}
            className="rounded-lg border border-line px-2 py-1 text-xs hover:bg-panel-2 disabled:opacity-40" title="A note for Claude's notes job (rewrite the script, re-cut the film…)">🤖 note</button>
        )}
      </div>
      <div className="flex items-center gap-2 text-[11px] text-muted">
        <span suppressHydrationWarning title={when(i.createdAt)}>{ago(i.createdAt)}</span>
        {i.batch && <span>· {i.batch}</span>}
        {(i.feedback?.length ?? 0) > 0 && <button onClick={() => setOpen(!open)} className="ml-auto text-rise hover:underline">{open ? "hide history" : `history (${i.feedback!.length})`}</button>}
      </div>
      {open && (
        <ul className="space-y-0.5 border-t border-line pt-2 text-[11px] text-muted">
          {i.feedback!.map((f) => (
            <li key={f.id}><span suppressHydrationWarning title={when(f.createdAt)}>{ago(f.createdAt)}</span> · {f.kind}{f.value ? `: ${f.kind === "tag" || f.kind === "untag" ? board.reasons[f.value] ?? f.value : f.value}` : ""}</li>
          ))}
        </ul>
      )}
    </article>
  );
}
