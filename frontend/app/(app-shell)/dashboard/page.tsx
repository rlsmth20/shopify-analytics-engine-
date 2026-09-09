"use client";

import Link from "next/link";

import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-guard";
import { workspaceStorageKey } from "@/lib/browser-session";
import { BrowserHealthCheckOption } from "@/components/browser-health-check-option";
import { IdentityReviewNotice } from "@/components/identity-review-notice";
import { trackGrowthEvent } from "@/lib/analytics";
import {
  AreaLineChart,
  ChartPanel,
  DivergingBarChart,
  DonutChart,
  HorizontalBarChart,
} from "@/components/charts";
import {
  currency,
  fetchDashboard,
  type DashboardResponse,
  type DashboardSeriesPoint,
} from "@/lib/api-v2";
import { dashboardKpiNote, formatDashboardMoney, formatForecastVariance, labelRevenueDays } from "@/lib/dashboard-presentation";
import { knownPointValue } from "@/lib/financial-values";
import styles from "./dashboard.module.css";

const ONBOARDING_STORAGE_KEY = "skubase_stocky_migration_steps";
const ONBOARDING_DISMISSED_KEY = "skubase_dashboard_onboarding_dismissed";
const ACTION_PATH_STEPS = [
  {
    step: "1",
    title: "Review top stockout risk",
    body: "Start with the SKUs most likely to run short or miss demand.",
    href: "/actions",
  },
  {
    step: "2",
    title: "Review reorder recommendations",
    body: "Turn urgent replenishment signals into supplier-grouped PO drafts.",
    href: "/purchase-orders",
  },
  {
    step: "3",
    title: "Review dead-stock recovery",
    body: "Find stale inventory tying up cash and pick the next clearance move.",
    href: "/liquidation",
  },
  {
    step: "4",
    title: "Check supplier and lead-time issues",
    body: "Confirm the lead times Skubase uses before trusting reorder math.",
    href: "/lead-time-settings",
  },
  {
    step: "5",
    title: "Configure an alert",
    body: "Let rules watch the queue so stockout and dead-stock risk reaches you sooner.",
    href: "/alerts",
  },
] as const;
const ONBOARDING_STEPS = [
  { id: "connect-shopify", label: "Review Shopify access & sync", href: "/store-sync" },
  { id: "upload-stocky", label: "Import current inventory", href: "/import-stocky" },
  { id: "lead-times", label: "Set lead times", href: "/lead-time-settings" },
  { id: "forecast-review", label: "Review forecast trust", href: "/forecast" },
  { id: "purchase-orders", label: "Save first PO", href: "/purchase-orders" },
] as const;

