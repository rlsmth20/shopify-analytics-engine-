"use client";

import Link from "next/link";

import { ActionCard } from "@/components/action-card";
import { ChartCard } from "@/components/chart-card";
import { EmptyState } from "@/components/empty-state";
import { KpiCard } from "@/components/kpi-card";
import { SectionCard } from "@/components/section-card";
import { SyncStatusCard } from "@/components/sync-status-card";
import {
  confidenceLabel,
  currencyFormatter,
  getActionImpactValue,
  numberFormatter,
  summarizeDataSource
} from "@/lib/app-helpers";
import { useActionFeed } from "@/lib/use-action-feed";
import { useStoredShopDomain } from "@/lib/use-stored-shop-domain";
import { useSyncStatus } from "@/lib/use-sync-status";

export default function DashboardPage() {
  const { actions, dataSource, isLoading, errorMessage, errorStatus } =
    useActionFeed();
  const { shopifyDomain } = useStoredShopDomain();
  const { latestSyncStatus, isLoadingSyncStatus, syncStatusError } =
    useSyncStatus(shopifyDomain);

  const urgentActions = actions.filter((action) => action.status === "urgent");
  const topUrgentActions = (urgentActions.length > 0 ? urgentActions : actions).slice(
    0,
    3
  );
  const urgentProfitAtRisk = urgentActions.reduce(
    (sum, action) => sum + action.estimated_profit_impact,
    0
  );
  const cashTiedUp = actions
    .filter((action) => action.status !== "urgent")
    .reduce((sum, action) => sum + action.cash_tied_up, 0);
  const highConfidenceCount = actions.filter(
    (action) => action.data_quality_confidence === "high"
  ).length;

  const statusMix = [
    {
      label: "Urgent",
      value: urgentActions.length,
      share: actions.length === 0 ? 0 : (urgentActions.length / actions.length) * 100
    },
    {
      label: "Optimize",
      value: actions.filter((action) => action.status === "optimize").length,
      share:
        actions.length === 0
          ? 0
          : (actions.filter((action) => action.status === "optimize").length /
              actions.length) *
            100
    },
    {
      label: "Dead",
      value: actions.filter((action) => action.status === "dead").length,
      share:
        actions.length === 0
          ? 0
          : (actions.filter((action) => action.status === "dead").length /
              actions.length) *
            100
    }
  ];

  const impactLeaders = [...actions]
    .sort((left, right) => getActionImpactValue(right) - getActionImpactValue(left))
    .slice(0, 4);

  return (
    <div className="page-stack">
      <div className="kpi-grid">
        <KpiCard
          label="Actionable items"
          value={isLoading ? "..." : errorMessage ? "—" : actions.length}
          note={dataSource ? summarizeDataSource(dataSource) : "Awaiting feed"}
        />
        <KpiCard
          label="Urgent items"
          value={isLoading ? "..." : errorMessage ? "—" : urgentActions.length}
          note="Items at immediate stockout risk"
        />
        <KpiCard
          label="Urgent profit at risk"
          value={
            isLoading
              ? "..."
              : errorMessage
                ? "—"
                : currencyFormatter.format(urgentProfitAtRisk)
          }
          note="Projected exposure from urgent stockouts"
        />
        <KpiCard
          label="Cash tied up"
          value={
            isLoading ? "..." : errorMessage ? "—" : currencyFormatter.format(cashTiedUp)
          }
          note={
            isLoading || errorMessage
              ? "Awaiting feed"
              : `${highConfidenceCount} ${confidenceLabel.high.toLowerCase()} confidence items`
          }
        />
      </div>

      <div className="content-grid content-grid-2-1">
        <SyncStatusCard
          isLoading={isLoadingSyncStatus}
          errorMessage={syncStatusError}
          status={latestSyncStatus}
        />

        <ChartCard
          title="Action mix"
          description="Current queue composition by action type."
        >
          <div className="bar-list">
            {statusMix.map((item) => (
              <div key={item.label} className="bar-row">
                <div className="bar-row-meta">
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </div>
                <div className="bar-track">
                  <div
                    className="bar-fill"
                    style={{ width: `${Math.max(item.share, item.value > 0 ? 8 : 0)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </ChartCard>
      </div>

      <div className="content-grid content-grid-2-1">
        <SectionCard>
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">Priority Preview</p>
              <h2 className="section-title">Top urgent decisions</h2>
            </div>
            <Link href="/actions" className="button button-secondary">
              View all actions
            </Link>
          </div>

          {isLoading ? (
            <EmptyState
              title="Loading action preview"
              description="Pulling the top items from the backend queue."
            />
          ) : null}

          {errorMessage ? (
            <EmptyState
              title={errorStatus === 503 ? "Live actions unavailable" : "Action preview unavailable"}
              description={errorMessage}
              tone="error"
            />
          ) : null}

          {!isLoading && !errorMessage && topUrgentActions.length === 0 ? (
            <EmptyState
              title="No priority items yet"
              description="Once the action engine returns inventory decisions, the most urgent items will appear here."
            />
          ) : null}

          {!isLoading && !errorMessage && topUrgentActions.length > 0 ? (
            <div className="action-list">
              {topUrgentActions.map((action) => (
                <ActionCard key={`${action.status}-${action.sku_id}`} action={action} />
              ))}
            </div>
          ) : null}
        </SectionCard>

        <ChartCard
          title="Impact concentration"
          description="Largest current exposure across the active queue."
        >
          <div className="signal-list">
            {impactLeaders.length > 0 ? (
              impactLeaders.map((action) => (
                <div key={`${action.status}-${action.sku_id}`} className="signal-item">
                  <div>
                    <p className="signal-title">{action.name}</p>
                    <p className="signal-copy">{action.status}</p>
                  </div>
                  <strong>{currencyFormatter.format(getActionImpactValue(action))}</strong>
                </div>
              ))
            ) : (
              <p className="section-copy">
                Impact ranking will appear here once the feed is available.
              </p>
            )}
          </div>
        </ChartCard>
      </div>

      <div className="content-grid content-grid-2-1">
        <ChartCard
          title="Signal quality"
          description="How much of the live queue is backed by stronger input quality."
        >
          <div className="stat-grid-compact">
            {(["high", "medium", "low"] as const).map((level) => {
              const count = actions.filter(
                (action) => action.data_quality_confidence === level
              ).length;
              return (
                <div key={level} className="stat-item stat-item-emphasis">
                  <span className="stat-label">{confidenceLabel[level]} confidence</span>
                  <strong>{isLoading ? "..." : count}</strong>
                </div>
              );
            })}
          </div>
        </ChartCard>

        <ChartCard
          title="Trend placeholder"
          description="Trend views come next once sync history and inventory snapshots are expanded."
        >
          <div className="placeholder-graph">
            {[38, 54, 46, 60, 58, 72, 68].map((value, index) => (
              <span
                key={index}
                className="placeholder-bar"
                style={{ height: `${value}%` }}
              />
            ))}
          </div>
          <p className="section-copy">
            Today the product is optimized for action clarity over historical analytics.
          </p>
        </ChartCard>
      </div>
    </div>
  );
}
