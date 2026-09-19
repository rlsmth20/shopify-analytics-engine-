"use client";

import { Fragment, useId, useState, type ReactNode } from "react";
import { reportPage } from "@/lib/chart-interaction";

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
              <button type="button" key={filter.key} className="report-filter-chip" onClick={() => onChange(filter.key, "")} aria-label={`Remove ${filter.label} filter`}>
                {filter.label}:{" "}
                {filter.options.find((option) => option.value === values[filter.key])?.label ??
                  values[filter.key]} <span aria-hidden="true">×</span>
              </button>
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
  selectedRowKey,
  onRowClick,
  renderRowDetails,
  sortKey,
  sortDirection,
  onSort,
  loading = false,
  emptyState,
}: {
  columns: ReportColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  selectedRowKey?: string | null;
  onRowClick?: (row: T) => void;
  renderRowDetails?: (row: T) => ReactNode;
  sortKey: string;
  sortDirection: "asc" | "desc";
  onSort: (key: string) => void;
  loading?: boolean;
  emptyState: ReactNode;
}) {
  const [pageState, setPageState] = useState<{ rows: T[]; page: number } | null>(null);
  const [pageSize, setPageSize] = useState(25);
  const [compact, setCompact] = useState(false);
  const [hiddenColumns, setHiddenColumns] = useState<string[]>([]);
  const tableId = useId();
  const identityColumn = columns.find(column => column.key === "product") ?? columns[0];
  const orderedColumns = identityColumn ? [identityColumn, ...columns.filter(column => column !== identityColumn)] : columns;
  const visibleColumns = orderedColumns.filter(column => column === identityColumn || !hiddenColumns.includes(column.key));
  // Sorting/filtering produces a new row set; begin at its first page.
  const page = reportPage(pageState?.rows === rows ? pageState.page : 0, pageSize, rows.length);
  const visibleRows = rows.slice(page.start, page.end);
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
    <div className={`report-table-shell${compact ? " report-table-compact" : ""}`}>
      <div className="report-table-tools">
        <p role="status"><strong>{(page.start + 1).toLocaleString()}–{page.end.toLocaleString()}</strong> of {rows.length.toLocaleString()} rows</p>
        <div className="report-table-options">
          <label>Rows <select value={pageSize} onChange={event => { setPageSize(Number(event.target.value)); setPageState(null); }}>{[25, 50, 100].map(size => <option key={size} value={size}>{size}</option>)}</select></label>
          <button type="button" aria-pressed={compact} onClick={() => setCompact(!compact)} className="chart-reset">Compact rows</button>
          <details className="report-column-picker"><summary>Columns <span aria-hidden="true">⌄</span></summary><div>
            {orderedColumns.map(column => <label key={column.key}><input type="checkbox" checked={column === identityColumn || !hiddenColumns.includes(column.key)} disabled={column === identityColumn} onChange={event => setHiddenColumns(current => event.target.checked ? current.filter(key => key !== column.key) : [...current, column.key])} />{column.label}</label>)}
            <button type="button" className="chart-reset" onClick={() => setHiddenColumns([])}>Show all columns</button>
          </div></details>
        </div>
      </div>
      <div className="report-table-wrap" role="region" aria-label="Report results, scroll for more columns" tabIndex={0}>
      <table className="report-table" id={tableId}>
        <caption className="sr-only">Report results. Select a column heading to sort.</caption>
        <thead>
          <tr>
            {visibleColumns.map((column) => {
              const sorted = sortKey === column.key;
              return (
                <th scope="col" key={column.key} aria-sort={sorted ? (sortDirection === "asc" ? "ascending" : "descending") : "none"} className={`align-${column.align ?? "left"}`}>
                  <button
                    type="button"
                    onClick={() => onSort(column.key)}
                    className={sorted ? "report-sort report-sort-active" : "report-sort"}
                  >
                    <span>{column.label}</span>
                    <span aria-hidden>{sorted ? (sortDirection === "asc" ? "↑" : "↓") : "↕"}</span>
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((row, index) => {
            const key = rowKey(row);
            const expanded = selectedRowKey === key;
            return (
              <Fragment key={key}>
                <tr
                  className={expanded ? "report-row report-row-expanded" : "report-row"}
                  onClick={(event) => { if (!(event.target as HTMLElement).closest("a,button,input,select,label")) onRowClick?.(row); }}
                >
                  {visibleColumns.map((column, columnIndex) => (
                    <td key={column.key} className={`align-${column.align ?? "left"}`}>
                      {column.render(row)}
                      {columnIndex === 0 && onRowClick ? <button type="button" className="report-row-toggle" aria-expanded={expanded} aria-controls={renderRowDetails ? `${tableId}-detail-${index}` : undefined} onClick={() => onRowClick(row)}>{expanded ? "Close details" : "View details"}</button> : null}
                    </td>
                  ))}
                </tr>
                {expanded && renderRowDetails ? (
                  <tr className="report-detail-row" id={`${tableId}-detail-${index}`}>
                    <td colSpan={visibleColumns.length}><div className="report-detail-content">{renderRowDetails(row)}</div></td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      </div>
      <div className="report-pagination" aria-label="Report pages">
        <span>Page {page.index + 1} of {page.count}</span>
        <div><button type="button" disabled={page.index === 0} onClick={() => setPageState({ rows, page: page.index - 1 })}>← Previous</button><button type="button" disabled={page.index === page.count - 1} onClick={() => setPageState({ rows, page: page.index + 1 })}>Next →</button></div>
      </div>
    </div>
  );
}
