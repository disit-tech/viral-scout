import { isLocal } from "@/lib/data";
import ScheduleManager from "@/components/ScheduleManager";

export const metadata = { title: "Schedule" };
export const dynamic = "force-dynamic";

export default function Schedule() {
  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Schedule</h1>
      <p className="mt-1 max-w-3xl text-sm text-muted">
        The weekly tasks in Windows Task Scheduler: one per business (scouting run, ads scout and search demand on the ads
        day, then the AI ideas note) and a final publish to the dashboard. Pause, resume, move or run them here. Scheduled
        runs use paid sources (Apify), so a task only runs while it is on.
      </p>
      {isLocal ? (
        <ScheduleManager />
      ) : (
        <div className="mt-6 rounded-xl border border-dashed border-line p-8 text-center text-muted">
          The schedule is only on the local dashboard (<code className="text-text">cd web &amp;&amp; npm run dev</code>): the
          tasks live in Task Scheduler on your PC.
        </div>
      )}
    </div>
  );
}
