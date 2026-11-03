import Link from "next/link";
import { loadIndex } from "@/lib/data";
import { num, times, when } from "@/lib/format";

export default async function Home() {
  const { exported, profiles } = await loadIndex();
  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Your businesses</h1>
          <p className="text-sm text-muted">What&apos;s going viral in each niche, and what to film next.</p>
        </div>
        <p className="text-xs text-muted">Data exported {when(exported)}</p>
      </div>

      {profiles.length === 0 ? (
        <div className="rounded-xl border border-dashed border-line p-10 text-center text-muted">
          No data yet. Run <code className="text-text">python -m viral_scout run &lt;profile&gt;</code>, then{" "}
          <code className="text-text">python -m viral_scout export</code>.
        </div>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {profiles.map((p) => (
            <Link key={p.name} href={`/p/${p.name}`}
              className="group flex flex-col overflow-hidden rounded-2xl border border-line bg-panel transition hover:-translate-y-0.5 hover:border-accent/60">
              <div className="grid h-32 grid-cols-4 gap-px bg-line">
                {[0, 1, 2, 3].map((i) => {
                  const t = p.top[i];
                  return t?.thumbnail ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img key={i} src={t.thumbnail} alt="" className="h-full w-full object-cover opacity-90 group-hover:opacity-100" />
                  ) : (
                    <div key={i} className="bg-panel-2" />
                  );
                })}
              </div>
              <div className="flex flex-1 flex-col gap-3 p-4">
                <div className="flex items-baseline justify-between gap-2">
                  <h2 className="text-lg font-semibold">{p.name}</h2>
                  <span className="text-xs text-muted">{when(p.date)}</span>
                </div>
                <p className="line-clamp-2 text-sm text-muted">{p.business || "No business description in the profile."}</p>
                <div className="mt-auto grid grid-cols-4 gap-2 text-center">
                  <Stat label="posts" value={num(p.posts)} />
                  <Stat label="outliers" value={num(p.outliers)} tone="text-viral" />
                  <Stat label="🔥 mega" value={num(p.mega)} tone="text-mega" />
                  <Stat label="saved" value={num(p.saved)} />
                </div>
                {p.top[0] && (
                  <p className="truncate text-xs text-muted">
                    Top: <span className="text-text">{p.top[0].title}</span> · {times(p.top[0].outlier)} usual
                  </p>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, tone = "text-text" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg bg-panel-2 px-2 py-1.5">
      <div className={`text-base font-semibold ${tone}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
    </div>
  );
}
