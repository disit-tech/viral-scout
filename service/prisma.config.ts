import { defineConfig } from "prisma/config";

/**
 * Prisma CLI config. This service only runs `prisma generate` (no migrations: the database and its schema belong to
 * the solar site, D:/repo/solar-site/site/prisma). Never run `prisma migrate` or `db push` from here.
 */
export default defineConfig({
  schema: "prisma/schema.prisma",
  datasource: { url: "file:./data/local.db" },
});
