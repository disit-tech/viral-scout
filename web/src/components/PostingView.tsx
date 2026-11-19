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
  prereqs: Record<"META_APP_ID" | "META_APP_SECRET" | "META_USER_TOKEN" | "LINKEDIN_CLIENT_ID" | "LINKEDIN_CLIENT_SECRET" | "GOOGLE_CLIENT" | "TIKTOK_POST_CLIENT_KEY" | "TIKTOK_POST_CLIENT_SECRET", boolean>;
  handles: Record<string, string>;
  queue: string; posts_queue: string; films: Row[]; posts: Row[]; keys: Record<string, Key>; warnings: string[];
  published: { time: string; platform: string; permalink?: string; id?: string; video?: string; post?: string; mode?: string; caption?: string }[];
  challenges: { replied: number; active: number };
};
type Msg = { ok: boolean; text: string } | null;

const PLATFORMS = ["instagram", "facebook", "youtube", "linkedin", "threads", "tiktok"] as const;
const NAMES: Record<string, string> = { instagram: "Instagram", facebook: "Facebook", youtube: "YouTube", linkedin: "LinkedIn", threads: "Threads", tiktok: "TikTok (drafts)" };
const field = "w-full rounded-lg border border-line bg-panel-2 px-2 py-1.5 text-sm";
const btn = "rounded-lg border border-line px-3 py-1.5 text-sm hover:bg-panel-2 disabled:opacity-40";
const STATE_STYLE: Record<Row["state"], string> = {
  posted: "text-above", stopped: "text-mega", "due now": "text-accent", "waiting for approval": "text-muted", missed: "text-muted", scheduled: "text-text",
};
const STATE_LABEL: Record<Row["state"], string> = {
  posted: "📤 posted", stopped: "🛑 stopped", "due now": "⏱ due now", "waiting for approval": "👀 waiting for ✅", missed: "missed", scheduled: "🗓 scheduled",
};

function Ext({ href, children }: { href: string; children: React.ReactNode }) {
  return <a className="text-accent hover:underline" href={href} target="_blank" rel="noreferrer">{children}</a>;
}

/** A key on the Setup page: the link scrolls to its row and flashes it (#key-NAME). */
function SetupKey({ k }: { k: string }) {
  return <a className="font-mono text-accent hover:underline" href={`/setup#key-${k}`}>{k}</a>;
}

