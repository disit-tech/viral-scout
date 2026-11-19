"use client";

import { useCallback, useEffect, useState } from "react";

type Row = {
  kind: "film" | "post"; date: string; time: string; title: string; file: string; status: string;
  state: "posted" | "stopped" | "due now" | "waiting for approval" | "missed" | "scheduled";
  approved: boolean; caption: boolean; platforms: Record<string, boolean>;
};
type Key = { connected: boolean; missing: string[]; connect: "meta" | "google" | "linkedin"; expires?: string };
type Status = {
  profile: string; timezone: string; now: string; error?: string;
  settings: {
    approval: "owner" | "auto"; per_day: number; times: string[]; platforms: string[]; auto_post: Record<string, boolean>;
    posts: { enabled: boolean; per_day: number; times: string[]; platforms: string[] };
    challenges: { enabled: boolean; dm: boolean; reply_text: string; reply_text_instagram: string };
    film_job: boolean; posts_job: boolean;
  };
  queue: string; posts_queue: string; films: Row[]; posts: Row[]; keys: Record<string, Key>; warnings: string[];
  published: { time: string; platform: string; permalink?: string; id?: string; video?: string; post?: string }[];
  challenges: { replied: number; active: number };
};
type Msg = { ok: boolean; text: string } | null;

const PLATFORMS = ["instagram", "facebook", "youtube", "linkedin"] as const;
const NAMES: Record<string, string> = { instagram: "Instagram", facebook: "Facebook", youtube: "YouTube", linkedin: "LinkedIn" };
const field = "w-full rounded-lg border border-line bg-panel-2 px-2 py-1.5 text-sm";
const btn = "rounded-lg border border-line px-3 py-1.5 text-sm hover:bg-panel-2 disabled:opacity-40";
const STATE_STYLE: Record<Row["state"], string> = {
  posted: "text-above", stopped: "text-mega", "due now": "text-accent", "waiting for approval": "text-muted", missed: "text-muted", scheduled: "text-text",
};
const STATE_LABEL: Record<Row["state"], string> = {
  posted: "📤 posted", stopped: "🛑 stopped", "due now": "⏱ due now", "waiting for approval": "👀 waiting for ✅", missed: "missed", scheduled: "🗓 scheduled",
};

async function post(body: object) {
  return fetch("/api/posting", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })
    .then((r) => r.json()).catch(() => ({ ok: false, output: "request failed" }));
}

/** A business's Posting page: auto mode on/off, films per day and times, which platforms post by themselves, text/photo
 *  posts, comment challenges, the accounts each platform posts to, the queue with 🛑 / ✅ per row, and recent posts.
 *  Local dashboard only: everything runs `python -m viral_scout publish <p> …` on this PC. */
