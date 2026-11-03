import { notFound } from "next/navigation";
import { isLocal, loadProfile, profileNames } from "@/lib/data";
import { loadPerf, perfNames, type Perf } from "@/lib/perf";
import PerformanceView from "@/components/perf/PerformanceView";

export async function generateStaticParams() {
  const names = new Set([...(await profileNames()), ...(await perfNames())]);
  return Array.from(names).map((name) => ({ name }));
}

export async function generateMetadata({ params }: { params: Promise<{ name: string }> }) {
  return { title: `Your performance · ${(await params).name}` };
}

function empty(name: string): Perf {
  return {
    name, date: new Date().toISOString(), goal: "sales", days: 28, economics: {}, unit_economics: {},
    sources: { pulled: {}, skipped: [], errors: [], stored: {} }, records: [],
    medians: { organic: { all: {}, n: {}, bands: {} }, paid: { all: {}, n: {}, bands: {} } }, account: {},
    priorities: { organic: [], paid: [], goal: "sales" }, kpi_defs: [], groups: {}, platform_differences: [],
  };
}

export default async function PerformancePage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const perf = await loadPerf(name);
  if (!perf && !(await loadProfile(name))) notFound();
  return <PerformanceView perf={perf ?? empty(name)} local={isLocal} />;
}
