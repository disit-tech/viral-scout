"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/** Settings → Delete business. Moves everything to data/deleted/<name>-<time>/ (restorable) and removes its tasks.
 *  Backend: python -m viral_scout profile <name> delete --confirm <name> (viral_scout/profile_delete.py). */
export default function DeleteBusiness({ name }: { name: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function go() {
    setBusy(true);
    setMsg(null);
    const r = await fetch("/api/profile", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ profile: name, delete: true, confirm: typed }) }).then((x) => x.json()).catch(() => ({ ok: false, error: "request failed" }));
    setBusy(false);
    if (!r.ok) return setMsg({ ok: false, text: String(r.error ?? "failed") });
    setMsg({ ok: true, text: `Deleted. Everything is in ${r.folder}${r.tasks_removed?.length ? `; removed ${r.tasks_removed.join(", ")}` : ""}. Going back to Businesses…` });
    setTimeout(() => { router.push("/"); router.refresh(); }, 2500);
  }

  return (
    <section id="delete" className="scroll-mt-20 rounded-2xl border border-mega/40 bg-panel p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-semibold text-mega">Delete business</h2>
        {!open && <button onClick={() => setOpen(true)} className="ml-auto rounded-lg border border-mega/50 px-3 py-1.5 text-mega hover:bg-mega/10">Delete {name}…</button>}
      </div>
      <p className="mt-1 text-muted">
        Removes <b className="text-text">{name}</b> from the dashboard and stops its scheduled tasks. Nothing is erased: its profile,
        database, run data, frames, scores, idea batches and paid ads data move to <code>data/deleted/{name}-&lt;time&gt;/</code>, with a
        note on how to restore it. Not touched: its notes in the Obsidian vault, its ideas in the Telegram bot, and the API keys (shared).
      </p>
      {open && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <label className="text-xs text-muted" htmlFor="del-confirm">Type <b className="text-text">{name}</b> to confirm</label>
          <input id="del-confirm" value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus
            className="rounded-lg border border-line bg-panel-2 px-2 py-1 text-sm" />
          <button disabled={busy || typed !== name} onClick={go}
            className="rounded-lg bg-mega px-3 py-1.5 font-semibold text-ink disabled:opacity-40">{busy ? "Deleting…" : "Delete"}</button>
          <button onClick={() => { setOpen(false); setTyped(""); }} className="text-xs text-muted hover:text-text">Cancel</button>
        </div>
      )}
      {msg && <p className={`mt-2 ${msg.ok ? "text-above" : "text-mega"}`}>{msg.text}</p>}
    </section>
  );
}
