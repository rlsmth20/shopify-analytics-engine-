"use client";

import { ChartCard } from "@/components/chart-card";
import { EmptyState } from "@/components/empty-state";
import { KpiCard } from "@/components/kpi-card";
import {
  confidenceLabel,
  currencyFormatter,
  leadTimeSourceLabel,
  numberFormatter,
  summarizeDataSource,
  urgencyLabel
} from "@/lib/app-helpers";
import { useActionFeed } from "@/lib/use-action-feed";

export default function AnalyticsPage() {
  const { actions, dataSource, isLoading, errorMessage } = useActionFeed();

  const statusImpact = [
    {
      label: "Urgent",
      value: actions
        .filter((action) => action.status === "urgent")
        .reduce((sum, action) => sum + action.estimated_profit_impact, 0)
    },
    {
      label: "Optimize",
      value: actions
        .filter((action) => action.status === "optimize")
        .reduce((sum, action) => sum + action.cash_tied_up, 0)
    },
    {
      label: "Dead",
      value: actions
        .filter((action) => action.status === "dead")
        .reduce((sum, action) => sum + action.cash_tied_up, 0)
    }
  ];

  const maxImpact = Math.max(...statusImpact.map((item) => item.value), 1);
  const urgencyMix = (["critical", "high", "medium"] as const).map((level) => ({
    label: urgencyLabel[level],
    value: actions.filter(
      (action) => action.status === "urgent" && action.urgency_level === level
    ).length
  }));
  const leadTimeMix = (
    ["sku_override", "vendor", "category", "global_default"] as const
  ).map((source) => ({
    label: leadTimeSourceLabel[source],
    value: actions.filter((action) => action.lead_time_source === source).length
  }));

  return (
    <div className="page-stack">
      <div className="kpi-grid kpi-grid-tight">
        <KpiCard
          label="Data source"
          value={dataSource ? summarizeDataSource(dataSource) : isLoading ? "..." : "—"}
          note="Current feed origin"
        />
        <KpiCard
          label="Average priority score"
          value={
            isLoading
              ? "..."
              : actions.length === 0
                ? "0"
                : numberFormatter.format(
                    actions.reduce((sum, action) => sum + action.priority_score, 0) /
                      actions.length
                  )
          }
          note="Across the visible queue"
        />
        <KpiCard
          label="High confidence items"
          value={
            isLoading
              ? "..."
              : actions.filter((action) => action.data_quality_confidence === "high")
                  .length
          }
          note={confidenceLabel.high}
        />
      </div>

      {errorMessage ? (
        <EmptyState
          title="Analytics unavailable"
          description={errorMessage}
          tone="error"
        />
      ) : null}

      {!errorMessage ? (
        <div className="content-grid content-grid-2-2">
          <ChartCard
            title="Profit and cash exposure"
            description="Urgent items use profit at risk. Optimize and dead use cash tied up."
          >
            <div className="bar-list">
              {statusImpact.map((item) => (
                <div key={item.label} className="bar-row">
                  <div className="bar-row-meta">
                    <span>{item.label}</span>
                    <strong>{currencyFormatter.format(item.value)}</strong>
                  </div>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{ width: `${(item.value / maxImpact) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </ChartCard>

          <ChartCard
            title="Urgency mix"
            description="Current spread of urgent items by stockout timing."
          >
            <div className="signal-list">
              {urgencyMix.map((item) => (
                <div key={item.label} className="signal-item">
                  <div>
                    <p className="signal-title">{item.label}</p>
                    <p className="signal-copy">Urgent items</p>
                  </div>
                  <strong>{item.value}</strong>
                </div>
              ))}
            </div>
          </ChartCard>

          <ChartCard
            title="Lead time source mix"
            description="Which configuration layers are driving current action recommendations."
          >
            <div className="signal-list">
              {leadTimeMix.map((item) => (
                <div key={item.label} className="signal-item">
                  <div>
                    <p className="signal-title">{item.label}</p>
                    <p className="signal-copy">Actions using this source</p>
                  </div>
                  <strong>{item.value}</strong>
                </div>
              ))}
            </div>
          </ChartCard>

          <ChartCard
            title="Inventory risk trend"
            description="Trend history appears after repeated inventory snapshots."
          >
            <EmptyState
              title="Waiting for snapshot history"
              description="Run a few Shopify syncs over time to build a real inventory risk trend."
            />
          </ChartCard>
        </div>
      ) : null}
    </div>
  );
}
