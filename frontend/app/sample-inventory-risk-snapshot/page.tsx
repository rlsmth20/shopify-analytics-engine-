import { AnalyticsEventOnView } from "@/components/analytics-event-on-view";
import { SampleDemoCta, SampleSnapshotCta } from "@/components/inventory-risk-snapshot-ctas";
import { MarketingNav } from "@/components/marketing-nav";

export const metadata = {
  title: "Sample Inventory Risk Snapshot - skubase",
  description: "A sample Shopify inventory risk snapshot with demo data.",
  alternates: { canonical: "/sample-inventory-risk-snapshot" },
};

const stockoutRows = [
  ["SKU-LINEN-NAVY-M", "Premium Linen Shirt - Navy M", "48", "186", "8", "Reorder 120 units"],
  ["SKU-SCARF-BURG", "Silk Scarf - Burgundy", "18", "98", "5", "Add to next supplier PO"],
  ["SKU-SWEATER-GRY-L", "Wool Blend Sweater - Grey L", "31", "142", "8", "Order before lead time expires"],
  ["SKU-CHINO-KHAKI-32", "Slim Fit Chinos - Khaki 32x30", "73", "124", "18", "Place reorder this week"],
];

const deadStockRows = [
  ["SKU-RUN-SHORT-BLU", "Running Shorts - Blue M", "318", "94 days ago", "$1,905", "Wholesale liquidation"],
  ["SKU-WALLET-BRN", "Leather Wallet - Brown", "204", "67 days ago", "$3,230", "40% markdown"],
  ["SKU-DENIM-IND-L", "Denim Jacket - Indigo L", "156", "22 days ago", "$4,680", "Bundle or light markdown"],
  ["SKU-POLO-WHT-S", "Classic Polo - White S", "142", "8 days ago", "$2,005", "Flash sale test"],
];

const reorderRows = [
  ["1", "SKU-LINEN-NAVY-M", "Premium Linen Shirt - Navy M", "74% stockout risk", "120"],
  ["2", "SKU-SWEATER-GRY-L", "Wool Blend Sweater - Grey L", "Seasonal demand rising", "200"],
  ["3", "SKU-SCARF-BURG", "Silk Scarf - Burgundy", "Below reorder point", "80"],
  ["4", "SKU-CHINO-KHAKI-32", "Slim Fit Chinos - Khaki 32x30", "Lead time exceeds cover", "150"],
];

const actions = [
  "Reorder urgent SKUs",
  "Discount or bundle stale SKUs",
  "Review supplier lead-time outliers",
  "Check bundle component bottlenecks",
];

export default function SampleInventoryRiskSnapshotPage() {
  return (
    <div className="marketing-shell">
      <AnalyticsEventOnView eventName="sample_snapshot_view" />
      <MarketingNav />

      <section className="snapshot-report-hero">
        <div>
          <p className="marketing-eyebrow">Sample snapshot - demo data only</p>
          <h1 className="marketing-hero-title">Inventory Risk Snapshot</h1>
          <p className="marketing-hero-sub">
            This is a fake example of the short action report a Shopify merchant could receive.
          </p>
        </div>
        <div className="marketing-hero-ctas">
          <SampleSnapshotCta cta="report_top" />
          <SampleDemoCta cta="report_top_demo" />
        </div>
      </section>

      <section className="snapshot-summary-grid">
        {[
          ["7", "SKUs at stockout risk"],
          ["$4,820", "Estimated cash tied up in slow-moving inventory"],
          ["12", "Reorder actions"],
          ["3", "Supplier lead-time warnings"],
        ].map(([value, label]) => (
          <article key={label} className="snapshot-summary-card">
            <strong>{value}</strong>
            <span>{label}</span>
          </article>
        ))}
      </section>

      <ReportTable
        title="Stockout risk"
        columns={["SKU", "Product", "Current stock", "30-day sales", "Days of inventory", "Recommended action"]}
        rows={stockoutRows}
      />
      <ReportTable
        title="Dead stock / cash recovery"
        columns={["SKU", "Product", "Units on hand", "Last sold", "Estimated cash tied up", "Suggested action"]}
        rows={deadStockRows}
      />
      <ReportTable
        title="Reorder priorities"
        columns={["Priority", "SKU", "Product", "Reason", "Suggested reorder quantity"]}
        rows={reorderRows}
      />

      <section className="snapshot-action-list">
        <p className="marketing-section-kicker">This week&apos;s action list</p>
        <h2 className="marketing-section-title">Work these in order.</h2>
        <ol>
          {actions.map((action) => (
            <li key={action}>{action}</li>
          ))}
        </ol>
        <div className="marketing-hero-ctas">
          <SampleSnapshotCta cta="report_bottom" />
          <SampleDemoCta cta="report_bottom_demo" />
        </div>
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
