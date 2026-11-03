"use client";

import { useState } from "react";
import type { Check } from "@/lib/types";
import ScorecardView from "./ScorecardView";

const ICON = { pass: "✅", warn: "⚠️", fail: "❌" };

export default function CheckVideo({ profiles, past }: { profiles: string[]; past: (Check & { profile: string })[] }) {
  const [profile, setProfile] = useState(profiles[0] ?? "");
  const [platform, setPlatform] = useState("any");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<(Check & { profile: string }) | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setErr(null);
    const fd = new FormData();
    fd.set("profile", profile);
    fd.set("platform", platform);
    fd.set("file", file);
    const r = await fetch("/api/check", { method: "POST", body: fd }).then((x) => x.json()).catch(() => ({ ok: false, output: "request failed" }));
    setBusy(false);
    if (!r.ok) return setErr(r.output);
    setResult({ ...r.check, profile });
  }

  return (
    <div className="mt-6 space-y-6">
      <form onSubmit={submit} className="flex flex-wrap items-end gap-3 rounded-2xl border border-line bg-panel p-4">
        <label className="text-sm">Business<br />
          <select value={profile} onChange={(e) => setProfile(e.target.value)} className="mt-1 rounded-lg border border-line bg-panel-2 px-2 py-1.5">
            {profiles.map((p) => <option key={p}>{p}</option>)}
          </select>
        </label>
        <label className="text-sm">Platform<br />
          <select value={platform} onChange={(e) => setPlatform(e.target.value)} className="mt-1 rounded-lg border border-line bg-panel-2 px-2 py-1.5">
            <option value="any">Any short-form</option><option value="tiktok">TikTok</option><option value="reels">Instagram Reels</option><option value="shorts">YouTube Shorts</option>
          </select>
        </label>
        <label className="text-sm">Your video<br />
          <input type="file" accept="video/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="mt-1 text-sm" />
        </label>
        <button disabled={busy || !file} className="rounded-lg bg-accent px-4 py-2 font-semibold text-ink disabled:opacity-50">
          {busy ? "Checking… (up to a minute)" : "Check it"}
        </button>
        {err && <p className="w-full text-sm text-mega">{err}</p>}
      </form>

      {result && <CheckResult c={result} />}

      {past.length > 0 && (
        <section>
          <h2 className="mb-2 font-semibold">Earlier checks</h2>
          <div className="space-y-2">
            {past.map((c) => (
              <details key={c.profile + c.slug} className="rounded-xl border border-line bg-panel p-3">
                <summary className="cursor-pointer text-sm">
                  <b>{c.name}</b> · {c.profile} · {c.checked.slice(0, 16).replace("T", " ")} · ✅ {c.summary.pass} ⚠️ {c.summary.warn} ❌ {c.summary.fail}
                  {c.scorecard?.total != null ? ` · ${c.scorecard.total}/100` : ""}
                </summary>
                <div className="mt-3"><CheckResult c={c} /></div>
              </details>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function CheckResult({ c }: { c: Check & { profile: string } }) {
  const tr = c.transcript;
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
      <div className="space-y-4">
        <section className="rounded-2xl border border-line bg-panel p-4 text-sm">
          <h3 className="mb-2 font-semibold">{c.name} · {c.probe.duration.toFixed(1)} s · {c.probe.width}×{c.probe.height}</h3>
          <table className="w-full">
            <tbody>
              {c.results.map((r) => (
                <tr key={r.area} className="border-t border-line align-top">
                  <td className="w-8 py-1.5">{ICON[r.status]}</td>
                  <td className="w-44 py-1.5 font-medium">{r.area}</td>
                  <td className="py-1.5 text-muted">{r.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        {tr && (
          <section className="rounded-2xl border border-line bg-panel p-4 text-sm">
            <h3 className="mb-2 font-semibold">Script</h3>
            <p><span className="text-muted">Hook (first 4 s):</span> “{tr.hook || "—"}”</p>
            <p className="mt-1"><span className="text-muted">Ending (last 5 s):</span> “{tr.cta || "—"}”</p>
            <p className="mt-1 text-muted">{tr.wpm ?? "—"} words/min</p>
            <details className="mt-2"><summary className="cursor-pointer text-rise">Transcript</summary><p className="mt-1 whitespace-pre-line">{tr.transcript}</p></details>
          </section>
        )}
        <section className="rounded-2xl border border-line bg-panel p-4 text-sm">
          <h3 className="mb-2 font-semibold">Creative scorecard</h3>
          <ScorecardView card={c.scorecard} cmd={`/viral-scout ${c.profile} check ${c.slug}`} />
        </section>
        <section className="rounded-2xl border border-line bg-panel p-4 text-sm">
          <h3 className="mb-2 font-semibold">Check by eye</h3>
          <ul className="space-y-1">{c.manual.map((m) => <li key={m}>☐ {m}</li>)}</ul>
        </section>
      </div>
      <div className="grid grid-cols-2 gap-2 self-start">
        {["first", "1s", "3s", "middle", "last"].map((f) => (
          // eslint-disable-next-line @next/next/no-img-element
          <img key={f} alt={f} title={f} className="w-full rounded-lg border border-line"
            src={`/api/check?profile=${c.profile}&slug=${c.slug}&frame=frame-${f}.jpg`} />
        ))}
      </div>
    </div>
  );
}
