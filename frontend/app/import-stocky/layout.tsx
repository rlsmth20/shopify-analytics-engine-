import type { ReactNode } from "react";

export const metadata = {
  title: "Import Stocky CSV — slelfly",
  description:
    "Migrating off Shopify Stocky? Drop in your Inventory On Hand and Vendor List exports — slelfly maps them in one step. No consultant required.",
  alternates: { canonical: "/import-stocky" },
  openGraph: {
    title: "Import Stocky CSV — slelfly",
    description:
      "Drop in your Stocky export and start with real data in minutes.",
    url: "/import-stocky",
    type: "website",
  },
};

export default function ImportStockyLayout({ children }: { children: ReactNode }) {
  return children;
}
