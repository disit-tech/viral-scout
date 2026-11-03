import { isLocal } from "@/lib/data";
import SetupKeys from "@/components/SetupKeys";

export const metadata = { title: "Setup" };
export const dynamic = "force-dynamic";

export default function Setup() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold tracking-tight">Setup</h1>
      <p className="mt-1 text-sm text-muted">
        API keys unlock more sources. Everything is optional; a missing key just skips that source. Keys are saved to
        <code className="mx-1 text-text">.env</code> in the repo on this PC (git-ignored) and are never shown in full.
      </p>
      {isLocal ? (
        <SetupKeys />
      ) : (
        <div className="mt-6 rounded-xl border border-dashed border-line p-8 text-center text-muted">
          Keys can only be managed on the local dashboard (<code className="text-text">cd web &amp;&amp; npm run dev</code>), never on the published site.
        </div>
      )}
    </div>
  );
}
