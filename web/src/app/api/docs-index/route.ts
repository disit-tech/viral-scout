import { NextResponse } from "next/server";
import { docSections } from "@/lib/docs";

export const dynamic = "force-static";

/** The docs split into sections, fetched once by the docs search box. */
export async function GET() {
  return NextResponse.json(await docSections());
}
