"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type Job = { status: "running" | "done" | "failed"; posts?: number; errors?: number; error?: string; started?: string };

export default function NewProject() {
  const [mode, setMode] = useState<"research" | "project">("research");
  const [f, setF] = useState({ name: "", business: "", keywords: "", hashtags: "", languages: "", vaultProject: "", window: "month" });
  const [projects, setProjects] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [profile, setProfile] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);

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

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    const r = await fetch("/api/new", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ ...f, research: mode === "research", vaultProject: mode === "project" ? f.vaultProject : "" }) })
      .then((x) => x.json()).catch(() => ({ ok: false, output: "request failed" }));
    setBusy(false);
    if (!r.ok) return setErr(r.output);
    setProfile(r.profile);
    setJob({ status: "running" });
  }

  if (profile) {
    return (
      <div className="mt-6 rounded-2xl border border-line bg-panel p-6">
        <p className="text-sm text-muted">Profile</p>
        <p className="text-lg font-semibold">{profile}</p>
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
        {(["research", "project"] as const).map((m) => (
          <button type="button" key={m} onClick={() => setMode(m)}
            className={`rounded-lg border px-3 py-1.5 text-sm ${mode === m ? "border-accent text-accent" : "border-line text-muted"}`}>
            {m === "research" ? "Quick research (one-off)" : "New project (ongoing)"}
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
      <button disabled={busy} className="rounded-lg bg-accent px-4 py-2 font-semibold text-ink hover:brightness-110 disabled:opacity-50">
        {busy ? "Creating…" : "Create and start the first run"}
      </button>
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
