import type { Metadata } from "next";

import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/next";

import "./globals.css";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://slelfly.com";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "slelfly — The Shopify inventory tool that tells you what to do first",
    template: "%s · slelfly",
  },
  description:
    "Forecast the next 90 days, rank every SKU, score every supplier, and recover cash from dead stock — in one Shopify-first product, at a price that doesn't triple at renewal.",
  keywords: [
    "Shopify inventory",
    "Shopify forecasting",
    "Stocky alternative",
    "Inventory Planner alternative",
    "Cin7 alternative",
    "supplier scorecards",
    "dead stock liquidation",
    "stockout probability",
  ],
  authors: [{ name: "slelfly" }],
  creator: "slelfly",
  publisher: "slelfly",
  applicationName: "slelfly",
  category: "business",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "slelfly",
    title: "slelfly — The Shopify inventory tool that tells you what to do first",
    description: "Forecast 90 days. Rank every SKU. Score every supplier. Recover cash from dead stock.",
    url: SITE_URL,
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "slelfly — The Shopify inventory tool that tells you what to do first",
    description: "Forecast 90 days. Rank every SKU. Score every supplier. Recover cash from dead stock.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-snippet": -1,
      "max-image-preview": "large",
      "max-video-preview": -1,
    },
  },
};

const SOFTWARE_APP_LD = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "slelfly",
  applicationCategory: "BusinessApplication",
  applicationSubCategory: "Inventory Management",
  operatingSystem: "Web",
  url: SITE_URL,
  description: "Forecast 90 days, rank every SKU, score every supplier, and recover cash from dead stock.",
  offers: [
    { "@type": "Offer", name: "Starter", price: "49", priceCurrency: "USD", url: `${SITE_URL}/pricing` },
    { "@type": "Offer", name: "Growth", price: "149", priceCurrency: "USD", url: `${SITE_URL}/pricing` },
    { "@type": "Offer", name: "Scale", price: "349", priceCurrency: "USD", url: `${SITE_URL}/pricing` },
  ],
  publisher: { "@type": "Organization", name: "slelfly", url: SITE_URL },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        {children}
        <Analytics />
        <SpeedInsights />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(SOFTWARE_APP_LD) }}
        />
      </body>
    </html>
  );
}
