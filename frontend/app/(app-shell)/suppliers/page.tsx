"use client";

import { useEffect, useState } from "react";

import { DataQualityNote } from "@/components/data-quality-note";
import { GatedFeature } from "@/components/gated-feature";
import { fetchSuppliers, type SupplierScorecard } from "@/lib/api-v2";
import { exportFormattedReport } from "@/lib/report-export";

export default function SuppliersPage() {
  return (
    <GatedFeature
      capability="supplier_scorecards"
      title="Measure supplier performance"
      description="Upgrade to Scale to unlock supplier scorecards when PO receipt history is available."
    >
      <SuppliersContent />
    </GatedFeature>
  );
}

function SuppliersContent() {
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
    return <div className="page-loading">Scoring suppliers...</div>;
  }
  if (error) return <p className="page-error-copy">{error}</p>;

  if (vendors.length === 0) {
    return (
      <DataQualityNote
        title="Supplier scorecards need purchase order receipt history"
        actions={
          <>
            <a className="button button-secondary" href="/purchase-orders">
              Open purchase orders
            </a>
            <a className="button button-ghost" href="/lead-time-settings">
              Set lead times
            </a>
          </>
        }
      >
        <p>
          Supplier names come from Shopify product data, but on-time rate, fill rate,
          lead-time variance, and cost stability require expected and received dates.
          Import PO history or keep using the reorder workflow to build supplier
          performance data.
        </p>
      </DataQualityNote>
    );
  }

  function exportScorecards() {
    const tierTone = (tier: SupplierScorecard["tier"]) =>
      tier === "preferred" ? ("good" as const) : tier === "at_risk" ? ("danger" as const) : null;
    void exportFormattedReport({
      title: "Supplier Scorecards",
      subtitle:
        "On-time delivery, fill rate, lead-time stability, and cost stability per supplier, built from purchase order receipt history.",
      filename: `skubase-supplier-scorecards-${new Date().toISOString().slice(0, 10)}.xlsx`,
      detailSheetName: "Suppliers",
      kpis: [
        { label: "Suppliers", value: String(vendors.length) },
        {
          label: "Preferred",
          value: String(vendors.filter((v) => v.tier === "preferred").length),
          tone: "good",
        },
        {
          label: "At risk",
          value: String(vendors.filter((v) => v.tier === "at_risk").length),
          tone: "danger",
        },
        {
          label: "Avg on-time",
          value: vendors.length
            ? `${(vendors.reduce((sum, v) => sum + v.on_time_pct, 0) / vendors.length).toFixed(0)}%`
            : "-",
        },
      ],
      charts: [
        {
          title: "Overall score by supplier",
          points: [...vendors]
            .sort((l, r) => r.overall_score - l.overall_score)
            .slice(0, 8)
            .map((v) => ({
              label: v.vendor,
              value: v.overall_score,
              display: v.overall_score.toFixed(0),
              tone: tierTone(v.tier) ?? "neutral",
            })),
        },
      ],
      todos: [
        { label: "Review at-risk suppliers", detail: "Slipping lead times and fill rates feed directly into stockouts.", tone: "danger" },
        { label: "Shift volume toward preferred suppliers", detail: "Reward consistent on-time delivery with bigger orders.", tone: "good" },
        { label: "Keep recording receipts", detail: "Every received PO sharpens these scores.", tone: "neutral" },
      ],
      tableTitle: "Supplier Scorecards",
      rows: vendors,
      columns: [
        { key: "vendor", label: "Supplier", width: 30, format: (v) => v.vendor },
        {
          key: "tier",
          label: "Tier",
          width: 13,
          format: (v) => v.tier.replace("_", " "),
          tone: (v) => tierTone(v.tier),
        },
        {
          key: "score",
          label: "Score",
          align: "right",
          width: 10,
          format: (v) => v.overall_score.toFixed(0),
          numericValue: (v) => v.overall_score,
          numFmt: "#,##0",
          tone: (v) => (v.overall_score >= 80 ? "good" : v.overall_score < 60 ? "danger" : null),
        },
        {
          key: "skus",
          label: "SKUs",
          align: "right",
          width: 9,
          format: (v) => String(v.sku_count),
          numericValue: (v) => v.sku_count,
          numFmt: "#,##0",
          summarize: "sum",
        },
        {
          key: "onTime",
          label: "On-time",
          align: "right",
          width: 11,
          format: (v) => `${v.on_time_pct.toFixed(0)}%`,
          numericValue: (v) => v.on_time_pct / 100,
          numFmt: "0%",
          tone: (v) => (v.on_time_pct < 80 ? "danger" : null),
        },
        {
          key: "fillRate",
          label: "Fill rate",
          align: "right",
          width: 11,
          format: (v) => `${v.fill_rate_pct.toFixed(0)}%`,
          numericValue: (v) => v.fill_rate_pct / 100,
          numFmt: "0%",
        },
        {
          key: "leadTime",
          label: "Avg lead (d)",
          align: "right",
          width: 13,
          format: (v) => v.avg_lead_time_days.toFixed(1),
          numericValue: (v) => v.avg_lead_time_days,
          numFmt: "0.0",
        },
        {
          key: "leadVar",
          label: "Lead variance (d)",
          align: "right",
          width: 17,
          format: (v) => v.lead_time_variance_days.toFixed(1),
          numericValue: (v) => v.lead_time_variance_days,
          numFmt: "0.0",
          tone: (v) => (v.lead_time_variance_days > 7 ? "warning" : null),
        },
        {
          key: "costStability",
          label: "Cost stability",
          align: "right",
          width: 14,
          format: (v) => `${v.cost_stability_score.toFixed(0)}%`,
          numericValue: (v) => v.cost_stability_score / 100,
          numFmt: "0%",
        },
        {
          key: "notes",
          label: "Notes",
          width: 50,
          format: (v) => v.notes.join(" "),
        },
      ],
    });
  }

  return (
    <div className="suppliers-page">
      <div className="button-row" style={{ justifyContent: "flex-end", marginBottom: "12px" }}>
        <button type="button" className="button button-secondary" onClick={exportScorecards}>
          Export styled Excel
        </button>
      </div>
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
                  {v.sku_count} SKUs - {v.avg_lead_time_days.toFixed(1)}d avg lead
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
                value={`+/-${v.lead_time_variance_days.toFixed(1)}d`}
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
