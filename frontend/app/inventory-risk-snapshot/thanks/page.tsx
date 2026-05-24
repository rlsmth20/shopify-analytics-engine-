import Link from "next/link";

import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Inventory snapshot request received - skubase",
  alternates: { canonical: "/inventory-risk-snapshot/thanks" },
};

export default function InventoryRiskSnapshotThanksPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero">
        <p className="marketing-eyebrow">Request received</p>
        <h1 className="marketing-hero-title">You&apos;re on the list.</h1>
        <p className="marketing-hero-sub">
          Skubase will review the submitted store and send a short inventory risk snapshot
          with practical SKU-level actions.
        </p>
        <div className="marketing-hero-ctas">
          <Link href="/dashboard?demo=1" className="button button-primary button-lg">
            View live demo
          </Link>
          <Link href="/blog/how-to-clear-dead-stock-shopify" className="button button-secondary button-lg">
            Read the dead stock guide
          </Link>
          <Link href="/goodbye-stocky" className="button button-secondary button-lg">
            Stocky migration
          </Link>
        </div>
      </section>
    </div>
  );
}
