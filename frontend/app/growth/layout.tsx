import type { Metadata } from "next";

export const metadata: Metadata = { title: "Growth operator", robots: { index: false, follow: false } };

export default function GrowthLayout({ children }: { children: React.ReactNode }) {
  return children;
}
