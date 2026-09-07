"use client";

import { useEffect, useMemo, useState } from "react";
import { DEFAULT_ACTION_FILTERS, filterInventoryActions, readActionFilters, type ActionFilters } from "@/lib/action-filters";

import { ActionCard } from "@/components/action-card";
import { ActionTable } from "@/components/action-table";
import { EmptyState } from "@/components/empty-state";
import type { ActionDataSource, InventoryAction } from "@/lib/api";
import {
  statusLabel,
  summarizeDataSource,
} from "@/lib/app-helpers";
import { exportActionsReport } from "@/lib/report-export";

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
  const [filters, setFilters] = useState<ActionFilters>(DEFAULT_ACTION_FILTERS);
  const [filtersReady, setFiltersReady] = useState(false);
  const [limit, setLimit] = useState(30);
  const [view, setView] = useState<"cards" | "table">("cards");
  useEffect(() => {
    const read = () => { setFilters(readActionFilters(new URLSearchParams(window.location.search))); setLimit(30); };
    read();
    setFiltersReady(true);
    window.addEventListener("popstate", read);
    return () => window.removeEventListener("popstate", read);
  }, []);
  useEffect(() => {
    if (!filtersReady) return;
    const url = new URL(window.location.href);
    const values = { q: filters.query, status: filters.status, confidence: filters.confidence, stockout: filters.stockoutDays, sort: filters.sort };
    Object.entries(values).forEach(([key, value]) => {
      if (!value || value === "all" || value === "priority") url.searchParams.delete(key);
      else url.searchParams.set(key, value);
    });
    window.history.replaceState(window.history.state, "", url);
  }, [filters, filtersReady]);
  function updateFilters(changes: Partial<ActionFilters>) {
    setFilters((previous) => ({ ...previous, ...changes }));
    setLimit(30);
  }
  const visibleActions = useMemo(() => filterInventoryActions(actions, filters), [actions, filters]);
  const displayedActions = visibleActions.slice(0, limit);

  const visibleGroups = {
    urgent: displayedActions.filter((action) => action.status === "urgent"),
    optimize: displayedActions.filter((action) => action.status === "optimize"),
    dead: displayedActions.filter((action) => action.status === "dead")
  };

  return (
    <div className="feed-shell">
      <div className="toolbar-card">
        <div className="toolbar-left">
          <div>
            <p className="section-eyebrow">Action Queue</p>
            <h2 className="section-title section-title-small">Prioritized Action Queue</h2>
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
                  filters.status === filterValue ? " filter-chip-active" : ""
                }`}
                aria-pressed={filters.status === filterValue}
                onClick={() => updateFilters({ status: filterValue })}
              >
                {filterValue === "all" ? "All" : statusLabel[filterValue]}
              </button>
            ))}
          </div>

          <div className="toolbar-actions">
            <div className="filter-row" role="group" aria-label="Action view">
              {(["cards", "table"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={`filter-chip${view === option ? " filter-chip-active" : ""}`}
                  aria-pressed={view === option}
                  onClick={() => setView(option)}
                >
                  {option === "cards" ? "Cards" : "Compare table"}
                </button>
              ))}
            </div>
            <label className="field-label field-label-inline">
              <span>Sort</span>
              <select
                className="input-control input-select"
                value={filters.sort}
                onChange={(event) => updateFilters({ sort: event.target.value as ActionFilters["sort"] })}
              >
                <option value="priority">Priority score</option>
                <option value="impact">Profit/cash impact</option>
                <option value="coverage">Fewest days of stock</option>
              </select>
            </label>

            <button
              type="button"
              className="button button-secondary"
              disabled={visibleActions.length === 0}
              onClick={() => exportActionsReport(visibleActions)}
            >
              Export styled Excel
            </button>
          </div>
        </div>
      </div>

      <div className="toolbar-card inventory-filter-panel">
        <label className="field-label"><span>Search products or SKU IDs</span>
          <input className="input-control" type="search" placeholder="Search the action queue…" value={filters.query} onChange={(event) => updateFilters({ query: event.target.value })} />
        </label>
        <label className="field-label"><span>Forecast confidence</span>
          <select className="input-control" value={filters.confidence} onChange={(event) => updateFilters({ confidence: event.target.value as ActionFilters["confidence"] })}>
            <option value="all">All confidence levels</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
          </select>
        </label>
        <label className="field-label"><span>Stockout window</span>
          <select className="input-control" value={filters.stockoutDays} onChange={(event) => updateFilters({ stockoutDays: event.target.value as ActionFilters["stockoutDays"] })}>
            <option value="all">Any time</option><option value="7">Within 7 days</option><option value="14">Within 14 days</option>
          </select>
        </label>
        <button className="button button-ghost" type="button" onClick={() => updateFilters(DEFAULT_ACTION_FILTERS)}>Clear filters</button>
        {!isLoading && !errorMessage ? <p className="section-copy inventory-filter-count" role="status">Showing {displayedActions.length} of {visibleActions.length} matching actions · {actions.length} total. Excel export includes all matches.</p> : null}
      </div>

      {isLoading ? (
        <EmptyState
          title="Loading Action Queue"
          description="Pulling prioritized Action Queue items from the backend."
        />
      ) : null}

      {errorMessage ? (
        <EmptyState
          title={errorStatus === 503 ? "Live feed unavailable" : "Feed unavailable"}
          description={
            errorStatus === 503
              ? `${errorMessage} Check your Shopify connection and run a sync from Store Sync.`
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

      {!isLoading && !errorMessage && view === "table" && displayedActions.length > 0 ? <ActionTable actions={displayedActions} /> : null}

      {!isLoading && !errorMessage && view === "cards" ? (
        <div className="action-group-stack">
          <ActionSection
            title="Urgent"
            description="Stockout risks that need immediate replenishment decisions."
            actions={visibleGroups.urgent}
          />
          <ActionSection
            title="Optimize"
            description="Review coverage and data gaps before changing purchasing or clearing stock."
            actions={visibleGroups.optimize}
          />
          <ActionSection
            title="Dead"
            description="Stale inventory that should be marked down, bundled, or cleared."
            actions={visibleGroups.dead}
          />
        </div>
      ) : null}
      {!isLoading && !errorMessage && visibleActions.length > limit ? (
        <button type="button" className="button button-secondary" onClick={() => setLimit((previous) => previous + 30)}>Show next {Math.min(30, visibleActions.length - limit)} actions</button>
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
