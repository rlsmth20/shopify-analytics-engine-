import type { Metadata } from "next";

import "./globals.css";


export const metadata: Metadata = {
  title: "Inventory Command",
  description:
    "Prioritized Shopify inventory actions for stockouts, overstock, dead stock, and lead-time decisions."
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
