import { NextRequest, NextResponse } from "next/server";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "https://api.skubase.io");

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const headers = new Headers();
  const authorization = request.headers.get("authorization");
  const cookie = request.headers.get("cookie");

  if (authorization) headers.set("authorization", authorization);
  if (cookie) headers.set("cookie", cookie);

  try {
    const response = await fetch(`${API_BASE}/integrations/stocky/import`, {
      method: "POST",
      headers,
      body: formData,
    });
    const text = await response.text();
    return new NextResponse(text, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") || "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      { detail: "The import result could not be confirmed. It may already have been saved. Check your catalog before uploading again, or contact info@skubase.io for help." },
      { status: 502 },
    );
  }
}