/** One platform's numbered steps; the first open step is highlighted. */
function Guide({ title, status, done, steps }: { title: string; status: string; done: boolean; steps: { done: boolean; text: React.ReactNode }[] }) {
  const next = steps.findIndex((s) => !s.done);
  return (
    <div className={`rounded-xl border p-3 ${done ? "border-above/40" : "border-line"}`}>
      <div className="flex items-baseline justify-between gap-2"><span className="font-medium">{title}</span><span className="text-xs">{status}</span></div>
      <ol className="mt-2 space-y-2 text-xs">
        {steps.map((s, i) => (
          <li key={i} className={`flex gap-2 rounded-lg p-1.5 ${i === next ? "bg-accent/10" : ""} ${s.done ? "text-muted" : ""}`}>
            <span className="shrink-0 font-semibold">{s.done ? "✅" : `${i + 1}.`}</span><div className="min-w-0 leading-relaxed">{s.text}</div>
          </li>
        ))}
      </ol>
    </div>
  );
}

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
  const [link, setLink] = useState("");
  const [thToken, setThToken] = useState("");

  const load = useCallback(async () => {
    const d = await fetch(`/api/posting?profile=${encodeURIComponent(profile)}`).then((r) => r.json()).catch(() => ({ error: "couldn't reach the dashboard server" }));
    if (d.error) setLoadErr(String(d.error));
    else { setSt(d); setForm(d.settings); setLoadErr(""); }
  }, [profile]);
  useEffect(() => { load(); }, [load]);

  async function act(key: string, body: object) {
    setBusy(key);
    setMsg(null);
    setLink("");
    const r = await post({ profile, ...body });
    setBusy("");
    if (r.url) setLink(String(r.url));
    window.scrollTo({ top: 0, behavior: "smooth" });
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
          <p className="mt-2 text-mega">Not connected yet: {notConnected.map((p) => NAMES[p]).join(", ")}. Nothing posts there until you connect it: <a className="text-accent underline" href="#accounts">step-by-step below ↓</a></p>
        )}
        {st.warnings.map((w) => <p key={w} className="mt-1 text-mega">⚠ {w}</p>)}
        {msg && <p className={`mt-2 whitespace-pre-wrap ${msg.ok ? "text-above" : "text-mega"}`}>{msg.text}</p>}
        {link && <p className="mt-1"><a className="text-accent underline" href={link} target="_blank" rel="noreferrer">Open the sign-in page →</a></p>}
      </section>

      {/* ── Settings ── */}
      <section className="rounded-2xl border border-line bg-panel p-4">
        <h3 className="mb-1 font-semibold">How it posts</h3>
        <p className="mb-3 text-muted">Saved in this business&apos;s profile (<code>publish:</code> and <code>jobs:</code>). TikTok goes to the TikTok app as a draft: you get the caption in the bot, paste it and tap Post (TikTok wants that tap from a person).</p>
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
              <div className="mt-1 flex gap-3">{(["linkedin", "facebook", "threads"] as const).map((p) => (
                <label key={p} className="flex items-center gap-1"><input type="checkbox" checked={form.posts.platforms.includes(p)}
                  onChange={(e) => setForm({ ...form, posts: { ...form.posts, platforms: e.target.checked ? [...form.posts.platforms, p] : form.posts.platforms.filter((x) => x !== p) } })} />
                  {NAMES[p]}</label>))}</div>
              <p className="mt-0.5 text-xs text-muted">Instagram photo posts stay by hand, and Threads gets the text only (both APIs take images only from a public URL).</p>
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
      <section id="accounts" className="rounded-2xl border border-line bg-panel p-4">
        <h3 className="mb-1 font-semibold">Accounts: how to connect</h3>
        <p className="mb-3 text-muted">
          Each platform needs a free developer app once (shared by all your businesses), then one sign-in per business. Go
          through the steps top to bottom; a step ticks itself when it&apos;s done (reload the page). The keys stay on this PC
          in <code>data/publish/{profile}/keys.env</code>.
        </p>
        <div className="grid gap-3 lg:grid-cols-3">
          <Guide title="Meta: Instagram + Facebook" done={!!st.keys.instagram?.connected && !!st.keys.facebook?.connected}
            status={(["instagram", "facebook"] as const).map((p) => `${st.keys[p]?.connected ? "✅" : "⚪"} ${NAMES[p]}`).join("  ")}
            steps={[
              { done: !!st.keys.instagram?.connected, text: <>Check: the Instagram account is a <b>Business or Creator</b> account and is linked to the business&apos;s <b>Facebook Page</b> (Instagram app → Settings → Account type and tools; Facebook Page → Settings → Linked accounts).</> },
              { done: st.prereqs.META_APP_ID && st.prereqs.META_APP_SECRET, text: <>
                Create a Meta app: <Ext href="https://developers.facebook.com/apps/creation/">developers.facebook.com → Create app</Ext>, type <b>Business</b>.
                Add the product <b>Facebook Login for Business</b>; in its Settings put <code>http://localhost:8765/</code> under <i>Valid OAuth Redirect URIs</i>.
                Then App settings → Basic: copy <b>App ID</b> and <b>App secret</b> into <SetupKey k="META_APP_ID" /> and <SetupKey k="META_APP_SECRET" /> on the Setup page.
                Leave the app in Development mode: you are its admin, so posting to your own Pages works without App Review.</> },
              { done: st.prereqs.META_USER_TOKEN, text: <>On the <a className="text-accent hover:underline" href="/setup">Setup page</a> press <b>Connect Meta</b> and sign in with the Facebook account that manages the Page. Tick <b>every</b> Page, Instagram account and permission it asks for (posting needs <i>instagram_content_publish</i> and <i>pages_manage_posts</i>).</> },
              { done: !!st.keys.instagram?.connected || !!st.keys.facebook?.connected, text: <>Pick this business&apos;s Page. Empty box = the Page whose Instagram matches the profile{st.handles.instagram ? ` (${st.handles.instagram})` : ""}; or type the Page name.
                <input className={`${field} mt-1.5`} placeholder="Page name or id (optional)" value={page} onChange={(e) => setPage(e.target.value)} />
                <button className={`${btn} mt-1.5`} disabled={!!busy || !st.prereqs.META_USER_TOKEN} title={st.prereqs.META_USER_TOKEN ? "" : "Do step 3 first"}
                  onClick={() => act("meta", { action: "connect-meta", page })}>{busy === "meta" ? "Connecting…" : "Connect Page"}</button></> },
            ]} />
          <Guide title="YouTube" done={!!st.keys.youtube?.connected} status={st.keys.youtube?.connected ? "✅ connected" : "⚪ not connected"}
            steps={[
              { done: st.prereqs.GOOGLE_CLIENT, text: <>
                Make a Google sign-in client (once): <Ext href="https://console.cloud.google.com/projectcreate">create a Google Cloud project</Ext>,{" "}
                <Ext href="https://console.cloud.google.com/apis/library/youtube.googleapis.com">enable YouTube Data API v3</Ext>, set up the{" "}
                <Ext href="https://console.cloud.google.com/auth/overview">OAuth consent screen</Ext> (External, your email) and press <b>Publish app</b> (in Testing the sign-in stops after 7 days).
                Then <Ext href="https://console.cloud.google.com/apis/credentials">Credentials</Ext> → Create credentials → OAuth client ID → <b>Desktop app</b>.
                Copy its client ID and secret into <SetupKey k="YT_OAUTH_CLIENT_ID" /> and <SetupKey k="YT_OAUTH_CLIENT_SECRET" /> on the Setup page.</> },
              { done: !!st.keys.youtube?.connected, text: <>Press Connect: a Google page opens (or a link appears at the top of this page). Sign in with the account that owns the business&apos;s channel; if it asks which channel, pick the business&apos;s. Allow every box.
                <br /><button className={`${btn} mt-1.5`} disabled={!!busy || !st.prereqs.GOOGLE_CLIENT} title={st.prereqs.GOOGLE_CLIENT ? "" : "Do step 1 first"}
                  onClick={() => act("google", { action: "connect-google" })}>{busy === "google" ? "Opening…" : "Connect YouTube"}</button></> },
              { done: false, text: <>Ask Google for the API audit: <Ext href="https://support.google.com/youtube/contact/yt_api_form">YouTube API Services form</Ext> → &quot;Audit and quota extension&quot;. Until it is approved, YouTube keeps every API upload <b>private</b> (uploaded, but nobody sees it). Takes days to weeks.</> },
            ]} />
          <Guide title="LinkedIn" done={!!st.keys.linkedin?.connected}
            status={st.keys.linkedin?.connected ? `✅ connected${st.keys.linkedin.expires ? ` · renew by ${st.keys.linkedin.expires}` : ""}` : "⚪ not connected"}
            steps={[
              { done: st.prereqs.LINKEDIN_CLIENT_ID && st.prereqs.LINKEDIN_CLIENT_SECRET, text: <>
                <Ext href="https://www.linkedin.com/developers/apps/new">linkedin.com/developers → Create app</Ext> (it asks for a LinkedIn company Page: use the business&apos;s, or create one first).
                Tab <b>Products</b>: request <b>Share on LinkedIn</b> and <b>Sign In with LinkedIn using OpenID Connect</b> (both are instant).
                Tab <b>Auth</b>: add the redirect URL <code>http://127.0.0.1:8766/</code>, then copy Client ID and Primary Client Secret into <SetupKey k="LINKEDIN_CLIENT_ID" /> and <SetupKey k="LINKEDIN_CLIENT_SECRET" /> on the Setup page.</> },
              { done: !!st.keys.linkedin?.connected, text: <>Press Connect and sign in. Empty box = posts go out as <b>your profile</b>. To post as the <b>company Page</b>, type its number (from the admin URL <code>linkedin.com/company/12345678/admin</code>); that also needs the <i>Community Management API</i> product, which LinkedIn reviews.
                <input className={`${field} mt-1.5`} placeholder="Company Page id (optional)" value={org} onChange={(e) => setOrg(e.target.value)} />
                <button className={`${btn} mt-1.5`} disabled={!!busy || !(st.prereqs.LINKEDIN_CLIENT_ID && st.prereqs.LINKEDIN_CLIENT_SECRET)} title={st.prereqs.LINKEDIN_CLIENT_ID ? "" : "Do step 1 first"}
                  onClick={() => act("li", { action: "connect-linkedin", org })}>{busy === "li" ? "Opening…" : "Connect LinkedIn"}</button></> },
              { done: !!st.keys.linkedin?.connected && !st.warnings.length, text: <>The LinkedIn sign-in lasts 60 days. This page and the posting job warn you a week before; then press Connect again.</> },
            ]} />
        </div>
        <div className="mt-3 grid gap-3 lg:grid-cols-3">
          <Guide title="Threads" done={!!st.keys.threads?.connected} status={st.keys.threads?.connected ? "✅ connected" : "⚪ not connected"}
            steps={[
              { done: !!st.keys.threads?.connected, text: <>
                In the same Meta app as Instagram (<Ext href="https://developers.facebook.com/apps/">developers.facebook.com → your app</Ext>): <b>Use cases → Add use case → Access the Threads API</b>, with the permissions <code>threads_basic</code> and <code>threads_content_publish</code>.
                Optional: copy the Threads app secret into <SetupKey k="THREADS_APP_SECRET" /> (then a short token is swapped for a 60-day one).</> },
              { done: !!st.keys.threads?.connected, text: <>
                <b>App roles → Roles → Add people → Threads Tester</b>: the business&apos;s Threads account{st.handles.threads ? ` (${st.handles.threads})` : st.handles.instagram ? ` (same as Instagram: ${st.handles.instagram})` : ""}.
                Accept the invite in the Threads app: Settings → Account → Website permissions → Invites.</> },
              { done: !!st.keys.threads?.connected, text: <>
                Threads use case → Settings → <b>User Token Generator</b> → Generate access token for that account. Paste it here:
                <input className={`${field} mt-1.5`} type="password" placeholder="THAA…" value={thToken} onChange={(e) => setThToken(e.target.value)} />
                <button className={`${btn} mt-1.5`} disabled={!!busy || thToken.length < 20} onClick={() => { act("th", { action: "connect-threads", token: thToken }); setThToken(""); }}>
                  {busy === "th" ? "Connecting…" : "Connect Threads"}</button>
                <span className="mt-1 block text-muted">The token renews itself every time posting runs, so you paste it once.</span></> },
              { done: !!st.settings.auto_post.threads, text: <>Tick <b>Threads</b> under &quot;Posts by itself to&quot; (films: the Threads text + a link to the Reel/Short) and under &quot;Text/photo posts go to&quot;, then Save.</> },
            ]} />
          <Guide title="TikTok (drafts)" done={!!st.keys.tiktok?.connected} status={st.keys.tiktok?.connected ? "✅ connected" : "⚪ not connected"}
            steps={[
              { done: st.prereqs.TIKTOK_POST_CLIENT_KEY && st.prereqs.TIKTOK_POST_CLIENT_SECRET, text: <>
                <Ext href="https://developers.tiktok.com/apps/">developers.tiktok.com → Manage apps</Ext> → Connect an app (log in with any TikTok account; it becomes the developer).
                Add the products <b>Login Kit</b> and <b>Content Posting API</b> (leave <i>Direct Post</i> off: drafts only). Platform <b>Desktop</b>, redirect URI <code>http://localhost:8767/callback/</code>, scopes <code>user.info.basic</code> and <code>video.upload</code>.
                Copy Client key and Client secret into <SetupKey k="TIKTOK_POST_CLIENT_KEY" /> and <SetupKey k="TIKTOK_POST_CLIENT_SECRET" /> on the Setup page.
                Then <b>Submit for review</b> in the app (TikTok checks it, usually a few days). While it is in review, add the business&apos;s TikTok account under <i>Sandbox → Target users</i> and it works already.</> },
              { done: !!st.keys.tiktok?.connected, text: <>Press Connect and log in with the <b>business&apos;s</b> TikTok account{st.handles.tiktok ? ` (${st.handles.tiktok})` : ""}, then Authorize.
                <br /><button className={`${btn} mt-1.5`} disabled={!!busy || !(st.prereqs.TIKTOK_POST_CLIENT_KEY && st.prereqs.TIKTOK_POST_CLIENT_SECRET)} title={st.prereqs.TIKTOK_POST_CLIENT_KEY ? "" : "Do step 1 first"}
                  onClick={() => act("tt", { action: "connect-tiktok" })}>{busy === "tt" ? "Opening…" : "Connect TikTok"}</button></> },
              { done: !!st.settings.auto_post.tiktok, text: <>Tick <b>TikTok (drafts)</b> under &quot;Posts by itself to&quot; above and Save. At each film&apos;s time the video lands in the TikTok app (inbox notification) and the caption comes in the bot: open TikTok, paste, tap Post.</> },
            ]} />
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
              {p.permalink && <> · <a className="text-accent hover:underline" href={p.permalink} target="_blank" rel="noreferrer">open</a></>}
              {p.mode === "draft" && <> · <span className="text-accent">draft in the TikTok app: tap Post there</span>
                {p.caption && <button className="ml-2 rounded border border-line px-1.5 hover:bg-panel-2" onClick={() => navigator.clipboard?.writeText(p.caption ?? "")}>copy caption</button>}</>}</li>))}</ul>
        )}
      </section>
    </div>
  );
}
