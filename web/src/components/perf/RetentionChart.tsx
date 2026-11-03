"use client";

import { useState } from "react";
import type { Curve } from "@/lib/perf";

/** Retention curve (% of the starting audience still watching) with drop-off markers. Plain SVG, one y-axis. */
export default function RetentionChart({ curve, duration }: { curve: Curve; duration: number | null }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 320, H = 150, L = 34, R = 10, T = 10, B = 24;
  const yMax = Math.max(100, Math.ceil(curve.peak / 25) * 25);
  const x = (r: number) => L + r * (W - L - R);
  const y = (v: number) => T + (1 - v / yMax) * (H - T - B);
  const pts = curve.points;
  const d = pts.map(([r, v], i) => `${i ? "L" : "M"}${x(r).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area = `${d} L${x(pts[pts.length - 1][0]).toFixed(1)},${y(0)} L${x(pts[0][0]).toFixed(1)},${y(0)} Z`;
  const ticks = [0, 25, 50, 75, 100].filter((t) => t <= yMax);
  const label = (r: number) => (duration ? `${Math.round(r * duration)} s` : `${Math.round(r * 100)}%`);
  const h = hover !== null ? pts[hover] : null;

  return (
    <figure className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
        aria-label={`Retention curve: ${pts.map(([r, v]) => `${label(r)} ${Math.round(v)}%`).join(", ")}`}
        onMouseLeave={() => setHover(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="var(--color-line)" strokeWidth="1" strokeDasharray={t ? "2 3" : undefined} />
            <text x={L - 5} y={y(t) + 3} textAnchor="end" fontSize="9" fill="var(--color-muted)">{t}%</text>
          </g>
        ))}
        {[0, 0.25, 0.5, 0.75, 1].map((r) => (
          <text key={r} x={x(r)} y={H - 8} textAnchor={r === 0 ? "start" : r === 1 ? "end" : "middle"} fontSize="9" fill="var(--color-muted)">{label(r)}</text>
        ))}
        {curve.drops.map((dr, i) => (
          <g key={i}>
            <rect x={x(dr.from)} y={T} width={Math.max(2, x(dr.to) - x(dr.from))} height={H - T - B}
              fill="var(--color-mega)" opacity={i === 0 ? 0.14 : 0.07} />
            <text x={(x(dr.from) + x(dr.to)) / 2} y={T + 9} textAnchor="middle" fontSize="9" fill="var(--color-text)">−{Math.round(dr.drop)}</text>
          </g>
        ))}
        <path d={area} fill="var(--color-rise)" opacity="0.08" />
        <path d={d} fill="none" stroke="var(--color-rise)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {h && (
          <g pointerEvents="none">
            <line x1={x(h[0])} x2={x(h[0])} y1={T} y2={H - B} stroke="var(--color-muted)" strokeWidth="1" />
            <circle cx={x(h[0])} cy={y(h[1])} r="4" fill="var(--color-rise)" stroke="var(--color-panel)" strokeWidth="2" />
          </g>
        )}
        {pts.map(([r], i) => {
          const prev = i ? x(pts[i - 1][0]) : x(r);
          const next = i < pts.length - 1 ? x(pts[i + 1][0]) : x(r);
          return (
            <rect key={i} x={(prev + x(r)) / 2} y={T} width={Math.max(4, (next - prev) / 2)} height={H - T - B}
              fill="transparent" onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} />
          );
        })}
      </svg>
      {h && (
        <div className="pointer-events-none absolute top-0 rounded-md border border-line bg-panel-2 px-2 py-1 text-[11px] shadow"
          style={{ left: `${Math.min(70, (x(h[0]) / W) * 100)}%` }}>
          <span className="text-muted">at {label(h[0])}: </span><span className="font-semibold">{h[1].toFixed(0)}%</span> still watching
        </div>
      )}
      <figcaption className="mt-1 text-[11px] text-muted">
        {curve.source === "retention" ? "YouTube audience retention" : "From 25/50/75/100% view counts"} · shaded = biggest drops (points lost)
        {curve.peak > 100 ? " · above 100% = rewatched" : ""}
      </figcaption>
    </figure>
  );
}
