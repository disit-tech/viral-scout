import { notFound } from "next/navigation";
import { marked } from "marked";
import { isLocal, loadProfile, profileNames } from "@/lib/data";
import { deObsidian } from "@/lib/format";
import SwipeBoard from "@/components/SwipeBoard";
import IdeasNotes from "@/components/IdeasNotes";

export async function generateStaticParams() {
  return (await profileNames()).map((name) => ({ name }));
}

export async function generateMetadata({ params }: { params: Promise<{ name: string }> }) {
  return { title: `Ideas & swipe file · ${(await params).name}` };
}

/** What to make next: saved references (videos and ads) on a board, then the AI idea notes. */
export default async function SwipePage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const profile = await loadProfile(name);
  if (!profile) notFound();
  const ideas = profile.ideas.map((i) => ({
    date: i.date, file: i.file, html: marked.parse(deObsidian(i.markdown), { async: false }) as string,
  }));
  return (
    <div className="space-y-10">
      <section>
        <h2 className="text-lg font-semibold">Swipe file</h2>
        <p className="mb-4 mt-0.5 max-w-3xl text-sm text-muted">
          Videos and competitor ads you saved, from idea to posted. Each card is a note in the Obsidian vault; moving it here
          changes its status there. Save more with the <b className="text-text">Save</b> button on a video or an ad.
        </p>
        <SwipeBoard notes={profile.swipe} profile={profile.name} local={isLocal} />
      </section>
      <section id="ideas" className="scroll-mt-20">
        <h2 className="text-lg font-semibold">Idea notes</h2>
        <p className="mb-4 mt-0.5 max-w-3xl text-sm text-muted">
          AI breakdowns of the top posts (format, hook, why people watch to the end) and ideas adapted to this business,
          written by the <code className="text-text">/viral-scout</code> skill in Claude Code.
        </p>
        <IdeasNotes ideas={ideas} profile={profile.name} />
      </section>
    </div>
  );
}
