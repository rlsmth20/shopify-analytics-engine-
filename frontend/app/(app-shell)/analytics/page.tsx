"use client";

import { useEffect, useMemo, useState } from "react";

import { ChartCard } from "@/components/chart-card";
import { EmptyState } from "@/components/empty-state";
import { KpiCard } from "@/components/kpi-card";
import {
  confidenceLabel,
  currencyFormatter,
  leadTimeSourceLabel,
  numberFormatter,
  summarizeDataSource,
  urgencyLabel,
} from "@/lib/app-helpers";
import {
  fetchInventoryHealth,
  type InventoryHealthBucket,
  type InventoryHealthResponse,
  type InventoryHealthSku,
} from "@/lib/api-v2";
import { useActionFeed } from "@/lib/use-action-feed";

function formatKpiValue(value: number, unit: InventoryHealthResponse["kpis"][number]["unit"]) {
  if (unit === "currency") return currencyFormatter.format(value);
  if (unit === "percent") return `${Math.round(value * 100)}%`;
  if (unit === "days") return `${numberFormatter.format(value)}d`;
  return numberFormatter.format(value);
}

function maxBucketValue(items: InventoryHealthBucket[]): number {
  return Math.max(...items.map((item) => item.value), 1);
}

function BucketBars({ items }: { items: InventoryHealthBucket[] }) {
  const maxValue = maxBucketValue(items);
  return (
    <div className="bar-list">
      {items.map((item) => (
        <div key={item.label} className="bar-row">
          <div className="bar-row-meta">
            <span>{item.label}</span>
            <strong>{numberFormatter.format(item.value)}</strong>
          </div>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{ width: `${Math.max((item.value / maxValue) * 100, 4)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function RiskList({
  items,
  emptyTitle,
  emptyDescription,
}: {
  items: InventoryHealthSku[];
  emptyTitle: string;
  emptyDescription: string;
}) {
  if (items.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }

  return (
    <div className="signal-list">
      {items.map((item) => (
        <div key={item.sku_id} className="signal-item">
          <div>
            <p className="signal-title">{item.name}</p>
            <p className="signal-copy">{item.vendor} - {item.note}</p>
          </div>
          <strong>{currencyFormatter.format(item.value)}</strong>
        </div>
      ))}
    </div>
  );
}

export default function AnalyticsPage() {
  const { actions, dataSource, isLoading, errorMessage } = useActionFeed();
  const [health, setHealth] = useState<InventoryHealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setHealthLoading(true);
    fetchInventoryHealth(controller.signal)
      .then((data) => {
        setHealth(data);
        setHealthError(null);
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setHealthError(error instanceof Error ? error.message : String(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setHealthLoading(false);
      });
    return () => controller.abort();
  }, []);

  const statusImpact = useMemo(() => [
    {
      label: "Urgent",
      value: actions
        .filter((action) => action.status === "urgent")
        .reduce((sum, action) => sum + action.estimated_profit_impact, 0),
    },
    {
      label: "Optimize",
      value: actions
        .filter((action) => action.status === "optimize")
        .reduce((sum, action) => sum + action.cash_tied_up, 0),
    },
    {
      label: "Dead",
      value: actions
        .filter((action) => action.status === "dead")
        .reduce((sum, action) => sum + action.cash_tied_up, 0),
    },
  ], [actions]);

  const maxImpact = Math.max(...statusImpact.map((item) => item.value), 1);
  const urgencyMix = (["critical", "high", "medium"] as const).map((level) => ({
    label: urgencyLabel[level],
    value: actions.filter(
      (action) => action.status === "urgent" && action.urgency_level === level
    ).length,
  }));
  const leadTimeMix = (
    ["sku_override", "vendor", "category", "global_default"] as const
  ).map((source) => ({
    label: leadTimeSourceLabel[source],
    value: actions.filter((action) => action.lead_time_source === source).length,
  }));

  return (
    <div className="page-stack">
      {healthError ? (
        <EmptyState
          title="Inventory health unavailable"
          description={healthError}
          tone="error"
        />
      ) : null}

      <div className="kpi-grid">
        {healthLoading
          ? Array.from({ length: 4 }, (_, index) => (
              <KpiCard key={index} label="Loading" value="..." note="Calculating inventory health" />
            ))
          : health?.kpis.slice(0, 4).map((kpi) => (
              <KpiCard
                key={kpi.label}
                label={kpi.label}
                value={formatKpiValue(kpi.value, kpi.unit)}
                note={kpi.note}
              />
            ))}
      </div>

      {health && health.insights.length > 0 ? (
        <div className="content-grid content-grid-2-2">
          {health.insights.map((insight) => (
            <ChartCard
              key={insight.title}
              title={insight.title}
              description={insight.description}
            >
              <div className="signal-list">
                <div className="signal-item">
                  <div>
                    <p className="signal-title">{insight.metric_label}</p>
                    <p className="signal-copy">{insight.severity}</p>
                  </div>
                  <strong>{insight.metric_value}</strong>
                </div>
              </div>
            </ChartCard>
          ))}
        </div>
      ) : null}

      {health ? (
        <div className="content-grid content-grid-2-2">
          <ChartCard
            title="Inventory health mix"
            description="Catalog buckets based on stockout probability, stale inventory, overstock, and demand signal."
          >
            <BucketBars items={health.health_buckets} />
          </ChartCard>

          <ChartCard
            title="Forecast confidence"
            description="How much of the catalog has enough clean history for higher-trust recommendations."
          >
            <BucketBars items={health.forecast_confidence} />
          </ChartCard>

          <ChartCard
            title="Revenue most exposed to stockouts"
            description="SKUs where forecast demand, current on-hand, and stockout probability create the largest near-term revenue risk."
          >
            <RiskList
              items={health.top_stockout_risk}
              emptyTitle="No stockout exposure found"
              emptyDescription="Current forecasts do not show meaningful revenue at risk from stockouts."
            />
          </ChartCard>

          <ChartCard
            title="Cash trapped in slow inventory"
            description="Stale or over-covered SKUs ranked by inventory cost currently tied up."
          >
            <RiskList
              items={health.top_cash_trapped}
              emptyTitle="No trapped cash found"
              emptyDescription="No stale or heavily over-covered SKUs are currently visible in the catalog."
            />
          </ChartCard>
        </div>
      ) : null}

      <div className="kpi-grid kpi-grid-tight">
        <KpiCard
          label="Data source"
          value={dataSource ? summarizeDataSource(dataSource) : isLoading ? "..." : "-"}
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
          title="Action analytics unavailable"
          description={errorMessage}
          tone="error"
        />
      ) : null}

      {!errorMessage ? (
        <div className="content-grid content-grid-2-2">
          <ChartCard
            title="Action queue exposure"
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