export default function PostingView({ profile }: { profile: string }) {
  const [st, setSt] = useState<Status | null>(null);
  const [loadErr, setLoadErr] = useState("");
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState<Msg>(null);
  const [form, setForm] = useState<Status["settings"] | null>(null);
  const [page, setPage] = useState("");
  const [org, setOrg] = useState("");

  const load = useCallback(async () => {
    const d = await fetch(`/api/posting?profile=${encodeURIComponent(profile)}`).then((r) => r.json()).catch(() => ({ error: "couldn't reach the dashboard server" }));
    if (d.error) setLoadErr(String(d.error));
    else { setSt(d); setForm(d.settings); setLoadErr(""); }
  }, [profile]);
  useEffect(() => { load(); }, [load]);

  async function act(key: string, body: object) {
    setBusy(key);
    setMsg(null);
    const r = await post({ profile, ...body });
    setBusy("");
    setMsg({ ok: !!r.ok, text: String(r.output ?? "").trim().split("\n").filter(Boolean).slice(-4).join(" · ") || (r.ok ? "Done." : "Failed.") });
    load();
  }

  async function save() {
    if (!form || !st) return;
    setBusy("save");
    setMsg(null);
    const g = await fetch(`/api/profile?profile=${encodeURIComponent(profile)}`).then((r) => r.json()).catch(() => ({}));
    const set: Record<string, unknown> = {
      "publish.approval": form.approval, "publish.per_day": form.per_day, "publish.times": form.times.slice(0, form.per_day),
      "publish.posts.enabled": form.posts.enabled, "publish.posts.per_day": form.posts.per_day,
      "publish.posts.times": form.posts.times.slice(0, form.posts.per_day), "publish.posts.platforms": form.posts.platforms,
      "publish.challenges.enabled": form.challenges.enabled, "publish.challenges.dm": form.challenges.dm,
      "publish.challenges.reply_text": form.challenges.reply_text, "publish.challenges.reply_text_instagram": form.challenges.reply_text_instagram,
      "jobs.film.enabled": form.film_job, "jobs.posts.enabled": form.posts_job,
    };
    for (const p of PLATFORMS) set[`publish.auto_post.${p}`] = !!form.auto_post[p];
    const r = await fetch("/api/profile", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ profile, base: g.base, set }) }).then((x) => x.json()).catch(() => ({ ok: false, error: "request failed" }));
    setBusy("");
    setMsg({ ok: !!r.ok, text: r.ok ? `Saved (${(r.changed ?? []).length} changes). Press "Update tasks" when you turned a job or a platform on or off.` : String(r.error ?? "failed") });
    load();
  }

  if (loadErr) return <div className="rounded-xl border border-dashed border-line p-6 text-sm text-mega">Couldn&apos;t load the posting status: {loadErr}</div>;
  if (!st || !form) return <div className="p-6 text-sm text-muted">Loading…</div>;

  const times = (n: number, t: string[]) => Array.from({ length: n }, (_, i) => t[i] ?? t[t.length - 1] ?? "18:30");
  const setTime = (which: "films" | "posts", i: number, v: string) => {
    if (which === "films") { const t = times(form.per_day, form.times); t[i] = v; setForm({ ...form, times: t }); }
    else { const t = times(form.posts.per_day, form.posts.times); t[i] = v; setForm({ ...form, posts: { ...form.posts, times: t } }); }
  };
  const autoOn = PLATFORMS.filter((p) => st.settings.auto_post[p]);
  const notConnected = autoOn.filter((p) => !st.keys[p]?.connected);

  return (
    <div className="space-y-5 text-sm">
      {/* ── Status line ── */}
      <section className="rounded-2xl border border-line bg-panel p-4">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-xl font-semibold">Posting</h2>
          <span className={`rounded-full px-2 py-0.5 text-xs ${st.settings.approval === "auto" ? "bg-accent/15 text-accent" : "bg-panel-2 text-muted"}`}>
            {st.settings.approval === "auto" ? "Auto mode: posts without your ✅" : "Every post waits for your ✅"}
          </span>
          <span className="text-xs text-muted">{st.settings.per_day} film(s) a day · {st.timezone} · now {st.now.slice(11, 16)}</span>
          <div className="ml-auto flex flex-wrap gap-2">
            <button className={btn} disabled={!!busy} onClick={() => act("dry", { action: "dry-run" })}>{busy === "dry" ? "Checking…" : "What would post now?"}</button>
            <button className={btn} disabled={!!busy} onClick={() => act("now", { action: "autopost" })}>{busy === "now" ? "Starting…" : "▶ Post what's due now"}</button>
            <button className={btn} disabled={!!busy} onClick={() => act("sync", { action: "sync-tasks" })} title="Registers the film, posts and autopost tasks in Task Scheduler. New tasks start paused: turn them on on the Schedule page.">
              {busy === "sync" ? "Updating…" : "⟳ Update tasks"}</button>
          </div>
        </div>
        {notConnected.length > 0 && (
          <p className="mt-2 text-mega">Not connected yet: {notConnected.map((p) => NAMES[p]).join(", ")}. Nothing posts there until you connect it below.</p>
        )}
        {st.warnings.map((w) => <p key={w} className="mt-1 text-mega">⚠ {w}</p>)}
        {msg && <p className={`mt-2 whitespace-pre-wrap ${msg.ok ? "text-above" : "text-mega"}`}>{msg.text}</p>}
      </section>

      {/* ── Settings ── */}
      <section className="rounded-2xl border border-line bg-panel p-4">
        <h3 className="mb-1 font-semibold">How it posts</h3>
        <p className="mb-3 text-muted">Saved in this business&apos;s profile (<code>publish:</code> and <code>jobs:</code>). TikTok always stays by hand: its API keeps posts private.</p>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-3">
            <label className="block">Approval
              <select className={field} value={form.approval} onChange={(e) => setForm({ ...form, approval: e.target.value as "owner" | "auto" })}>
                <option value="auto">Auto: post every finished film and post (🛑 to stop one)</option>
                <option value="owner">Owner: each one waits for my ✅</option>
              </select>
            </label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.film_job} onChange={(e) => setForm({ ...form, film_job: e.target.checked })} />
              Make films every day (film job)</label>
            <label className="block">Films per day
              <select className={field} value={form.per_day} onChange={(e) => setForm({ ...form, per_day: Number(e.target.value) })}>
                {[1, 2, 3].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
            <div>Posting times
              <div className="mt-1 flex flex-wrap gap-2">{times(form.per_day, form.times).map((t, i) => (
                <label key={i} className="flex items-center gap-1 text-xs text-muted">film {i + 1}
                  <input type="time" className={`${field} w-28`} value={t} onChange={(e) => setTime("films", i, e.target.value)} /></label>))}</div>
            </div>
            <div>Posts by itself to
              <div className="mt-1 flex flex-wrap gap-3">{PLATFORMS.map((p) => (
                <label key={p} className="flex items-center gap-1">
                  <input type="checkbox" checked={!!form.auto_post[p]} onChange={(e) => setForm({ ...form, auto_post: { ...form.auto_post, [p]: e.target.checked } })} />
                  {NAMES[p]}</label>))}</div>
            </div>
          </div>
          <div className="space-y-3">
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.posts.enabled && form.posts_job}
              onChange={(e) => setForm({ ...form, posts_job: e.target.checked, posts: { ...form.posts, enabled: e.target.checked } })} />
              Text / photo posts every day (posts job)</label>
            <div className="grid grid-cols-2 gap-2">
              <label>Per day<select className={field} value={form.posts.per_day} onChange={(e) => setForm({ ...form, posts: { ...form.posts, per_day: Number(e.target.value) } })}>
                {[1, 2, 3].map((n) => <option key={n} value={n}>{n}</option>)}</select></label>
              <div>Times<div className="mt-0.5 flex flex-wrap gap-1">{times(form.posts.per_day, form.posts.times).map((t, i) => (
                <input key={i} type="time" className={`${field} w-28`} value={t} onChange={(e) => setTime("posts", i, e.target.value)} />))}</div></div>
            </div>
            <div>Text/photo posts go to
              <div className="mt-1 flex gap-3">{(["linkedin", "facebook"] as const).map((p) => (
                <label key={p} className="flex items-center gap-1"><input type="checkbox" checked={form.posts.platforms.includes(p)}
                  onChange={(e) => setForm({ ...form, posts: { ...form.posts, platforms: e.target.checked ? [...form.posts.platforms, p] : form.posts.platforms.filter((x) => x !== p) } })} />
                  {NAMES[p]}</label>))}</div>
              <p className="mt-0.5 text-xs text-muted">Instagram photo posts stay by hand (its API only takes a public image URL).</p>
            </div>
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.challenges.enabled}
              onChange={(e) => setForm({ ...form, challenges: { ...form.challenges, enabled: e.target.checked } })} />
              Comment challenges (&quot;comment GUIDE and get the checklist&quot;)</label>
            {form.challenges.enabled && (<>
              <label className="block">Reply under a matching comment (<code>{"{link}"}</code> = the reward)
                <input className={field} value={form.challenges.reply_text} onChange={(e) => setForm({ ...form, challenges: { ...form.challenges, reply_text: e.target.value } })} /></label>
              <label className="block">Instagram reply (links aren&apos;t clickable there)
                <input className={field} value={form.challenges.reply_text_instagram} onChange={(e) => setForm({ ...form, challenges: { ...form.challenges, reply_text_instagram: e.target.value } })} /></label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={form.challenges.dm} onChange={(e) => setForm({ ...form, challenges: { ...form.challenges, dm: e.target.checked } })} />
                Try a private message first (needs Meta App Review)</label>
              <p className="text-xs text-muted">{st.challenges.active} post(s) with a challenge this week · {st.challenges.replied} comments answered so far. &quot;Tag 2 friends&quot; runs on Instagram only.</p>
            </>)}
          </div>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button disabled={!!busy} onClick={save} className="rounded-lg border border-accent/60 px-3 py-1.5 text-accent hover:bg-accent/10 disabled:opacity-40">{busy === "save" ? "Saving…" : "Save"}</button>
          <button disabled={!!busy} onClick={() => setForm(st.settings)} className={btn}>Undo changes</button>
        </div>
      </section>

      {/* ── Accounts ── */}
      <section className="rounded-2xl border border-line bg-panel p-4">
        <h3 className="mb-1 font-semibold">Accounts</h3>
        <p className="mb-3 text-muted">The keys this business posts with, saved in <code>data/publish/{profile}/keys.env</code> on this PC (never in the profile).</p>
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border border-line p-3">
            <div className="font-medium">Meta: Instagram + Facebook</div>
            <p className="my-1 text-xs">{(["instagram", "facebook"] as const).map((p) => <span key={p} className="mr-2">{st.keys[p]?.connected ? "✅" : "⚪"} {NAMES[p]}</span>)}</p>
            <p className="mb-2 text-xs text-muted">Uses your Facebook sign-in from the Setup page (Connect Meta; sign in again once so it asks for posting). Then pick this business&apos;s Page.</p>
            <input className={field} placeholder="Page name or id (empty = match the handles)" value={page} onChange={(e) => setPage(e.target.value)} />
            <button className={`${btn} mt-2`} disabled={!!busy} onClick={() => act("meta", { action: "connect-meta", page })}>{busy === "meta" ? "Connecting…" : "Connect Page"}</button>
          </div>
          <div className="rounded-xl border border-line p-3">
            <div className="font-medium">YouTube</div>
            <p className="my-1 text-xs">{st.keys.youtube?.connected ? "✅ connected" : "⚪ not connected"}</p>
            <p className="mb-2 text-xs text-muted">Sign in as the business&apos;s channel. Until Google audits the API project, uploads arrive as private.</p>
            <button className={btn} disabled={!!busy} onClick={() => act("google", { action: "connect-google" })}>{busy === "google" ? "Opening…" : "Connect YouTube"}</button>
          </div>
          <div className="rounded-xl border border-line p-3">
            <div className="font-medium">LinkedIn</div>
            <p className="my-1 text-xs">{st.keys.linkedin?.connected ? `✅ connected${st.keys.linkedin.expires ? ` · renew by ${st.keys.linkedin.expires}` : ""}` : "⚪ not connected"}</p>
            <p className="mb-2 text-xs text-muted">Needs LINKEDIN_CLIENT_ID / SECRET on the Setup page. Empty id = post as you; a company Page id needs the Community Management API.</p>
            <input className={field} placeholder="Company Page id (optional)" value={org} onChange={(e) => setOrg(e.target.value)} />
            <button className={`${btn} mt-2`} disabled={!!busy} onClick={() => act("li", { action: "connect-linkedin", org })}>{busy === "li" ? "Opening…" : "Connect LinkedIn"}</button>
          </div>
        </div>
      </section>

      {/* ── Queues ── */}
      {([["Films", st.films, st.queue], ["Text / photo posts", st.posts, st.posts_queue]] as const).map(([title, rows, file]) => (
        <section key={title} className="rounded-2xl border border-line bg-panel p-4">
          <h3 className="mb-1 font-semibold">{title}</h3>
          <p className="mb-2 truncate text-xs text-muted" title={file}>From the last 3 days on · {file || "no queue file"}</p>
          {rows.length === 0 ? <p className="text-muted">Nothing queued.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-muted"><tr><th className="py-1 pr-3">when</th><th className="pr-3">title</th><th className="pr-3">state</th><th className="pr-3">platforms</th><th /></tr></thead>
                <tbody>{rows.map((r) => (
                  <tr key={r.file + r.date} className="border-t border-line align-top">
                    <td className="py-1.5 pr-3 whitespace-nowrap">{r.date} {r.time}</td>
                    <td className="pr-3">{r.title}{!r.caption && r.state !== "posted" && <span className="ml-1 text-mega" title="The posting job needs caption.md in the film folder (or the post file)">· no caption</span>}</td>
                    <td className={`pr-3 whitespace-nowrap ${STATE_STYLE[r.state]}`} title={r.status}>{STATE_LABEL[r.state]}</td>
                    <td className="pr-3">{Object.entries(r.platforms).map(([p, ok]) => <span key={p} className={`mr-1.5 ${ok ? "text-above" : "text-muted"}`}>{ok ? "✓" : "·"}{NAMES[p] ?? p}</span>)}</td>
                    <td className="whitespace-nowrap text-right">
                      {r.state !== "posted" && r.state !== "missed" && (r.state === "stopped"
                        ? <button className={btn} disabled={!!busy} onClick={() => act(r.file, { action: "resume", file: r.file })}>✅ Resume</button>
                        : <button className={btn} disabled={!!busy} onClick={() => act(r.file, { action: "stop", file: r.file })}>🛑 Stop</button>)}
                    </td>
                  </tr>))}</tbody>
              </table>
            </div>
          )}
        </section>
      ))}

      {/* ── Recent posts ── */}
      <section className="rounded-2xl border border-line bg-panel p-4">
        <h3 className="mb-2 font-semibold">Recent posts</h3>
        {st.published.length === 0 ? <p className="text-muted">Nothing posted through the APIs yet.</p> : (
          <ul className="space-y-1 text-xs">{st.published.map((p, i) => (
            <li key={i}><span className="text-muted">{p.time.slice(0, 16).replace("T", " ")}</span> · {NAMES[p.platform] ?? p.platform} · {p.video || p.post}
              {p.permalink && <> · <a className="text-accent hover:underline" href={p.permalink} target="_blank" rel="noreferrer">open</a></>}</li>))}</ul>
        )}
      </section>
    </div>
  );
}
