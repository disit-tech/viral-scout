import { isLocal } from "@/lib/data";
import IdeasBoard from "@/components/IdeasBoard";

export const dynamic = "force-dynamic";
export const metadata = { title: "Ideas" };

/** Every business's ideas and daily films on one board (local dashboard: it reads the bot service's database). */
export default async function IdeasPage({ searchParams }: { searchParams: Promise<{ project?: string }> }) {
  const { project } = await searchParams;
  if (!isLocal) {
    return <p className="text-muted">The ideas board runs on the local dashboard only: it reads and changes the ideas in the bot service.</p>;
  }
  return <IdeasBoard initialProject={project ?? ""} />;
}
