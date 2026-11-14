import { isLocal } from "@/lib/data";
import ActivityFeed from "@/components/ActivityFeed";

export const metadata = { title: "Activity" };
export const dynamic = "force-dynamic";

export default function Activity() {
  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Activity</h1>
      <p className="mt-1 max-w-3xl text-sm text-muted">
        What is running on this PC right now, line by line, and what Apify is doing and costing. Every run, ads and
        perf command writes a live log here, whether it was started from the CLI, the weekly task, an AI agent or this
        dashboard.
      </p>
      {isLocal ? (
        <ActivityFeed />
      ) : (
        <div className="mt-6 rounded-xl border border-dashed border-line p-8 text-center text-muted">
          Activity is only on the local dashboard (<code className="text-text">cd web &amp;&amp; npm run dev</code>): runs
          happen on your PC, not on the published site.
        </div>
      )}
    </div>
  );
}
