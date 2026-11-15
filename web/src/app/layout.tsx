import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { isLocal } from "@/lib/data";
import { isPublicDemo } from "@/lib/auth";
import NavActivity from "@/components/NavActivity";

export const metadata: Metadata = {
  title: { default: "Viral Scout", template: "%s · Viral Scout" },
  description: "What's going viral in your niche, and what to film next.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <header className="sticky top-0 z-20 border-b border-line bg-ink/85 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
            <Link href="/" className="flex shrink-0 items-center gap-2 whitespace-nowrap font-semibold tracking-tight">
              <svg viewBox="0 0 64 64" className="h-6 w-6" aria-hidden>
                <path d="M12 46 L26 30 L35 38 L52 16" fill="none" stroke="#ffb020" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="52" cy="16" r="6" fill="#ff5d3a" />
              </svg>
              Viral Scout
            </Link>
            <nav className="flex min-w-0 gap-1 overflow-x-auto whitespace-nowrap text-sm sm:ml-4">
              <Link href="/" className="rounded-md px-2 py-1 text-muted hover:bg-panel hover:text-text">Businesses</Link>
              <Link href="/search" className="rounded-md px-2 py-1 text-muted hover:bg-panel hover:text-text" title="Search every post already collected">Search posts</Link>
              <Link href="/check" className="rounded-md px-2 py-1 text-muted hover:bg-panel hover:text-text">Check a video</Link>
              {isLocal && <NavActivity local={isLocal} />}
              <Link href="/setup" className="rounded-md px-2 py-1 text-muted hover:bg-panel hover:text-text">Setup</Link>
              <Link href="/docs" className="rounded-md px-2 py-1 text-muted hover:bg-panel hover:text-text">Docs</Link>
            </nav>
            <span className={`ml-auto hidden rounded-full sm:inline border px-2.5 py-0.5 text-xs ${isLocal ? "border-above/40 text-above" : "border-line text-muted"}`}>
              {isLocal ? "local · actions on" : isPublicDemo ? "demo · read-only" : "published · read-only"}
            </span>
          </div>
        </header>
        {isPublicDemo && (
          <div className="border-b border-line bg-panel-2 px-4 py-2 text-center text-xs text-muted">
            Public demo with sample data: one example business, real public YouTube posts, competitor ads with the advertisers renamed. Read-only.{" "}
            <a href="https://github.com/disit-tech/viral-scout" className="text-rise underline">Source on GitHub</a>
          </div>
        )}
        <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-7xl px-4 pb-10 pt-4 text-xs text-muted">
          Data from public posts (yt-dlp), official APIs and Apify. Viral posts are references for formats, never footage to reuse.
        </footer>
      </body>
    </html>
  );
}
