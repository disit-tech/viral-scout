import { z } from "zod";
import { apiSecret } from "@/lib/config";
import { bearer, safeEqual } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { postBlogReview, setBlogStatus } from "@/lib/idea-bot";

/**
 * Blog guide reviews for Claude's weekly job (`node scripts/ideas.mjs blog …`). Same contract as the solar site's
 * /api/blog-review. Auth: "Authorization: Bearer <IDEAS_API_SECRET>". The bot is blog.bot in projects.json.
 *   GET   → every review (newest first)
 *   POST  → { slug, title, summary } send the draft with ✅ Publish / ✏️ Changes
 *   PATCH → { id, status: "published" } after the job set draft: false and pushed
 */

export const dynamic = "force-dynamic";

const authorized = (req: Request) => safeEqual(bearer(req), apiSecret());

const Post = z.object({
  slug: z.string().regex(/^[a-z0-9-]{3,90}$/),
  title: z.string().trim().min(5).max(200),
  summary: z.string().trim().min(20).max(3000),
});
const Patch = z.object({ id: z.number().int().positive(), status: z.enum(["published"]) });

export async function GET(req: Request) {
  if (!authorized(req)) return new Response("Unauthorized", { status: 401 });
  return Response.json({ reviews: await prisma.blogReview.findMany({ orderBy: { id: "desc" } }) });
}

export async function POST(req: Request) {
  if (!authorized(req)) return new Response("Unauthorized", { status: 401 });
  const parsed = Post.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: z.flattenError(parsed.error) }, { status: 400 });
  const b = await postBlogReview(parsed.data.slug, parsed.data.title, parsed.data.summary);
  return Response.json({ id: b.id, messageId: b.messageId });
}

export async function PATCH(req: Request) {
  if (!authorized(req)) return new Response("Unauthorized", { status: 401 });
  const parsed = Patch.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: z.flattenError(parsed.error) }, { status: 400 });
  const b = await prisma.blogReview.findUnique({ where: { id: parsed.data.id } });
  if (!b) return Response.json({ error: "not found" }, { status: 404 });
  await setBlogStatus(b, parsed.data.status);
  return Response.json({ ok: true });
}
