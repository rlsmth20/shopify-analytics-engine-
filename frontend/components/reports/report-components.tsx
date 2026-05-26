"use client";

import type { ReactNode } from "react";

export type ReportOption = {
  label: string;
  value: string;
};

export type ReportFilterConfig = {
  key: string;
  label: string;
  options: ReportOption[];
};

export type ReportColumn<T> = {
  key: string;
  label: string;
  align?: "left" | "right" | "center";
  render: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number;
};

export type ReportMetric = {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  tone?: "neutral" | "positive" | "warning" | "danger";
};

export function ReportToolbar({
  title,
  description,
  badge,
  actions,
}: {
  title: string;
  description: string;
  badge?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="report-workspace-toolbar">
      <div>
        <div className="report-title-row">
          <h2>{title}</h2>
          {badge}
        </div>
        <p>{description}</p>
      </div>
      {actions ? <div className="report-toolbar-actions">{actions}</div> : null}
    </div>
  );
}

export function ReportSearchInput({
  value,
  onChange,
  placeholder = "Search product or SKU",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="report-search">
      <span>Search</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}

export function ReportFilters({
  filters,
  values,
  onChange,
  onReset,
}: {
  filters: ReportFilterConfig[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  onReset: () => void;
}) {
  const activeFilters = filters.filter((filter) => values[filter.key]);

  return (
    <div className="report-filters">
      <div className="report-filter-grid">
        {filters.map((filter) => (
          <label key={filter.key} className="report-filter-field">
            <span>{filter.label}</span>
            <select
              value={values[filter.key] ?? ""}
              onChange={(event) => onChange(filter.key, event.target.value)}
            >
              <option value="">All</option>
              {filter.options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <div className="report-filter-footer">
        <div className="report-filter-chips" aria-label="Selected filters">
          {activeFilters.length === 0 ? (
            <span className="report-filter-muted">No filters applied</span>
          ) : (
            activeFilters.map((filter) => (
              <span key={filter.key} className="report-filter-chip">
                {filter.label}:{" "}
                {filter.options.find((option) => option.value === values[filter.key])?.label ??
                  values[filter.key]}
              </span>
            ))
          )}
        </div>
        <button type="button" className="button button-ghost button-sm" onClick={onReset}>
          Reset filters
        </button>
      </div>
    </div>
  );
}

export function ReportMetricCards({ metrics }: { metrics: ReportMetric[] }) {
  return (
    <section className="report-metric-grid">
      {metrics.map((metric) => (
        <article
          key={metric.label}
          className={`report-metric-card report-metric-${metric.tone ?? "neutral"}`}
        >
          <span>{metric.label}</span>
          <strong>{metric.value}</strong>
          {metric.note ? <p>{metric.note}</p> : null}
        </article>
      ))}
    </section>
  );
}

export function ReportStatusBadge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "positive" | "warning" | "danger" | "demo";
}) {
  return <span className={`report-status-badge report-status-badge-${tone}`}>{children}</span>;
}

export function ReportEmptyState({
  title,
  description,
  actions,
}: {
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <div className="report-empty-state">
      <p className="report-empty-title">{title}</p>
      <p className="report-empty-copy">{description}</p>
      {actions ? <div className="report-empty-actions">{actions}</div> : null}
    </div>
  );
}

export function ReportTable<T>({
  columns,
  rows,
  rowKey,
  sortKey,
  sortDirection,
  onSort,
  loading = false,
  emptyState,
}: {
  columns: ReportColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  sortKey: string;
  sortDirection: "asc" | "desc";
  onSort: (key: string) => void;
  loading?: boolean;
  emptyState: ReactNode;
}) {
  if (loading) {
    return (
      <ReportEmptyState
        title="Loading report"
        description="Pulling current inventory signals into the report table."
      />
    );
  }

  if (rows.length === 0) {
    return <>{emptyState}</>;
  }

  return (
    <div className="report-table-wrap">
      <table className="report-table">
        <thead>
          <tr>
            {columns.map((column) => {
              const sorted = sortKey === column.key;
              return (
                <th key={column.key} className={`align-${column.align ?? "left"}`}>
                  <button
                    type="button"
                    onClick={() => onSort(column.key)}
                    className={sorted ? "report-sort report-sort-active" : "report-sort"}
                  >
                    <span>{column.label}</span>
                    <span aria-hidden>{sorted ? (sortDirection === "asc" ? "^" : "v") : ""}</span>
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td key={column.key} className={`align-${column.align ?? "left"}`}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
