import Link from "next/link";
import { notFound } from "next/navigation";
import { adsNames, loadAds } from "@/lib/data";
import { num, when } from "@/lib/format";
import type { AdItem } from "@/lib/types";
import {
  OFFER, SOURCE, adHref, advName, competitorSearch, copyBreakdown, median, queryLabel, similarAds, worthStudying,
} from "@/lib/ads";
import AdTimeline from "@/components/AdTimeline";

export async function generateStaticParams() {
  const out: { name: string; key: string }[] = [];
  for (const name of await adsNames()) {
    const d = await loadAds(name);
    for (const a of d?.ads ?? []) out.push({ name, key: encodeURIComponent(a.key) });
  }
  return out;
}

export async function generateMetadata({ params }: { params: Promise<{ name: string; key: string }> }) {
  const { name, key } = await params;
  const ad = (await loadAds(name))?.ads.find((a) => a.key === decodeURIComponent(key));
  return { title: ad ? `${advName(ad)} · ad` : "Ad" };
}

const days = (d: number | null) => (d === null ? "—" : `${Math.round(d)} d`);
const date = (iso?: string | null) => (iso ? iso.slice(0, 10) : "—");

export default async function AdPage({ params }: { params: Promise<{ name: string; key: string }> }) {
  const { name, key } = await params;
  const data = await loadAds(name);
  const ad = data?.ads.find((a) => a.key === decodeURIComponent(key));
  if (!data || !ad) notFound();

  const all = data.ads;
  const mine = all.filter((a) => advName(a) === advName(ad));
  const variants = ad.group ? all.filter((a) => a.group === ad.group && a.key !== ad.key) : [];
  const advDays = mine.map((a) => a.days_running).filter((d): d is number => d !== null);
  const advMedian = median(advDays);
  const rank = [...all].sort((a, b) => b.ad_score - a.ad_score).findIndex((a) => a.key === ad.key) + 1;
  const copy = copyBreakdown(ad);
  const similar = similarAds(ad, all);
  const lookup = data.lookup.find((r) => r.label.toLowerCase() === advName(ad).toLowerCase());
  const offerMix = new Map<string, number>();
  mine.forEach((a) => a.offers.forEach((o) => offerMix.set(o, (offerMix.get(o) ?? 0) + 1)));
  const sourceMix = new Map<string, number>();
  mine.forEach((a) => sourceMix.set(a.source, (sourceMix.get(a.source) ?? 0) + 1));
  const formatMix = new Map<string, number>();
  mine.forEach((a) => formatMix.set(a.format || "unknown", (formatMix.get(a.format || "unknown") ?? 0) + 1));
  const longest = [...mine].sort((a, b) => (b.days_running ?? -1) - (a.days_running ?? -1))[0];
  const newest = [...mine].filter((a) => a.start).sort((a, b) => (b.start as string).localeCompare(a.start as string))[0];

  const why = reasons(ad, { advMedian, advCount: mine.length, rank, total: all.length });

  return (
    <div className="space-y-5">
      <div>
        <Link href={`/p/${name}/ads`} className="text-xs text-muted hover:text-text">← {name} · Ads</Link>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold tracking-tight">{advName(ad)}</h1>
          <span className="rounded-full border border-accent bg-accent px-2 py-0.5 text-xs font-semibold text-ink" title="ad score (proxy)">{Math.round(ad.ad_score)}</span>
          <span className={`rounded-full border px-2 py-0.5 text-xs ${ad.active ? "border-above bg-above text-ink" : "border-line text-muted"}`}>{ad.active ? "running" : "stopped"}</span>
          {worthStudying(ad) && <span className="rounded-full border border-viral/60 px-2 py-0.5 text-xs text-viral">★ worth studying</span>}
          {ad.new && <span className="rounded-full border border-rise bg-rise px-2 py-0.5 text-xs font-semibold text-ink">new since last run</span>}
          <span className="text-sm text-muted">{SOURCE[ad.source] ?? ad.source} · {ad.format}{ad.platforms.length ? ` · ${ad.platforms.join(", ")}` : ""}</span>
        </div>
        {ad.labels.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{ad.labels.map((l) => <span key={l} className="rounded-full bg-panel-2 px-2 py-0.5 text-[11px]">{l}</span>)}</div>}
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <Creative ad={ad} />
        <div className="space-y-5">
          <Section title="Why it's worth studying">
            <ul className="space-y-1.5">{why.map((r) => <li key={r} className="flex gap-2"><span className="text-muted">•</span><span>{r}</span></li>)}</ul>
            <p className="mt-3 text-xs text-muted">
              Days running and variants are <b className="text-text">proxies</b> for spend, not proof of profit: a long run can also
              be a cheap brand ad. US ads publish no reach, so there are no views to compare.
            </p>
          </Section>
          <Section title="Numbers">
            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <Num label="days running" value={days(ad.days_running)} tone={(ad.days_running ?? 0) >= 30 ? "text-viral" : undefined} />
              <Num label="started" value={date(ad.start)} />
              <Num label={ad.active ? "status" : "stopped"} value={ad.active ? "running" : date(ad.stop)} tone={ad.active ? "text-above" : undefined} />
              <Num label="variants" value={String(ad.variants)} tone={ad.variants >= 3 ? "text-mega" : undefined} />
              <Num label={ad.reach !== null ? ad.reach_label || "reach" : ad.likes ? "likes" : "reach"} value={ad.reach !== null ? num(ad.reach) : ad.likes ? num(ad.likes) : "not published"} />
              <Num label="score rank" value={`#${rank} of ${all.length}`} />
              <Num label="CTA" value={ad.cta || ad.cta_text || "—"} />
              <Num label="landing domain" value={ad.landing_domain || "—"} />
              <Num label="countries" value={(ad.countries ?? []).join(", ") || "—"} />
            </dl>
          </Section>
        </div>
      </div>

      <Section title="Copy breakdown">
        {copy.text ? (
          <>
            <p className="text-xs text-muted">{copy.limitLabel}. The part people see before tapping is in bold.</p>
            <p className="mt-2 whitespace-pre-line rounded-lg bg-panel-2 p-3 leading-relaxed">
              <b className="text-text">{copy.visible}</b><span className="text-muted">{copy.cut}</span>
            </p>
            <dl className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-2">
              <Row label="Hook (first line)" value={ad.hook || "—"} note={copy.hookFits === null ? undefined : copy.hookFits ? "fits before the cut" : "longer than the visible part: the hook gets cut"} />
              <Row label="Names a problem" value={copy.problem.length ? copy.problem.join(", ") : "no (no pain words found)"} />
              <Row label="Offer" value={ad.offers.length ? ad.offers.map((o) => OFFER[o] ?? o).join(", ") : "none detected"} note={ad.offer_text?.length ? ad.offer_text.slice(0, 4).join("; ") : undefined} />
              <Row label="Money / free" value={copy.money.length ? copy.money.join(", ") : "—"} />
              <Row label="Proof" value={copy.proof.length ? copy.proof.join(", ") : "none (no reviews, years, warranty or licence mentioned)"} />
              <Row label="Urgency" value={copy.urgency.length ? copy.urgency.join(", ") : "none"} />
              <Row label="Call to action" value={ad.cta || ad.cta_text || "—"} />
              <Row label="Voice" value={`${copy.youCount}× "you"${copy.firstPerson ? ", speaks as \"we\"" : ""}${copy.questions ? `, ${copy.questions} question${copy.questions > 1 ? "s" : ""}` : ""}${copy.emoji ? `, ${copy.emoji} emoji` : ""}`} />
              <Row label="Length" value={`${copy.words} words · ${copy.chars} characters`} />
              <Row label="Found by" value={ad.found_by.map(queryLabel).join("; ")} note={competitorSearch(ad) ? "a competitor search" : "a keyword or category search"} />
            </dl>
          </>
        ) : (
          <p className="text-muted">This source gave no ad copy (common for Google image/video ads and TikTok). Open the library link to read it.</p>
        )}
      </Section>

      {variants.length > 0 && (
        <Section title={`Variants: ${variants.length + 1} versions of this ad`}>
          <p className="mb-3 text-xs text-muted">Same advertiser, same copy, different images or wording. Several versions running at once is a paid test: compare what changes.</p>
          <MiniGrid profile={name} ads={variants} />
        </Section>
      )}

      <Section title={`${advName(ad)}'s playbook in this run`}>
        <div className="mb-4 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <Num label="ads" value={String(mine.length)} />
          <Num label="running" value={String(mine.filter((a) => a.active).length)} tone="text-above" />
          <Num label="30d+" value={String(mine.filter((a) => (a.days_running ?? 0) >= 30).length)} tone="text-viral" />
          <Num label="median run" value={days(advMedian)} />
          <Num label="longest" value={days(longest?.days_running ?? null)} />
          <Num label="newest start" value={date(newest?.start)} />
        </div>
        <AdTimeline advertiser={advName(ad)} current={ad.key} now={data.date}
          ads={mine.map((a) => ({ key: a.key, href: adHref(name, a), start: a.start, stop: a.stop, active: a.active, days: a.days_running, hook: a.hook || a.title || "", score: a.ad_score, format: a.format, source: a.source }))} />
        <div className="mt-4 grid gap-3 text-xs sm:grid-cols-3">
          <Mix title="Offers" rows={[...offerMix.entries()].map(([k, v]) => [OFFER[k] ?? k, v])} total={mine.length} empty="no offers detected" />
          <Mix title="Platforms" rows={[...sourceMix.entries()].map(([k, v]) => [SOURCE[k] ?? k, v])} total={mine.length} />
          <Mix title="Formats" rows={[...formatMix.entries()]} total={mine.length} />
        </div>
        <p className="mt-3 text-xs">
          <Link href={`/p/${name}/ads?advertiser=${encodeURIComponent(advName(ad))}&view=table`} className="text-rise hover:underline">All {mine.length} ads of {advName(ad)} in a table →</Link>
        </p>
      </Section>

      {similar.length > 0 && (
        <Section title="Same angle elsewhere">
          <p className="mb-3 text-xs text-muted">Other advertisers whose copy overlaps with this ad or uses the same offer. If several run it for weeks, it&apos;s a category pattern, not one company&apos;s trick.</p>
          <div className="space-y-2">
            {similar.map(({ ad: b, sharedOffers, sharedWords }) => (
              <Link key={b.key} href={adHref(name, b)} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-lg border border-line p-2.5 hover:bg-panel-2">
                <span className="font-medium">{advName(b)}</span>
                <span className="text-xs text-muted">{days(b.days_running)} · {b.active ? "running" : "stopped"} · score {Math.round(b.ad_score)} · {SOURCE[b.source] ?? b.source}</span>
                <span className="w-full line-clamp-1 text-sm">{b.hook || b.title}</span>
                <span className="text-[11px] text-muted">
                  {sharedOffers.length > 0 && <>same offer: {sharedOffers.map((o) => OFFER[o] ?? o).join(", ")} · </>}
                  {sharedWords.length > 0 && <>shared words: {sharedWords.join(", ")}</>}
                </span>
              </Link>
            ))}
          </div>
        </Section>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Section title="History">
          <dl className="grid grid-cols-2 gap-2">
            <Num label="first seen by viral-scout" value={ad.first_seen ? when(ad.first_seen) : "this run"} />
            <Num label="last seen" value={ad.last_seen ? when(ad.last_seen) : when(data.date)} />
          </dl>
          <p className="mt-2 text-xs text-muted">The weekly runs build this up: an ad still there Monday after Monday is the strongest signal this page has.</p>
        </Section>
        <Section title="Links">
          <ul className="space-y-1.5">
            {ad.url && <li><a href={ad.url} target="_blank" rel="noreferrer" className="text-rise underline">Open in the ad library ↗</a></li>}
            {ad.link_url && <li><a href={ad.link_url} target="_blank" rel="noreferrer nofollow" className="text-rise underline">Landing page ↗</a> <span className="text-xs text-muted">({ad.landing_domain})</span></li>}
            {lookup && Object.entries(lookup.links).map(([k, v]) => <li key={k}><a href={v} target="_blank" rel="noreferrer" className="text-rise underline">{k}: {lookup.label} ↗</a></li>)}
          </ul>
          <p className="mt-3 text-xs text-muted">Borrow the angle (the problem, the offer type, the format), never the creative, copy or trademarks. Every claim in your own ad must be true and provable.</p>
        </Section>
      </div>
    </div>
  );
}

function reasons(ad: AdItem, c: { advMedian: number | null; advCount: number; rank: number; total: number }) {
  const out: string[] = [];
  const d = ad.days_running;
  if (d !== null) {
    const run = `${Math.round(d)} days${ad.active ? " and still running" : `, stopped ${date(ad.stop)}`}`;
    out.push(d >= 90 ? `Running for ${run}: 90+ days usually means it pays for itself, or it's a core brand ad.`
      : d >= 60 ? `Running for ${run}: past 60 days, well beyond where most tests get switched off.`
      : d >= 30 ? `Running for ${run}: past the 30-day mark; ads still live at day 21 are about 3× as likely to reach day 60.`
      : d >= 21 ? `Running for ${run}: three weeks in, the first point where longevity starts to mean something.`
      : `Only ${run}: too early to call. Come back after a few weekly runs.`);
  } else out.push("No start date from this source, so longevity can't be scored.");
  if (c.advMedian !== null && d !== null && c.advCount >= 3) {
    const x = c.advMedian > 0 ? d / c.advMedian : null;
    if (x !== null) out.push(`${x >= 1 ? `${x.toFixed(1)}× longer than` : `${Math.round((1 - x) * 100)}% shorter than`} this advertiser's median run (${Math.round(c.advMedian)} days over ${c.advCount} ads).`);
  }
  if (ad.variants >= 3) out.push(`${ad.variants} versions of this ad are live: the advertiser is paying to test it, which they rarely do for a loser.`);
  else if (ad.variants === 2) out.push("2 versions of this ad: a small test.");
  out.push(`#${c.rank} of ${c.total} ads in this run by score (top ${Math.max(1, Math.round((c.rank / c.total) * 100))}%).`);
  if (ad.new) out.push("New since the last run: something they started testing this week.");
  out.push(competitorSearch(ad) ? "Found by searching for a named competitor." : "Found by a keyword or category search, not a named competitor.");
  return out;
}

function Creative({ ad }: { ad: AdItem }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-line bg-panel">
      {ad.video ? (
        <>
          <video controls preload="none" poster={ad.image || undefined} src={ad.video} className="aspect-video w-full bg-black" />
          <p className="px-4 py-2 text-[11px] text-muted">Video links from the ad libraries are signed and expire after a few days. If it doesn&apos;t play, open the library link.</p>
        </>
      ) : ad.image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={ad.image} alt="" referrerPolicy="no-referrer" className="max-h-[32rem] w-full bg-panel-2 object-contain" />
      ) : ad.format === "text" || ad.source === "apify_google" ? (
        <div className="p-5">
          <div className="rounded-xl border border-line bg-panel-2 p-4">
            <p className="text-[11px] text-muted">Sponsored · {ad.landing_domain || advName(ad)}</p>
            <p className="mt-1 text-lg font-medium text-rise">{ad.title || ad.hook || "(no headline from this source)"}</p>
            {ad.body && <p className="mt-1 text-sm text-muted">{ad.body}</p>}
          </div>
          <p className="mt-2 text-[11px] text-muted">A text ad, laid out the way search results show it.</p>
        </div>
      ) : (
        <div className="flex aspect-video items-center justify-center text-sm text-muted">No preview from this source.</div>
      )}
    </section>
  );
}

