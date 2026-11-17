"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Section tabs shared by every page of one business (app/p/[name]/layout.tsx). */
export default function BusinessNav({ name, counts }: { name: string; counts: Partial<Record<string, string>> }) {
  const path = usePathname() ?? "";
  const base = `/p/${encodeURIComponent(name)}`;
  const tabs: { href: string; label: string; key: string; match: (p: string) => boolean }[] = [
    { key: "overview", label: "Overview", href: base, match: (p) => p === base || p === `${base}/` },
    { key: "videos", label: "Videos", href: `${base}/videos`, match: (p) => p.startsWith(`${base}/videos`) || p.startsWith(`${base}/v/`) },
    { key: "ads", label: "Ads", href: `${base}/ads`, match: (p) => p.startsWith(`${base}/ads`) || p.startsWith(`${base}/a/`) },
    { key: "demand", label: "Search demand", href: `${base}/demand`, match: (p) => p.startsWith(`${base}/demand`) },
    { key: "swipe", label: "Ideas & swipe file", href: `${base}/swipe`, match: (p) => p.startsWith(`${base}/swipe`) },
    { key: "runs", label: "Runs", href: `${base}/runs`, match: (p) => p.startsWith(`${base}/runs`) },
    { key: "paid", label: "Paid ads", href: `${base}/paid`, match: (p) => p.startsWith(`${base}/paid`) },
    { key: "performance", label: "Your performance", href: `${base}/performance`, match: (p) => p.startsWith(`${base}/performance`) },
    { key: "settings", label: "Settings", href: `${base}/settings`, match: (p) => p.startsWith(`${base}/settings`) },
  ];
  return (
    <nav className="mb-5 flex gap-1 overflow-x-auto border-b border-line">
      {tabs.map((t) => {
        const on = t.match(path);
        return (
          <Link key={t.key} href={t.href}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm transition ${on ? "border-accent text-text" : "border-transparent text-muted hover:text-text"}`}>
            {t.key === "settings" && <span aria-hidden className="mr-1">⚙</span>}
            {t.label}
            {counts[t.key] && <span className="ml-1.5 rounded-full bg-panel-2 px-1.5 text-[11px] text-muted">{counts[t.key]}</span>}
          </Link>
        );
      })}
    </nav>
  );
}
