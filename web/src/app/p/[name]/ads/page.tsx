import Link from "next/link";
import { adsNames, loadAds, loadProfile, profileNames } from "@/lib/data";
import { when } from "@/lib/format";
import AdsBoard from "@/components/AdsBoard";

export async function generateStaticParams() {
  const names = new Set([...(await profileNames()), ...(await adsNames())]);
  return [...names].map((name) => ({ name }));
}

export async function generateMetadata({ params }: { params: Promise<{ name: string }> }) {
  return { title: `Ads · ${(await params).name}` };
}

export default async function AdsPage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const [ads, profile] = await Promise.all([loadAds(name), loadProfile(name)]);
  const business = ads?.business || profile?.business || "";

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link href={profile ? `/p/${name}` : "/"} className="text-xs text-muted hover:text-text">
            ← {profile ? `${name}: viral posts` : "All businesses"}
          </Link>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">{name} · Ads</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            The ads that keep running in this niche: competitors and the category. Long-running ads and ads with
            many variants are the likely winners. Scores are <b className="text-text">proxies</b> (days running,
            variants, reach where published), not spend or ROAS.
          </p>
          {business && <p className="mt-1 max-w-3xl text-xs text-muted line-clamp-2">{business}</p>}
        </div>
        {ads && (
          <div className="text-right text-xs text-muted">
            <div>Last ads run {when(ads.date)}</div>
            <div>{ads.ads.length} ads · {ads.advertisers.length} advertisers · {(ads.countries ?? []).join(", ")}</div>
          </div>
        )}
      </div>
      {ads ? (
        <AdsBoard data={ads} />
      ) : (
        <div className="rounded-xl border border-dashed border-line p-8 text-center text-muted">
          No ads run yet. Add an <code className="text-text">ads:</code> block to the profile, then run{" "}
          <code className="text-text">python -m viral_scout ads {name}</code>. Sources without keys are listed as skipped;
          see the Setup page and docs/ads-scout.md.
        </div>
      )}
    </div>
  );
}
