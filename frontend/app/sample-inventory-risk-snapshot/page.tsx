import { AnalyticsEventOnView } from "@/components/analytics-event-on-view";
import { SampleDemoCta, SampleSnapshotCta } from "@/components/inventory-risk-snapshot-ctas";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Sample Inventory Risk Snapshot - skubase",
  description: "A polished sample Shopify inventory risk snapshot with demo data.",
  alternates: { canonical: "/sample-inventory-risk-snapshot" },
};

const storeSummary = [
  ["Demo store", "Northstar Apparel Co."],
  ["Catalog reviewed", "428 active SKUs"],
  ["Data window", "Last 90 days of demo orders"],
  ["Snapshot type", "Sample report - demo data only"],
];

const urgentActions = [
  {
    priority: "98",
    title: "Reorder Premium Linen Shirt - Navy M",
    detail: "Only 8 days of cover against a 14-day lead time. Suggested reorder: 120 units.",
    impact: "$2,940 profit at risk",
  },
  {
    priority: "91",
    title: "Add Silk Scarf - Burgundy to next PO",
    detail: "5 days of inventory left with demand trending up 18% over the last month.",
    impact: "$1,120 profit at risk",
  },
  {
    priority: "87",
    title: "Review Coastal Apparel lead time",
    detail: "Recent receipts are running 4 days slower than the configured vendor lead time.",
    impact: "3 SKUs affected",
  },
  {
    priority: "82",
    title: "Clear Leather Wallet - Brown",
    detail: "204 units on hand and no meaningful velocity. Suggested action: 40% markdown test.",
    impact: "$3,230 cash tied up",
  },
  {
    priority: "78",
    title: "Check hoodie bundle component",
    detail: "Black XL hoodie demand is healthy, but component stock would cap bundle availability.",
    impact: "Bundle bottleneck risk",
  },
];

const stockoutRows = [
  ["SKU-LINEN-NAVY-M", "Premium Linen Shirt - Navy M", "48", "186", "8", `${sampleStockoutRiskPercent(48, 186, 6.2, 0.14)}%`, "Reorder 120 units"],
  ["SKU-SCARF-BURG", "Silk Scarf - Burgundy", "18", "98", "5", `${sampleStockoutRiskPercent(18, 98, 3.3, 0.38)}%`, "Add to next supplier PO"],
  ["SKU-SWEATER-GRY-L", "Wool Blend Sweater - Grey L", "31", "142", "8", `${sampleStockoutRiskPercent(31, 142, 3.8, 0.32)}%`, "Order before lead time expires"],
  ["SKU-CHINO-KHAKI-32", "Slim Fit Chinos - Khaki 32x30", "73", "124", "18", `${sampleStockoutRiskPercent(73, 124, 4.1, 0.11)}%`, "Place reorder this week"],
];

const deadStockRows = [
  ["SKU-RUN-SHORT-BLU", "Running Shorts - Blue M", "318", "94 days ago", "$3,021", "$1,905", "Wholesale liquidation"],
  ["SKU-WALLET-BRN", "Leather Wallet - Brown", "204", "67 days ago", "$4,284", "$3,230", "40% markdown"],
  ["SKU-DENIM-IND-L", "Denim Jacket - Indigo L", "156", "22 days ago", "$6,006", "$4,680", "Bundle or light markdown"],
  ["SKU-POLO-WHT-S", "Classic Polo - White S", "142", "8 days ago", "$2,017", "$2,005", "Flash sale test"],
];

const reorderRows = [
  ["1", "SKU-LINEN-NAVY-M", "Premium Linen Shirt - Navy M", "Below reorder point; lead time exceeds cover", "120"],
  ["2", "SKU-SWEATER-GRY-L", "Wool Blend Sweater - Grey L", `Seasonal demand rising; ${sampleStockoutRiskPercent(31, 142, 3.8, 0.32)}% stockout risk`, "200"],
  ["3", "SKU-SCARF-BURG", "Silk Scarf - Burgundy", "Only 5 days of cover", "80"],
  ["4", "SKU-CHINO-KHAKI-32", "Slim Fit Chinos - Khaki 32x30", "Lead time buffer is thin", "150"],
];

const nextSteps = [
  "Confirm lead times for Coastal Apparel and Metro Textile before final PO quantities.",
  "Create a reorder draft for the four urgent SKUs, grouped by vendor.",
  "Run a 40% markdown test on Leather Wallet - Brown before deeper liquidation.",
  "Check bundle component stock before promoting hoodie bundles.",
  "Turn on stockout and dead-stock alerts so the team sees new risks early.",
];

