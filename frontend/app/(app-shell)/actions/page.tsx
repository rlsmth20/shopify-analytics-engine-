"use client";

import { useEffect } from "react";
import { trackGrowthEvent } from "@/lib/analytics";

import { ActionFeed } from "@/components/action-feed";
import { KpiCard } from "@/components/kpi-card";
import {
  currencyFormatter,
  summarizeDataSource
} from "@/lib/app-helpers";
import { useActionFeed } from "@/lib/use-action-feed";

export default function ActionsPage() {
  const { actions, dataSource, isLoading, errorMessage, errorStatus } =
    useActionFeed();

  useEffect(() => {
    if (!isLoading && !errorMessage && dataSource === "db" && actions.length > 0) void trackGrowthEvent("KEY_ACTION_VIEWED");
  }, [isLoading, errorMessage, dataSource, actions.length]);

  const urgentProfitAtRisk = actions
    .filter((action) => action.status === "urgent")
    .reduce((sum, action) => sum + action.estimated_profit_impact, 0);
  const cashTiedUp = actions
    .filter((action) => action.status !== "urgent")
    .reduce((sum, action) => sum + action.cash_tied_up, 0);

  return (
    <div className="page-stack">
      <div className="kpi-grid kpi-grid-tight">
        <KpiCard
          label="Queue size"
          value={isLoading ? "..." : errorMessage ? "—" : actions.length}
          note="Actionable inventory items only"
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
          note="Urgent exposure from the current queue"
        />
        <KpiCard
          label="Capital tied up"
          value={
            isLoading ? "..." : errorMessage ? "—" : currencyFormatter.format(cashTiedUp)
          }
          note={dataSource ? summarizeDataSource(dataSource) : "Awaiting feed"}
        />
      </div>

      <ActionFeed
        actions={actions}
        dataSource={dataSource}
        isLoading={isLoading}
        errorMessage={errorMessage}
        errorStatus={errorStatus}
      />
    </div>
  );
}
