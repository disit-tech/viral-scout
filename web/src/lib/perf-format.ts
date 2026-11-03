/** Client-safe formatting for own-performance KPIs (no Node imports). */
export function fmtKpi(unit: string | undefined, v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  switch (unit) {
    case "pct": return `${v.toFixed(v >= 10 ? 1 : 2)}%`;
    case "money": return v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    case "x": return `${v.toFixed(2)}×`;
    case "seconds": return `${v.toFixed(1)} s`;
    case "score": return `${v > 0 ? "+" : ""}${Math.round(v)}`;
    default: {
      const a = Math.abs(v);
      if (a >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
      if (a >= 1e4) return `${(v / 1e3).toFixed(1)}K`;
      return Math.round(v).toLocaleString("en-US");
    }
  }
}
