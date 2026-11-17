import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { isLocal, loadAds, loadIndex, loadProfile, profileNames } from "@/lib/data";
import { loadDemand, geoLabel } from "@/lib/demand";
import { loadPerf } from "@/lib/perf";
import { loadPaid, usd } from "@/lib/paid";
import { ago, num, times, when } from "@/lib/format";
import { studyPicks } from "@/lib/ads";
import RunButton from "@/components/RunButton";

export async function generateStaticParams() {
  return (await profileNames()).map((name) => ({ name }));
}

export async function generateMetadata({ params }: { params: Promise<{ name: string }> }): Promise<Metadata> {
  return { title: (await params).name };
}

const WEEK = 7 * 864e5;
const SCHEDULE = "Weekly, Mondays (scheduled task)";

type Fresh = "fresh" | "stale" | "never" | "off";
function freshness(iso: string | null | undefined, configured = true): Fresh {
  if (!configured) return "off";
  if (!iso) return "never";
  return Date.now() - new Date(iso).getTime() <= WEEK + 864e5 ? "fresh" : "stale";
}
const FRESH: Record<Fresh, [string, string]> = {
  fresh: ["up to date", "border-above/50 text-above"],
  stale: ["older than a week", "border-viral/50 text-viral"],
  never: ["not run yet", "border-line text-muted"],
  off: ["not set up", "border-line text-muted"],
};
const fmtDate = (d: string) => new Date(`${d}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });

export default async function Overview({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const [profile, ads, demand, perf, index, paid] = await Promise.all([loadProfile(name), loadAds(name), loadDemand(name), loadPerf(name), loadIndex(), loadPaid(name)]);
  if (!profile && !ads) notFound();
  const entry = index.profiles.find((p) => p.name === name);
  const setup = profile?.setup;
  const base = `/p/${encodeURIComponent(name)}`;

  // ---- videos
  const live = (profile?.items ?? []).filter((i) => !i.dismissed);
  const viral = live.filter((i) => (i.outlier ?? 0) >= 3);
  const fresh = live.filter((i) => i.new);
  const top = [...viral].sort((a, b) => (b.weighted ?? b.outlier ?? 0) - (a.weighted ?? a.outlier ?? 0)).slice(0, 4);
  const scanned = live.flatMap((i) => (i.history.length ? [i.history[i.history.length - 1][0]] : [])).sort().pop() ?? profile?.date ?? null;

  // ---- ads
  const adList = ads?.ads ?? [];
  const running = adList.filter((a) => a.active).length;
  const long = adList.filter((a) => (a.days_running ?? 0) >= 30).length;
  const newAds = adList.filter((a) => a.new).length;
  const picks = ads ? studyPicks(adList).size : 0;
  const topAdv = [...(ads?.advertisers ?? [])].sort((a, b) => b.long_runners - a.long_runners || b.ads - a.ads).slice(0, 4);

  // ---- demand: what's next on the calendar
  const today = new Date().toISOString().slice(0, 10);
  const cal = demand?.calendar ?? [];
  const upcoming = [...cal].filter((c) => c.start_by).sort((a, b) => a.start_by.localeCompare(b.start_by));
  const inSeason = cal.filter((c) => c.in_season);
  const nextUp = upcoming.find((c) => c.start_by >= today);

  // ---- swipe / ideas
  const swipe = profile?.swipe ?? [];
  const toFilm = swipe.filter((n) => ["idea", "scripted"].includes(n.status ?? "idea")).length;
  const filmed = swipe.filter((n) => n.status === "filmed").length;

  // ---- this week: the few things worth doing now
  const todo: { text: React.ReactNode; href: string; tone?: string }[] = [];
  if (inSeason.length) todo.push({ text: <>In season now: <b className="text-text">{inSeason.map((c) => c.term).slice(0, 3).join(", ")}</b>. Post and advertise these first.</>, href: `${base}/demand`, tone: "text-above" });
  if (nextUp) todo.push({ text: <>Start posting about <b className="text-text">{nextUp.term}</b> by {fmtDate(nextUp.start_by)} (it rises {fmtDate(nextUp.rise)}, peaks {fmtDate(nextUp.peak)}).</>, href: `${base}/demand` });
  if (viral.length) todo.push({ text: <><b className="text-text">{viral.length}</b> videos at 3× their creator&apos;s usual{fresh.length ? <>, <b className="text-text">{fresh.length}</b> new since the last run</> : null}. Pick formats to borrow.</>, href: `${base}/videos` });
  if (picks) todo.push({ text: <><b className="text-text">{picks}</b> competitor ads worth studying{newAds ? <> · {newAds} new this run</> : null}.</>, href: `${base}/ads?worth=1` });
  if (toFilm) todo.push({ text: <><b className="text-text">{toFilm}</b> saved ideas waiting to be scripted or filmed.</>, href: `${base}/swipe` });
  const warnings = [...(profile?.budget ?? []), ...(ads?.budget ?? [])];

  return (
    <div className="space-y-6">
      {/* business */}
      <section className="rounded-2xl border border-line bg-panel p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 max-w-4xl">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">The business</h2>
            <p className="mt-1.5 whitespace-pre-line text-sm leading-relaxed text-text/90">
              {profile?.business || ads?.business || "No description yet. Add one in Settings: every AI breakdown and idea is adapted to it."}
            </p>
          </div>
          <Link href={`${base}/settings#business`} className="shrink-0 rounded-lg border border-line px-2.5 py-1 text-xs text-muted hover:border-accent/60 hover:text-text">
            ⚙ Edit business
          </Link>
        </div>
      </section>

      {/* this week */}
      {(todo.length > 0 || warnings.length > 0) && (
        <section>
          <h2 className="mb-2 text-sm font-semibold">This week</h2>
          <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-panel">
            {todo.map((t, i) => (
              <li key={i}>
                <Link href={t.href} className={`flex items-center justify-between gap-3 px-4 py-2.5 text-sm hover:bg-panel-2 ${t.tone ?? "text-muted"}`}>
                  <span>{t.text}</span><span className="text-muted">→</span>
                </Link>
              </li>
            ))}
            {warnings.map((w) => <li key={w} className="px-4 py-2.5 text-sm text-viral">⚠️ {w}</li>)}
          </ul>
        </section>
      )}

      {/* sections */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Videos" href={`${base}/videos`} settings={`${base}/settings#videos`}
          state={freshness(profile?.date, Boolean(profile))} last={scanned}
          what="Viral Shorts, Reels and TikToks on the topic: outliers against each creator's usual, fastest, rising, your tracked links."
          stats={[["posts", num(live.length)], ["3×+ usual", num(viral.length)], ["new", num(fresh.length)], ["hashtags · keywords", `${profile?.sources.hashtags ?? 0} · ${profile?.sources.keywords ?? 0}`]]}
          footer={<>
            <span>{SCHEDULE}. YouTube is free; TikTok{setup?.tiktok ? "" : " (not set up)"} uses Apify.</span>
            {profile && <RunButton profile={name} job="videos" label="Run YouTube now (free)" command={`python -m viral_scout run ${name} --free`} local={isLocal} />}
          </>}>
          {top.length > 0 && (
            <div className="grid grid-cols-4 gap-2">
              {top.map((i) => (
                <Link key={i.key} href={`${base}/v/${encodeURIComponent(i.id)}`} className="group relative block aspect-[9/12] overflow-hidden rounded-lg bg-panel-2" title={i.title}>
                  {i.thumbnail && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={i.thumbnail} alt="" loading="lazy" className="h-full w-full object-cover opacity-90 group-hover:opacity-100" />
                  )}
                  <span className="absolute left-1 top-1 rounded-full bg-ink/85 px-1.5 text-[11px] font-semibold text-viral">{times(i.outlier)}</span>
                </Link>
              ))}
            </div>
          )}
        </Card>

        <Card title="Ads" href={`${base}/ads`} settings={`${base}/settings#ads`}
          state={freshness(ads?.date, Boolean(setup?.ads ?? ads))} last={ads?.date}
          what="Competitors' and the category's long-running ads: offers, hooks, formats. Scores are proxies, not spend."
          stats={[["ads", num(adList.length)], ["running", num(running)], ["30d+", num(long)], ["competitors", num(setup?.ads?.advertisers ?? ads?.advertisers.length ?? 0)]]}
          footer={<>
            <span>{SCHEDULE}. Apify (paid), about $0.17 per Facebook ad-library search.</span>
            {ads && <RunButton profile={name} job="ads-rescore" label="Re-score last run (free)" command={`python -m viral_scout ads ${name} --rescore`} local={isLocal} />}
          </>}>
          {topAdv.length > 0 && (
            <ul className="space-y-1 text-sm">
              {topAdv.map((a) => (
                <li key={a.advertiser} className="flex justify-between gap-2">
                  <Link href={`${base}/ads?advertiser=${encodeURIComponent(a.advertiser)}`} className="truncate hover:text-accent">{a.advertiser}{a.launch_burst ? " 🚀" : ""}</Link>
                  <span className="shrink-0 text-xs text-muted">{a.ads} ads · <span className="text-viral">{a.long_runners} long</span>{a.longest_days ? ` · ${Math.round(a.longest_days)} d max` : ""}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Search demand" href={`${base}/demand`} settings={`${base}/settings#demand`}
          state={freshness(demand?.fetched, Boolean(setup?.demand ?? demand))} last={demand?.fetched}
          what={`Google Trends${demand ? ` for ${geoLabel(demand.geo)}` : ""}: when each service rises and peaks, so posts and ads go out before demand does.`}
          stats={[["terms", num(demand?.terms.length ?? setup?.demand?.terms ?? 0)], ["in season", num(inSeason.length)], ["next start-by", nextUp ? fmtDate(nextUp.start_by) : "—"], ["area", demand?.geo || setup?.demand?.geo || "—"]]}
          footer={<span>{SCHEDULE}, cached 7 days. Apify, about $0.005 per term.</span>}>
          {upcoming.length > 0 && (
            <ul className="space-y-1 text-sm">
              {[...inSeason, ...upcoming.filter((c) => !c.in_season)].slice(0, 4).map((c) => (
                <li key={c.term} className="flex justify-between gap-2">
                  <span className="truncate">{c.term}</span>
                  <span className={`shrink-0 text-xs ${c.in_season ? "text-above" : "text-muted"}`}>
                    {c.in_season ? (c.peak < today ? `in season · peaked ${fmtDate(c.peak)} · ends ${fmtDate(c.end)}` : `in season · peaks ${fmtDate(c.peak)}`) : `post by ${fmtDate(c.start_by)} · ${c.label}`}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Paid ads" href={`${base}/paid`} settings={`${base}/paid#brief`}
          state={!paid || !Object.keys(paid.accounts).length ? "off" : freshness(paid.snapshot?.pulled ?? null)} last={paid?.snapshot?.pulled ?? null} lastLabel="read"
          what="Your own ad accounts (Meta, Google, TikTok) in one place: spend this month against the cap, what's running, cost per result, and Claude building campaigns from your brief."
          stats={[
            ["cap / month", paid?.cap ? usd(paid.cap) : "not set"],
            ["spent", usd(paid?.month.spent ?? 0)],
            ["projected", usd(paid?.month.projected ?? 0)],
            ["running", String(Object.values(paid?.snapshot?.platforms ?? {}).reduce((n, a) => n + (a?.campaigns ?? []).filter((c) => c.running).length, 0))],
          ]}
          footer={<span>{paid?.cap ? paid.month.check : "Set a monthly cap and the brief to let Claude build campaigns."} <Link href={`${base}/paid`} className="text-rise hover:underline">Open →</Link></span>} />

        <Card title="Your performance" href={`${base}/performance`} settings={`${base}/settings#perf`}
          state={freshness(perf?.date, Boolean(setup?.perf || setup?.own || perf))} last={perf?.date}
          what="Your own videos and ads against benchmarks: hook rate, retention, CTR, CPA, ROAS, and what to fix first."
          stats={[["records", num(perf?.records.length ?? 0)], ["goal", perf?.goal ?? "—"], ["own channels", num(setup?.own ?? 0)], ["ad account", setup?.perf ? "linked" : "—"]]}
          footer={<span>Run with <code className="text-text">python -m viral_scout perf {name}</code> (Meta / YouTube APIs, free) or import a CSV.</span>} />

        <Card title="Ideas & swipe file" href={`${base}/swipe`} settings={`${base}/settings#business`}
          state={(profile?.ideas.length ?? 0) || swipe.length ? "fresh" : "never"} last={profile?.ideas[0]?.date ?? null} lastLabel="latest note"
          what="AI breakdowns adapted to this business, and saved references from idea to posted."
          stats={[["idea notes", num(profile?.ideas.length ?? 0)], ["saved", num(swipe.length)], ["to film", num(toFilm)], ["filmed", num(filmed)]]}
          footer={<span>New breakdowns: <code className="text-text">/viral-scout {name}</code> in Claude Code. <Link href={`${base}/swipe#ideas`} className="text-rise hover:underline">Idea notes →</Link></span>} />

        <Card title="Runs" href={`${base}/runs`} settings={`${base}/settings`}
          state={profile?.errors.length ? "stale" : "fresh"} last={entry?.date ?? profile?.date}
          what="What the videos, ads and search demand runs did, what they skipped and why (expected, temporary or a missing key), and hashtags or creators worth adding."
          stats={[["skipped", num((profile?.skipped.length ?? 0) + (ads?.skipped.length ?? 0))], ["errors", num((profile?.errors.length ?? 0) + (ads?.errors.length ?? 0))], ["runs logged", num(profile?.runs.length ?? 0)], ["watched", num(profile?.sources.watch ?? 0)]]}
          footer={<Link href="/setup" className="text-rise hover:underline">API keys and setup →</Link>} />
      </div>
    </div>
  );
}

function Card({ title, href, settings, state, last, lastLabel = "last run", what, stats, footer, children }: {
  title: string; href: string; settings: string; state: Fresh; last?: string | null; lastLabel?: string; what: string;
  stats: [string, string][]; footer?: React.ReactNode; children?: React.ReactNode;
}) {
  const [label, cls] = FRESH[state];
  return (
    <section className="flex flex-col gap-3 rounded-2xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Link href={href} className="text-lg font-semibold hover:text-accent">{title} →</Link>
        <span className={`rounded-full border px-2 py-0.5 text-[11px] ${cls}`}>{label}</span>
        <span suppressHydrationWarning className="text-xs text-muted" title={last ? when(last) : undefined}>{last ? `${lastLabel} ${ago(last)}` : ""}</span>
        <Link href={settings} className="ml-auto text-xs text-muted hover:text-text">⚙ Settings</Link>
      </div>
      <p className="text-sm text-muted">{what}</p>
      <dl className="grid grid-cols-4 gap-2 text-center">
        {stats.map(([k, v]) => (
          <div key={k} className="rounded-lg bg-panel-2 px-1 py-1.5">
            <dd className="truncate text-sm font-semibold">{v}</dd>
            <dt className="truncate text-[10px] uppercase tracking-wide text-muted">{k}</dt>
          </div>
        ))}
      </dl>
      {children}
      {footer && <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-line pt-2.5 text-xs text-muted">{footer}</div>}
    </section>
  );
}
