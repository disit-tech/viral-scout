import { prisma } from "./db";

/** NWS alerts the solar site saw in the last `hours` (the generator opens with a storm idea when there are any). */
export function recentStorms(hours = 72) {
  return prisma.stormAlert
    .findMany({
      where: { createdAt: { gte: new Date(Date.now() - hours * 3600_000) } },
      orderBy: { createdAt: "desc" },
      select: { event: true, headline: true, areaDesc: true, onset: true, expires: true, createdAt: true },
      take: 20,
    })
    .catch((e) => {
      console.error("storms", e);
      return [];
    });
}
