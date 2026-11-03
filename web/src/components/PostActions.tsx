"use client";

import { useState } from "react";
import type { Item } from "@/lib/types";
import { cli, runAction, type ActionBody } from "./actions";

/** Save / Track / Dismiss for the video page (local: runs the CLI; published: copies the command). */
export default function PostActions({ item, profile, local }: { item: Item; profile: string; local: boolean }) {
  const [state, setState] = useState({ saved: item.saved, tracked: item.tracked, dismissed: item.dismissed });
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [note, setNote] = useState("");

  async function act(body: ActionBody, patch: Partial<typeof state>) {
    if (!local) {
      await navigator.clipboard?.writeText(cli(body)).catch(() => undefined);
      return setMsg(`Copied: ${cli(body)}`);
    }
    setBusy(body.action);
    const r = await runAction(body);
    setBusy(null);
    if (r.ok) setState((s) => ({ ...s, ...patch }));
    setMsg(r.ok ? (body.action === "save" ? "Saved to the swipe file" : "Done") : r.output.slice(0, 200));
  }

  return (
    <div className="flex flex-col items-end gap-1.5">
      <div className="flex flex-wrap gap-2">
        {!state.saved && (
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why it works (optional)"
            className="w-48 rounded-lg border border-line bg-panel px-2 py-1.5 text-sm outline-none focus:border-accent" />
        )}
        <button disabled={!!busy || state.saved} onClick={() => act({ profile, action: "save", ref: item.id, note: note || undefined }, { saved: true, tracked: true })}
          className="rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-ink disabled:opacity-60">
          {state.saved ? "✓ In swipe file" : busy === "save" ? "Saving…" : "Save to swipe file"}
        </button>
        {!state.tracked && (
          <button disabled={!!busy} onClick={() => act({ profile, action: "track", ref: item.url }, { tracked: true })}
            className="rounded-lg border border-accent/60 px-3 py-1.5 text-sm text-accent disabled:opacity-60">Track</button>
        )}
        <button disabled={!!busy || state.dismissed} onClick={() => act({ profile, action: "dismiss", ref: item.id }, { dismissed: true })}
          className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted hover:text-text disabled:opacity-60">
          {state.dismissed ? "Dismissed" : "Dismiss"}
        </button>
      </div>
      {msg && <p className="max-w-md break-all text-right text-xs text-muted">{msg}</p>}
    </div>
  );
}
