import type { Item } from "@/lib/types";
import { num, times } from "@/lib/format";

type Result = { name: string; q: string; status: "pass" | "warn" | "fail" | "n/a"; evidence: string };

/** The 5 tests every video must pass, judged from PUBLIC signals (others' videos don't expose watch time or sales). */
export function fiveTests(i: Item): Result[] {
  const sc = i.scorecard?.criteria;
  const out: Result[] = [];
  // 1. Attention: did it stop the right people? Public proxy: distribution relative to the creator and niche.
  const att = i.outlier ?? null;
  out.push({ name: "Attention", q: "Does it stop the right people from scrolling?",
    status: att == null ? "n/a" : att >= 3 ? "pass" : att >= 1.5 ? "warn" : "fail",
    evidence: att == null ? "no creator baseline" : `${times(att)} the creator's usual${i.vs_topic ? `, ${times(i.vs_topic)} the niche` : ""}${sc?.hook ? `; hook rated ${sc.hook.score}/5` : ""}` });
  // 2. Retention: platforms keep pushing videos people finish; proxy = sustained per-day views + growth.
  out.push({ name: "Retention", q: "Does it keep viewers interested?",
    status: i.rise_per_day ? "pass" : sc?.retention ? (sc.retention.score >= 4 ? "pass" : sc.retention.score >= 3 ? "warn" : "fail") : (i.per_day ?? 0) > 0 ? "warn" : "n/a",
    evidence: `${i.rise_per_day ? `still growing +${num(i.rise_per_day)}/day` : `${num(i.per_day)} views/day`}${sc?.pacing ? `; pacing ${sc.pacing.score}/5` : ""}${i.wpm ? `; ${i.wpm} words/min` : ""} (watch time is private to the creator)` });
  // 3. Engagement
  const eng = i.engagement;
  out.push({ name: "Engagement", q: "Does it make viewers care or react?",
    status: eng == null ? "n/a" : eng >= 0.04 ? "pass" : eng >= 0.015 ? "warn" : "fail",
    evidence: eng == null ? "no public counts" : `${(eng * 100).toFixed(1)}% liked or commented${i.shares ? `, ${num(i.shares)} shares` : ""}${i.saves ? `, ${num(i.saves)} saves` : ""}${i.questions?.length ? `; ${i.questions.length} viewer questions` : ""}` });
  // 4. Action
  out.push({ name: "Action", q: "Does it motivate the next step?",
    status: i.cta ? (sc?.cta && sc.cta.score < 3 ? "warn" : "pass") : sc?.cta ? (sc.cta.score >= 4 ? "pass" : "warn") : "warn",
    evidence: i.cta ? `ends with: “${i.cta.slice(0, 80)}”` : "no spoken call to action detected (clicks and follows are private)" });
  // 5. Business impact: not observable on someone else's post.
  out.push({ name: "Business impact", q: "Does it deliver the result efficiently?", status: "n/a",
    evidence: "CPA, ROAS and profit are private. Measure on your own posts and ads (Your performance)." });
  return out;
}

const STYLE = { pass: "bg-above text-ink", warn: "bg-viral text-ink", fail: "bg-mega text-ink", "n/a": "bg-panel-2 text-muted" };

export default function FiveTests({ item }: { item: Item }) {
  return (
    <div className="grid gap-2 sm:grid-cols-5">
      {fiveTests(item).map((t) => (
        <div key={t.name} className="rounded-lg bg-panel-2 p-2.5" title={t.q}>
          <div className="flex items-center justify-between gap-1">
            <span className="text-xs font-semibold">{t.name}</span>
            <span className={`rounded-full px-1.5 text-[10px] font-semibold uppercase ${STYLE[t.status]}`}>{t.status}</span>
          </div>
          <p className="mt-1 text-[11px] leading-snug text-muted">{t.evidence}</p>
        </div>
      ))}
    </div>
  );
}
