import { notFound } from "next/navigation";
import { demandNames, geoLabel, loadDemand, type DemandTerm } from "@/lib/demand";
import { isLocal, loadProfile, profileNames } from "@/lib/data";
import SetupNeeds from "@/components/SetupNeeds";
import { when } from "@/lib/format";
import { HistoryLine, SeasonCurve } from "@/components/DemandChart";

export async function generateStaticParams() {
  const names = new Set([...(await profileNames()), ...(await demandNames())]);
  return [...names].map((name) => ({ name }));
}

export async function generateMetadata({ params }: { params: Promise<{ name: string }> }) {
  return { title: `Search demand · ${(await params).name}` };
}

function isoWeek(d: Date) {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = (t.getUTCDay() + 6) % 7;
  t.setUTCDate(t.getUTCDate() - day + 3);
  const first = new Date(Date.UTC(t.getUTCFullYear(), 0, 4));
  return Math.min(52, 1 + Math.round(((t.getTime() - first.getTime()) / 86_400_000 - 3 + ((first.getUTCDay() + 6) % 7)) / 7));
}
const fmt = (iso: string) => new Date(iso + "T12:00:00Z").toLocaleDateString([], { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${v}%`);

export default async function DemandPage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const d = await loadDemand(name);
  if (!d) {
    if (!(await loadProfile(name))) notFound();
    return (
      <div className="space-y-3">
        {isLocal && <SetupNeeds profile={name} sections={["demand"]} title="Search demand needs" />}
        <div className="rounded-xl border border-dashed border-line p-8 text-center text-sm text-muted">
          No search demand yet. Add the services to track and the area in Settings → Search demand, then run{" "}
          <code className="text-text">python -m viral_scout demand {name}</code> (about $0.005 per term via Apify).
        </div>
      </div>
    );
  }
  const nowWeek = isoWeek(new Date());
  const inSeason = d.calendar.filter((c) => c.in_season);
  const next = d.calendar.filter((c) => !c.in_season);
  const ok = d.terms.filter((t) => t.status === "ok");

  return (
    <div className="space-y-5">
      <div>
        {/* The business layout (p/[name]/layout.tsx) adds the back link, the name and the tabs. */}
        <p className="max-w-3xl text-sm text-muted">
          When people in the <b className="text-text">{geoLabel(d.geo)}</b> search for each service, what&apos;s rising now and
          which words they use. Google Trends, {d.time.replace("today ", "last ")}, refreshed {when(d.fetched)}. Values are
          Google&apos;s 0–100 index (each term against its own peak), <b className="text-text">not search volumes</b>.
          Start posting and advertising about {d.lead_weeks} weeks before a season starts.
        </p>
      </div>

      {inSeason.length > 0 && (
        <section>
          <h2 className="mb-2 font-semibold">In season now</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {inSeason.map((c) => (
              <a key={c.term + c.label} href={`#${slug(c.term)}`} className="rounded-2xl border border-above/40 bg-panel p-3 hover:bg-panel-2">
                <p className="font-semibold">{c.term}</p>
                <p className="text-sm text-above">{c.label} · until {fmt(c.end)}</p>
                <p className="mt-1 text-xs text-muted">started {fmt(c.rise)} · peak {fmt(c.peak)}{c.low_volume ? " · few searches here" : ""}</p>
              </a>
            ))}
          </div>
        </section>
      )}

      {next.length > 0 && (
        <section className="overflow-x-auto rounded-2xl border border-line bg-panel">
          <h2 className="px-4 pt-3 font-semibold">Next to prepare</h2>
          <table className="mt-2 w-full min-w-[640px] text-sm">
            <thead className="bg-panel-2 text-left text-xs uppercase tracking-wide text-muted">
              <tr><th className="px-4 py-2">Service</th><th className="px-3">Season</th><th className="px-3">Start posting by</th><th className="px-3">Demand rises</th><th className="px-3">Peak</th><th className="px-3">Ends</th></tr>
            </thead>
            <tbody>
              {next.map((c) => (
                <tr key={c.term + c.label} className="border-t border-line">
                  <td className="px-4 py-2"><a href={`#${slug(c.term)}`} className="font-medium hover:underline">{c.term}</a>{c.low_volume && <span className="ml-1 text-xs text-muted">(few searches)</span>}</td>
                  <td className="px-3 text-muted">{c.label}</td>
                  <td className="px-3 font-semibold text-accent">{fmt(c.start_by)}</td>
                  <td className="px-3">{fmt(c.rise)}</td>
                  <td className="px-3">{fmt(c.peak)}</td>
                  <td className="px-3 text-muted">{fmt(c.end)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {d.compare && (
        <section className="rounded-2xl border border-line bg-panel p-4">
          <h2 className="font-semibold">Which words people use</h2>
          <p className="mb-3 text-xs text-muted">The same idea in different words, on one shared scale (last 12 months). Use the most searched wording in hooks, headlines and keywords.</p>
          <ul className="space-y-2">
            {d.compare.rows.map((r) => (
              <li key={r.term} className="flex items-center gap-3 text-sm">
                <span className="w-56 shrink-0 truncate" title={r.term}>{r.term}</span>
                <span className="h-2.5 flex-1 rounded-full bg-panel-2"><span className="block h-full rounded-full bg-accent" style={{ width: `${Math.max(1, r.share_pct)}%` }} /></span>
                <span className="w-28 text-right text-xs"><b>{r.share_pct}%</b> <span className="text-muted">of searches</span></span>
              </li>
            ))}
          </ul>
          <a href={d.compare.trends_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs text-rise hover:underline">Open the comparison in Google Trends ↗</a>
        </section>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {ok.map((t) => <TermCard key={t.term} t={t} nowWeek={nowWeek} />)}
      </div>
      {d.terms.filter((t) => t.status !== "ok").map((t) => <p key={t.term} className="text-sm text-muted">{t.term}: {t.note}</p>)}

      {(d.errors.length > 0 || d.skipped.length > 0) && (
        <section className="rounded-2xl border border-line bg-panel p-4 text-sm text-muted">
          {[...d.skipped, ...d.errors].map((e) => <p key={e}>{e}</p>)}
        </section>
      )}
      <p className="text-xs text-muted">
        How it&apos;s read: 5 years of weekly values averaged into one year (smoothed over 5 weeks). A season is a peak at
        least 15% above the term&apos;s yearly average; it starts after the last week below average and ends at the last week
        above it. &quot;Now vs normal&quot; compares the last 4 weeks with what this time of year usually looks like. Refreshed
        weekly with the ads run (about $0.005 per term via Apify): <code>python -m viral_scout demand {name}</code>.
      </p>
    </div>
  );
}

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-");

function TermCard({ t, nowWeek }: { t: DemandTerm; nowWeek: number }) {
  const rel = t.related;
  const buyer = rel?.rising.filter((q) => q.buyer) ?? [];
  const other = rel?.rising.filter((q) => !q.buyer) ?? [];
  return (
    <section id={slug(t.term)} className="scroll-mt-20 rounded-2xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="text-lg font-semibold">{t.term}</h3>
        <span className="rounded-full bg-panel-2 px-2 py-0.5 text-[11px] text-muted">{t.shape}</span>
        {t.in_season && <span className="rounded-full border border-above/50 px-2 py-0.5 text-[11px] text-above">in season</span>}
        {t.trends_url && <a href={t.trends_url} target="_blank" rel="noreferrer" className="ml-auto text-xs text-rise hover:underline">Google Trends ↗</a>}
      </div>
      <dl className="mt-2 grid grid-cols-3 gap-2 text-center">
        <Stat label="now vs last year" value={pct(t.vs_last_year_pct)} />
        <Stat label="vs normal for now" value={pct(t.vs_normal_pct)} />
        <Stat label="2-year trend" value={pct(t.trend_pct)} />
      </dl>
      {t.note && <p className="mt-2 text-xs text-muted">{t.note}</p>}
      <div className="mt-3">
        <p className="mb-1 text-xs font-semibold text-text">The average year</p>
        <SeasonCurve index={t.season_index ?? []} seasons={t.seasons ?? []} nowWeek={nowWeek} />
      </div>
      <div className="mt-3">
        <p className="mb-1 text-xs font-semibold text-text">Last 5 years, weekly</p>
        <HistoryLine series={t.series ?? []} />
      </div>
      {buyer.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-semibold text-text">Rising buyer searches <span className="font-normal text-muted">(ideas for videos, ads and keywords)</span></p>
          <div className="mt-1 flex flex-wrap gap-1.5">{buyer.slice(0, 10).map((q) => <span key={q.query} className="rounded-full border border-accent/40 px-2 py-0.5 text-xs">{q.query} <span className="text-accent">{q.value}</span></span>)}</div>
        </div>
      )}
      {rel && rel.top.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-semibold text-text">Most searched with it</p>
          <div className="mt-1 flex flex-wrap gap-1.5">{rel.top.slice(0, 10).map((q) => <span key={q.query} className="rounded-full bg-panel-2 px-2 py-0.5 text-xs text-muted">{q.query}</span>)}</div>
        </div>
      )}
      {other.length > 0 && (
        <details className="mt-3 text-xs text-muted">
          <summary className="cursor-pointer">Other rising searches ({other.length}, often noise: games, shows, brands)</summary>
          <p className="mt-1">{other.map((q) => `${q.query} (${q.value})`).join(" · ")}</p>
        </details>
      )}
      {rel && rel.places.length > 0 && (
        <p className="mt-3 text-xs text-muted">Searched most in: {rel.places.slice(0, 8).map((p) => p.name).join(", ")}</p>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-panel-2 px-1 py-1.5">
      <dt className="truncate text-[10px] uppercase tracking-wide text-muted">{label}</dt>
      <dd className={`text-sm font-semibold ${value.startsWith("+") ? "text-above" : value.startsWith("-") ? "text-mega" : "text-text"}`}>{value}</dd>
    </div>
  );
}
