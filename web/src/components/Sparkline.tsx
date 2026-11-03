export default function Sparkline({ points }: { points: [string, number | null][] }) {
  const pts = points.filter((p): p is [string, number] => typeof p[1] === "number");
  if (pts.length < 2) return null;
  const xs = pts.map(([t]) => new Date(t).getTime());
  const ys = pts.map(([, v]) => v);
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
  const [y0, y1] = [Math.min(...ys), Math.max(...ys)];
  const W = 120, H = 28;
  const d = pts
    .map(([, v], i) => {
      const x = x1 === x0 ? (i / (pts.length - 1)) * W : ((xs[i] - x0) / (x1 - x0)) * W;
      const y = y1 === y0 ? H / 2 : H - ((v - y0) / (y1 - y0)) * (H - 4) - 2;
      return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const up = ys[ys.length - 1] > ys[0];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-7 w-28" aria-label={`${pts.length} measurements`}>
      <path d={d} fill="none" stroke={up ? "var(--color-rise)" : "var(--color-muted)"} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
