"use client";

import Link from "next/link";
import { useMemo, useRef, useState } from "react";

export type TimelineAd = {
  key: string; href: string; start: string | null; stop: string | null; active: boolean; days: number | null;
  hook: string; score: number; format: string; source: string;
};

const DAY = 86_400_000;
const fmt = (t: number) => new Date(t).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });

/** One advertiser's ads as start→stop bars (a bar that reaches the right edge is still running).
 *  Single series: the current ad is the accent bar with a direct label, the rest are neutral. Hover any bar for
 *  its dates and hook; click to open that ad. A table view lists the same rows. */
export default function AdTimeline({ ads, current, advertiser, now, max = 40 }: {
  ads: TimelineAd[]; current: string; advertiser: string; now: string; max?: number;
}) {
  const [hover, setHover] = useState<{ i: number; x: number; y: number } | null>(null);
  const [table, setTable] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const end = new Date(now).getTime();

  const { rows, undated, from, ticks, total } = useMemo(() => {
    const dated = ads.filter((a) => a.start).map((a) => ({
      ...a, s: new Date(a.start as string).getTime(),
      e: a.active || !a.stop ? end : Math.min(end, new Date(a.stop).getTime()),
    }));
    dated.sort((x, y) => x.s - y.s);
    let pick = dated.slice(-max);                                   // the most recent starts
    const cur = dated.find((a) => a.key === current);
    if (cur && !pick.includes(cur)) pick = [...pick.slice(1), cur].sort((x, y) => x.s - y.s);
    const from = pick.length ? Math.min(...pick.map((a) => a.s)) - 3 * DAY : end - 30 * DAY;
    const ticks: { t: number; label: string }[] = [];
    const d = new Date(from);
    d.setDate(1); d.setMonth(d.getMonth() + 1); d.setHours(0, 0, 0, 0);
    const months = (end - from) / (30 * DAY);
    const step = months > 18 ? 3 : months > 9 ? 2 : 1;
    while (d.getTime() < end) {
      ticks.push({ t: d.getTime(), label: d.toLocaleDateString([], { month: "short", ...(d.getMonth() === 0 || ticks.length === 0 ? { year: "2-digit" } : {}) }) });
      d.setMonth(d.getMonth() + step);
    }
    return { rows: pick, undated: ads.length - dated.length, from, ticks, total: dated.length };
  }, [ads, current, end, max]);

  const x = (t: number) => `${((t - from) / (end - from)) * 100}%`;
  const w = (s: number, e: number) => `max(6px, ${((e - s) / (end - from)) * 100}%)`;
  const h = hover !== null ? rows[hover.i] : null;

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
        <span className="flex items-center gap-1.5"><span className="inline-block h-2 w-4 rounded bg-accent" /> this ad</span>
        <span className="flex items-center gap-1.5"><span className="inline-block h-2 w-4 rounded bg-muted/45" /> other ads by {advertiser}</span>
        <span>a bar that reaches the right edge is still running</span>
        <button onClick={() => setTable(!table)} className="ml-auto text-rise hover:underline">{table ? "Show as timeline" : "Show as table"}</button>
      </div>

      {table ? (
        <div className="max-h-80 overflow-auto rounded-lg border border-line">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-panel-2 text-muted"><tr><th className="px-2 py-1.5">Start</th><th className="px-2">End</th><th className="px-2 text-right">Days</th><th className="px-2 text-right">Score</th><th className="px-2">Hook</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key} className={`border-t border-line ${r.key === current ? "bg-accent/10" : ""}`}>
                  <td className="px-2 py-1 text-muted">{fmt(r.s)}</td>
                  <td className="px-2 text-muted">{r.active ? "running" : fmt(r.e)}</td>
                  <td className="px-2 text-right">{r.days !== null ? Math.round(r.days) : "—"}</td>
                  <td className="px-2 text-right">{Math.round(r.score)}</td>
                  <td className="px-2"><Link href={r.href} className="line-clamp-1 hover:underline">{r.hook || "(no copy)"}</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div ref={box} className="relative select-none" onMouseLeave={() => setHover(null)}>
          {/* month axis: recessive grid */}
          <div className="relative h-5 text-[10px] text-muted">
            {ticks.map((t) => <span key={t.t} className="absolute -translate-x-1/2" style={{ left: x(t.t) }}>{t.label}</span>)}
            <span className="absolute right-0">today</span>
          </div>
          <div className="relative">
            {ticks.map((t) => <span key={t.t} className="absolute bottom-0 top-0 w-px bg-line/60" style={{ left: x(t.t) }} />)}
            {rows.map((r, i) => {
              const me = r.key === current;
              return (
                <Link key={r.key} href={r.href} className="relative block h-3" aria-label={`${r.hook || "ad"}: ${fmt(r.s)} to ${r.active ? "today" : fmt(r.e)}`}
                  onMouseMove={(e) => {
                    const b = box.current?.getBoundingClientRect();
                    if (b) setHover({ i, x: e.clientX - b.left, y: e.clientY - b.top });
                  }}>
                  <span className={`absolute top-0.5 h-2 rounded ${me ? "bg-accent" : hover?.i === i ? "bg-text/70" : "bg-muted/45"}`}
                    style={{ left: x(r.s), width: w(r.s, r.e) }} />
                  {me && <span className="absolute -top-0.5 whitespace-nowrap pl-1 text-[10px] font-semibold text-text" style={{ left: `calc(${x(r.e)} + 4px)`, transform: r.e > end - 0.15 * (end - from) ? "translateX(-100%) translateX(-14px)" : undefined }}>this ad</span>}
                </Link>
              );
            })}
          </div>
          {h && hover && (
            <div className="pointer-events-none absolute z-10 w-72 rounded-lg border border-line bg-ink/95 p-2.5 text-xs shadow-lg"
              style={{ left: Math.min(hover.x + 12, (box.current?.clientWidth ?? 600) - 290), top: hover.y + 14 }}>
              <p className="line-clamp-3 font-medium text-text">{h.hook || "(no copy)"}</p>
              <p className="mt-1 text-muted">{fmt(h.s)} → {h.active ? "still running" : fmt(h.e)} · {h.days !== null ? `${Math.round(h.days)} days` : "no dates"}</p>
              <p className="text-muted">score {Math.round(h.score)} · {h.format}</p>
            </div>
          )}
        </div>
      )}
      <p className="mt-2 text-[11px] text-muted">
        {total > rows.length ? `The ${rows.length} most recent starts of ${total} dated ads. ` : ""}
        {undated ? `${undated} ad${undated > 1 ? "s" : ""} without a start date not shown.` : ""}
      </p>
    </div>
  );
}
