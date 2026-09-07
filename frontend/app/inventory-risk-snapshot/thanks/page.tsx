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
        <h1 className="marketing-hero-title">Your inventory review request is in.</h1>
        <p className="marketing-hero-sub">
          We&apos;ll review your request and reply from info@skubase.io. You can start
          now with a browser-based check of your SKU summary—no app installation needed.
        </p>
        <div className="marketing-hero-ctas">
          <Link href="/tools/inventory-health-check" className="button button-primary button-lg">
            Check my inventory summary
          </Link>
          <Link href="/sample-inventory-risk-snapshot" className="button button-secondary button-lg">
            See a sample report
          </Link>
        </div>
        <p className="marketing-hero-trust">Skubase is currently in Shopify&apos;s review process and is not yet listed in the Shopify App Store. A SKU summary lets us start the discussion while review is pending. Please don&apos;t email customer records, passwords or access tokens.</p>
      </section>
    </div>
  );
}
