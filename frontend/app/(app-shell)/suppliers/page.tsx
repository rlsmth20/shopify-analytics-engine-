"use client";

import { useEffect, useState } from "react";

import { fetchSuppliers, type SupplierScorecard } from "@/lib/api-v2";

export default function SuppliersPage() {
  const [vendors, setVendors] = useState<SupplierScorecard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchSuppliers(controller.signal)
      .then((r) => setVendors(r.vendors))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  if (loading && vendors.length === 0) {
    return <div className="page-loading">Scoring suppliers…</div>;
  }
  if (error) return <p className="page-error-copy">{error}</p>;

  if (vendors.length === 0) {
    return (
      <div className="empty-state">
        <p className="empty-state-title">Supplier performance needs receipt history</p>
        <p className="empty-state-copy">
          Vendor names come from Shopify product data. On-time rate, fill rate, lead variance,
          and cost stability need purchase order and receiving observations before skubase can
          score suppliers honestly.
        </p>
      </div>
    );
  }

  return (
    <div className="suppliers-page">
      <div className="tier-summary">
        <TierBox
          tier="preferred"
          count={vendors.filter((v) => v.tier === "preferred").length}
        />
        <TierBox
          tier="acceptable"
          count={vendors.filter((v) => v.tier === "acceptable").length}
        />
        <TierBox
          tier="at_risk"
          count={vendors.filter((v) => v.tier === "at_risk").length}
        />
      </div>

      <div className="suppliers-grid">
        {vendors.map((v) => (
          <div key={v.vendor} className={`supplier-card tier-${v.tier}`}>
            <div className="supplier-card-head">
              <div>
                <h4 className="supplier-name">{v.vendor}</h4>
                <p className="supplier-meta">
                  {v.sku_count} SKUs · {v.avg_lead_time_days.toFixed(1)}d avg lead
                </p>
              </div>
              <div className="score-ring" data-score={v.overall_score}>
                <svg width="64" height="64" viewBox="0 0 64 64">
                  <circle cx="32" cy="32" r="28" className="score-ring-bg" />
                  <circle
                    cx="32"
                    cy="32"
                    r="28"
                    className={`score-ring-fg tier-${v.tier}`}
                    strokeDasharray={`${(v.overall_score / 100) * 175.93} 175.93`}
                    transform="rotate(-90 32 32)"
                  />
                </svg>
                <span className="score-ring-value">{v.overall_score.toFixed(0)}</span>
              </div>
            </div>
            <div className="supplier-metrics">
              <Metric label="On-time" value={`${v.on_time_pct.toFixed(0)}%`} />
              <Metric label="Fill rate" value={`${v.fill_rate_pct.toFixed(0)}%`} />
              <Metric
                label="Lead variance"
                value={`±${v.lead_time_variance_days.toFixed(1)}d`}
              />
              <Metric
                label="Cost stability"
                value={`${v.cost_stability_score.toFixed(0)}%`}
              />
            </div>
            <ul className="supplier-notes">
              {v.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

function TierBox({
  tier,
  count,
}: {
  tier: "preferred" | "acceptable" | "at_risk";
  count: number;
}) {
  const labels = {
    preferred: "Preferred",
    acceptable: "Acceptable",
    at_risk: "At risk",
  };
  return (
    <div className={`tier-box tier-${tier}`}>
      <p className="tier-box-count">{count}</p>
      <p className="tier-box-label">{labels[tier]}</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="supplier-metric">
      <p className="supplier-metric-label">{label}</p>
      <p className="supplier-metric-value">{value}</p>
    </div>
  );
}
