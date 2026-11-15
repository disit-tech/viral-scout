"use client";

import { useState } from "react";

/** The AI idea notes (<date>-viral-ideas.md from the /viral-scout skill), one at a time, newest first. */
export default function IdeasNotes({ ideas, profile }: { ideas: { date: string; file: string; html: string }[]; profile: string }) {
  const [idx, setIdx] = useState(0);
  if (!ideas.length) {
    return (
      <div className="rounded-xl border border-dashed border-line p-8 text-center text-muted">
        No idea notes yet. In Claude Code run <code className="text-text">/viral-scout {profile}</code>: it breaks down the top posts
        and writes ideas adapted to this business.
      </div>
    );
  }
  return (
    <div className="grid gap-6 lg:grid-cols-[180px_1fr]">
      <aside className="flex gap-1 overflow-x-auto lg:flex-col">
        {ideas.map((d, i) => (
          <button key={d.file} onClick={() => setIdx(i)}
            className={`rounded-lg px-3 py-1.5 text-left text-sm ${i === idx ? "bg-panel-2 text-text" : "text-muted hover:text-text"}`}>
            {d.date}
          </button>
        ))}
      </aside>
      <article className="prose-dark min-w-0 rounded-2xl border border-line bg-panel p-5 sm:p-7"
        dangerouslySetInnerHTML={{ __html: ideas[idx]?.html ?? "" }} />
    </div>
  );
}
