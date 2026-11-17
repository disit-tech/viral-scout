"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type Job = { status: "running" | "done" | "failed"; posts?: number; errors?: number; error?: string; started?: string };

export default function NewProject() {
  const [mode, setMode] = useState<"research" | "project">("project");
  const [f, setF] = useState({ name: "", business: "", keywords: "", hashtags: "", languages: "", vaultProject: "", window: "month" });
  const [projects, setProjects] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [profile, setProfile] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);

  useEffect(() => {                     // ?mode=research from "Quick research" on the Businesses page
    if (new URLSearchParams(window.location.search).get("mode") === "research") setMode("research");
  }, []);
  useEffect(() => { fetch("/api/new").then((r) => r.json()).then((d) => setProjects(d.projects ?? [])).catch(() => {}); }, []);
  useEffect(() => {
    if (!profile || job?.status === "done" || job?.status === "failed") return;
    const t = setInterval(async () => {
      const d = await fetch(`/api/new?name=${profile}`).then((r) => r.json()).catch(() => null);
      if (d?.job) setJob(d.job);
    }, 4000);
    return () => clearInterval(t);
  }, [profile, job?.status]);

  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setF({ ...f, [k]: e.target.value });

  const [run, setRun] = useState(true);   // which button was pressed: create and run, or create only
  const post = (body: object) => fetch("/api/new", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })
    .then((x) => x.json()).catch(() => ({ ok: false, output: "request failed" }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    // Which button submitted the form (state set in onClick would still be the old value here).
    const go = (e.nativeEvent as SubmitEvent).submitter?.getAttribute("data-run") !== "no";
    setRun(go);
    setBusy(true);
    setErr(null);
    const r = await post({ ...f, run: go, research: mode === "research", vaultProject: mode === "project" ? f.vaultProject : "" });
    setBusy(false);
    if (!r.ok) return setErr(r.output);
    setProfile(r.profile);
    setJob(r.started ? { status: "running" } : null);
  }

  async function startNow() {
    setBusy(true);
    const r = await post({ startRun: profile });
    setBusy(false);
    if (!r.ok) return setErr(r.output);
    setJob({ status: "running" });
  }

  if (profile) {
    return (
      <div className="mt-6 rounded-2xl border border-line bg-panel p-6">
        <p className="text-sm text-muted">Profile</p>
        <p className="text-lg font-semibold">{profile}</p>
        {!job && (
          <div className="mt-3 space-y-3 text-sm">
            <p className="text-above">Created. Nothing has run yet, so no API credits were used.</p>
            <div className="flex flex-wrap gap-2">
              <Link href={`/p/${profile}`} className="rounded-lg border border-line px-3 py-1.5 hover:bg-panel-2">Open the business →</Link>
              <Link href={`/p/${profile}/settings`} className="rounded-lg border border-line px-3 py-1.5 hover:bg-panel-2">⚙ Settings (keywords, ads, search demand…)</Link>
              <button onClick={startNow} disabled={busy} className="rounded-lg bg-accent px-3 py-1.5 font-semibold text-ink disabled:opacity-50">
                {busy ? "Starting…" : "Start the first run now"}
              </button>
            </div>
            {err && <p className="text-mega">{err}</p>}
            <p className="text-xs text-muted">The overview&apos;s tiles show what each feature still needs. The weekly run starts it too once it&apos;s on the Schedule page.</p>
          </div>
        )}
        {job?.status === "running" && <p className="mt-3 text-sm text-viral">Running… this takes 3–8 minutes. You can leave this page.</p>}
        {job?.status === "done" && (
          <p className="mt-3 text-sm text-above">
            Done: {job.posts} posts{job.errors ? `, ${job.errors} errors` : ""}.{" "}
            <Link href={`/p/${profile}`} className="underline">Open the results →</Link>
          </p>
        )}
        {job?.status === "failed" && <p className="mt-3 text-sm text-mega">Failed: {job.error}</p>}
        <p className="mt-4 text-xs text-muted">
          Next: open <code>profiles/{profile}.yaml</code> to tune keywords and filters, and run <code>/viral-scout {profile}</code> in
          Claude Code for the AI breakdown and ideas.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="mt-6 space-y-4 rounded-2xl border border-line bg-panel p-5">
      <div className="flex gap-2">
        {(["project", "research"] as const).map((m) => (
          <button type="button" key={m} onClick={() => setMode(m)}
            className={`rounded-lg border px-3 py-1.5 text-sm ${mode === m ? "border-accent text-accent" : "border-line text-muted"}`}>
            {m === "research" ? "Quick research (one-off)" : "New business (ongoing)"}
          </button>
        ))}
      </div>
      <Field label="Name" hint="Short id, e.g. dog-grooming">
        <input required value={f.name} onChange={set("name")} className={input} />
      </Field>
      <Field label="Business / topic" hint="Who it's for, what you sell, who films, tone, formats you like, hard rules. The AI step adapts ideas to this.">
        <textarea rows={3} value={f.business} onChange={set("business")} className={input} />
      </Field>
      <Field label="Search phrases" hint='One per line (or separated by ";"). Mix formats ("before and after …") and customer situations. Add phrases in every language your audience speaks.'>
        <textarea required rows={5} value={f.keywords} onChange={set("keywords")} className={input}
          placeholder={"dog grooming at home\npuppy first bath\nстрижка собак"} />
      </Field>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Hashtags (optional)" hint="Derived from the phrases if empty.">
          <input value={f.hashtags} onChange={set("hashtags")} className={input} placeholder="doggrooming petgroomer" />
        </Field>
        <Field label="Languages (optional)" hint='"phrase=ru; other phrase=uk" (YouTube API key needed)'>
          <input value={f.languages} onChange={set("languages")} className={input} />
        </Field>
        <Field label="Time window">
          <select value={f.window} onChange={set("window")} className={input}>
            <option value="week">Last week</option><option value="month">Last month</option><option value="year">Last year</option>
          </select>
        </Field>
        {mode === "project" && (
          <Field label="Obsidian project folder" hint="Reports and the swipe file go to projects/<folder>/05 Marketing/viral">
            <select value={f.vaultProject} onChange={set("vaultProject")} className={input}>
              <option value="">— repo reports/ folder —</option>
              {projects.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </Field>
        )}
      </div>
      {err && <p className="text-sm text-mega">{err}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <button disabled={busy} data-run="yes" className="rounded-lg bg-accent px-4 py-2 font-semibold text-ink hover:brightness-110 disabled:opacity-50">
          {busy && run ? "Creating…" : "Create and start the first run"}
        </button>
        <button disabled={busy} data-run="no" className="rounded-lg border border-line px-4 py-2 text-sm hover:bg-panel-2 disabled:opacity-50"
          title="Saves the business only. Add keys and settings first, then start the run from the next screen or the overview.">
          {busy && !run ? "Creating…" : "Create only (run later)"}
        </button>
      </div>
    </form>
  );
}

const input = "w-full rounded-lg border border-line bg-panel-2 px-3 py-2 text-sm outline-none focus:border-accent";

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-sm font-medium">{label}</span>
      {hint && <span className="block text-xs text-muted">{hint}</span>}
      <div className="mt-1">{children}</div>
    </label>
  );
}
