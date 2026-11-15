import { botSlugs, config, projectSlugs, tokenOf, webhookSecretOf, forwardSecretOf } from "@/lib/config";

/**
 * Liveness + config check. Says which bots have a token and a secret (true/false only: never a value). ?db=1 also
 * runs one tiny query to prove the database answers.
 */
export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  let configOk = true;
  let error: string | undefined;
  try {
    config();
  } catch (e) {
    configOk = false;
    error = (e as Error).message;
  }
  if (!configOk) return Response.json({ ok: false, error }, { status: 500 });
  const bots = Object.fromEntries(
    botSlugs().map((b) => [b, { token: Boolean(tokenOf(b)), webhook: Boolean(webhookSecretOf(b)), forward: Boolean(forwardSecretOf(b)) }]),
  );
  const body: Record<string, unknown> = { ok: true, projects: projectSlugs(), bots, database: Boolean(process.env.DATABASE_URL) };
  if (new URL(req.url).searchParams.get("db") === "1") {
    try {
      const { prisma } = await import("@/lib/db");
      await prisma.videoIdea.count({ where: { id: -1 } });
      body.db = "ok";
    } catch {
      body.ok = false;
      body.db = "error";
    }
  }
  return Response.json(body, { status: body.ok ? 200 : 503 });
}
