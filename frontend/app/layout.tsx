import type { Metadata } from "next";

import "./globals.css";


export const metadata: Metadata = {
  title: "slelfly — The Shopify inventory tool that tells you what to do first",
  description:
    "Forecast the next 90 days, rank every SKU, score every supplier, and recover cash from dead stock — in one Shopify-first product, at a price that doesn't triple at renewal."
};


export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
