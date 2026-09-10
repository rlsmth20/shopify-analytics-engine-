import Link from "next/link";

import { WaitlistForm } from "@/components/waitlist-form";
import { MarketingNav } from "@/components/marketing-nav";
import { MarketingFooter } from "@/components/marketing-footer";

export const metadata = {
  title: "Better than your spreadsheet - skubase",
  description: "Turn inventory data into reorder priorities, exportable purchase orders, and a repeatable weekly planning routine.",
  alternates: { canonical: "/vs-spreadsheet" },
  openGraph: {
    title: "Inventory planning beyond the spreadsheet - skubase",
    description: "Turn inventory data into reorder priorities, exportable purchase orders, and a repeatable weekly planning routine.",
    url: "/vs-spreadsheet",
    type: "website",
  },
};

const reasons = [
  { title: "Know what needs attention.", body: "Review stockout risk, excess inventory, and reorder priorities together instead of maintaining a separate shortlist." },
  { title: "See demand changes.", body: "Forecast views use recent sales, trend, and weekly patterns when sufficient history is available. Compare the outlook with your upcoming promotions." },
  { title: "Plan your next supplier order.", body: "Turn reorder recommendations into supplier-grouped PO drafts and export Excel workbooks with quantities and costs." },
  { title: "Learn from actual deliveries.", body: "Record receipts and use supplier scorecards to review on-time delivery, fill rate, and lead-time stability on supported plans." },
  { title: "Give slow stock a next action.", body: "Review markdown, bundle, wholesale, and write-off recommendations, with projected recovery when costs are available." },
];

const compare = [
  { metric: "Demand planning", sheet: "Choose formulas and refresh source data", skubase: "Forecast views with trend and weekly patterns when history supports them" },
  { metric: "Reorder review", sheet: "Maintain lead-time and buffer calculations", skubase: "Ranked recommendations using sales, stock, lead times, and safety settings" },
  { metric: "Purchase orders", sheet: "Build and maintain supplier order templates", skubase: "Supplier-grouped drafts, Excel exports, and vendor email drafts" },
  { metric: "Supplier review", sheet: "Maintain order and receipt logs", skubase: "Receipt-based scorecards on supported plans" },
  { metric: "Slow stock", sheet: "Compare recovery options manually", skubase: "Suggested recovery plans on supported plans" },
  { metric: "Data refresh", sheet: "Refresh imports and formulas", skubase: "Shopify sync where installed, or supported CSV uploads" },
];

const steps = [
  { n: "1", title: "Add inventory and sales data", body: "Use a supported Stocky product CSV for a CSV workspace and ShipStation for non-Shopify shipment history. Shopify-backed workspaces retain Shopify as the source for stock quantities." },
  { n: "2", title: "Set your planning inputs", body: "Review supplier lead times, costs, and safety settings. Check a few familiar products against your current sheet." },
  { n: "3", title: "Review and export your next order", body: "Work through the ranked actions, review the supplier-grouped purchase-order drafts, and export the approved plan." },
];

export default function VsSpreadsheetPage() {
  return (
    <div className="marketing-shell">
      <MarketingNav />

      <section className="marketing-hero marketing-hero-migration">
        <p className="marketing-eyebrow">vs. your forecasting spreadsheet</p>
        <h1 className="marketing-hero-title">Turn your inventory sheet into a weekly action plan.</h1>
        <p className="marketing-hero-sub">
          Bring sales, stock, and supplier lead times into one view. Skubase helps you see what needs reordering, review slow stock, and prepare purchase orders you can export and share.
        </p>
        <p className="marketing-hero-trust">Skubase is in Shopify&apos;s review process and is not yet listed in the Shopify App Store. CSV workspaces and the <Link href="/tools/inventory-health-check">free inventory health check</Link> are available now.</p>
        <WaitlistForm source="vs_spreadsheet_hero" ctaLabel="Start free trial" />
        <p className="marketing-hero-trust">
          14-day free trial · No credit card · <strong>Prices locked at renewal</strong> ·{" "}
          <Link href="/inventory-risk-snapshot">Get a free inventory risk snapshot</Link>
        </p>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">A repeatable planning routine</p>
        <h2 className="marketing-section-title">Five ways to simplify your inventory review.</h2>
        <div className="beliefs-grid">
          {reasons.map((r) => (
            <article key={r.title} className="belief-card">
              <h3 className="belief-card-title">{r.title}</h3>
              <p className="belief-card-body">{r.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-section-alt">
        <p className="marketing-section-kicker">Side by side</p>
        <h2 className="marketing-section-title">The math, made visible.</h2>
        <div className="compare-table-wrapper">
          <table className="compare-table">
            <thead>
              <tr><th>Metric</th><th>Spreadsheet workflow</th><th>skubase</th></tr>
            </thead>
            <tbody>
              {compare.map((row) => (
                <tr key={row.metric}>
                  <td className="compare-table-label">{row.metric}</td>
                  <td className="compare-table-old">{row.sheet}</td>
                  <td className="compare-table-new">{row.skubase}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="marketing-section">
        <p className="marketing-section-kicker">How it works</p>
        <h2 className="marketing-section-title">Three steps to your first review.</h2>
        <div className="migration-steps">
          {steps.map((s) => (
            <article key={s.n} className="migration-step">
              <span className="migration-step-number">{s.n}</span>
              <div>
                <h3 className="migration-step-title">{s.title}</h3>
                <p className="migration-step-body">{s.body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-cta-section">
        <h2 className="marketing-section-title">Make your next order easier to review.</h2>
        <p className="marketing-section-sub">
          Try the sample dashboard, then bring a few representative products into your own workspace.
        </p>
        <WaitlistForm source="vs_spreadsheet_footer" ctaLabel="Start free trial" />
      </section>

      <MarketingFooter />
    </div>
  );
}
