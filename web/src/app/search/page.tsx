import { isLocal, loadProfile, profileNames } from "@/lib/data";
import SearchBox, { type Hit } from "@/components/SearchBox";

export const metadata = { title: "Search" };

/** Published site: search the exported latest runs in the browser. Local: the full history via the CLI. */
export default async function SearchPage() {
  const corpus: Hit[] = [];
  if (!isLocal) {
    for (const name of await profileNames()) {
      const p = await loadProfile(name);
      for (const i of p?.items ?? []) {
        if (i.dismissed) continue;
        corpus.push({ profile: name, platform: i.platform, id: i.id, url: i.url, title: i.title, channel: i.channel,
          views: i.views, likes: i.likes, hook: i.hook ?? "", cta: i.cta ?? "", saved: i.saved,
          snippet: (i.transcript || i.description || "").slice(0, 600), score: 0 });
      }
    }
  }
  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Search</h1>
      <p className="mt-1 text-sm text-muted">
        {isLocal
          ? "Everything ever collected for every business: titles, hooks, endings, transcripts, captions, creators."
          : "Posts from the latest runs: titles, hooks, endings, transcripts. (The local dashboard searches the full history.)"}
      </p>
      <SearchBox local={isLocal} corpus={corpus} />
    </div>
  );
}
