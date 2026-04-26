import type { MetadataRoute } from "next";

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://slelfly.com";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/dashboard",
          "/actions",
          "/alerts",
          "/forecast",
          "/analytics",
          "/suppliers",
          "/purchase-orders",
          "/transfers",
          "/bundles",
          "/liquidation",
          "/store-sync",
          "/lead-time-settings",
          "/billing",
          "/account",
          "/api/",
        ],
      },
    ],
    sitemap: `${BASE_URL}/sitemap.xml`,
    host: BASE_URL,
  };
}
