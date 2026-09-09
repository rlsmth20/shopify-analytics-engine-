import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  const headers = new Headers(request.headers);
  headers.delete("x-skubase-embedded");
  const params = request.nextUrl.searchParams;
  if (params.get("embedded") === "1" || (params.has("shop") && params.has("host"))) {
    headers.set("x-skubase-embedded", "1");
    if (request.nextUrl.pathname === "/") {
      // Older installs launch at the root. Route them before rendering and
      // hydrating the marketing page; the dashboard still verifies the session.
      const dashboard = request.nextUrl.clone();
      dashboard.pathname = "/dashboard";
      dashboard.searchParams.set("embedded", "1");
      const response = NextResponse.redirect(dashboard);
      response.headers.set("Cache-Control", "private, no-store");
      return response;
    }
  }
  return NextResponse.next({ request: { headers } });
}

export const config = { matcher: ["/((?!api|_next|favicon.ico|robots.txt|sitemap.xml|.*\\..*).*)"] };
