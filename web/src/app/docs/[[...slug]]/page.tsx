import Link from "next/link";
import { notFound } from "next/navigation";
import DocsSearch from "@/components/DocsSearch";
import { docSlugs, loadDoc } from "@/lib/docs";

export async function generateStaticParams() {
  return [{ slug: [] }, ...(await docSlugs()).map((s) => ({ slug: [s] }))];
}

/** Sidebar groups, in reading order (same as docs/README.md). Docs not listed go under "More". */
const GROUPS: [string, string[]][] = [
  ["", ["readme"]],
  ["Get started", ["setup", "profiles", "marketing-workflow"]],
  ["Features", ["dashboard", "ads-scout", "search-demand", "performance"]],
  ["Making better videos", ["video-quality-framework", "originality-and-duplicate-detection"]],
  ["Under the hood", ["how-it-works", "similar-tools", "references"]],
];

export async function generateMetadata({ params }: { params: Promise<{ slug?: string[] }> }) {
  const s = (await params).slug?.[0] ?? "readme";
  return { title: (await loadDoc(s))?.title ?? "Docs" };
}

export default async function DocsPage({ params }: { params: Promise<{ slug?: string[] }> }) {
  const slug = (await params).slug?.[0] ?? "readme";
  const doc = await loadDoc(slug);
  if (!doc) notFound();
  const all = await docSlugs();
  const listed = new Set(GROUPS.flatMap(([, s]) => s));
  const groups = [...GROUPS, ["More", all.filter((s) => !listed.has(s))] as [string, string[]]]
    .map(([label, s]) => [label, s.filter((x) => all.includes(x))] as const).filter(([, s]) => s.length);
  const title = async (s: string) => (s === "readme" ? "Overview" : (await loadDoc(s))?.title.replace(/ \(.*\)$|:.*$/, "") ?? s);
  const nav = await Promise.all(groups.map(async ([label, s]) => [label, await Promise.all(s.map(async (x) => [x, await title(x)] as const))] as const));
  return (
    <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
      <aside className="lg:sticky lg:top-20 lg:self-start">
        <DocsSearch />
        <nav className="flex gap-1 overflow-x-auto lg:flex-col">
          {nav.map(([label, items]) => (
            <div key={label || "top"} className="flex shrink-0 gap-1 lg:mb-3 lg:flex-col">
              {label && <p className="hidden px-3 pb-1 pt-1 text-[11px] uppercase tracking-wide text-muted lg:block">{label}</p>}
              {items.map(([s, t]) => (
                <Link key={s} href={`/docs/${s}`}
                  className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm lg:whitespace-normal ${s === slug ? "bg-panel-2 text-text" : "text-muted hover:text-text"}`}>
                  {t}
                </Link>
              ))}
            </div>
          ))}
        </nav>
      </aside>
      <article className="prose-dark min-w-0 rounded-2xl border border-line bg-panel p-5 sm:p-8"
        dangerouslySetInnerHTML={{ __html: doc.html }} />
    </div>
  );
}
