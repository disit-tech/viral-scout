"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

type Job = { status: "running" | "done" | "failed"; error?: string; updated?: string };

/** "Run now" for a free job (api/run). Off the local dashboard it copies the CLI command instead. */
export default function RunButton({ profile, job, label, command, local }: {
  profile: string; job: "videos" | "ads-rescore"; label: string; command: string; local: boolean;
}) {
  const router = useRouter();
  const [state, setState] = useState<Job | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [ran, setRan] = useState(false);            // started from this page (so "done" is news)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  async function poll() {
    const r = await fetch(`/api/run?profile=${encodeURIComponent(profile)}&job=${job}`).then((x) => x.json()).catch(() => null);
    const j: Job | null = r?.job ?? null;
    setState(j);
    if (j && j.status !== "running" && timer.current) {
      clearInterval(timer.current);
      timer.current = null;
      if (j.status === "done") router.refresh();
    }
    return j;
  }
  useEffect(() => {
    if (!local) return;
    poll().then((j) => { if (j?.status === "running") timer.current = setInterval(poll, 5000); });
    return () => { if (timer.current) clearInterval(timer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [local]);

  async function start() {
    if (!local) {
      await navigator.clipboard?.writeText(command).catch(() => undefined);
      setMsg(`Copied: ${command}`);
      return;
    }
    setMsg(null);
    const r = await fetch("/api/run", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ profile, job }) })
      .then((x) => x.json()).catch(() => ({ ok: false, output: "request failed" }));
    if (!r.ok) { setMsg(r.output ?? "Could not start"); return; }
    setState({ status: "running" });
    setRan(true);
    if (!timer.current) timer.current = setInterval(poll, 5000);
  }

  const running = state?.status === "running";
  return (
    <span className="inline-flex flex-col items-start gap-1">
      <button onClick={start} disabled={running}
        className="rounded-lg border border-accent/50 px-2.5 py-1 text-xs text-accent hover:bg-accent/10 disabled:cursor-default disabled:opacity-60"
        title={`Free: ${command}`}>
        {running ? "Running… (see Activity)" : `▶ ${label}`}
      </button>
      {(ran || state?.status === "failed") && state?.status === "failed" && <span className="text-[11px] text-mega">Last run failed: {state.error?.slice(0, 120)}</span>}
      {ran && state?.status === "done" && !msg && <span className="text-[11px] text-above">Done, data refreshed</span>}
      {msg && <span className="break-all text-[11px] text-muted">{msg}</span>}
    </span>
  );
}
