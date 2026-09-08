"use client";

import { useEffect, useState } from "react";
import { IdentityReviewNotice } from "@/components/identity-review-notice";
import type { IdentityIssue } from "@/lib/product-identity";

import {
  currency,
  fetchLiquidation,
  type LiquidationSuggestion,
} from "@/lib/api-v2";
import { exportLiquidationReport } from "@/lib/report-export";
import { financialValue, financialTotal } from "@/lib/financial-values";

const TACTIC_LABELS: Record<LiquidationSuggestion["tactic"], string> = {
  markdown: "Markdown",
  bundle: "Bundle",
  wholesale: "Wholesale",
  donate_write_off: "Write-off",
};
const NEVER_SOLD_DAYS = 999;

export default function LiquidationPage() {
  const [suggestions, setSuggestions] = useState<LiquidationSuggestion[]>([]);
  const [identityIssues, setIdentityIssues] = useState<IdentityIssue[]>([]);
  const [totalRecoverable, setTotalRecoverable] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchLiquidation(controller.signal)
      .then((r) => {
        setSuggestions(r.suggestions);
        setIdentityIssues(r.identity_issues ?? []);
        setTotalRecoverable(financialValue(r, "total_capital_recoverable", r.total_capital_recoverable));
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  if (loading && suggestions.length === 0) {
    return <div className="page-loading">Generating liquidation plan…</div>;
  }
  if (error) return <p className="page-error-copy">{error}</p>;

  if (suggestions.length === 0) {
    return (
      <div className="page-stack">
        <IdentityReviewNotice issues={identityIssues} />
        <div className="empty-state">
        <p className="empty-state-title">No recovery recommendations</p>
        <p className="empty-state-copy">
          No safely matched SKU with sufficient sales history currently qualifies for a recovery plan.
        </p>
        </div>
      </div>
    );
  }

  const capitalTiedUp = financialTotal(suggestions.map(s => financialValue(s, "capital_tied_up", s.capital_tied_up)));
  const missingCostCount = suggestions.filter(s => s.financial_values_known === false).length;

  return (
    <div className="liquidation-page">
      <IdentityReviewNotice issues={identityIssues} />
      {missingCostCount > 0 && <p className="section-copy">{missingCostCount} SKU{missingCostCount === 1 ? " needs" : "s need"} recorded unit costs before Skubase can suggest a markdown or estimate recovery. Review these items and add costs before choosing a clearance price.</p>}
      <div className="liquidation-summary">
        <div className="kpi-card kpi-tone-negative">
          <p className="kpi-label">Capital in this plan</p>
          <p className="kpi-value">{currency(capitalTiedUp)}</p>
        </div>
        <div className="kpi-card kpi-tone-positive">
          <p className="kpi-label">Projected recovery</p>
          <p className="kpi-value">{currency(totalRecoverable)}</p>
        </div>
        <div className="kpi-card">
          <p className="kpi-label">SKUs in this plan</p>
          <p className="kpi-value">{suggestions.length}</p>
        </div>
      </div>
      <div className="button-row">
        <button
          type="button"
          className="button button-primary"
          onClick={() => exportLiquidationReport(suggestions)}
        >
          Export styled plan
        </button>
      </div>

      <div className="liquidation-grid">
        {suggestions.map((s) => (
          <div key={s.sku_id} className={`liquidation-card tactic-${s.tactic}`}>
            <div className="liquidation-head">
              <h4 className="liquidation-name">{s.name}</h4>
              <span className={`tactic-pill tactic-pill-${s.tactic}`}>
                {s.financial_values_known === false ? "Add unit costs" : TACTIC_LABELS[s.tactic]}
              </span>
            </div>
            <div className="liquidation-stats">
              <Stat label="On hand" value={s.on_hand.toString()} />
              <Stat
                label={s.days_since_last_sale >= NEVER_SOLD_DAYS ? "Sales age" : "Days stale"}
                value={
                  s.days_since_last_sale >= NEVER_SOLD_DAYS
                    ? "No sales"
                    : `${s.days_since_last_sale}d`
                }
              />
              <Stat
                label="Markdown"
                value={financialValue(s, "suggested_markdown_pct", s.suggested_markdown_pct) === null ? "Unknown" : `${financialValue(s, "suggested_markdown_pct", s.suggested_markdown_pct)!.toFixed(0)}%`}
              />
              <Stat
                label="Suggested price"
                value={currency(financialValue(s, "suggested_price", s.suggested_price))}
              />
              <Stat
                label="Capital stuck"
                value={currency(financialValue(s, "capital_tied_up", s.capital_tied_up))}
              />
              <Stat
                label="Projected recovery"
                value={currency(financialValue(s, "projected_recovered_capital", s.projected_recovered_capital))}
                tone="positive"
              />
            </div>
            <p className="liquidation-rationale">{s.rationale}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "positive" | "neutral";
}) {
  return (
    <div className={`liquidation-stat tone-${tone}`}>
      <p className="liquidation-stat-label">{label}</p>
      <p className="liquidation-stat-value">{value}</p>
    </div>
  );
}
