import Link from "next/link";
import { notFound } from "next/navigation";
import { marked } from "marked";
import { isLocal, loadProfile, profileNames } from "@/lib/data";
import { aiMentions, embedUrl, whyNotable } from "@/lib/analysis";
import { age, deObsidian, num, tier, times } from "@/lib/format";
import GrowthChart from "@/components/GrowthChart";
import PostActions from "@/components/PostActions";

export async function generateStaticParams() {
  const out: { name: string; id: string }[] = [];
  for (const name of await profileNames()) {
    const p = await loadProfile(name);
    for (const i of p?.items ?? []) out.push({ name, id: encodeURIComponent(i.id) });
  }
  return out;
}

export async function generateMetadata({ params }: { params: Promise<{ name: string; id: string }> }) {
  const { name, id } = await params;
  const p = await loadProfile(name);
  const i = p?.items.find((x) => x.id === decodeURIComponent(id));
  return { title: i ? i.title.slice(0, 60) : "Video" };
}

const PLATFORM: Record<string, string> = { youtube: "YouTube", instagram: "Instagram", tiktok: "TikTok" };

export default async function VideoPage({ params }: { params: Promise<{ name: string; id: string }> }) {
  const { name, id } = await params;
  const profile = await loadProfile(name);
  const item = profile?.items.find((x) => x.id === decodeURIComponent(id));
  if (!profile || !item) notFound();

  const t = tier(item.outlier);
  const embed = embedUrl(item);
  const reasons = whyNotable(item);
  const ai = aiMentions(item, profile.ideas).map((m) => ({
    date: m.date, html: m.lines.map((l) => marked.parse(deObsidian(l), { async: false }) as string).join(""),
  }));
  const vertical = (item.duration ?? 61) <= 180 || item.platform !== "youtube";

  return (
    <div>
      <Link href={`/p/${name}`} className="text-xs text-muted hover:text-text">← {name}</Link>

      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 max-w-4xl">
          <h1 className="text-xl font-bold leading-snug sm:text-2xl">{item.title || item.id}</h1>
          <p className="mt-1 text-sm text-muted">
            <a href={item.channel_url || undefined} target="_blank" rel="noreferrer" className="hover:text-text">{item.channel}</a>
            {item.followers ? ` · ${num(item.followers)} followers` : ""} · {PLATFORM[item.platform] ?? item.platform}
            {item.published ? ` · posted ${new Date(item.published).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })} (${age(item.published)} ago)` : ""}
            {item.duration ? ` · ${Math.round(item.duration)} s` : ""}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
            {t && <Badge cls={t === "mega" ? "bg-mega text-ink" : t === "viral" ? "bg-viral text-ink" : "bg-above text-ink"}>{t === "mega" ? "🔥 mega" : t === "viral" ? "⚡ viral" : "↑ above"} {times(item.outlier)}</Badge>}
            {item.new && <Badge cls="bg-rise text-ink">new this run</Badge>}
            {item.emerging && <Badge cls="bg-panel-2">🌱 emerging creator</Badge>}
            {item.own && <Badge cls="bg-panel-2">your post</Badge>}
            {item.saved && <Badge cls="bg-above text-ink">in swipe file</Badge>}
            {item.tracked && <Badge cls="bg-panel-2">tracked</Badge>}
            {item.early && <Badge cls="bg-panel-2">⏳ under 6 h</Badge>}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <a href={item.url} target="_blank" rel="noreferrer" className="rounded-lg border border-line px-3 py-1.5 text-sm hover:border-accent">Open on {PLATFORM[item.platform] ?? "site"} ↗</a>
          <PostActions item={item} profile={name} local={isLocal} />
        </div>
      </div>

      <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(280px,380px)_1fr]">
        {/* Left: the video */}
        <div className="space-y-3">
          <div className={`overflow-hidden rounded-2xl border border-line bg-panel-2 ${vertical ? "aspect-[9/16]" : "aspect-video"}`}>
            {embed ? (
              <iframe src={embed} title={item.title} className="h-full w-full" loading="lazy"
                allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowFullScreen />
            ) : item.thumbnail ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={item.thumbnail} alt="" className="h-full w-full object-cover" />
            ) : null}
          </div>
          <p className="text-xs text-muted">Played through the platform&apos;s official embed. Study the format; never reuse the footage.</p>
        </div>

        {/* Right: the analysis */}
        <div className="min-w-0 space-y-5">
          {reasons.length > 0 && (
            <Section title="Why it's worth studying">
              <ul className="list-disc space-y-1.5 pl-5">{reasons.map((r) => <li key={r}>{r}</li>)}</ul>
            </Section>
          )}

          <Section title="Numbers">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Metric label="Views" value={num(item.views)} />
              <Metric label="Likes" value={num(item.likes)} />
              <Metric label="Comments" value={num(item.comments)} />
              <Metric label="Engagement" value={item.engagement != null ? `${(item.engagement * 100).toFixed(1)}%` : "—"} hint="(likes + comments) ÷ views" />
              <Metric label="Per day" value={num(item.per_day)} hint="views ÷ age" />
              <Metric label="Rise / day" value={item.rise_per_day ? `+${num(item.rise_per_day)}` : "—"} hint="growth since the last run" />
              <Metric label="× usual" value={times(item.outlier)} hint="vs the creator's median post" />
              <Metric label="Percentile" value={item.creator_pct != null ? `${Math.round(item.creator_pct)}%` : "—"} hint="of the creator's recent posts it beats" />
              <Metric label="× niche" value={times(item.vs_topic)} hint="vs the run's median views/day" />
              <Metric label="× pace" value={times(item.vs_pace)} hint="vs the creator's usual views/day (YouTube API)" />
              <Metric label="Followers" value={num(item.followers)} />
              <Metric label="Words / min" value={item.wpm ? String(item.wpm) : "—"} hint="speaking pace" />
            </div>
          </Section>

          {item.history.length > 1 && (
            <Section title="Growth across runs">
              <GrowthChart points={item.history} />
            </Section>
          )}

          {(item.hook || item.cta) && (
            <Section title="Script structure">
              {item.hook && <Quote label="Hook (first 4 seconds)">{item.hook}</Quote>}
              {item.cta && <Quote label="Ending / call to action (last 5 seconds)">{item.cta}</Quote>}
              <p className="mt-2 text-xs text-muted">From the video&apos;s own captions{item.platform !== "youtube" ? " or a local Whisper transcript" : ""}.</p>
            </Section>
          )}

          {ai.length > 0 && (
            <Section title="AI breakdown (from the ideas notes)">
              {ai.map((a) => (
                <div key={a.date} className="mb-3">
                  <p className="mb-1 text-xs text-muted">{a.date}</p>
                  <div className="prose-dark text-sm" dangerouslySetInnerHTML={{ __html: a.html }} />
                </div>
              ))}
            </Section>
          )}

          {((item.questions?.length ?? 0) > 0 || (item.top_comments?.length ?? 0) > 0) && (
            <Section title="What viewers say">
              {item.questions && item.questions.length > 0 && (
                <>
                  <p className="mb-1 text-xs uppercase tracking-wide text-muted">Questions (ideas your audience already asked for)</p>
                  <ul className="mb-3 list-disc space-y-1 pl-5">{item.questions.map((q, n) => <li key={n}>{q}</li>)}</ul>
                </>
              )}
              {item.top_comments && item.top_comments.length > 0 && (
                <>
                  <p className="mb-1 text-xs uppercase tracking-wide text-muted">Top comments</p>
                  <ul className="space-y-1.5">{item.top_comments.map((c, n) => (
                    <li key={n} className="rounded-lg bg-panel-2 px-3 py-2"><span className="text-muted">♥ {num(c.likes)}</span> · {c.text}</li>
                  ))}</ul>
                </>
              )}
            </Section>
          )}

          {item.transcript && (
            <Section title="Transcript">
              <p className="max-h-96 overflow-auto whitespace-pre-line text-sm leading-relaxed text-text/90">{item.transcript}</p>
            </Section>
          )}

          {item.description && (
            <Section title="Caption / description">
              <p className="max-h-72 overflow-auto whitespace-pre-line text-sm text-muted">{item.description}</p>
            </Section>
          )}

          <p className="text-xs text-muted">Found by: {item.found_by.join(", ")} · ID <code>{item.id}</code></p>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-panel p-4 text-sm">
      <h2 className="mb-2.5 font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg bg-panel-2 px-2.5 py-2" title={hint}>
      <div className="text-base font-semibold">{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
      {hint && <div className="mt-0.5 text-[10px] leading-tight text-muted/80">{hint}</div>}
    </div>
  );
}

function Quote({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-2">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <blockquote className="mt-1 border-l-2 border-accent pl-3 italic">“{children}”</blockquote>
    </div>
  );
}

function Badge({ cls, children }: { cls: string; children: React.ReactNode }) {
  return <span className={`rounded-full px-2 py-0.5 font-semibold ${cls}`}>{children}</span>;
}
