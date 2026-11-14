"use client";

import { useRef, useState } from "react";
import type { DemandSeason } from "@/lib/demand";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const W = 600;

function weekDate(week: number) {
  const y = new Date().getFullYear();
  const jan4 = new Date(Date.UTC(y, 0, 4));
  const monday = new Date(jan4.getTime() - ((jan4.getUTCDay() + 6) % 7) * 86_400_000);
  return new Date(monday.getTime() + (week - 1) * 7 * 86_400_000);
}
const short = (d: Date) => d.toLocaleDateString([], { month: "short", day: "numeric", timeZone: "UTC" });

function useHover() {
  const ref = useRef<SVGSVGElement>(null);
  const [hx, setHx] = useState<number | null>(null);
  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const b = ref.current?.getBoundingClientRect();
    if (b) setHx(Math.max(0, Math.min(1, (e.clientX - b.left) / b.width)));
  };
  return { ref, hx, onMove, onLeave: () => setHx(null) };
}

/** The average year: 52 weekly values of the seasonal index (1 = the term's yearly average). */
export function SeasonCurve({ index, seasons, nowWeek, height = 150 }: {
  index: number[]; seasons: DemandSeason[]; nowWeek: number; height?: number;
}) {
  const { ref, hx, onMove, onLeave } = useHover();
  const [table, setTable] = useState(false);
  const H = height, pad = { t: 18, b: 20 };
  const max = Math.max(1.2, ...index) * 1.08;
  const x = (w: number) => ((w - 1) / 51) * W;               // week 1..52
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  const line = index.map((v, i) => `${i ? "L" : "M"}${x(i + 1).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const area = `${line}L${x(52)},${y(0)}L${x(1)},${y(0)}Z`;
  const hw = hx === null ? null : Math.round(hx * 51) + 1;

  if (table) {
    return (
      <div>
        <button onClick={() => setTable(false)} className="mb-1 text-xs text-rise hover:underline">Show as chart</button>
        <div className="max-h-56 overflow-auto rounded-lg border border-line text-xs">
          <table className="w-full"><thead className="sticky top-0 bg-panel-2 text-muted"><tr><th className="px-2 py-1 text-left">Week of</th><th className="px-2 text-right">× yearly average</th></tr></thead>
            <tbody>{index.map((v, i) => <tr key={i} className={`border-t border-line ${i + 1 === nowWeek ? "bg-accent/10" : ""}`}><td className="px-2 py-0.5">{short(weekDate(i + 1))}</td><td className="px-2 text-right">{v.toFixed(2)}×</td></tr>)}</tbody>
          </table>
        </div>
      </div>
    );
  }
  return (
    <div className="relative">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-[150px] w-full overflow-visible"
        onMouseMove={onMove} onMouseLeave={onLeave} role="img" aria-label="Average year of searches by week">
        {seasons.map((s) => {
          const a = x(s.rise_week), b = x(s.end_week);
          const spans = a <= b ? [[a, b]] : [[a, W], [0, b]];
          return spans.map(([p, q], k) => (
            <g key={`${s.peak_week}-${k}`}>
              <rect x={p} y={pad.t} width={Math.max(2, q - p)} height={H - pad.t - pad.b} className="fill-accent/10" />
              {k === 0 && <text x={Math.min(p + 4, W - 70)} y={pad.t - 5} className="fill-muted text-[11px]">{s.label}</text>}
            </g>
          ));
        })}
        <line x1="0" x2={W} y1={y(1)} y2={y(1)} className="stroke-line" strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
        <path d={area} className="fill-accent/15" />
        <path d={line} fill="none" className="stroke-accent" strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        <line x1={x(nowWeek)} x2={x(nowWeek)} y1={pad.t} y2={H - pad.b} className="stroke-text/60" strokeDasharray="2 3" vectorEffect="non-scaling-stroke" />
        {MONTHS.map((m, i) => <text key={m} x={(i / 12) * W + 4} y={H - 5} className="fill-muted text-[10px]">{m}</text>)}
        {hw !== null && (
          <>
            <line x1={x(hw)} x2={x(hw)} y1={pad.t} y2={H - pad.b} className="stroke-text/40" vectorEffect="non-scaling-stroke" />
            <circle cx={x(hw)} cy={y(index[hw - 1])} r="4" className="fill-accent stroke-panel" strokeWidth="2" vectorEffect="non-scaling-stroke" />
          </>
        )}
      </svg>
      <span className="pointer-events-none absolute text-[10px] text-muted" style={{ left: `${((nowWeek - 1) / 51) * 100}%`, top: 0, transform: "translateX(-50%)" }}>today</span>
      {hw !== null && (
        <div className="pointer-events-none absolute top-6 z-10 rounded-md border border-line bg-ink/95 px-2 py-1 text-xs shadow"
          style={{ left: `${Math.min(80, Math.max(0, ((hw - 1) / 51) * 100 - 8))}%` }}>
          Week of {short(weekDate(hw))}: <b>{index[hw - 1].toFixed(2)}×</b> the yearly average
        </div>
      )}
      <div className="mt-1 flex justify-between text-[11px] text-muted">
        <span>dashed line = the term&apos;s yearly average · shaded = its season</span>
        <button onClick={() => setTable(true)} className="text-rise hover:underline">Show as table</button>
      </div>
    </div>
  );
}

/** Five years of weekly values (0–100, Google's index against the term's own peak). */
export function HistoryLine({ series, height = 90 }: { series: [string, number][]; height?: number }) {
  const { ref, hx, onMove, onLeave } = useHover();
  if (!series.length) return null;
  const H = height, pad = { t: 6, b: 16 };
  const n = series.length;
  const x = (i: number) => (i / (n - 1)) * W;
  const y = (v: number) => pad.t + (1 - v / 100) * (H - pad.t - pad.b);
  const line = series.map(([, v], i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const years = series.map(([d], i) => [d, i] as const).filter(([d], i) => i === 0 || d.slice(0, 4) !== series[i - 1][0].slice(0, 4));
  const hi = hx === null ? null : Math.round(hx * (n - 1));
  return (
    <div className="relative">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-[90px] w-full"
        onMouseMove={onMove} onMouseLeave={onLeave} role="img" aria-label="Weekly searches over five years">
        {years.slice(1).map(([d, i]) => <line key={d} x1={x(i)} x2={x(i)} y1={pad.t} y2={H - pad.b} className="stroke-line/70" vectorEffect="non-scaling-stroke" />)}
        <path d={line} fill="none" className="stroke-muted" strokeWidth="1.5" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        {years.map(([d, i]) => <text key={d} x={x(i) + 3} y={H - 3} className="fill-muted text-[10px]">{d.slice(0, 4)}</text>)}
        {hi !== null && <circle cx={x(hi)} cy={y(series[hi][1])} r="3.5" className="fill-text stroke-panel" strokeWidth="2" vectorEffect="non-scaling-stroke" />}
      </svg>
      {hi !== null && (
        <div className="pointer-events-none absolute top-0 z-10 rounded-md border border-line bg-ink/95 px-2 py-1 text-xs shadow"
          style={{ left: `${Math.min(78, Math.max(0, (hi / (n - 1)) * 100 - 8))}%` }}>
          Week of {series[hi][0]}: <b>{series[hi][1]}</b>/100
        </div>
      )}
    </div>
  );
}
