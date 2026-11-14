import { notFound } from "next/navigation";
import { isLocal } from "@/lib/data";
import { runCli } from "@/lib/cli";
import type { ProfileFields } from "@/lib/types";
import SettingsForm from "@/components/SettingsForm";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ name: string }> }) {
  return { title: `Settings · ${(await params).name}` };
}

export default async function SettingsPage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  if (!/^[\w.-]+$/.test(name)) notFound();
  if (!isLocal) {
    return (
      <div className="rounded-xl border border-dashed border-line p-8 text-center text-muted">
        Settings are edited on the local dashboard (they write <code className="text-text">profiles/{name}.yaml</code> on your PC).
      </div>
    );
  }
  const r = await runCli(["profile", name, "get"]);
  let data: ProfileFields | null = null;
  try { data = JSON.parse(r.output.split("\n").filter((l) => l.startsWith("{")).pop() ?? ""); } catch { /* below */ }
  if (!data || "error" in (data as object)) {
    return (
      <div className="rounded-xl border border-dashed border-line p-8 text-center text-muted">
        Couldn&apos;t read <code className="text-text">profiles/{name}.yaml</code>: {(data as { error?: string } | null)?.error ?? r.output.slice(-300)}
      </div>
    );
  }
  return <SettingsForm initial={data} />;
}
