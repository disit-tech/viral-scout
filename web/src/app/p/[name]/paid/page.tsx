import { notFound } from "next/navigation";
import { isLocal, loadProfile, profileNames } from "@/lib/data";
import { loadPaid, type Paid } from "@/lib/paid";
import PaidView from "@/components/PaidView";

export async function generateStaticParams() {
  return (await profileNames()).map((name) => ({ name }));
}

export async function generateMetadata({ params }: { params: Promise<{ name: string }> }) {
  return { title: `Paid ads · ${(await params).name}` };
}

const empty = (name: string): Paid => ({
  profile: name, cap: 0, platforms: ["meta", "google", "tiktok"], accounts: {}, brief: {}, snapshot: null,
  month: { spent: 0, running: 0, projected: 0, days_left: 0, check: "not pulled yet", rows: [] }, log: [],
});

export default async function PaidPage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const [paid, profile] = await Promise.all([loadPaid(name), loadProfile(name)]);
  if (!paid && !profile) notFound();
  return <PaidView paid={paid ?? empty(name)} local={isLocal} />;
}
