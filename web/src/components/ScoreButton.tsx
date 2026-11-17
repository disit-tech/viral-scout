"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

/** Local-dashboard button: Claude (headless, the owner's subscription) scores one post on the 20-criteria
 *  scorecard through `python -m viral_scout score run`. The page re-reads its data when it finishes. */
export default function ScoreButton({ profile, id, scored }: { profile: string; id: string; scored: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [started, setStarted] = useState(0);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function run() {
    setBusy(true);
    setMsg(null);
    setStarted(Date.now());
    const r = await fetch("/api/score", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ profile, id, force: scored }) }).then((x) => x.json()).catch(() => ({ ok: false, output: "request failed" }));
    setBusy(false);
    const last = String(r.output ?? "").trim().split("\n").filter(Boolean).slice(-1).join("");
    setMsg({ ok: r.ok, text: r.ok ? last : String(r.output ?? "").slice(-400) });
    if (r.ok) router.refresh();
  }

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <button disabled={busy} onClick={run}
          className="rounded-lg border border-accent/60 px-3 py-1.5 text-sm text-accent hover:bg-accent/10 disabled:opacity-40"
          title="Runs the Claude Code CLI headless with this post's numbers, hook, transcript, comments and first frame. Uses your Claude subscription.">
          {busy ? "Claude is scoring… (about a minute)" : scored ? "Score again" : "Score with AI"}{" "}
          <span className="text-xs opacity-70">Claude subscription</span>
        </button>
        <a href="/activity" target="_blank" className="text-xs text-rise hover:underline">watch on Activity ↗</a>
      </div>
      {busy && <Elapsed since={started} />}
      {msg && <p className={`text-xs ${msg.ok ? "text-above" : "text-mega"}`}>{msg.text}</p>}
    </div>
  );
}

function Elapsed({ since }: { since: number }) {
  const [, tick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => tick((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, []);
  return <p className="text-xs text-muted">Working… {Math.round((Date.now() - since) / 1000)} s</p>;
}