function MiniGrid({ profile, ads }: { profile: string; ads: AdItem[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {ads.slice(0, 12).map((a) => (
        <Link key={a.key} href={adHref(profile, a)} className="overflow-hidden rounded-xl border border-line hover:border-accent/60">
          {a.image ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={a.image} alt="" loading="lazy" referrerPolicy="no-referrer" className="aspect-video w-full object-cover" />
          ) : <div className="flex aspect-video items-center justify-center bg-panel-2 text-xs uppercase text-muted">{a.format}</div>}
          <div className="p-2 text-xs">
            <p className="line-clamp-2">{a.hook || a.title || "(no copy)"}</p>
            <p className="mt-1 text-muted">{days(a.days_running)} · {a.active ? "running" : "stopped"} · score {Math.round(a.ad_score)}</p>
          </div>
        </Link>
      ))}
    </div>
  );
}

function Mix({ title, rows, total, empty }: { title: string; rows: [string, number][]; total: number; empty?: string }) {
  const sorted = [...rows].sort((a, b) => b[1] - a[1]).slice(0, 6);
  return (
    <div>
      <p className="mb-1.5 font-semibold text-text">{title}</p>
      {sorted.length ? (
        <ul className="space-y-1">
          {sorted.map(([k, v]) => (
            <li key={k} className="flex items-center gap-2">
              <span className="w-28 truncate text-muted" title={k}>{k}</span>
              <span className="h-1.5 flex-1 rounded-full bg-panel-2"><span className="block h-full rounded-full bg-muted/60" style={{ width: `${(v / total) * 100}%` }} /></span>
              <span className="w-8 text-right">{v}</span>
            </li>
          ))}
        </ul>
      ) : <p className="text-muted">{empty ?? "—"}</p>}
    </div>
  );
}

function Num({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg bg-panel-2 px-2.5 py-2">
      <dt className="truncate text-[10px] uppercase tracking-wide text-muted">{label}</dt>
      <dd className={`truncate text-sm font-semibold ${tone ?? "text-text"}`} title={value}>{value}</dd>
    </div>
  );
}

function Row({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-muted">{label}</dt>
      <dd className="text-sm">{value}{note && <span className="block text-xs text-muted">{note}</span>}</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-panel p-4 text-sm">
      <h2 className="mb-2.5 font-semibold">{title}</h2>
      {children}
    </section>
  );
}
