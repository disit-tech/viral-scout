import type { Scorecard } from "@/lib/types";

const LABELS: Record<string, string> = {
  hook: "Hook", first_frame: "First-frame impact", audience: "Target audience", engagement: "Engagement",
  retention: "Retention", watch_time: "Watch time", pacing: "Pacing", storytelling: "Storytelling",
  pattern_interrupts: "Pattern interrupts", clarity: "Clarity", value: "Value proposition", emotion: "Emotional impact",
  credibility: "Credibility / proof", authenticity: "Authenticity", cta: "CTA", conversion: "Conversion potential",
  visual: "Visual appeal", audio: "Audio quality", platform_fit: "Platform fit", shareability: "Shareability",
};

function color(score: number | null) {
  if (score == null) return "var(--color-muted)";
  return score >= 70 ? "var(--color-above)" : score >= 55 ? "var(--color-viral)" : "var(--color-mega)";
}

export default function ScorecardView({ card, cmd }: { card?: Scorecard | null; cmd: string }) {
  if (!card) {
    return (
      <div className="text-sm text-muted">
        Not scored yet. The AI step scores the strongest posts on 20 criteria (100 points). In Claude Code run{" "}
        <code className="text-text">{cmd}</code>.
      </div>
    );
  }
  const total = card.total ?? 0;
  const R = 34, C = 2 * Math.PI * R;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-5">
        <svg viewBox="0 0 84 84" className="h-24 w-24 shrink-0" role="img" aria-label={`${total} out of 100`}>
          <circle cx="42" cy="42" r={R} fill="none" stroke="var(--color-panel-2)" strokeWidth="9" />
          <circle cx="42" cy="42" r={R} fill="none" stroke={color(card.total)} strokeWidth="9" strokeLinecap="round"
            strokeDasharray={`${(total / 100) * C} ${C}`} transform="rotate(-90 42 42)" />
          <text x="42" y="47" textAnchor="middle" fontSize="20" fontWeight="700" fill="var(--color-text)">{card.total ?? "—"}</text>
        </svg>
        <div className="min-w-0 flex-1">
          <p className="text-lg font-semibold" style={{ color: color(card.total) }}>{card.verdict}</p>
          {card.summary && <p className="text-sm">{card.summary}</p>}
          {card.fix_first && <p className="mt-1 text-sm text-muted"><b className="text-text">Fix first:</b> {card.fix_first}</p>}
          <p className="mt-1 text-[11px] text-muted">A subjective creative assessment by AI, not a prediction of views or sales. Read it next to the real numbers.</p>
        </div>
      </div>

      <div className="grid gap-1.5 sm:grid-cols-2">
        {Object.entries(card.groups).map(([k, g]) => (
          <div key={k} className="rounded-lg bg-panel-2 px-3 py-2">
            <div className="flex justify-between text-xs"><span>{g.label}</span><span className="text-muted">{g.points}/{g.max}</span></div>
            <div className="mt-1 h-1.5 rounded-full bg-ink">
              <div className="h-1.5 rounded-full" style={{ width: `${(g.points / g.max) * 100}%`, background: color((g.points / g.max) * 100) }} />
            </div>
          </div>
        ))}
      </div>

      <details>
        <summary className="cursor-pointer text-sm text-rise">All 20 criteria with reasons</summary>
        <table className="mt-2 w-full text-sm">
          <tbody>
            {Object.entries(card.criteria).map(([k, c]) => (
              <tr key={k} className="border-t border-line align-top">
                <td className="w-40 py-1.5 pr-2 text-muted">{LABELS[k] ?? k}</td>
                <td className="w-16 py-1.5 font-semibold">{"●".repeat(Math.round(c.score))}<span className="text-line">{"●".repeat(5 - Math.round(c.score))}</span></td>
                <td className="py-1.5">{c.why}</td>
              </tr>
            ))}
            {card.compliance && (
              <tr className="border-t border-line align-top">
                <td className="py-1.5 pr-2 text-muted">Accessibility / compliance</td>
                <td className="py-1.5 font-semibold">{"●".repeat(Math.round(card.compliance.score))}</td>
                <td className="py-1.5">{card.compliance.why}</td>
              </tr>
            )}
          </tbody>
        </table>
      </details>
    </div>
  );
}
