"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

/** "Activity" nav link with a pulsing dot while a run is going (local dashboard only; jobs only, no Apify calls). */
export default function NavActivity({ local }: { local: boolean }) {
  const [running, setRunning] = useState(0);

  useEffect(() => {
    if (!local) return;
    let stop = false;
    async function poll() {
      const r = await fetch("/api/activity?jobs=1").then((x) => x.json()).catch(() => null);
      if (!stop && r?.ok) setRunning((r.jobs ?? []).filter((j: { status: string }) => j.status === "running").length);
    }
    poll();
    const t = setInterval(() => document.visibilityState === "visible" && poll(), 10_000);
    return () => { stop = true; clearInterval(t); };
  }, [local]);

  return (
    <Link href="/activity" className="flex items-center gap-1.5 rounded-md px-2 py-1 text-muted hover:bg-panel hover:text-text"
      title={running ? `${running} run${running > 1 ? "s" : ""} in progress` : "Nothing running"}>
      Activity
      {running > 0 && (
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-above opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-above" />
        </span>
      )}
    </Link>
  );
}
