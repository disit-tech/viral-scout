import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { isLocal } from "@/lib/data";

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
            <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
              <svg viewBox="0 0 64 64" className="h-6 w-6" aria-hidden>
                <path d="M12 46 L26 30 L35 38 L52 16" fill="none" stroke="#ffb020" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="52" cy="16" r="6" fill="#ff5d3a" />
              </svg>
              Viral Scout
            </Link>
            <span className={`ml-auto rounded-full border px-2.5 py-0.5 text-xs ${isLocal ? "border-above/40 text-above" : "border-line text-muted"}`}>
              {isLocal ? "local · actions on" : "published · read-only"}
            </span>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-7xl px-4 pb-10 pt-4 text-xs text-muted">
          Data from public posts (yt-dlp), official APIs and Apify. Viral posts are references for formats, never footage to reuse.
        </footer>
      </body>
    </html>
  );
}
