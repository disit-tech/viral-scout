import Link from "next/link";
import { adsNames, isLocal, loadAds, profileNames } from "@/lib/data";
import SetupNeeds from "@/components/SetupNeeds";
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
  const ads = await loadAds(name);

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="max-w-3xl text-sm text-muted">
            The ads that keep running in this niche: competitors and the category. Long-running ads and ads with
            many variants are the likely winners. Scores are <b className="text-text">proxies</b> (days running,
            variants, reach where published), not spend or ROAS.
          </p>
        </div>
        {ads && (
          <div className="text-right text-xs text-muted">
            <div>Last ads run {when(ads.date)}</div>
            <Link href={`/p/${name}/settings#ads`} className="hover:text-text">Edit competitors and searches →</Link>
            <div>{ads.ads.length} ads · {ads.advertisers.length} advertisers · {(ads.countries ?? []).join(", ")}</div>
          </div>
        )}
      </div>
      {ads ? (
        <AdsBoard data={ads} profile={name} />
      ) : (
        <div className="space-y-3">
          {isLocal && <SetupNeeds profile={name} sections={["ads"]} title="Ads scout: to set up" showDone />}
          <div className="rounded-xl border border-dashed border-line p-8 text-center text-muted">
            No ads run yet. Add competitors or keyword searches in <Link href={`/p/${name}/settings#ads`} className="text-rise underline">Settings → Ads</Link>, then run{" "}
            <code className="text-text">python -m viral_scout ads {name}</code>. Sources without keys are listed as skipped;
            see the Setup page and docs/ads-scout.md.
          </div>
        </div>
      )}
    </div>
  );
}
