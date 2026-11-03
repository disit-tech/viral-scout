import Link from "next/link";
import { notFound } from "next/navigation";
import { docSlugs, loadDoc } from "@/lib/docs";

export async function generateStaticParams() {
  return [{ slug: [] }, ...(await docSlugs()).map((s) => ({ slug: [s] }))];
}

const ORDER = ["readme", "marketing-workflow", "performance", "originality-and-duplicate-detection", "dashboard", "how-it-works",
  "setup", "profiles", "similar-tools", "references"];

export async function generateMetadata({ params }: { params: Promise<{ slug?: string[] }> }) {
  const s = (await params).slug?.[0] ?? "readme";
  return { title: (await loadDoc(s))?.title ?? "Docs" };
}

export default async function DocsPage({ params }: { params: Promise<{ slug?: string[] }> }) {
  const slug = (await params).slug?.[0] ?? "readme";
  const doc = await loadDoc(slug);
  if (!doc) notFound();
  const slugs = (await docSlugs()).sort((a, b) => (ORDER.indexOf(a) + 99) % 99 - (ORDER.indexOf(b) + 99) % 99);
  const titles = await Promise.all(slugs.map(async (s) => [s, (await loadDoc(s))?.title ?? s] as const));
  return (
    <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
      <aside className="lg:sticky lg:top-20 lg:self-start">
        <p className="mb-2 text-xs uppercase tracking-wide text-muted">Docs</p>
        <nav className="flex gap-1 overflow-x-auto lg:flex-col">
          {titles.map(([s, t]) => (
            <Link key={s} href={`/docs/${s}`}
              className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm lg:whitespace-normal ${s === slug ? "bg-panel-2 text-text" : "text-muted hover:text-text"}`}>
              {s === "readme" ? "Overview" : t}
            </Link>
          ))}
        </nav>
      </aside>
      <article className="prose-dark min-w-0 rounded-2xl border border-line bg-panel p-5 sm:p-8"
        dangerouslySetInnerHTML={{ __html: doc.html }} />
    </div>
  );
}
