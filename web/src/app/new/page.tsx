import { isLocal } from "@/lib/data";
import NewProject from "@/components/NewProject";

export const metadata = { title: "New research" };
export const dynamic = "force-dynamic";

export default function NewPage() {
  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold tracking-tight">New research</h1>
      <p className="mt-1 text-sm text-muted">
        Describe a business or a topic and a few search phrases. Viral Scout writes a profile (hashtags, topic filter and
        spam rules derived from your phrases) and starts the first run: 3–8 minutes.
      </p>
      {isLocal ? <NewProject /> : (
        <div className="mt-6 rounded-xl border border-dashed border-line p-8 text-center text-muted">
          Runs happen on your PC. Open the local dashboard (<code className="text-text">cd web &amp;&amp; npm run dev</code>) or run
          <code className="mx-1 text-text">python -m viral_scout new &lt;name&gt; --keywords &quot;a; b&quot; --run</code>.
        </div>
      )}
    </div>
  );
}
