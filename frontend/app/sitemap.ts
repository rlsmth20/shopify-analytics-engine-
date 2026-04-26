import type { MetadataRoute } from "next";

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://slelfly.com";

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  const routes: { path: string; priority: number; freq: MetadataRoute.Sitemap[number]["changeFrequency"] }[] = [
    { path: "/", priority: 1.0, freq: "weekly" },
    { path: "/pricing", priority: 0.9, freq: "monthly" },
    { path: "/about", priority: 0.8, freq: "monthly" },
    { path: "/changelog", priority: 0.7, freq: "weekly" },
    { path: "/vs-spreadsheet", priority: 0.9, freq: "monthly" },
    { path: "/goodbye-stocky", priority: 0.9, freq: "monthly" },
    { path: "/goodbye-genie", priority: 0.7, freq: "monthly" },
    { path: "/import-stocky", priority: 0.6, freq: "monthly" },
    { path: "/import-shipstation", priority: 0.6, freq: "monthly" },
    { path: "/blog", priority: 0.85, freq: "weekly" },
    { path: "/blog/stocky-alternatives-2026", priority: 0.85, freq: "monthly" },
    { path: "/blog/why-six-month-moving-average-overstocks-you", priority: 0.85, freq: "monthly" },
    { path: "/login", priority: 0.4, freq: "yearly" },
  ];

  return routes.map(({ path, priority, freq }) => ({
    url: `${BASE_URL}${path}`,
    lastModified,
    changeFrequency: freq,
    priority,
  }));
}
