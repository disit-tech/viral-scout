import { isLocal, loadKeyCatalog } from "@/lib/data";
import SetupKeys from "@/components/SetupKeys";
import KeyCatalog from "@/components/KeyCatalog";

export const metadata = { title: "Setup" };
export const dynamic = "force-dynamic";

export default async function Setup() {
  const catalog = isLocal ? [] : await loadKeyCatalog();
  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold tracking-tight">Setup</h1>
      <p className="mt-1 text-sm text-muted">
        API keys unlock more sources. Everything is optional; a missing key just skips that source. Keys are saved to
        <code className="mx-1 text-text">.env</code> in the repo on this PC (git-ignored). Secrets are never shown in full;
        actor ids and settings are. <span className="text-text">Test</span> never starts a paid run: on an actor it only looks
        it up, and on <code className="text-text">APIFY_TOKEN</code> it shows the plan and this cycle&apos;s spend.
      </p>
      {isLocal ? (
        <SetupKeys />
      ) : catalog.length ? (
        <KeyCatalog keys={catalog} />
      ) : (
        <div className="mt-6 rounded-xl border border-dashed border-line p-8 text-center text-muted">
          Keys can only be managed on the local dashboard (<code className="text-text">cd web &amp;&amp; npm run dev</code>), never on the published site.
        </div>
      )}
    </div>
  );
}
