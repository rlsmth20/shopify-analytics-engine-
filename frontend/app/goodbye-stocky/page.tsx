import Link from "next/link";

import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";
import { MarketingFooter } from "@/components/marketing-footer";

export const metadata = {
  title: "Goodbye Stocky, hello skubase - skubase",
  description: "Plan inventory after Stocky's August 31, 2026 retirement. Explore skubase's read-only planning tools and supported product CSV import.",
  alternates: { canonical: "/goodbye-stocky" },
  keywords: ["Stocky alternative", "Stocky replacement", "Stocky sunset"],
  openGraph: { title: "Goodbye Stocky, hello skubase", description: "Inventory planning and catalog import after Stocky's August 31, 2026 retirement.", url: "/goodbye-stocky", type: "website" },
};

const compareRows = [
  { capability: "Inventory", stocky: "Maintain accurate quantities at each location.", skubase: "Read aggregate inventory totals from Shopify for planning." },
  { capability: "Purchasing", stocky: "Send supplier orders and receive stock.", skubase: "Review reorder plans and record receipts; Shopify stock stays unchanged." },
  { capability: "Transfers", stocky: "Move stock between locations and confirm receipt.", skubase: "Does not execute transfers or update store quantities." },
  { capability: "Dead stock", stocky: "Approve and carry out markdowns or other actions.", skubase: "Review suggested markdown, bundle, wholesale, or write-off plans, depending on your plan." },
  { capability: "Product data", stocky: "Retain catalog exports and verify stock counts.", skubase: "Import product CSV fields and stock quantities, including vendor names when present on product rows." },
  { capability: "Historical records", stocky: "Keep supplier, purchase-order, and transfer records for reference.", skubase: "Product CSV import does not migrate standalone vendor lists, PO history, transfers, or sales history." }
];

const steps = [
  { number: "1", title: "Preserve your records", body: "Save available exports while read-only access remains. Keep historical records and supplier details for reference." },
  { number: "2", title: "Import your product catalog", body: "Use the supported Stocky product CSV format for catalog details and stock quantities. Verify the imported fields and counts." },
  { number: "3", title: "Add sales data and review recommendations", body: "Connect Shopify or import supported sales data for demand analysis. Check lead times and representative products before relying on recommendations." },
  { number: "4", title: "Carry out approved actions", body: "Use Shopify or your operations system for purchasing, receiving, transfers, and inventory adjustments. skubase helps you decide what to do." }
];

export default function GoodbyeStockyPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero marketing-hero-migration">
        <p className="marketing-eyebrow">After Stocky - retired August 31, 2026</p>
        <h1 className="marketing-hero-title">Goodbye Stocky. Hello skubase.</h1>
        <p className="marketing-hero-sub">
          Plan your next inventory decisions with forecasts, stockout risk, and a ranked action queue.
          skubase reads your Shopify data and helps you review recommendations; purchasing and stock movements
          stay in Shopify or your operations system.
        </p>
        <p className="marketing-hero-trust">
          Shopify provides read-only Stocky exports for at least 90 days after retirement. <a href="https://help.shopify.com/en/manual/products/inventory/transitioning-from-stocky">Check Shopify&apos;s migration guidance</a>.
          {" "}Availability checked September 6, 2026.
        </p>
        <WaitlistForm source="goodbye_stocky_hero" ctaLabel="Get early access" />
        <p className="marketing-hero-trust">
          14-day trial - No credit card - <strong>Prices locked at renewal</strong> -{" "}
          <Link href="/inventory-risk-snapshot">Get a free inventory risk snapshot</Link>
        </p>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">Planning and operations</p>
        <h2 className="marketing-section-title">Where skubase fits in your workflow.</h2>
        <p className="marketing-section-sub">
          <Link href="/pricing">Monthly plans are $29, $99, and $199</Link>. Review included features and limits
          to choose the plan for your store. Prices checked September 6, 2026.
        </p>
        <div className="compare-table-wrapper">
          <table className="compare-table">
            <thead><tr><th>Workflow</th><th>Operational task</th><th>skubase planning</th></tr></thead>
            <tbody>
              {compareRows.map((row) => (
                <tr key={row.capability}>
                  <td className="compare-table-label">{row.capability}</td>
                  <td className="compare-table-old">{row.stocky}</td>
                  <td className="compare-table-new">{row.skubase}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="marketing-section marketing-section-alt">
        <p className="marketing-section-kicker">Migration path</p>
        <h2 className="marketing-section-title">Prepare your data and planning workflow.</h2>
        <div className="migration-steps">
          {steps.map((s) => (
            <article key={s.number} className="migration-step">
              <span className="migration-step-number">{s.number}</span>
              <div>
                <h3 className="migration-step-title">{s.title}</h3>
                <p className="migration-step-body">{s.body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-cta-section">
        <h2 className="marketing-section-title">Explore inventory planning with skubase.</h2>
        <p className="marketing-section-sub">
          <Link href="/dashboard?demo=1">Try the live demo with sample data</Link>, or join the early-access list for availability updates.
        </p>
        <WaitlistForm source="goodbye_stocky_footer" ctaLabel="Get early access" />
      </section>

      <MarketingFooter />
    </div>
  );
}
