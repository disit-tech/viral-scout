import { PrismaLibSql } from "@prisma/adapter-libsql";
import { PrismaClient } from "@/generated/prisma/client";

/**
 * The solar site's database (Turso / libSQL), shared with the CRM pages (/admin/ideas). Same tables, no migrations here.
 * Production: DATABASE_URL (libsql://…) + DATABASE_AUTH_TOKEN. Local: a scratch SQLite file, never the production DB.
 * The client is created on first use, so a build without the env vars doesn't fail.
 */
function createPrisma() {
  if (process.env.VERCEL && !process.env.DATABASE_URL) {
    throw new Error("DATABASE_URL is not set: on Vercel the service needs the Turso database (libsql://…).");
  }
  const adapter = new PrismaLibSql({
    url: process.env.DATABASE_URL || "file:./data/local.db",
    authToken: process.env.DATABASE_AUTH_TOKEN,
  });
  return new PrismaClient({ adapter });
}

type Client = ReturnType<typeof createPrisma>;
const g = globalThis as unknown as { prisma?: Client };

export const prisma: Client = new Proxy({} as Client, {
  get(_t, prop) {
    g.prisma ??= createPrisma();
    return Reflect.get(g.prisma, prop, g.prisma);
  },
});

export type { VideoIdea, BlogReview, IdeaFeedback } from "@/generated/prisma/client";
