"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  ChartPanel,
  ForecastBandChart,
  WeekdayIndexBars,
} from "@/components/charts";
import { GatedFeature } from "@/components/gated-feature";
import { IdentityReviewNotice } from "@/components/identity-review-notice";
import { productRowKey, IDENTITY_REVIEW_MESSAGE, type IdentityIssue } from "@/lib/product-identity";
import {
  fetchForecasts,
  type ForecastResult,
} from "@/lib/api-v2";
import { filterForecasts, forecastNumber, forecastPercent, forecastRiskPercent, forecastView, rankForecastsByStockoutRisk,
  type ForecastQuickView } from "@/lib/forecast-presentation";

export default function ForecastPage() {
  return (
    <GatedFeature
      capability="forecast"
      title="Plan reorders with demand forecasts"
      description="Upgrade to Growth to forecast demand, calculate reorder quantities, and plan replenishment from sales velocity and lead time."
    >
      <ForecastContent />
    </GatedFeature>
  );
}

function ForecastContent() {
  const [forecasts, setForecasts] = useState<ForecastResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [quickView, setQuickView] = useState<ForecastQuickView>("all");
  const [search, setSearch] = useState("");
  const [retry, setRetry] = useState(0);
  const [identityIssues, setIdentityIssues] = useState<IdentityIssue[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchForecasts(controller.signal)
      .then((res) => {
        if (controller.signal.aborted) return;
        if (!Array.isArray(res.forecasts)) throw new Error("Invalid forecast response");
        const rankedForecasts = rankForecastsByStockoutRisk(res.forecasts);
        setForecasts(rankedForecasts);
        setIdentityIssues(res.identity_issues ?? []);
        setSelectedId(rankedForecasts[0] ? productRowKey(rankedForecasts[0]) : null);
        setError(null);
      })
      .catch(() => { if (!controller.signal.aborted) setError("Forecasts could not be loaded. Please try again."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [retry]);

  const visibleForecasts = useMemo(
    () => filterForecasts(forecasts, quickView, search),
    [forecasts, quickView, search],
  );
  const selected = useMemo(
    () => visibleForecasts.find((f) => productRowKey(f) === selectedId) ?? visibleForecasts[0] ?? null,
    [visibleForecasts, selectedId]
  );
  const selectedView = selected ? forecastView(selected) : null;
  const selectedWarnings = selected?.data_quality_warnings?.filter(
    warning => !selectedView?.identityReview || warning !== selected.identity_warning
  ) ?? [];

  if (loading && forecasts.length === 0) {
    return <div className="page-loading">Computing forecasts...</div>;
  }
  if (error) return <div className="empty-state" role="alert"><p className="page-error-copy">{error}</p><button type="button" className="button button-secondary" disabled={loading} onClick={() => setRetry(value => value + 1)}>{loading ? "Retrying…" : "Retry forecasts"}</button></div>;

  if (forecasts.length === 0) {
    return (
      <div className="empty-state">
        <IdentityReviewNotice issues={identityIssues} />
        <p className="empty-state-title">Forecasts need sales history</p>
        <p className="empty-state-copy">
          Import products, inventory, and recent order history before skubase can project demand.
        </p>
        <SalesHistoryLinks />
      </div>
    );
  }

  return (
    <div className="forecast-page">
      <aside className="forecast-list">
        <h3 className="panel-section-title">SKUs</h3>
        <p className="panel-section-subtitle">Highest estimated stockout risk first. Missing history stays unknown.</p>
        <IdentityReviewNotice issues={identityIssues} />
        <label className="forecast-search">
          <span>Search</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search SKU"
          />
        </label>
        <div className="quick-filter-row quick-filter-row-compact">
          {[
            ["all", "All"],
            ["high-risk", "High 30-day risk"],
            ["at-risk", "At risk"],
            ["high-confidence", "High confidence"],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              aria-pressed={quickView === key}
              className={`quick-filter-chip${quickView === key ? " quick-filter-chip-active" : ""}`}
              onClick={() => setQuickView(key as typeof quickView)}
            >
              {label}
            </button>
          ))}
        </div>
        <ul className="sku-list">
          {visibleForecasts.map((f) => { const view = forecastView(f); return (
            <li
              key={productRowKey(f)}
              className={`sku-list-row${
                f === selected ? " sku-list-row-active" : ""
              }`}
            >
              <button
                type="button"
                aria-pressed={f === selected}
                onClick={() => setSelectedId(productRowKey(f))}
                className="sku-list-button"
              >
                <div className="sku-list-name">
                  {f.sku_id}
                </div>
                {view.identityReview ? <span className="muted small">{identityIssues.find(issue => issue.product_id === f.product_id)?.name}</span> : null}
                <div className="sku-list-meta">
                  {view.available ? <span className={`trend-pill trend-${f.trend}`}>{view.noRecentSales ? "No recent sales" : f.trend}</span> : <span className="trend-pill">{view.identityReview ? "Review SKU mapping" : view.missingHistory ? "Sales history needed" : "Forecast status unknown"}</span>}
                  <span
                    className={`risk-pill risk-${
                      view.risk === null || view.noRecentSales ? "unknown" : view.risk > 0.5
                        ? "high"
                        : view.risk > 0.2
                        ? "medium"
                        : "low"
                    }`}
                  >
                    {forecastRiskPercent(view.risk)} estimated risk
                  </span>
                </div>
              </button>
            </li>
          ); })}
        </ul>
        {visibleForecasts.length === 0 ? (
          <div><p className="muted small">No SKUs match this quick view. Forecasts with unknown risk are excluded from risk filters.</p><button type="button" className="button button-secondary button-sm" onClick={() => { setQuickView("all"); setSearch(""); }}>Show all SKUs</button></div>
        ) : null}
      </aside>

      <section className="forecast-detail">
        {selected && selectedView ? (
          <>
            {!selectedView.available ? <div className="empty-state"><p className="empty-state-title">{selectedView.identityReview ? "Review this SKU’s product mapping" : selectedView.missingHistory ? "Sales history is needed for this SKU" : "Forecast availability is unknown"}</p><p className="empty-state-copy">{selectedView.identityReview ? selected.identity_warning || IDENTITY_REVIEW_MESSAGE : selectedView.missingHistory ? "Inventory counts alone do not establish demand, stockout risk, or forecast accuracy. Add dated sales or shipment history before using this SKU in a purchase plan." : "This response does not confirm whether the forecast uses recorded sales. Its numbers are withheld until that can be confirmed."}</p>{selectedView.identityReview ? <Link className="button button-secondary" href="/store-sync">Review source data & sync</Link> : <SalesHistoryLinks />}</div> : selectedView.noRecentSales ? <div className="forecast-warning-list"><p className="forecast-warning">The recorded sales window has no recent sales. Zero estimated demand is not proof that future demand or stockout risk is zero.</p></div> : null}
            {selectedWarnings.length ? <div className="forecast-warning-list" aria-label="Forecast data notes">{selectedWarnings.map(warning => <p key={warning} className="forecast-warning">{warning}</p>)}</div> : null}
            {selectedView.available && selectedView.confidence === "low" && !selectedView.noRecentSales ? <p className="forecast-warning">Low confidence: short or sparse sales history can make risk estimates uncertain. Review the recorded demand before a large purchase.</p> : null}
            <div className="forecast-kpis">
              <Kpi label="30-day demand" value={forecastNumber(selectedView.demand30)} />
              <Kpi label="60-day demand" value={forecastNumber(selectedView.demand60)} />
              <Kpi label="90-day demand" value={forecastNumber(selectedView.demand90)} />
              <Kpi
                label="Estimated stockout risk (30d)"
                value={forecastRiskPercent(selectedView.risk)}
                tone={
                  selectedView.risk === null || selectedView.noRecentSales ? "neutral" : selectedView.risk > 0.5
                    ? "negative"
                    : selectedView.risk > 0.2
                    ? "neutral"
                    : "positive"
                }
              />
              <Kpi label="Confidence" value={selectedView.confidence} />
              <Kpi
                label="14-day backtest error"
                value={forecastPercent(selectedView.error)}
                tone={
                  selectedView.error !== null && selectedView.error <= 0.3
                    ? "positive"
                    : selectedView.error !== null && selectedView.error > 0.6
                    ? "negative"
                    : "neutral"
                }
              />
              <Kpi
                label="Bias"
                value={selectedView.bias}
              />
              <Kpi label="Recorded history" value={selectedView.history} />
              <Kpi label="Method" value={
                !selectedView.available ? "Unavailable" : selected.method === "holt_double_exponential" ? "Holt DES"
                : selected.method === "moving_average" ? "Moving avg"
                : selected.method.replace(/_/g, " ")
              } />
            </div>
            <p className="muted small">Backtest error averages each day’s absolute prediction error divided by the larger of actual sales and one unit. It can exceed 100%. Unknown means no valid percentage comparison is available.</p>

            {selectedView.available ? <section className="planning-preview-grid">
              <PlanningCard
                title="Demand Plan"
                label="Next 90 days"
                value={`${forecastNumber(selectedView.demand90)} units`}
                note={`30d ${forecastNumber(selectedView.demand30)} / 60d ${forecastNumber(selectedView.demand60)} / 90d ${forecastNumber(selectedView.demand90)}`}
              />
              <PlanningCard
                title="Replenishment Signal"
                label="Estimated 30-day stockout risk"
                value={forecastRiskPercent(selectedView.risk)}
                note="Use purchase orders for quantity and supplier grouping."
              />
            </section> : null}

            {selectedView.available ? <ChartPanel
              title={`Forecast - ${selected.sku_id}`}
              subtitle={selected.explain}
              accent="primary"
            >
              <ForecastBandChart points={selected.points} />
            </ChartPanel> : null}

            {selectedView.available ? <ExplainCard selected={selected} /> : null}

            {selectedView.available && selected.weekly_index.length > 0 ? (
              <ChartPanel
                title="Weekly seasonality"
                subtitle={`Detected pattern: ${selected.seasonality.replace("_", " ")}`}
              >
                <WeekdayIndexBars index={selected.weekly_index} />
              </ChartPanel>
            ) : null}
          </>
        ) : (
          <p className="muted">{visibleForecasts.length ? "Select a SKU on the left." : "Clear the quick view or search to select a forecast."}</p>
        )}
      </section>
    </div>
  );
}

function SalesHistoryLinks() {
  return <div className="button-row"><Link className="button button-secondary" href="/store-sync">Review Shopify order sync</Link><Link className="button button-secondary" href="/import-shipstation">Import non-Shopify shipments</Link></div>;
}

function Kpi({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "positive" | "negative" | "neutral";
}) {
  return (
    <div className={`kpi-card kpi-tone-${tone}`}>
      <p className="kpi-label">{label}</p>
      <p className="kpi-value">{value}</p>
    </div>
  );
}

function PlanningCard({
  title,
  label,
  value,
  note,
}: {
  title: string;
  label: string;
  value: string;
  note: string;
}) {
  return (
    <article className="planning-card">
      <span>{title}</span>
      <p>{label}</p>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}

function ExplainCard({ selected }: { selected: ForecastResult }) {
  const [open, setOpen] = useState(false);
  const view = forecastView(selected);
  return (
    <section className={`explain-card${open ? " explain-card-open" : ""}`}>
      <button
        type="button"
        className="explain-card-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="explain-card-icon" aria-hidden>?</span>
        <span className="explain-card-toggle-text">
          Why this number? Show the forecasting math.
        </span>
        <span className="explain-card-chevron" aria-hidden>
          {open ? "v" : ">"}
        </span>
      </button>
      {open ? (
        <div className="explain-card-body">
          <p className="explain-card-lead">
            {selected.method === "naive" || selected.method === "moving_average"
              ? "This estimate uses a simple average because the recorded history cannot support a stronger trend or seasonal model."
              : "This estimate smooths recorded demand and applies the detected weekly pattern. Short or sparse history reduces confidence."}
          </p>
          <dl className="explain-card-grid">
            <div><dt>Method</dt><dd>{selected.method.replace(/_/g, " ")}</dd></div>
            <div><dt>Confidence</dt><dd>{view.confidence}</dd></div>
            <div><dt>Seasonality</dt><dd>{selected.seasonality.replace(/_/g, " ")}</dd></div>
            <div><dt>Estimated 30-day stockout risk</dt><dd>{forecastRiskPercent(view.risk)}</dd></div>
          </dl>
          <p className="explain-card-explain">{selected.explain}</p>
          {selected.trust_reasons?.length ? (
            <div className="forecast-warning-list">
              {selected.trust_reasons.map((reason) => (
                <p key={reason} className="forecast-warning">
                  {reason}
                </p>
              ))}
            </div>
          ) : null}
          {selected.adjusted_stockout_days ? (
            <p className="explain-card-footnote">
              Adjusted {selected.adjusted_stockout_days} recent zero-sales days because the SKU appears stockout-limited.
            </p>
          ) : null}
          <p className="explain-card-footnote">
            Use this detail when you want to audit why Skubase ranked the SKU.
          </p>
        </div>
      ) : null}
    </section>
  );
}
