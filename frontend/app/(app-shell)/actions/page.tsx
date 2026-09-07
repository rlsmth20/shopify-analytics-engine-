"use client";

import { useEffect } from "react";
import { trackGrowthEvent } from "@/lib/analytics";

import { ActionFeed } from "@/components/action-feed";
import { KpiCard } from "@/components/kpi-card";
import {
  summarizeDataSource
} from "@/lib/app-helpers";
import { useActionFeed } from "@/lib/use-action-feed";
import { financialTotal } from "@/lib/financial-values";
import { getActionImpactValue } from "@/lib/app-helpers";
import { currency } from "@/lib/api-v2";

export default function ActionsPage() {
  const { actions, dataSource, isLoading, errorMessage, errorStatus } =
    useActionFeed();

  useEffect(() => {
    if (!isLoading && !errorMessage && dataSource === "db" && actions.length > 0) void trackGrowthEvent("KEY_ACTION_VIEWED");
  }, [isLoading, errorMessage, dataSource, actions.length]);

  const urgentProfitAtRisk = financialTotal(actions
    .filter((action) => action.status === "urgent")
    .map(getActionImpactValue));
  const cashTiedUp = financialTotal(actions
    .filter((action) => action.status !== "urgent")
    .map(getActionImpactValue));

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
                : currency(urgentProfitAtRisk)
          }
          note={urgentProfitAtRisk === null ? "Add missing unit costs to estimate profit exposure" : "Urgent exposure from the current queue"}
        />
        <KpiCard
          label="Capital tied up"
          value={
            isLoading ? "..." : errorMessage ? "—" : currency(cashTiedUp)
          }
          note={cashTiedUp === null ? "Add missing unit costs to estimate total capital" : dataSource ? summarizeDataSource(dataSource) : "Awaiting feed"}
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
