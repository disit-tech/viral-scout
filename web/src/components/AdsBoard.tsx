"use client";

import { useMemo, useState } from "react";
import type { AdItem, AdsData } from "@/lib/types";
import { num } from "@/lib/format";

const OFFER: Record<string, string> = {
  price: "price shown", free_trial: "free trial / lesson", free_quote: "free quote", free: "\"free\" claim",
  discount: "discount", guarantee: "guarantee", financing: "financing", incentive: "tax credit / rebate",
  urgency: "urgency", social_proof: "social proof",
};
const SOURCE: Record<string, string> = {
  meta_api: "Meta API", tiktok_api: "TikTok API", apify_meta: "Meta · Apify",
  apify_tiktok_top: "TikTok Top Ads", apify_google: "Google · Apify",
};

type Sort = "score" | "days" | "variants" | "newest";

export default function AdsBoard({ data }: { data: AdsData }) {
  const [advertiser, setAdvertiser] = useState("all");
  const [format, setFormat] = useState("all");
  const [offer, setOffer] = useState("all");
  const [activeOnly, setActiveOnly] = useState(false);
  const [sort, setSort] = useState<Sort>("score");
  const [q, setQ] = useState("");

  const advertisers = useMemo(() => data.advertisers.map((a) => a.advertiser), [data.advertisers]);
  const formats = useMemo(() => Array.from(new Set(data.ads.map((a) => a.format || "unknown"))).sort(), [data.ads]);
  const offers = useMemo(() => data.offers.map((o) => o.offer), [data.offers]);

  const list = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const out = data.ads
      .filter((a) => advertiser === "all" || a.advertiser === advertiser)
      .filter((a) => format === "all" || (a.format || "unknown") === format)
      .filter((a) => offer === "all" || a.offers.includes(offer))
      .filter((a) => !activeOnly || a.active)
      .filter((a) => !needle || `${a.advertiser} ${a.hook} ${a.title ?? ""} ${a.body ?? ""} ${a.landing_domain ?? ""}`
        .toLowerCase().includes(needle));
    const by: Record<Sort, (a: AdItem) => number> = {
      score: (a) => -a.ad_score,
      days: (a) => -(a.days_running ?? -1),
      variants: (a) => -a.variants,
      newest: (a) => -(a.start ? new Date(a.start).getTime() : 0),
    };
    return [...out].sort((x, y) => by[sort](x) - by[sort](y));
  }, [data.ads, advertiser, format, offer, activeOnly, sort, q]);

  const longRunners = data.ads.filter((a) => (a.days_running ?? 0) >= 30).length;

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-4">
        <Stat label="ads" value={num(data.ads.length)} />
        <Stat label="still running" value={num(data.ads.filter((a) => a.active).length)} tone="text-above" />
        <Stat label="🏆 30d+ long-runners" value={num(longRunners)} tone="text-viral" />
        <Stat label="advertisers" value={num(data.advertisers.length)} />
      </div>

      {data.advertisers.length > 0 && (
        <section className="overflow-x-auto rounded-2xl border border-line bg-panel">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="bg-panel-2 text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-3 py-2">Advertiser</th><th className="px-3 py-2">Ads</th><th className="px-3 py-2">Running</th>
                <th className="px-3 py-2">Longest</th><th className="px-3 py-2">30d+</th><th className="px-3 py-2">Max variants</th>
                <th className="px-3 py-2">Top offers</th><th className="px-3 py-2">New (14 d)</th>
              </tr>
            </thead>
            <tbody>
              {data.advertisers.slice(0, 30).map((r) => (
                <tr key={r.advertiser} className="cursor-pointer border-t border-line hover:bg-panel-2"
                  onClick={() => setAdvertiser(advertiser === r.advertiser ? "all" : r.advertiser)}>
                  <td className={`px-3 py-2 font-medium ${advertiser === r.advertiser ? "text-accent" : ""}`}>{r.advertiser}</td>
                  <td className="px-3 py-2">{r.ads}</td>
                  <td className="px-3 py-2 text-above">{r.active}</td>
                  <td className="px-3 py-2">{r.longest_days !== null ? `${Math.round(r.longest_days)} d` : "—"}</td>
                  <td className="px-3 py-2 text-viral">{r.long_runners || "—"}</td>
                  <td className="px-3 py-2">{r.max_variants}</td>
                  <td className="px-3 py-2 text-xs text-muted">{Object.keys(r.offers).map((o) => OFFER[o] ?? o).join(", ") || "—"}</td>
                  <td className="px-3 py-2">{r.launched_last_14d}{r.launch_burst ? " 🚀" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search hook, copy, domain…"
          className="w-60 rounded-lg border border-line bg-panel px-3 py-1.5 text-sm outline-none focus:border-accent" />
        <Select value={advertiser} onChange={setAdvertiser} all="All advertisers" options={advertisers} />
        <Select value={format} onChange={setFormat} all="All formats" options={formats} />
        <Select value={offer} onChange={setOffer} all="All offers" options={offers} labels={OFFER} />
        <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}
          className="rounded-lg border border-line bg-panel px-2 py-1.5 text-sm">
          <option value="score">Sort: ad score</option>
          <option value="days">Sort: days running</option>
          <option value="variants">Sort: variants</option>
          <option value="newest">Sort: newest</option>
        </select>
        <label className="flex items-center gap-1.5 text-sm text-muted">
          <input type="checkbox" checked={activeOnly} onChange={(e) => setActiveOnly(e.target.checked)} /> Still running
        </label>
        <span className="text-xs text-muted">{list.length} shown</span>
      </div>

      {list.length === 0 ? (
        <div className="rounded-xl border border-dashed border-line p-8 text-center text-muted">
          {data.ads.length ? "Nothing matches the filters." : "No ads collected in the last run. See the sources below: each skipped source says which key unlocks it."}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {list.map((a) => <AdCard key={a.key} ad={a} />)}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {data.offers.length > 0 && (
          <Panel title="Offers that keep running">
            <ul className="space-y-1">
              {data.offers.map((o) => (
                <li key={o.offer} className="flex justify-between gap-2">
                  <span>{OFFER[o.offer] ?? o.offer}</span>
                  <span><b className="text-text">{o.ads}</b> ads · <span className="text-viral">{o.long_runners}</span> in 30d+ ads</span>
                </li>
              ))}
            </ul>
          </Panel>
        )}
        {data.coverage.length > 0 && (
          <Panel title="Coverage">
            <ul className="list-disc space-y-1.5 pl-5">{data.coverage.map((c) => <li key={c}>{c}</li>)}</ul>
          </Panel>
        )}
        <Panel title="Skipped sources">
          {data.skipped.length ? <ul className="list-disc space-y-1.5 pl-5">{data.skipped.map((s) => <li key={s}>{s}</li>)}</ul> : <p>Everything ran.</p>}
        </Panel>
        {data.lookup.length > 0 && (
          <Panel title="Look them up yourself">
            <ul className="space-y-1.5">
              {data.lookup.map((r) => (
                <li key={`${r.kind}:${r.label}`}>
                  <span className="text-text">{r.label}</span> <span className="text-xs">({r.kind})</span>:{" "}
                  {Object.entries(r.links).map(([k, v], i) => (
                    <span key={k}>{i > 0 && " · "}<a href={v} target="_blank" rel="noreferrer" className="text-rise underline">{k}</a></span>
                  ))}
                </li>
              ))}
            </ul>
          </Panel>
        )}
        {(data.errors.length > 0 || (data.usage && Object.keys(data.usage).length > 0)) && (
          <Panel title="Usage and errors">
            {data.usage && <p className="text-xs">{Object.entries(data.usage).map(([k, v]) => `${k.replace(/_/g, " ")}: ${num(v)}`).join(" · ") || "Nothing counted."}</p>}
            {data.budget?.map((b) => <p key={b} className="mt-2 text-viral">⚠️ {b}</p>)}
            {data.errors.length > 0 && (
              <ul className="mt-2 max-h-48 space-y-1 overflow-auto font-mono text-[11px]">{data.errors.slice(0, 30).map((e, i) => <li key={i} className="break-all">{e}</li>)}</ul>
            )}
          </Panel>
        )}
      </div>
      <p className="text-xs text-muted">
        Borrow angles (the problem, the offer type, the format), never creatives, copy or trademarks. Every claim in your
        own ads must be true and provable.
      </p>
    </div>
  );
}

function AdCard({ ad }: { ad: AdItem }) {
  const [open, setOpen] = useState(false);
  const long = (ad.days_running ?? 0) >= 30;
  return (
    <article className={`flex flex-col overflow-hidden rounded-2xl border bg-panel ${long ? "border-viral/40" : "border-line"} ${ad.active ? "" : "opacity-70"}`}>
      <a href={ad.url || undefined} target="_blank" rel="noreferrer" className="relative block aspect-video bg-panel-2" title="Open in the ad library">
        {ad.image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={ad.image} alt="" loading="lazy" referrerPolicy="no-referrer" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-1 px-4 text-center text-sm text-muted">
            <span className="text-xs uppercase tracking-wide">{ad.format || "ad"}</span>
            <span>No preview from this source. Open in the library ↗</span>
          </div>
        )}
        <div className="absolute left-2 top-2 flex flex-wrap gap-1.5">
          <span className="rounded-full border border-accent bg-accent px-2 py-0.5 text-xs font-semibold text-ink">{Math.round(ad.ad_score)}</span>
          {ad.new && <span className="rounded-full border border-rise bg-rise px-2 py-0.5 text-xs font-semibold text-ink">new</span>}
          <span className={`rounded-full border px-2 py-0.5 text-xs ${ad.active ? "border-above bg-above text-ink" : "border-line bg-ink/90 text-muted"}`}>
            {ad.active ? "running" : "stopped"}
          </span>
        </div>
        <span className="absolute bottom-2 right-2 rounded bg-ink/80 px-1.5 py-0.5 text-[11px] text-muted">{SOURCE[ad.source] ?? ad.source} · {ad.format}</span>
      </a>
      <div className="flex flex-1 flex-col gap-2.5 p-3.5">
        <div className="flex items-start gap-2">
          <p className="line-clamp-3 flex-1 font-medium leading-snug">{ad.hook || ad.title || <span className="text-muted">No ad copy from this source</span>}</p>
          {ad.url && <a href={ad.url} target="_blank" rel="noreferrer" className="text-muted hover:text-text" title="Open in the ad library">↗</a>}
        </div>
        <p className="truncate text-sm text-muted">{ad.advertiser || "Unknown advertiser"}{ad.landing_domain ? ` · ${ad.landing_domain}` : ""}</p>
        <dl className="grid grid-cols-3 gap-1.5 text-center">
          <Metric label="days running" value={ad.days_running !== null ? `${Math.round(ad.days_running)}` : "—"} tone={long ? "text-viral" : undefined} />
          <Metric label="variants" value={`${ad.variants}`} tone={ad.variants >= 3 ? "text-mega" : undefined} />
          <Metric label={ad.reach_label || "reach"} value={num(ad.reach)} />
        </dl>
        {ad.labels.length > 0 && (
          <div className="flex flex-wrap gap-1">{ad.labels.map((l) => <span key={l} className="rounded-full bg-panel-2 px-2 py-0.5 text-[11px]">{l}</span>)}</div>
        )}
        {ad.offers.length > 0 && (
          <p className="text-xs"><span className="text-muted">Offer:</span> {ad.offers.map((o) => OFFER[o] ?? o).join(", ")}
            {ad.offer_text && ad.offer_text.length > 0 && <span className="text-muted"> ({ad.offer_text.slice(0, 3).join("; ")})</span>}</p>
        )}
        <p className="text-xs text-muted">
          {ad.cta && <><span>CTA:</span> <span className="text-text">{ad.cta}</span> · </>}
          {ad.platforms.length > 0 ? ad.platforms.join(", ") : "platforms unknown"}
          {ad.start && <> · since {ad.start.slice(0, 10)}</>}
        </p>
        {ad.body && ad.body !== ad.hook && (
          <button onClick={() => setOpen(!open)} className="mt-auto text-left text-xs text-rise hover:underline">
            {open ? "Hide ad copy" : "Show ad copy"}
          </button>
        )}
        {open && <p className="whitespace-pre-line text-xs text-muted">{ad.body}</p>}
      </div>
    </article>
  );
}

function Select({ value, onChange, all, options, labels }: {
  value: string; onChange: (v: string) => void; all: string; options: string[]; labels?: Record<string, string>;
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="max-w-48 rounded-lg border border-line bg-panel px-2 py-1.5 text-sm">
      <option value="all">{all}</option>
      {options.map((o) => <option key={o} value={o}>{labels?.[o] ?? o}</option>)}
    </select>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg bg-panel-2 px-1 py-1.5">
      <dt className="truncate text-[10px] uppercase tracking-wide text-muted">{label}</dt>
      <dd className={`text-sm font-semibold ${tone ?? "text-text"}`}>{value}</dd>
    </div>
  );
}

function Stat({ label, value, tone = "text-text" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-xl border border-line bg-panel px-3 py-2">
      <div className={`text-xl font-semibold ${tone}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-panel p-4 text-sm text-muted">
      <h3 className="mb-2 font-semibold text-text">{title}</h3>
      {children}
    </section>
  );
}
