import Link from "next/link";

/** Link to a business's "Your performance" page. Mount it in the business page header (Dashboard.tsx). */
export default function PerformanceLink({ name, className = "" }: { name: string; className?: string }) {
  return (
    <Link href={`/p/${encodeURIComponent(name)}/performance`}
      className={`inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1 text-xs text-muted hover:border-accent/60 hover:text-text ${className}`}
      title="Your own videos and ads: hook rate, retention, CTR, CPA, ROAS, diagnostics">
      <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" aria-hidden>
        <path d="M2 13 L6 8 L9 10 L14 3" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      Your performance
    </Link>
  );
}
