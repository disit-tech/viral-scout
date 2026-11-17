import Link from "next/link";
import { loadIndex } from "@/lib/data";
import { when } from "@/lib/format";
import BusinessGrid from "@/components/BusinessGrid";

export default async function Home() {
  const { exported, profiles } = await loadIndex();
  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Your businesses</h1>
          <p className="text-sm text-muted">What&apos;s going viral in each niche, and what to film next.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs text-muted">Data exported {when(exported)}</span>
          <Link href="/new?mode=research" className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted hover:border-accent/60 hover:text-text"
            title="A one-off look at a topic: a research-… profile with reports in the repo">Quick research</Link>
          <Link href="/new" className="rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-ink hover:opacity-90">+ New business</Link>
        </div>
      </div>

      {profiles.length === 0 ? (
        <div className="rounded-xl border border-dashed border-line p-10 text-center text-muted">
          No business yet. <Link href="/new" className="text-rise underline">+ New business</Link> describes it and starts the first run;
          or run <code className="text-text">python -m viral_scout run &lt;profile&gt;</code>, then{" "}
          <code className="text-text">python -m viral_scout export</code>.
        </div>
      ) : (
        <BusinessGrid profiles={profiles} />
      )}
    </div>
  );
}
