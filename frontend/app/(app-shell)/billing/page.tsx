import { SectionCard } from "@/components/section-card";

export default function BillingPage() {
  return (
    <div className="page-stack">
      <div className="content-grid content-grid-2-1">
        <SectionCard>
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">Current Plan</p>
              <h2 className="section-title">Growth</h2>
            </div>
            <span className="status-badge status-succeeded">Active</span>
          </div>

          <div className="plan-card">
            <strong className="plan-price">$299/mo</strong>
            <p className="section-copy">
              Placeholder billing surface for the current MVP. The production
              product can expand plan, seat, and usage controls here later.
            </p>
          </div>

          <div className="button-row">
            <button type="button" className="button button-primary">
              Upgrade plan
            </button>
            <button type="button" className="button button-secondary">
              Contact sales
            </button>
          </div>
        </SectionCard>

        <SectionCard>
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">Payment Method</p>
              <h2 className="section-title section-title-small">Billing profile</h2>
            </div>
          </div>
          <div className="signal-list">
            <div className="signal-item">
              <div>
                <p className="signal-title">Visa ending in 4242</p>
                <p className="signal-copy">Placeholder card on file</p>
              </div>
            </div>
            <div className="signal-item">
              <div>
                <p className="signal-title">Billing email</p>
                <p className="signal-copy">finance@store.com</p>
              </div>
            </div>
          </div>
        </SectionCard>
      </div>

      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Invoices</p>
            <h2 className="section-title section-title-small">Recent billing history</h2>
          </div>
        </div>

        <div className="signal-list">
          {[
            ["Mar 2026", "$299.00", "Paid"],
            ["Feb 2026", "$299.00", "Paid"],
            ["Jan 2026", "$299.00", "Paid"]
          ].map(([month, amount, status]) => (
            <div key={month} className="signal-item">
              <div>
                <p className="signal-title">{month}</p>
                <p className="signal-copy">Invoice placeholder</p>
              </div>
              <div className="signal-right">
                <strong>{amount}</strong>
                <span className="status-badge status-succeeded">{status}</span>
              </div>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}
