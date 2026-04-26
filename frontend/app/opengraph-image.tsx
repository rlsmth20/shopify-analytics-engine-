import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "slelfly — The Shopify inventory tool that tells you what to do first.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OGImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          background: "linear-gradient(135deg, #1e3a8a 0%, #0f766e 100%)",
          color: "#ffffff",
          fontFamily: "system-ui, -apple-system, sans-serif",
          padding: "72px 80px",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div
            style={{
              width: 72,
              height: 72,
              borderRadius: 18,
              background: "#ffffff",
              color: "#1e3a8a",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 32,
              fontWeight: 800,
              letterSpacing: "0.04em",
            }}
          >
            sf
          </div>
          <div style={{ fontSize: 36, fontWeight: 700, letterSpacing: "-0.01em" }}>slelfly</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div
            style={{
              fontSize: 72,
              fontWeight: 800,
              lineHeight: 1.05,
              letterSpacing: "-0.02em",
              maxWidth: 1040,
            }}
          >
            The Shopify inventory tool that tells you what to do first.
          </div>
          <div style={{ fontSize: 28, opacity: 0.9, maxWidth: 1040, lineHeight: 1.35 }}>
            Forecast 90 days. Rank every SKU. Score every supplier. Recover cash from dead stock.
          </div>
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: 22,
            opacity: 0.85,
          }}
        >
          <span>Independent · Founder-led · Prices locked at renewal</span>
          <span style={{ fontWeight: 700 }}>slelfly.com</span>
        </div>
      </div>
    ),
    { ...size }
  );
}
