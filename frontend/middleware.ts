import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  const headers = new Headers(request.headers);
  headers.delete("x-skubase-embedded");
  const params = request.nextUrl.searchParams;
  if (params.get("embedded") === "1" || (params.has("shop") && params.has("host"))) {
    headers.set("x-skubase-embedded", "1");
  }
  return NextResponse.next({ request: { headers } });
}

export const config = { matcher: ["/((?!api|_next|favicon.ico|robots.txt|sitemap.xml|.*\\..*).*)"] };
