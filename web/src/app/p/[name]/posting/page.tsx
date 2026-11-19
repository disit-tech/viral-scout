import { notFound } from "next/navigation";
import { isLocal, loadProfile, profileNames } from "@/lib/data";
import PostingView from "@/components/PostingView";

export async function generateStaticParams() {
  return (await profileNames()).map((name) => ({ name }));
}

export async function generateMetadata({ params }: { params: Promise<{ name: string }> }) {
  return { title: `Posting · ${(await params).name}` };
}

export const dynamic = "force-dynamic";

export default async function PostingPage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  if (!(await loadProfile(name))) notFound();
  if (!isLocal) {
    return (
      <div className="rounded-xl border border-dashed border-line p-8 text-center text-sm text-muted">
        Posting is managed on the local dashboard (<code className="text-text">cd web &amp;&amp; npm run dev</code>): the keys and the
        posting tasks live on your PC.
      </div>
    );
  }
  return <PostingView profile={name} />;
}
