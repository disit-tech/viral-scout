import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, authRequired, verifySession } from "@/lib/auth";

/** Password gate for the published dashboard; off locally unless SITE_PASSWORD is set. */
export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (!authRequired() || pathname === "/login" || pathname === "/api/login") {
    return withHeaders(NextResponse.next());
  }
  if (await verifySession(request.cookies.get(SESSION_COOKIE)?.value)) return withHeaders(NextResponse.next());
  if (pathname.startsWith("/api/")) return NextResponse.json({ error: "login required" }, { status: 401 });
  const url = new URL("/login", request.url);
  url.searchParams.set("next", pathname);
  return NextResponse.redirect(url);
}

function withHeaders(res: NextResponse) {
  res.headers.set("X-Robots-Tag", "noindex, nofollow");
  return res;
}

export const config = { matcher: ["/((?!_next/|favicon.ico|icon.svg).*)"] };
