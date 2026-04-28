import type { ReactNode } from "react";

export const metadata = {
  title: "Import ShipStation CSV — slelfly",
  description:
    "Drop in your ShipStation shipment export and slelfly turns it into 30/90/180-day per-SKU velocity, ready to forecast against. No consultant required.",
  alternates: { canonical: "/import-shipstation" },
  openGraph: {
    title: "Import ShipStation CSV — slelfly",
    description:
      "Turn your ShipStation export into per-SKU velocity in minutes.",
    url: "/import-shipstation",
    type: "website",
  },
};

export default function ImportShipstationLayout({ children }: { children: ReactNode }) {
  return children;
}
