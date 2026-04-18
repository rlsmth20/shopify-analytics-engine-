import type { NextConfig } from "next";

const isDevelopment = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Keep dev and production artifacts separate so stale server chunks do not
  // bleed across after large app-router refactors.
  distDir: isDevelopment ? ".next-dev" : ".next"
};

export default nextConfig;
