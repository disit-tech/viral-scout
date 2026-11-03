import { isLocal, loadIndex, loadProfile } from "@/lib/data";
import CheckVideo from "@/components/CheckVideo";
import type { Check } from "@/lib/types";

export const metadata = { title: "Check a video" };
export const dynamic = "force-dynamic";

export default async function CheckPage() {
  const { profiles } = await loadIndex();
  const past: (Check & { profile: string })[] = [];
  for (const p of profiles) {
    const d = await loadProfile(p.name);
    for (const c of d?.checks ?? []) past.push({ ...c, profile: p.name });
  }
  past.sort((a, b) => b.checked.localeCompare(a.checked));
  return (
    <div className="max-w-5xl">
      <h1 className="text-2xl font-bold tracking-tight">Check a video before you post</h1>
      <p className="mt-1 text-sm text-muted">
        For <b>your own</b> draft videos. It measures format, loudness, peaks, silences, cuts and pacing, pattern
        interrupts, how fast the talking starts and whether there&apos;s a call to action, then saves frames so the AI step
        can score the 20 criteria (100 points).
      </p>
      {isLocal ? <CheckVideo profiles={profiles.map((p) => p.name)} past={past} /> : (
        <div className="mt-6 rounded-xl border border-dashed border-line p-8 text-center text-muted">
          Checks run on your PC: open the local dashboard, or run <code className="text-text">python -m viral_scout check &lt;profile&gt; &lt;file&gt;</code>.
        </div>
      )}
    </div>
  );
}
