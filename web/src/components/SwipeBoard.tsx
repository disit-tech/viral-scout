"use client";

import { useState } from "react";
import Link from "next/link";
import type { SwipeNote } from "@/lib/types";
import { num, times } from "@/lib/format";
import { cli, runAction } from "./actions";

const COLUMNS = ["idea", "scripted", "filmed", "posted", "skip"] as const;

export default function SwipeBoard({ notes, profile, local }: { notes: SwipeNote[]; profile: string; local: boolean }) {
  const [items, setItems] = useState(notes);
  const [msg, setMsg] = useState<string | null>(null);

  async function move(n: SwipeNote, status: string) {
    const body = { profile, action: "status" as const, ref: n.file, status };
    if (!local) {
      await navigator.clipboard?.writeText(cli(body)).catch(() => undefined);
      setMsg(`Copied: ${cli(body)}`);
      return;
    }
    const r = await runAction(body);
    if (r.ok) setItems((all) => all.map((x) => (x.file === n.file ? { ...x, status } : x)));
    setMsg(r.ok ? null : r.output);
  }

  if (!items.length) {
    return (
      <div className="rounded-xl border border-dashed border-line p-8 text-center text-muted">
        Nothing saved yet. Press <b>Save</b> on a post, or run <code className="text-text">python -m viral_scout save {profile} &lt;ID&gt;</code>.
      </div>
    );
  }

  return (
    <div>
      {msg && <p className="mb-3 break-all text-xs text-muted">{msg}</p>}
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
        {COLUMNS.map((col) => {
          const colItems = items.filter((n) => (n.status || "idea") === col);
          return (
            <section key={col} className="rounded-2xl border border-line bg-panel/60 p-2.5">
              <h3 className="mb-2 flex items-center justify-between px-1 text-sm font-semibold capitalize">
                {col} <span className="text-xs font-normal text-muted">{colItems.length}</span>
              </h3>
              <div className="space-y-2.5">
                {colItems.map((n) => (
                  <article key={n.file} className="overflow-hidden rounded-xl border border-line bg-panel">
                    {n.thumbnail && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={n.thumbnail} alt="" className="aspect-video w-full object-cover" />
                    )}
                    <div className="space-y-1.5 p-2.5">
                      {n.post_id ? (
                        <Link href={`/p/${profile}/v/${encodeURIComponent(n.post_id)}`} className="line-clamp-2 text-sm font-medium hover:text-accent">
                          {titleOf(n)}
                        </Link>
                      ) : (
                        <a href={n.url} target="_blank" rel="noreferrer" className="line-clamp-2 text-sm font-medium hover:text-accent">{titleOf(n)}</a>
                      )}
                      <p className="text-xs text-muted">{n.creator} · {num(n.views ?? n.likes)} · {times(n.outlier)} usual</p>
                      {n.format && <span className="inline-block rounded-full bg-panel-2 px-2 py-0.5 text-[11px]">{n.format}</span>}
                      {n.hook && <p className="line-clamp-3 text-xs italic text-text/80">“{n.hook}”</p>}
                      {why(n.body) && <p className="line-clamp-3 text-xs text-muted">{why(n.body)}</p>}
                      <select value={n.status || "idea"} onChange={(e) => move(n, e.target.value)}
                        className="mt-1 w-full rounded-md border border-line bg-panel-2 px-1.5 py-1 text-xs">
                        {COLUMNS.map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

function titleOf(n: SwipeNote): string {
  const m = n.body.match(/^#\s+(.+)$/m);
  return m?.[1] ?? n.file.replace(/\.md$/, "");
}

function why(body: string): string {
  const m = body.match(/## Why it works\s+([\s\S]*?)(\n## |$)/);
  const t = m?.[1]?.trim() ?? "";
  return t.startsWith("_") ? "" : t;
}
