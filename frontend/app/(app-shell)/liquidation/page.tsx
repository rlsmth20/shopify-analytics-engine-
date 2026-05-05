"use client";

import { useEffect, useState } from "react";

import {
  currency,
  fetchLiquidation,
  type LiquidationSuggestion,
} from "@/lib/api-v2";

const TACTIC_LABELS: Record<LiquidationSuggestion["tactic"], string> = {
  markdown: "Markdown",
  bundle: "Bundle",
  wholesale: "Wholesale",
  donate_write_off: "Write-off",
};
const NEVER_SOLD_DAYS = 999;

export default function LiquidationPage() {
  const [suggestions, setSuggestions] = useState<LiquidationSuggestion[]>([]);
  const [totalRecoverable, setTotalRecoverable] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchLiquidation(controller.signal)
      .then((r) => {
        setSuggestions(r.suggestions);
        setTotalRecoverable(r.total_capital_recoverable);
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
      <div className="empty-state">
        <p className="empty-state-title">No stale inventory to clear</p>
        <p className="empty-state-copy">
          Nothing has crossed the dead-stock threshold yet.
        </p>
      </div>
    );
  }

  const capitalTiedUp = suggestions.reduce(
    (s, x) => s + x.capital_tied_up,
    0
  );

  return (
    <div className="liquidation-page">
      <div className="liquidation-summary">
        <div className="kpi-card kpi-tone-negative">
          <p className="kpi-label">Capital stuck</p>
          <p className="kpi-value">{currency(capitalTiedUp)}</p>
        </div>
        <div className="kpi-card kpi-tone-positive">
          <p className="kpi-label">Capital recoverable</p>
          <p className="kpi-value">{currency(totalRecoverable)}</p>
        </div>
        <div className="kpi-card">
          <p className="kpi-label">Dead SKUs</p>
          <p className="kpi-value">{suggestions.length}</p>
        </div>
      </div>

      <div className="liquidation-grid">
        {suggestions.map((s) => (
          <div key={s.sku_id} className={`liquidation-card tactic-${s.tactic}`}>
            <div className="liquidation-head">
              <h4 className="liquidation-name">{s.name}</h4>
              <span className={`tactic-pill tactic-pill-${s.tactic}`}>
                {TACTIC_LABELS[s.tactic]}
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
                value={`${s.suggested_markdown_pct.toFixed(0)}%`}
              />
              <Stat
                label="Suggested price"
                value={currency(s.suggested_price)}
              />
              <Stat
                label="Capital stuck"
                value={currency(s.capital_tied_up)}
              />
              <Stat
                label="Projected recovery"
                value={currency(s.projected_recovered_capital)}
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
