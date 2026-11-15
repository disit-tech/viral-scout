import Link from "next/link";
import { loadIndex } from "@/lib/data";
import { num } from "@/lib/format";
import BusinessNav from "@/components/BusinessNav";

/** Every page of one business: its name and the section tabs (Overview · Videos · Ads · Demand · Performance · Settings). */
export default async function BusinessLayout({ children, params }: { children: React.ReactNode; params: Promise<{ name: string }> }) {
  const { name } = await params;
  const entry = (await loadIndex()).profiles.find((p) => p.name === name);
  const title = entry?.display_name || name;
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div className="min-w-0">
          <Link href="/" className="text-xs text-muted hover:text-text">← All businesses</Link>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">
            {title}
            {title !== name && <span className="ml-2 align-middle font-mono text-xs font-normal text-muted">{name}</span>}
          </h1>
        </div>
      </div>
      <BusinessNav name={name} counts={{
        videos: entry ? num(entry.posts) : undefined,
        ads: entry?.ads ? num(entry.ads) : undefined,
        swipe: entry?.saved ? num(entry.saved) : undefined,
      }} />
      {children}
    </div>
  );
}
