import Link from "next/link";

import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";
import { MarketingFooter } from "@/components/marketing-footer";

export const metadata = {
  title: "Goodbye Stocky, hello skubase - skubase",
  description: "Plan inventory after Stocky's August 31, 2026 retirement. Review reorder recommendations, export purchase orders, and import your saved Stocky product CSV.",
  alternates: { canonical: "/goodbye-stocky" },
  keywords: ["Stocky alternative", "Stocky replacement", "Stocky sunset"],
  openGraph: { title: "Goodbye Stocky, hello skubase", description: "Inventory planning and catalog import after Stocky's August 31, 2026 retirement.", url: "/goodbye-stocky", type: "website" },
};

const compareRows = [
  { capability: "Inventory", stocky: "Maintain accurate quantities at each location.", skubase: "Read aggregate inventory totals from Shopify for planning." },
  { capability: "Purchasing", stocky: "Send supplier orders and receive stock.", skubase: "Create supplier-grouped PO drafts, export Excel workbooks, open vendor email drafts, and record receipts." },
  { capability: "Transfers", stocky: "Move stock between locations and confirm receipt.", skubase: "Use Shopify for stock movements while reviewing replenishment priorities in Skubase." },
  { capability: "Dead stock", stocky: "Approve and carry out markdowns or other actions.", skubase: "Review suggested markdown, bundle, wholesale, or write-off plans, depending on your plan." },
  { capability: "Product data", stocky: "Retain catalog exports and verify stock counts.", skubase: "CSV-only workspaces can import catalog fields and stock snapshots. When Shopify is connected or its catalog is already synced, CSV quantities are ignored; supported costs and lead times can enrich an unambiguous Shopify variant." },
  { capability: "Historical records", stocky: "Keep supplier, purchase-order, and transfer records for reference.", skubase: "Keep historical POs, transfers, and supplier records in a separate archive. Add sales history through a supported connection or shipment import." }
];

const steps = [
  { number: "1", title: "Preserve your records", body: "Save available exports while read-only access remains. Keep historical records and supplier details for reference." },
  { number: "2", title: "Import your product catalog", body: "Use a Stocky product CSV for catalog details and a stock snapshot in a CSV-only workspace. Shopify-backed workspaces keep Shopify stock quantities and accept supported cost and lead-time updates for unambiguous variants. Review the reported changes and skipped rows." },
  { number: "3", title: "Add sales data and review recommendations", body: "Import non-Shopify shipment history through ShipStation, or sync Shopify if Skubase is already installed for your store. Stocky product CSVs do not include sales history. Check lead times and representative products before relying on recommendations." },
  { number: "4", title: "Carry out approved actions", body: "Review supplier-grouped PO drafts, export an Excel workbook, and open a vendor email draft. Record receipts in Skubase and maintain stock quantities in Shopify or your operations system." }
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
          Turn reorder recommendations into supplier-grouped purchase orders you can export and share.
          Track receipts and supplier performance as you build your new planning routine.
        </p>
        <p className="marketing-hero-trust">
          Shopify provides read-only Stocky exports for at least 90 days after retirement. <a href="https://help.shopify.com/en/manual/products/inventory/transitioning-from-stocky">Check Shopify&apos;s migration guidance</a>.
          {" "}Availability checked September 9, 2026.
        </p>
        <p className="marketing-hero-trust">
          Skubase is in Shopify&apos;s review process and is not yet listed in the Shopify App Store.
          Start a CSV workspace now, or <Link href="/tools/inventory-health-check">try the free browser inventory check</Link> without an account or installation.
        </p>
        <WaitlistForm source="goodbye_stocky_hero" ctaLabel="Send my sign-in link" />
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
          to choose the plan for your store. Prices checked September 9, 2026.
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
          <Link href="/dashboard?demo=1">Try the demo with sample data</Link>, or request a sign-in link to start your CSV workspace.
          New accounts start a 14-day trial; this form does not install the Shopify app.
        </p>
        <WaitlistForm source="goodbye_stocky_footer" ctaLabel="Send my sign-in link" />
      </section>

      <MarketingFooter />
    </div>
  );
}
