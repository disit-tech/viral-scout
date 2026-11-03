import { num } from "@/lib/format";

/** Views (or likes) at each run, with a time axis. */
export default function GrowthChart({ points }: { points: [string, number | null][] }) {
  const pts = points.filter((p): p is [string, number] => typeof p[1] === "number");
  if (pts.length < 2) return null;
  const W = 640, H = 180, L = 78, B = 26, T = 10, R = 10;
  const xs = pts.map(([t]) => new Date(t).getTime());
  const ys = pts.map(([, v]) => v);
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
  const [lo, hi] = [Math.min(...ys), Math.max(...ys)];
  const pad = (hi - lo) * 0.1 || hi * 0.05 || 1;
  const [y0, y1] = [Math.max(0, lo - pad), hi + pad];
  const X = (t: number) => L + (x1 === x0 ? 0.5 : (t - x0) / (x1 - x0)) * (W - L - R);
  const Y = (v: number) => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
  const d = pts.map(([, v], i) => `${i ? "L" : "M"}${X(xs[i]).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
  const ticks = [y0, (y0 + y1) / 2, y1];
  // Small changes on big numbers: show exact values so the axis labels differ.
  const label = (v: number) => (hi > 0 && (hi - lo) / hi < 0.05 ? Math.round(v).toLocaleString("en-US") : num(v));
  const fmt = (t: number) => new Date(t).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric" });
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Growth across runs">
      {ticks.map((v) => (
        <g key={v}>
          <line x1={L} x2={W - R} y1={Y(v)} y2={Y(v)} stroke="var(--color-line)" strokeDasharray="3 4" />
          <text x={L - 6} y={Y(v) + 4} textAnchor="end" fontSize="11" fill="var(--color-muted)">{label(v)}</text>
        </g>
      ))}
      <path d={d} fill="none" stroke="var(--color-rise)" strokeWidth="2.5" strokeLinejoin="round" />
      {pts.map(([, v], i) => (
        <circle key={i} cx={X(xs[i])} cy={Y(v)} r="3.5" fill="var(--color-rise)"><title>{`${fmt(xs[i])}: ${Math.round(v).toLocaleString("en-US")}`}</title></circle>
      ))}
      <text x={L} y={H - 6} fontSize="11" fill="var(--color-muted)">{fmt(x0)}</text>
      <text x={W - R} y={H - 6} fontSize="11" fill="var(--color-muted)" textAnchor="end">{fmt(x1)}</text>
    </svg>
  );
}
