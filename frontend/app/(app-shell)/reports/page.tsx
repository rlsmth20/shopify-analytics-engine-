const reports = [
  {
    title: "Inventory Action Report",
    category: "Action queue",
    description: "Export the current urgent, optimize, and dead-stock queue with impact and recommendation detail.",
    status: "Available",
    href: "/actions",
    cta: "Open action queue",
  },
  {
    title: "Stockout Risk Report",
    category: "Forecasting",
    description: "Review the SKUs ranked by stockout probability, forecast confidence, and days of cover.",
    status: "Available",
    href: "/forecast",
    cta: "Review stockout risk",
  },
  {
    title: "Reorder Plan / Purchase Order Export",
    category: "Replenishment",
    description: "Open vendor-grouped PO drafts and export a styled purchase order workbook after review.",
    status: "Available",
    href: "/purchase-orders",
    cta: "Open PO drafts",
  },
  {
    title: "Dead Stock / Liquidation Plan",
    category: "Cash recovery",
    description: "Export stale-inventory markdown, bundle, wholesale, and write-off recommendations.",
    status: "Available",
    href: "/liquidation",
    cta: "Open liquidation plan",
  },
  {
    title: "Inventory Health Snapshot",
    category: "Analytics",
    description: "See stockout revenue risk, cash trapped, forecast confidence, and health buckets.",
    status: "Available",
    href: "/analytics",
    cta: "Open analytics",
  },
  {
    title: "Supplier Scorecard",
    category: "Suppliers",
    description: "Score vendors after Skubase has purchase order receipt history with expected and received dates.",
    status: "Requires data",
    href: "/suppliers",
    cta: "View suppliers",
  },
  {
    title: "Sample Inventory Risk Snapshot",
    category: "Outbound sample",
    description: "A demo-only example of the snapshot used for cold-email and diagnostic campaigns.",
    status: "Demo/sample",
    href: "/sample-inventory-risk-snapshot",
    cta: "View sample",
  },
  {
    title: "Scheduled Weekly Reports",
    category: "Automation",
    description: "Planned email delivery for recurring inventory summaries. Not active yet.",
    status: "Coming soon",
    href: "/alerts",
    cta: "Configure alerts",
  },
] as const;

export default function ReportsPage() {
  return (
    <div className="reports-page page-stack">
      <section className="section-card">
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Report library</p>
            <h2 className="section-title section-title-small">
              Use the reports already wired into the workflow
            </h2>
            <p className="muted section-copy">
              Skubase keeps reporting close to the action: review the page first, then export when the recommendation is ready.
            </p>
          </div>
        </div>
      </section>

      <section className="reports-grid">
        {reports.map((report) => (
          <article key={report.title} className="report-card">
            <div className="report-card-head">
              <div>
                <p className="section-eyebrow">{report.category}</p>
                <h3>{report.title}</h3>
              </div>
              <span className={`report-status report-status-${statusClass(report.status)}`}>
                {report.status}
              </span>
            </div>
            <p className="report-copy">{report.description}</p>
            <a
              className={`button ${report.status === "Coming soon" ? "button-ghost" : "button-secondary"}`}
              href={report.href}
            >
              {report.cta}
            </a>
          </article>
        ))}
      </section>
    </div>
  );
}

function statusClass(status: string): string {
  return status.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-$/g, "");
}