function sampleStockoutRiskPercent(
  onHand: number,
  projected30: number,
  avgDailyUnits: number,
  variabilityCv: number,
): number {
  const sigma30d = Math.max(avgDailyUnits * variabilityCv * Math.sqrt(30), 0.01);
  const z = (onHand - projected30) / sigma30d;
  return Math.round((1 - normalCdf(z)) * 100);
}

function normalCdf(z: number): number {
  return 0.5 * (1 + erf(z / Math.SQRT2));
}

function erf(x: number): number {
  const sign = x < 0 ? -1 : 1;
  const absX = Math.abs(x);
  const t = 1 / (1 + 0.3275911 * absX);
  const y =
    1 -
    (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t +
      0.254829592) *
      t *
      Math.exp(-absX * absX);
  return sign * y;
}

export default function SampleInventoryRiskSnapshotPage() {
  return (
    <div className="marketing-shell">
      <AnalyticsEventOnView eventName="sample_snapshot_view" />
      <MarketingNav />

      <section className="snapshot-report-hero">
        <div>
          <p className="marketing-eyebrow">Sample report - demo data only</p>
          <h1 className="marketing-hero-title">Shopify Inventory Risk Snapshot</h1>
          <p className="marketing-hero-sub">
            A sample of the deliverable a Shopify operator could receive after sharing
            read-only Shopify access or export data. This example is not a live store analysis.
          </p>
        </div>
        <div className="marketing-hero-ctas">
          <SampleSnapshotCta cta="report_top" />
          <SampleDemoCta cta="report_top_demo" />
        </div>
      </section>

      <section className="snapshot-deliverable">
        <div className="snapshot-store-card">
          <div>
            <p className="marketing-section-kicker">Store summary</p>
            <h2>Northstar Apparel Co.</h2>
            <p>
              Demo Shopify catalog with variants, seasonal items, supplier lead times,
              reorder recommendations, and stale inventory.
            </p>
          </div>
          <dl>
            {storeSummary.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="snapshot-summary-grid">
          {[
            ["7", "SKUs at stockout risk"],
            ["$4,820", "Estimated cash tied up in slow movers"],
            ["12", "Reorder actions"],
            ["3", "Supplier lead-time warnings"],
          ].map(([value, label]) => (
            <article key={label} className="snapshot-summary-card">
              <strong>{value}</strong>
              <span>{label}</span>
            </article>
          ))}
        </div>

        <section className="snapshot-report-section">
          <div className="snapshot-section-heading">
            <div>
              <p className="marketing-section-kicker">Top 5 urgent inventory actions</p>
              <h2>What to work first</h2>
            </div>
          </div>
          <div className="snapshot-action-card-grid">
            {urgentActions.map((action) => (
              <article key={action.title} className="snapshot-action-card">
                <span className="score-chip">Priority {action.priority}</span>
                <h3>{action.title}</h3>
                <p>{action.detail}</p>
                <strong>{action.impact}</strong>
              </article>
            ))}
          </div>
        </section>

        <ReportTable
          title="Stockout risk"
          columns={["SKU", "Product", "Current stock", "30-day sales", "Days of inventory", "Risk", "Recommended action"]}
          rows={stockoutRows}
        />
        <ReportTable
          title="Dead stock / cash recovery"
          columns={["SKU", "Product", "Units on hand", "Last sold", "Capital tied up", "Projected recovery", "Suggested action"]}
          rows={deadStockRows}
        />
        <ReportTable
          title="Reorder recommendations"
          columns={["Priority", "SKU", "Product", "Reason", "Suggested reorder quantity"]}
          rows={reorderRows}
        />

        <section className="snapshot-action-list">
          <p className="marketing-section-kicker">What Skubase would do next</p>
          <h2 className="marketing-section-title">Turn the report into this week&apos;s plan.</h2>
          <ol>
            {nextSteps.map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ol>
          <p className="snapshot-report-note">
            Skubase is read-only for this scan unless otherwise stated. A real snapshot
            requires connecting Shopify or sharing export data; this sample is available immediately.
          </p>
          <div className="marketing-hero-ctas">
            <SampleSnapshotCta cta="report_bottom" />
            <SampleDemoCta cta="report_bottom_demo" />
          </div>
        </section>
      </section>
    </div>
  );
}

function ReportTable({
  title,
  columns,
  rows,
}: {
  title: string;
  columns: string[];
  rows: string[][];
}) {
  return (
    <section className="snapshot-report-section">
      <h2>{title}</h2>
      <div className="compare-table-wrapper">
        <table className="compare-table snapshot-report-table">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.join("-")}>
                {row.map((cell, index) => (
                  <td key={`${cell}-${index}`}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
