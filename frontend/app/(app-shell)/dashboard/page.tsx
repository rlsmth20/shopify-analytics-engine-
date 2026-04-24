"use client";

import { useEffect, useState } from "react";

import {
  AreaLineChart,
  ChartPanel,
  DivergingBarChart,
  DonutChart,
  HorizontalBarChart,
  Sparkline,
} from "@/components/charts";
import {
  currency,
  fetchDashboard,
  type DashboardResponse,
} from "@/lib/api-v2";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchDashboard(controller.signal)
      .then((res) => {
        setData(res);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  if (loading && !data) {
    return <div className="page-loading">Loading command center…</div>;
  }

  if (error) {
    return (
      <div className="page-error">
        <p className="page-error-title">Could not load dashboard</p>
        <p className="page-error-copy">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="dashboard">
      <section className="dashboard-kpis">
        {data.kpis.map((kpi) => (
          <div key={kpi.label} className={`kpi-card kpi-tone-${kpi.tone}`}>
            <p className="kpi-label">{kpi.label}</p>
            <div className="kpi-value-row">
              <p className="kpi-value">
                {kpi.unit === "currency"
                  ? currency(kpi.value)
                  : kpi.unit === "percent"
                  ? `${kpi.value.toFixed(1)}%`
                  : kpi.value.toLocaleString()}
              </p>
              {kpi.delta_pct !== null ? (
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
                  {kpi.delta_pct >= 0 ? "▲" : "▼"} {Math.abs(kpi.delta_pct).toFixed(1)}%
                </span>
              ) : null}
            </div>
            <Sparkline
              values={sparkValues(kpi.label, data)}
              width={140}
              height={36}
            />
          </div>
        ))}
      </section>

      <section className="dashboard-grid">
        <ChartPanel
          className="col-8"
          title="Revenue · last 30 days"
          subtitle="Daily revenue across the full catalog"
          accent="primary"
        >
          <AreaLineChart
            points={data.revenue_trend_30d}
            height={240}
            yFormatter={(v) => `$${(v / 1000).toFixed(1)}k`}
          />
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
              .toString()}
          />
        </ChartPanel>

        <ChartPanel
          className="col-8"
          title="Top revenue movers"
          subtitle="30-day revenue contribution by SKU"
          accent="success"
        >
          <HorizontalBarChart
            points={data.top_movers.slice(0, 8)}
            valueFormatter={currency}
          />
        </ChartPanel>

        <ChartPanel
          className="col-4"
          title="ABC distribution"
          subtitle="Revenue concentration across the catalog"
        >
          <DonutChart
            points={data.abc_distribution}
            centerLabel="SKUs"
            centerValue={data.abc_distribution
              .reduce((s, p) => s + p.value, 0)
              .toString()}
          />
        </ChartPanel>

        <ChartPanel
          className="col-8"
          title="Cash parked by vendor"
          subtitle="Overstock + dead stock at cost, top 6 vendors"
          accent="warning"
        >
          <HorizontalBarChart
            points={data.cash_at_risk_by_vendor}
            valueFormatter={currency}
            barClassName="chart-hbar chart-hbar-warning"
          />
        </ChartPanel>

        <ChartPanel
          className="col-4"
          title="Alert activity"
          subtitle="Events fired by severity"
          accent="danger"
        >
          <DonutChart
            points={data.alert_counts_by_severity}
            centerLabel="Events"
            centerValue={data.alert_counts_by_severity
              .reduce((s, p) => s + p.value, 0)
              .toString()}
          />
        </ChartPanel>

        <ChartPanel
          className="col-6"
          title="Forecast accuracy · last 7 days"
          subtitle="Actual vs predicted, % variance"
        >
          <DivergingBarChart points={data.forecast_vs_actual_7d} />
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
              body="Push the prioritized action queue into purchase orders — they're grouped by vendor on the PO page."
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

function sparkValues(label: string, data: DashboardResponse): number[] {
  if (label.toLowerCase().includes("revenue")) {
    return data.revenue_trend_30d.map((p) => p.value);
  }
  if (label.toLowerCase().includes("movers")) {
    return data.top_movers.map((p) => p.value);
  }
  return data.revenue_trend_30d.slice(-14).map((p) => p.value);
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
    <a className="today-row" href={href}>
      <span className="today-step">{step}</span>
      <div>
        <p className="today-title">{title}</p>
        <p className="today-body">{body}</p>
      </div>
      <span className="today-arrow" aria-hidden>
        →
      </span>
    </a>
  );
}
