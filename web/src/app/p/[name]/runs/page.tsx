import { notFound } from "next/navigation";
import { isLocal, loadAds, loadProfile, profileNames } from "@/lib/data";
import { geoLabel, loadDemand } from "@/lib/demand";
import RunsView from "@/components/RunsView";

export async function generateStaticParams() {
  return (await profileNames()).map((name) => ({ name }));
}

export async function generateMetadata({ params }: { params: Promise<{ name: string }> }) {
  return { title: `Runs · ${(await params).name}` };
}

/** What each run did (videos, ads, search demand). Only the small run summaries go to the client. */
export default async function RunsPage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const [profile, ads, demand] = await Promise.all([loadProfile(name), loadAds(name), loadDemand(name)]);
  if (!profile && !ads && !demand) notFound();
  return (
    <RunsView
      profile={profile ? { ...profile, items: [], ideas: [], swipe: [], checks: [] } : null}
      ads={ads ? {
        date: ads.date, ads: ads.ads.length, advertisers: ads.advertisers.length, coverage: ads.coverage, skipped: ads.skipped,
        errors: ads.errors, usage: ads.usage, budget: ads.budget,
      } : null}
      demand={demand ? {
        date: demand.date, fetched: demand.fetched, terms: demand.terms.length, geo: geoLabel(demand.geo),
        skipped: (demand as { skipped?: string[] }).skipped ?? [], errors: (demand as { errors?: string[] }).errors ?? [],
        usage: (demand as { usage?: Record<string, number> }).usage,
      } : null}
      local={isLocal} />
  );
}
