import type { KeyInfo } from "@/lib/data";
import { PRICE, byTier, costDetail, priceOf, useLabel } from "@/lib/keys-ui";

// What each part of the app needs. Names match viral_scout/keys.py; a key missing here still shows in its group below.
const NEEDS: { what: string; free: string; keys: string[]; note: string }[] = [
  { what: "Viral videos: YouTube", free: "Hashtag feeds, watched channels and single post links work with no key (yt-dlp).",
    keys: ["YOUTUBE_API_KEY"], note: "Keyword search for Shorts and age-matched baselines. Free quota." },
  { what: "Viral videos: TikTok and Instagram", free: "Single post links work with no key.",
    keys: ["APIFY_TOKEN", "IG_GRAPH_TOKEN", "IG_GRAPH_USER_ID"], note: "TikTok search and watch list (Apify, paid per result); Instagram watch list and hashtag top posts (Graph API, free)." },
  { what: "Ads scout", free: "Lookup links to each ad library work with no key.",
    keys: ["APIFY_TOKEN", "META_AD_LIBRARY_TOKEN", "TIKTOK_RESEARCH_CLIENT_KEY", "TIKTOK_RESEARCH_CLIENT_SECRET"],
    note: "US ads through Apify actors (Facebook/Instagram, Google, TikTok top ads); the official Meta and TikTok APIs cover EU/EEA ads." },
  { what: "Search demand", free: "", keys: ["APIFY_TOKEN"], note: "Google Trends through Apify, about $0.005 per term." },
  { what: "Your performance", free: "CSV exports from each platform work with no key.",
    keys: ["IG_GRAPH_TOKEN", "YT_OAUTH_CLIENT_ID", "YT_OAUTH_CLIENT_SECRET", "YT_OAUTH_REFRESH_TOKEN", "META_ADS_TOKEN", "META_AD_ACCOUNT_ID", "TIKTOK_ADS_TOKEN", "TIKTOK_ADVERTISER_ID"],
    note: "Your own videos' and ads' private numbers: retention, CTR, CPA, ROAS." },
  { what: "Local competitors", free: "", keys: ["GOOGLE_PLACES_API_KEY"], note: "Nearby businesses in the niche and their public social channels." },
  { what: "Alerts", free: "", keys: ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"], note: "New outliers, fast risers and new long-running competitor ads." },
];

/** Read-only key catalog for the published site: what each key unlocks, its cost and how to get it. Never values. */
export default function KeyCatalog({ keys }: { keys: KeyInfo[] }) {
  const byName = new Map(keys.map((k) => [k.name, k]));
  const tiers = byTier(keys);
  return (
    <div className="mt-6 space-y-6">
      <div className="rounded-xl border border-line bg-panel-2 px-4 py-3 text-sm text-muted">
        This is the list of keys and what they unlock. Keys are set on your own PC: on the local dashboard&apos;s Setup page,
        or with <code className="text-text">python -m viral_scout keys set NAME</code>. The published site never sees them.
      </div>

      <section className="rounded-2xl border border-line bg-panel">
        <h2 className="border-b border-line px-4 py-3 font-semibold">What you need for what</h2>
        <div className="divide-y divide-line">
          {NEEDS.map((n) => (
            <div key={n.what} className="grid gap-2 px-4 py-3 md:grid-cols-[200px_1fr]">
              <div className="text-sm font-medium">{n.what}</div>
              <div className="space-y-1.5 text-sm">
                <div className="flex flex-wrap gap-1.5">
                  {n.keys.filter((k) => byName.has(k)).map((k) => {
                    const p = priceOf(byName.get(k)!);
                    return (
                      <a key={k} href={`#${k}`} title={p?.label} className={`rounded-md border px-2 py-0.5 font-mono text-[12px] hover:text-accent ${p?.cls ?? "border-line bg-panel-2 text-text"}`}>{k}</a>
                    );
                  })}
                </div>
                <p className="text-muted">{n.note}</p>
                {n.free && <p className="text-xs text-above">Without a key: {n.free}</p>}
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
        Cost:
        {Object.values(PRICE).map((p) => <span key={p.label} title={p.title} className={`rounded-full border px-2 py-0.5 text-[11px] ${p.cls}`}>{p.label}</span>)}
      </div>

      {tiers.map((t) => (
        <section key={t.id} className="space-y-3">
          <div>
            <h2 className="text-lg font-semibold">{t.title}</h2>
            <p className="text-sm text-muted">{t.text}</p>
          </div>
          {t.groups.map(({ group, keys: ks }) => (
            <div key={group} className="rounded-2xl border border-line bg-panel p-4">
              <h3 className="mb-3 font-semibold">{group}</h3>
              <div className="space-y-4">
                {ks.map((k) => (
                  <div key={k.name} id={k.name} className="scroll-mt-20">
                    <div className="flex flex-wrap items-center gap-2">
                      <code className="text-sm text-text">{k.name}</code>
                      {priceOf(k) && <span title={priceOf(k)!.title} className={`rounded-full border px-2 py-0.5 text-[11px] ${priceOf(k)!.cls}`}>{priceOf(k)!.label}</span>}
                      {k.uses?.map((u) => <span key={u} className="whitespace-nowrap rounded-full bg-panel-2 px-2 py-0.5 text-[11px] text-muted">{useLabel(u)}</span>)}
                      {k.secret === false && <span className="rounded-full bg-panel-2 px-2 py-0.5 text-[11px] text-muted">setting</span>}
                      {costDetail(k) && <span className="text-[11px] text-muted">{costDetail(k)}</span>}
                    </div>
                    <p className="mt-1 text-xs text-muted">{k.unlocks}</p>
                    <p className="mt-1 text-xs text-muted">
                      How: {k.get} {k.docs && <a href={k.docs} target="_blank" rel="noreferrer" className="text-rise hover:underline">docs ↗</a>}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