export default function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshAttempt, setRefreshAttempt] = useState(0);
  const [completedOnboardingSteps, setCompletedOnboardingSteps] = useState<string[]>([]);
  const [onboardingDismissed, setOnboardingDismissed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchDashboard(controller.signal)
      .then((res) => {
        setData(res);
        setError(null);
      })
      .catch((e) => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [refreshAttempt, user.id, user.shop_id]);

  useEffect(() => {
    if (data && !loading && !error) void trackGrowthEvent("INVENTORY_ANALYSIS_VIEWED");
  }, [data, loading, error]);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(workspaceStorageKey(ONBOARDING_STORAGE_KEY, user));
      setCompletedOnboardingSteps(parseCompletedOnboardingSteps(stored));
      setOnboardingDismissed(
        window.localStorage.getItem(workspaceStorageKey(ONBOARDING_DISMISSED_KEY, user)) === "1"
      );
    } catch {
      setCompletedOnboardingSteps([]);
      setOnboardingDismissed(false);
    }
  }, [user.id, user.shop_id]);

  if (loading && !data) {
    return <div className="page-loading">Loading command center…</div>;
  }

  if (error) {
    return (
      <div className="page-error">
        <p className="page-error-title">Could not load dashboard</p>
        <p className="page-error-copy">{error}</p>
        <button type="button" className="button button-primary" onClick={() => setRefreshAttempt((previous) => previous + 1)} disabled={loading}>{loading ? "Retrying…" : "Try again"}</button>
        <BrowserHealthCheckOption />
      </div>
    );
  }

  if (!data) return null;

  // Empty-state: a brand-new shop with no imported data. Every chart array
  // is empty when the backend has no rows to aggregate. Show an explicit
  // import CTA instead of empty charts that look broken.
  const hasNoData =
    data.revenue_trend_30d.length === 0 &&
    data.stock_health_breakdown.length === 0 &&
    data.top_movers.length === 0;

  if (hasNoData) {
    return (
      <div className="dashboard-empty">
        <div className="dashboard-empty-card">
          <p className="dashboard-empty-eyebrow">Welcome to skubase</p>
          <h2 className="dashboard-empty-title">Add inventory to start planning.</h2>
          <p className="dashboard-empty-copy">
            Planning needs current stock, recent sales, and supplier lead times.
            Import current inventory from Stocky and non-Shopify shipment history from ShipStation
            using matching SKUs. Skubase is in Shopify App Store review and is not listed yet;
            Shopify order history requires sync for a store with existing approved access.
          </p>
          <BrowserHealthCheckOption />
          <IdentityReviewNotice issues={data.identity_issues} />
          <div className="dashboard-empty-steps">
            <Link href="/store-sync" className="dashboard-empty-step">
              <span className="dashboard-empty-step-num">1</span>
              <div><p className="dashboard-empty-step-title">Shopify access & sync</p><p className="dashboard-empty-step-body">Review access options, or sync inventory and orders if Skubase is already installed for your store.</p></div>
              <span aria-hidden>→</span>
            </Link>
            <Link href="/import-stocky" className="dashboard-empty-step">
              <span className="dashboard-empty-step-num">2</span>
              <div>
                <p className="dashboard-empty-step-title">Import current inventory</p>
                <p className="dashboard-empty-step-body">Stocky’s Inventory On Hand export supplies your catalog and stock quantities, not sales history.</p>
              </div>
              <span aria-hidden>→</span>
            </Link>
            <Link href="/import-shipstation" className="dashboard-empty-step">
              <span className="dashboard-empty-step-num">3</span>
              <div>
                <p className="dashboard-empty-step-title">Import non-Shopify shipment history</p>
                <p className="dashboard-empty-step-body">ShipStation supplies demand from non-Shopify channels. Match its SKUs to your inventory; Shopify orders come through approved Shopify sync.</p>
              </div>
              <span aria-hidden>→</span>
            </Link>
            <Link href="/lead-time-settings" className="dashboard-empty-step">
              <span className="dashboard-empty-step-num">4</span>
              <div>
                <p className="dashboard-empty-step-title">Set lead times</p>
                <p className="dashboard-empty-step-body">Global default + supplier overrides - drives every reorder calculation.</p>
              </div>
              <span aria-hidden>→</span>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const revenueDays = labelRevenueDays(data.revenue_trend_30d, data.generated_at);
  const knownSupplierCapital = data.cash_at_risk_by_vendor.flatMap((point) => {
    const value = knownPointValue(point);
    return value === null ? [] : [{ ...point, value }];
  });
  const suppliersMissingCosts = data.cash_at_risk_by_vendor.length - knownSupplierCapital.length;

  return (
    <div className={`dashboard ${styles.dashboard}`}>
      <IdentityReviewNotice issues={data.identity_issues} />
      <section className="dashboard-kpis">
        {data.kpis.map((kpi) => (
          <div key={kpi.label} className={`kpi-card kpi-tone-${kpi.tone}`}>
            <p className="kpi-label">{kpi.label}</p>
            <div className="kpi-value-row">
              <p className="kpi-value">
                {knownPointValue(kpi) === null ? "Unknown" : kpi.unit === "currency"
                  ? currency(knownPointValue(kpi))
                  : kpi.unit === "percent"
                  ? `${kpi.value.toFixed(1)}%`
                  : kpi.unit === "days"
                  ? `${kpi.value.toLocaleString()} days`
                  : kpi.value.toLocaleString()}
              </p>
              {knownPointValue(kpi) !== null && kpi.delta_pct !== null ? (
                <span
                  className={`kpi-delta kpi-delta-${
                    kpi.delta_pct >= 0
                      ? kpi.tone === "negative"
                        ? "down"
                        : "up"
                      : kpi.tone === "negative"
                      ? "up"
                      : "down"
                  }`}
                >
                  {kpi.delta_pct >= 0 ? "+" : "-"}
                  {Math.abs(kpi.delta_pct).toFixed(1)}%
                </span>
              ) : null}
            </div>
            <p className={styles.kpiNote}>{knownPointValue(kpi) === null ? data.identity_issues?.length ? "Review product mapping and any missing unit costs before using this total" : "Add missing unit costs to calculate this total" : dashboardKpiNote(kpi.label)}</p>
          </div>
        ))}
      </section>

      <section className={`section-card action-path-card${user.id === 0 ? " action-path-demo" : ""}`}>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">{user.id === 0 ? "Demo path" : "Start here"}</p>
            <h2 className="section-title section-title-small">
              Start with your highest-impact Action Queue items
            </h2>
            <p className="muted section-copy">
              Work these in order to see how Skubase turns inventory data into a focused weekly plan.
            </p>
          </div>
          <Link className="button button-secondary" href="/actions">
            Open action queue
          </Link>
        </div>
        <div className="action-path-grid">
          {ACTION_PATH_STEPS.map((item) => (
            <Link key={item.step} href={item.href} className="action-path-step">
              <span className="today-step">{item.step}</span>
              <span>
                <strong>{item.title}</strong>
                <small>{item.body}</small>
              </span>
            </Link>
          ))}
        </div>
      </section>

      {!onboardingDismissed ? (
        <section className="section-card">
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">Setup progress</p>
              <h2 className="section-title section-title-small">
                Finish the workflow that turns analytics into orders
              </h2>
              <p className="muted section-copy">
                These are the remaining setup moves most likely to make the
                dashboard actionable for day-to-day buying.
              </p>
            </div>
            <div className="button-row">
              <Link className="button button-primary" href="/stocky-migration">
                Open checklist
              </Link>
              <button
                type="button"
                className="button button-ghost"
                onClick={() => {
                  try { window.localStorage.setItem(workspaceStorageKey(ONBOARDING_DISMISSED_KEY, user), "1"); } catch { /* Optional preference. */ }
                  setOnboardingDismissed(true);
                }}
              >
                Dismiss
              </button>
            </div>
          </div>
          <div className="signal-list">
            {ONBOARDING_STEPS.map((step) => {
              const complete = completedOnboardingSteps.includes(step.id);
              return (
                <Link key={step.id} className="signal-item" href={step.href}>
                  <div>
                    <p className="signal-title">{step.label}</p>
                    <p className="muted small">
                      {complete ? "Complete" : "Recommended next action"}
                    </p>
                  </div>
                  <span className={`po-status po-status-${complete ? "received" : "ready"}`}>
                    {complete ? "done" : "next"}
                  </span>
                </Link>
              );
            })}
          </div>
        </section>
      ) : null}

      <section className="dashboard-grid">
        <ChartPanel
          className="col-8"
          title="Revenue · last 30 days"
          subtitle="Recorded daily order revenue · USD · completed UTC days"
          accent="primary"
        >
          <div className={styles.revenuePlot}>
            <AreaLineChart
              points={revenueDays}
              height={240}
              yFormatter={formatDashboardMoney}
              label="Daily order revenue in USD"
            />
          </div>
          <SeriesTable points={revenueDays} caption="Recorded revenue by day (UTC)" nameLabel="Date" valueLabel="Revenue (USD)" formatter={formatDashboardMoney} />
        </ChartPanel>

        <ChartPanel
          className="col-4"
          title="Stock health"
          subtitle="Where every SKU sits today"
        >
          <DonutChart
            points={data.stock_health_breakdown}
            centerLabel="SKUs"
            centerValue={data.stock_health_breakdown
              .reduce((s, p) => s + p.value, 0)
              .toLocaleString()}
          />
        </ChartPanel>

        <ChartPanel
          className="col-8"
          title="Best sellers · revenue contribution"
          subtitle="Top 8 by units sold · 30-day sales at current prices (USD)"
          accent="success"
        >
          <HorizontalBarChart
            points={data.top_movers.slice(0, 8)}
            valueFormatter={currency}
          />
          <SeriesTable points={data.top_movers.slice(0, 8)} caption="Revenue from best-selling SKUs" nameLabel="Product" valueLabel="Revenue (USD)" formatter={formatDashboardMoney} />
        </ChartPanel>

        <ChartPanel
          className="col-4"
          title="ABC distribution"
          subtitle="Number of SKUs in each revenue-based ABC class"
          footer="A, B and C group products by revenue contribution. The counts show catalog mix, not each class’s share of revenue."
        >
          <DonutChart
            points={data.abc_distribution}
            centerLabel="SKUs"
            centerValue={data.abc_distribution
              .reduce((s, p) => s + p.value, 0)
              .toLocaleString()}
          />
        </ChartPanel>

        <ChartPanel
          className="col-8"
          title="Cash parked by supplier"
          subtitle="Optimize + dead-stock capital at cost · top 6 suppliers · USD"
          accent="warning"
        >
          <HorizontalBarChart
            points={knownSupplierCapital}
            valueFormatter={currency}
            barClassName="chart-hbar chart-hbar-warning"
          />
          {suppliersMissingCosts > 0 && <p className={styles.kpiNote}>{suppliersMissingCosts} supplier total{suppliersMissingCosts === 1 ? " is" : "s are"} unknown because unit costs are missing. The chart includes only complete totals.</p>}
          <SeriesTable points={data.cash_at_risk_by_vendor} caption="Capital requiring review by supplier" nameLabel="Supplier" valueLabel="Capital (USD)" formatter={formatDashboardMoney} />
        </ChartPanel>

        <ChartPanel
          className="col-4"
          title="Alert activity"
          subtitle="Severity of the most recent 500 alert events"
          accent="danger"
        >
          {data.alert_counts_by_severity.some((point) => point.value > 0) ? <DonutChart
            points={data.alert_counts_by_severity}
            centerLabel="Events"
            centerValue={data.alert_counts_by_severity
              .reduce((s, p) => s + p.value, 0)
              .toLocaleString()}
          /> : <p className={styles.chartEmpty}>No alert events recorded. <Link href="/alerts">Review your alert rules</Link> to make sure important inventory changes reach you.</p>}
        </ChartPanel>

        <ChartPanel
          className="col-6"
          title="Forecast variance · last 7 days"
          subtitle="Actual units sold compared with predicted units · up to 5 best sellers"
          footer="Positive means demand exceeded the forecast; negative means it fell short. Zero means actual and forecast matched. This is a variance check, not an overall accuracy score."
        >
          {data.forecast_vs_actual_7d.length > 0
            ? <DivergingBarChart points={data.forecast_vs_actual_7d} valueFormatter={formatForecastVariance} />
            : <p className={styles.chartEmpty}>No comparable forecasts yet. Percentage variance needs a non-zero forecast to compare with recorded sales.</p>}
          <SeriesTable points={data.forecast_vs_actual_7d} caption="Actual minus predicted units, as a percentage of predicted units" nameLabel="Product" valueLabel="Variance" formatter={formatForecastVariance} />
        </ChartPanel>

        <ChartPanel
          className="col-6"
          title="What should I do today?"
          subtitle="The three highest-impact moves right now"
        >
          <div className="today-list">
            <TodayRow
              step="1"
              title="Reorder urgent SKUs"
              body="Push the prioritized Action Queue into purchase orders - they're grouped by supplier on the PO page."
              href="/purchase-orders"
            />
            <TodayRow
              step="2"
              title="Clear dead stock capital"
              body="Run the liquidator — tactics are tailored by age, margin, and capital exposure."
              href="/liquidation"
            />
            <TodayRow
              step="3"
              title="Confirm alert routing"
              body="Make sure your email and Slack channels are verified so you hear about problems early."
              href="/alerts"
            />
          </div>
        </ChartPanel>
      </section>

      <footer className="dashboard-footer">
        Generated {new Date(data.generated_at).toLocaleString()}
      </footer>
    </div>
  );
}

function parseCompletedOnboardingSteps(stored: string | null): string[] {
  if (!stored) return [];
  const parsed = JSON.parse(stored) as unknown;
  if (Array.isArray(parsed)) {
    return parsed.filter((value): value is string => typeof value === "string");
  }
  if (parsed && typeof parsed === "object") {
    return Object.entries(parsed)
      .filter(([, value]) => Boolean(value))
      .map(([key]) => key);
  }
  return [];
}

function SeriesTable({ points, caption, nameLabel, valueLabel, formatter }: {
  points: DashboardSeriesPoint[];
  caption: string;
  nameLabel: string;
  valueLabel: string;
  formatter: (value: number) => string;
}) {
  if (points.length === 0) return null;
  return (
    <details className={styles.dataDetails}>
      <summary>View exact values</summary>
      <div className={styles.tableScroll} tabIndex={0} role="region" aria-label={caption}>
        <table className={styles.dataTable}>
          <caption>{caption}</caption>
          <thead>
            <tr><th scope="col">{nameLabel}</th><th scope="col">{valueLabel}</th></tr>
          </thead>
          <tbody>
            {points.map((point, index) => (
              <tr key={`${point.label}-${index}`}>
                <th scope="row">{point.label}</th>
                <td>{knownPointValue(point) === null ? "Unknown" : formatter(knownPointValue(point)!)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function TodayRow({
  step,
  title,
  body,
  href,
}: {
  step: string;
  title: string;
  body: string;
  href: string;
}) {
  return (
    <Link className="today-row" href={href}>
      <span className="today-step">{step}</span>
      <div>
        <p className="today-title">{title}</p>
        <p className="today-body">{body}</p>
      </div>
      <span className="today-arrow" aria-hidden>
        →
      </span>
    </Link>
  );
}
