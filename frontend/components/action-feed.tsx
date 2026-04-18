"use client";

import { useState } from "react";

import { ActionCard } from "@/components/action-card";
import { EmptyState } from "@/components/empty-state";
import type { ActionDataSource, InventoryAction } from "@/lib/api";
import {
  exportActionsCsv,
  getActionImpactValue,
  statusLabel,
  summarizeDataSource,
  type ActionFilter,
  type ActionSort
} from "@/lib/app-helpers";

export function ActionFeed({
  actions,
  dataSource,
  isLoading,
  errorMessage,
  errorStatus
}: {
  actions: InventoryAction[];
  dataSource: ActionDataSource | null;
  isLoading: boolean;
  errorMessage: string | null;
  errorStatus: number | null;
}) {
  const [actionFilter, setActionFilter] = useState<ActionFilter>("all");
  const [actionSort, setActionSort] = useState<ActionSort>("priority");

  const filteredActions = actions.filter((action) =>
    actionFilter === "all" ? true : action.status === actionFilter
  );
  const visibleActions =
    actionSort === "priority"
      ? filteredActions
      : [...filteredActions].sort(
          (left, right) =>
            getActionImpactValue(right) - getActionImpactValue(left) ||
            right.priority_score - left.priority_score
        );

  const visibleGroups = {
    urgent: visibleActions.filter((action) => action.status === "urgent"),
    optimize: visibleActions.filter((action) => action.status === "optimize"),
    dead: visibleActions.filter((action) => action.status === "dead")
  };

  return (
    <div className="feed-shell">
      <div className="toolbar-card">
        <div className="toolbar-left">
          <div>
            <p className="section-eyebrow">Work Queue</p>
            <h2 className="section-title section-title-small">Prioritized inventory actions</h2>
          </div>
          {dataSource ? (
            <span className="source-badge">{summarizeDataSource(dataSource)}</span>
          ) : null}
        </div>

        <div className="toolbar-controls">
          <div className="filter-row" role="toolbar" aria-label="Action filters">
            {(["all", "urgent", "optimize", "dead"] as const).map((filterValue) => (
              <button
                key={filterValue}
                type="button"
                className={`filter-chip${
                  actionFilter === filterValue ? " filter-chip-active" : ""
                }`}
                onClick={() => setActionFilter(filterValue)}
              >
                {filterValue === "all" ? "All" : statusLabel[filterValue]}
              </button>
            ))}
          </div>

          <div className="toolbar-actions">
            <label className="field-label field-label-inline">
              <span>Sort</span>
              <select
                className="input-control input-select"
                value={actionSort}
                onChange={(event) => setActionSort(event.target.value as ActionSort)}
              >
                <option value="priority">Priority score</option>
                <option value="impact">Profit/cash impact</option>
              </select>
            </label>

            <button
              type="button"
              className="button button-secondary"
              disabled={visibleActions.length === 0}
              onClick={() => exportActionsCsv(visibleActions)}
            >
              Export CSV
            </button>
          </div>
        </div>
      </div>

      {isLoading ? (
        <EmptyState
          title="Loading action feed"
          description="Pulling prioritized inventory actions from the backend."
        />
      ) : null}

      {errorMessage ? (
        <EmptyState
          title={errorStatus === 503 ? "Live feed unavailable" : "Feed unavailable"}
          description={
            errorStatus === 503
              ? `${errorMessage} Run a Shopify ingest or re-enable mock fallback in Lead Time Settings.`
              : errorMessage
          }
          tone="error"
        />
      ) : null}

      {!isLoading && !errorMessage && visibleActions.length === 0 ? (
        <EmptyState
          title="No actions to show"
          description={
            actions.length === 0
              ? "The backend did not return any actionable inventory items."
              : "No actions match the current filter."
          }
        />
      ) : null}

      {!isLoading && !errorMessage ? (
        <div className="action-group-stack">
          <ActionSection
            title="Urgent"
            description="Stockout risks that need immediate replenishment decisions."
            actions={visibleGroups.urgent}
          />
          <ActionSection
            title="Optimize"
            description="Inventory tying up working capital beyond the target coverage."
            actions={visibleGroups.optimize}
          />
          <ActionSection
            title="Dead"
            description="Stale inventory that should be marked down, bundled, or cleared."
            actions={visibleGroups.dead}
          />
        </div>
      ) : null}
    </div>
  );
}

function ActionSection({
  title,
  description,
  actions
}: {
  title: string;
  description: string;
  actions: InventoryAction[];
}) {
  if (actions.length === 0) {
    return null;
  }

  return (
    <section className="action-group">
      <div className="action-group-header">
        <div>
          <h3>{title}</h3>
          <p>{description}</p>
        </div>
        <span className="group-count">{actions.length}</span>
      </div>
      <div className="action-list">
        {actions.map((action) => (
          <ActionCard key={`${action.status}-${action.sku_id}`} action={action} />
        ))}
      </div>
    </section>
  );
}
