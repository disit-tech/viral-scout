"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type Action = "transcribe" | "analyze" | "save";

/** Local-dashboard buttons for one ad. Each runs `python -m viral_scout ad <profile> <key> <action>`; progress
 *  also shows on the Activity page. The page re-reads its data when the action finishes. */
export default function AdActions({ profile, adKey, hasVideo, hasTranscript, hasAI, swipeNote }: {
  profile: string; adKey: string; hasVideo: boolean; hasTranscript: boolean; hasAI: boolean; swipeNote?: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<Action | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [started, setStarted] = useState<number>(0);

  async function run(action: Action, force = false) {
    setBusy(action);
    setMsg(null);
    setStarted(Date.now());
    const r = await fetch("/api/ad", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ profile, key: adKey, action, force }) }).then((x) => x.json()).catch(() => ({ ok: false, output: "request failed" }));
    setBusy(null);
    const last = String(r.output ?? "").trim().split("\n").filter(Boolean).slice(-2).join(" · ");
    setMsg({ ok: r.ok, text: r.ok ? last : String(r.output ?? "").slice(-400) });
    if (r.ok) router.refresh();
  }

  const btn = "rounded-lg border px-3 py-1.5 text-sm disabled:opacity-40";
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {hasVideo && (
          <button disabled={!!busy} onClick={() => run("transcribe")} className={`${btn} border-line text-text hover:bg-panel-2`}
            title="Downloads the video from the ad library and transcribes it on this PC (faster-whisper). Free.">
            {busy === "transcribe" ? "Transcribing…" : hasTranscript ? "Transcribe again" : "Transcribe video"} <span className="text-xs text-muted">free</span>
          </button>
        )}
        <button disabled={!!busy} onClick={() => run("analyze", hasAI)} className={`${btn} border-accent/60 text-accent hover:bg-accent/10`}
          title="Runs the Claude Code CLI headless with this ad, its image, transcript, variants and the advertiser's playbook. Uses your Claude subscription.">
          {busy === "analyze" ? "Claude is analyzing… (about a minute)" : hasAI ? "Redo AI breakdown" : "Run AI breakdown"}{" "}
          <span className="text-xs opacity-70">Claude subscription</span>
        </button>
        <button disabled={!!busy} onClick={() => run("save")} className={`${btn} border-line text-text hover:bg-panel-2`}
          title="Writes a swipe note to the vault (never overwrites one you edited).">
          {busy === "save" ? "Saving…" : swipeNote ? "Saved ✓ (update link)" : "Save to swipe file"}
        </button>
        <a href="/activity" target="_blank" className="text-xs text-rise hover:underline">watch on Activity ↗</a>
      </div>
      {busy && <Elapsed since={started} />}
      {msg && <p className={`text-xs ${msg.ok ? "text-above" : "text-mega"}`}>{msg.text}</p>}
      {swipeNote && (
        <p className="truncate text-xs text-muted">
          Swipe note: <a href={`obsidian://open?path=${encodeURIComponent(swipeNote)}`} className="text-rise hover:underline">open in Obsidian</a> · <span title={swipeNote}>{swipeNote}</span>
        </p>
      )}
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
