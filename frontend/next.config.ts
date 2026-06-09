import type { NextConfig } from "next";

const isDevelopment = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Keep dev and production artifacts separate so stale server chunks do not
  // bleed across after large app-router refactors.
  distDir: isDevelopment ? ".next-dev" : ".next",
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors https://admin.shopify.com https://*.myshopify.com;",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
