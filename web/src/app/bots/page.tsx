import { isLocal } from "@/lib/data";
import BotsPanel from "@/components/BotsPanel";

export const metadata = { title: "Bots" };
export const dynamic = "force-dynamic";

export default function Bots() {
  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Bots</h1>
      <p className="mt-1 max-w-3xl text-sm text-muted">
        Are the Telegram bots of each business connected and working? The <b className="text-text">ideas bot</b> posts the
        ideas you rate; the <b className="text-text">video bot</b> sends scenarios, films and files, and takes your replies
        for Claude. Both are shared by every business (each message starts with the business&apos;s label). The numbers
        come from the bot service and from Telegram itself.
      </p>
      {isLocal ? (
        <BotsPanel />
      ) : (
        <div className="mt-6 rounded-xl border border-dashed border-line p-8 text-center text-muted">
          Bot status is only on the local dashboard (<code className="text-text">cd web &amp;&amp; npm run dev</code>): it
          needs the ideas API key from your PC.
        </div>
      )}
    </div>
  );
}
