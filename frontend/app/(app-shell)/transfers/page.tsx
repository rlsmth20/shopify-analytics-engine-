"use client";

import { useEffect, useMemo, useState } from "react";

import { DataQualityNote } from "@/components/data-quality-note";
import { GatedFeature } from "@/components/gated-feature";
import {
  ReportEmptyState,
  ReportFilters,
  ReportMetricCards,
  ReportSearchInput,
  ReportStatusBadge,
  ReportTable,
  type ReportColumn,
  type ReportFilterConfig,
  type ReportMetric,
} from "@/components/reports/report-components";
import { exportReportRowsCsv } from "@/lib/report-export";
import { fetchTransfers, type TransferRecommendation } from "@/lib/api-v2";

type TransferRow = {
  id: string;
  product: string;
  sku: string;
  sourceLocation: string;
  destinationLocation: string;
  sourceStock: number | null;
  destinationStock: number | null;
  destinationDaysLeft: number | null;
  leadTimeDays: number | null;
  recommendedQty: number;
  reason: string;
  priority: "Critical" | "High" | "Medium" | "Low";
  status: "Recommended" | "Reviewed" | "Exported";
  sourceCoverBefore: number | null;
  sourceCoverAfter: number | null;
  destinationCoverBefore: number | null;
  destinationCoverAfter: number | null;
};

type SortDirection = "asc" | "desc";

export default function TransfersPage() {
  return (
    <GatedFeature
      capability="transfers"
      title="Balance inventory across locations"
      description="Upgrade to Scale to use location-level inventory for transfer planning when Shopify location data is available."
    >
      <TransfersContent />
    </GatedFeature>
  );
}

function TransfersContent() {
  const [transfers, setTransfers] = useState<TransferRecommendation[]>([]);
  const [reviewedIds, setReviewedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [sortKey, setSortKey] = useState("priorityRank");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchTransfers(controller.signal)
      .then((r) => {
        setTransfers(r.transfers);
        setError(null);
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  const isDemo = isDemoMode();
  const rows = useMemo(
    () => transfers.map((transfer) => transferToRow(transfer, reviewedIds)),
    [transfers, reviewedIds],
  );
  const metrics = useMemo(() => buildMetrics(rows), [rows]);
  const filterConfig = useMemo(() => buildFilterConfig(rows), [rows]);
  const columns = useMemo(() => buildColumns(), []);
  const visibleRows = useMemo(
    () => sortRows(filterRows(rows, search, filters), columns, sortKey, sortDirection),
    [rows, search, filters, columns, sortKey, sortDirection],
  );

  function updateSort(key: string) {
    if (sortKey === key) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDirection(key === "product" ? "asc" : "desc");
  }

  function exportPlan() {
    exportReportRowsCsv({
      filename: `skubase-transfer-plan-${new Date().toISOString().slice(0, 10)}.csv`,
      rows: visibleRows,
      columns: [
        { label: "Product", value: (row) => row.product },
        { label: "SKU", value: (row) => row.sku },
        { label: "Source location", value: (row) => row.sourceLocation },
        { label: "Destination location", value: (row) => row.destinationLocation },
        { label: "Source stock", value: (row) => row.sourceStock ?? "" },
        { label: "Destination stock", value: (row) => row.destinationStock ?? "" },
        { label: "Destination days left", value: (row) => row.destinationDaysLeft ?? "" },
        { label: "Lead time", value: (row) => row.leadTimeDays ?? "" },
        { label: "Recommended transfer qty", value: (row) => row.recommendedQty },
        { label: "Priority", value: (row) => row.priority },
        { label: "Status", value: (row) => row.status },
        { label: "Reason", value: (row) => row.reason },
      ],
    });
  }

  function markReviewed(row: TransferRow) {
    setReviewedIds((current) => new Set(current).add(row.id));
  }

  if (loading && transfers.length === 0) {
    return <div className="page-loading">Pairing locations...</div>;
  }
  if (error) return <p className="page-error-copy">{error}</p>;

  if (transfers.length === 0) {
    return (
      <DataQualityNote
        title="Transfer recommendations require location-level inventory"
        actions={
          <div className="button-row">
            <a className="button button-secondary" href="/store-sync">
              Check Shopify sync
            </a>
            <a className="button button-ghost" href="/reports">
              Use reports instead
            </a>
          </div>
        }
      >
        <p>
          Your current sync is using aggregate inventory, so Skubase cannot safely
          recommend transfers yet. Confirm Shopify locations are enabled, re-sync
          inventory if location-level sync is supported, and use Stockout Risk and
          Reorder Plan reports in the meantime.
        </p>
      </DataQualityNote>
    );
  }

  return (
    <div className="transfers-page page-stack">
      <section className="section-card transfer-hero">
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Transfer planner</p>
            <h1 className="section-title section-title-small">Balance stock across locations</h1>
            <p className="section-copy">
              Skubase flags where inventory is overstocked in one location and at risk
              in another, then turns that into a transfer plan.
            </p>
          </div>
          {isDemo ? <ReportStatusBadge tone="demo">Sample data</ReportStatusBadge> : null}
        </div>
        <div className="transfer-honesty-note">
          Transfer sync is not automatic yet. Export the plan and finalize it in
          Shopify or your operations workflow.
        </div>
      </section>

      <ReportMetricCards metrics={metrics} />

      <section className="transfer-workflow section-card">
        <div>
          <p className="section-eyebrow">Workflow</p>
          <h2 className="section-title section-title-small">From imbalance to action</h2>
        </div>
        <div className="transfer-steps">
          <Step number="1" title="Review recommended transfers" />
          <Step number="2" title="Export transfer plan" />
          <Step number="3" title="Finalize in Shopify or operations workflow" />
        </div>
      </section>

      <section className="section-card transfer-table-card">
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Recommended transfers</p>
            <h2 className="section-title section-title-small">Transfer plan</h2>
            <p className="section-copy">
              Filter the current recommendations, export the visible rows, and mark
              rows reviewed as your team works through the plan.
            </p>
          </div>
          <div className="button-row">
            <button
              type="button"
              className="button button-primary"
              onClick={exportPlan}
              disabled={visibleRows.length === 0}
            >
              Export transfer plan CSV
            </button>
            <a className="button button-secondary" href="/reports">
              Open stockout report
            </a>
          </div>
        </div>
        <div className="report-control-panel">
          <ReportSearchInput value={search} onChange={setSearch} />
          <ReportFilters
            filters={filterConfig}
            values={filters}
            onChange={(key, value) => setFilters((current) => ({ ...current, [key]: value }))}
            onReset={() => {
              setSearch("");
              setFilters({});
            }}
          />
        </div>
        <ReportTable
          columns={columns}
          rows={visibleRows}
          rowKey={(row) => row.id}
          selectedRowKey={selectedRowId}
          onRowClick={(row) => setSelectedRowId((current) => (current === row.id ? null : row.id))}
          renderRowDetails={(row) => (
            <TransferDetails row={row} onReviewed={() => markReviewed(row)} />
          )}
          sortKey={sortKey}
          sortDirection={sortDirection}
          onSort={updateSort}
          loading={loading}
          emptyState={
            <ReportEmptyState
              title="No transfers match the current filters"
              description="Clear filters or search another SKU, product, source, or destination."
            />
          }
        />
      </section>
    </div>
  );
}

function Step({ number, title }: { number: string; title: string }) {
  return (
    <div className="transfer-step">
      <span>{number}</span>
      <strong>{title}</strong>
    </div>
  );
}

function TransferDetails({ row, onReviewed }: { row: TransferRow; onReviewed: () => void }) {
  return (
    <div className="transfer-detail-panel">
      <div>
        <p className="report-detail-eyebrow">Transfer rationale</p>
        <h3>{row.product}</h3>
        <p>{row.reason}</p>
      </div>
      <dl className="report-detail-grid">
        <Detail label="SKU" value={row.sku} />
        <Detail label="Source" value={row.sourceLocation} />
        <Detail label="Destination" value={row.destinationLocation} />
        <Detail label="Source cover" value={coverChange(row.sourceCoverBefore, row.sourceCoverAfter)} />
        <Detail label="Destination cover" value={coverChange(row.destinationCoverBefore, row.destinationCoverAfter)} />
        <Detail label="Recommended qty" value={formatNumber(row.recommendedQty)} />
        <Detail label="Priority" value={row.priority} />
        <Detail label="Status" value={row.status} />
      </dl>
      <div className="button-row">
        <button
          type="button"
          className="button button-secondary button-sm"
          onClick={(event) => {
            event.stopPropagation();
            onReviewed();
          }}
          disabled={row.status === "Reviewed"}
        >
          {row.status === "Reviewed" ? "Reviewed" : "Mark reviewed"}
        </button>
        <a className="button button-ghost button-sm" href="/purchase-orders">
          Open reorder plan
        </a>
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function transferToRow(
  transfer: TransferRecommendation,
  reviewedIds: Set<string>,
): TransferRow {
  const id = `${transfer.sku_id}-${transfer.from_location}-${transfer.to_location}`;
  const destinationDays = finiteOrNull(
    transfer.destination_days_left ?? transfer.to_days_of_cover_before,
  );
  const priority = transfer.priority ?? inferPriority(destinationDays, transfer.qty);
  return {
    id,
    product: transfer.name,
    sku: transfer.sku_id,
    sourceLocation: transfer.from_location,
    destinationLocation: transfer.to_location,
    sourceStock: finiteOrNull(transfer.source_stock),
    destinationStock: finiteOrNull(transfer.destination_stock),
    destinationDaysLeft: destinationDays,
    leadTimeDays: finiteOrNull(transfer.lead_time_days),
    recommendedQty: transfer.qty,
    reason: transfer.rationale,
    priority,
    status: reviewedIds.has(id) ? "Reviewed" : transfer.status ?? "Recommended",
    sourceCoverBefore: finiteOrNull(transfer.from_days_of_cover_before),
    sourceCoverAfter: finiteOrNull(transfer.from_days_of_cover_after),
    destinationCoverBefore: finiteOrNull(transfer.to_days_of_cover_before),
    destinationCoverAfter: finiteOrNull(transfer.to_days_of_cover_after),
  };
}

function buildColumns(): ReportColumn<TransferRow>[] {
  return [
    textColumn("product", "Product", (row) => row.product),
    textColumn("sku", "SKU", (row) => row.sku),
    textColumn("sourceLocation", "Source location", (row) => row.sourceLocation),
    textColumn("destinationLocation", "Destination location", (row) => row.destinationLocation),
    numberColumn("sourceStock", "Source stock", (row) => row.sourceStock),
    numberColumn("destinationStock", "Destination stock", (row) => row.destinationStock),
    numberColumn("destinationDaysLeft", "Dest. days left", (row) => row.destinationDaysLeft),
    numberColumn("leadTimeDays", "Lead time", (row) => row.leadTimeDays),
    numberColumn("recommendedQty", "Transfer qty", (row) => row.recommendedQty),
    badgeColumn("priority", "Priority", (row) => row.priority),
    textColumn("status", "Status / action", (row) => row.status),
  ];
}

function buildMetrics(rows: TransferRow[]): ReportMetric[] {
  return [
    metric("Transfer recommendations", rows.length, "warning"),
    metric("At-risk destination SKUs", rows.filter((row) => row.priority === "Critical" || row.priority === "High").length, "danger"),
    metric("Excess source SKUs", new Set(rows.map((row) => row.sourceLocation)).size, "neutral"),
    metric("Estimated units to move", rows.reduce((sum, row) => sum + row.recommendedQty, 0), "positive"),
  ];
}

function buildFilterConfig(rows: TransferRow[]): ReportFilterConfig[] {
  return [
    selectFilter("sourceLocation", "Source location", uniqueValues(rows, "sourceLocation")),
    selectFilter("destinationLocation", "Destination location", uniqueValues(rows, "destinationLocation")),
    selectFilter("priority", "Priority", ["Critical", "High", "Medium", "Low"]),
  ];
}

function filterRows(
  rows: TransferRow[],
  search: string,
  filters: Record<string, string>,
): TransferRow[] {
  const needle = search.trim().toLowerCase();
  return rows.filter((row) => {
    if (
      needle &&
      ![row.product, row.sku, row.sourceLocation, row.destinationLocation, row.reason]
        .join(" ")
        .toLowerCase()
        .includes(needle)
    ) {
      return false;
    }
    return Object.entries(filters).every(([key, value]) => {
      if (!value) return true;
      return String(row[key as keyof TransferRow]) === value;
    });
  });
}

function sortRows(
  rows: TransferRow[],
  columns: ReportColumn<TransferRow>[],
  sortKey: string,
  direction: SortDirection,
): TransferRow[] {
  const multiplier = direction === "asc" ? 1 : -1;
  return [...rows].sort((left, right) => {
    const a = sortKey === "priorityRank" ? priorityRank(left.priority) : columnSortValue(columns, sortKey, left);
    const b = sortKey === "priorityRank" ? priorityRank(right.priority) : columnSortValue(columns, sortKey, right);
    if (typeof a === "number" && typeof b === "number") return (a - b) * multiplier;
    return String(a).localeCompare(String(b)) * multiplier;
  });
}

function columnSortValue(
  columns: ReportColumn<TransferRow>[],
  key: string,
  row: TransferRow,
): string | number {
  return columns.find((column) => column.key === key)?.sortValue?.(row) ?? String(row[key as keyof TransferRow] ?? "");
}

function textColumn(
  key: string,
  label: string,
  value: (row: TransferRow) => string,
): ReportColumn<TransferRow> {
  return { key, label, render: value, sortValue: value };
}

function numberColumn(
  key: string,
  label: string,
  value: (row: TransferRow) => number | null,
): ReportColumn<TransferRow> {
  return {
    key,
    label,
    align: "right",
    render: (row) => formatNumber(value(row)),
    sortValue: (row) => value(row) ?? -1,
  };
}

function badgeColumn(
  key: string,
  label: string,
  value: (row: TransferRow) => string,
): ReportColumn<TransferRow> {
  return {
    key,
    label,
    render: (row) => (
      <ReportStatusBadge tone={value(row) === "Critical" ? "danger" : value(row) === "High" ? "warning" : "neutral"}>
        {value(row)}
      </ReportStatusBadge>
    ),
    sortValue: (row) => priorityRank(row.priority),
  };
}

function selectFilter(key: string, label: string, values: string[]): ReportFilterConfig {
  return {
    key,
    label,
    options: values.filter(Boolean).map((value) => ({ label: value, value })),
  };
}

function uniqueValues(rows: TransferRow[], key: keyof TransferRow): string[] {
  return [...new Set(rows.map((row) => String(row[key] ?? "")).filter(Boolean))].sort();
}

function metric(label: string, value: string | number, tone: ReportMetric["tone"]): ReportMetric {
  return { label, value, tone };
}

function inferPriority(daysLeft: number | null, qty: number): TransferRow["priority"] {
  if (daysLeft !== null && daysLeft <= 7) return "Critical";
  if (daysLeft !== null && daysLeft <= 14) return "High";
  if (qty >= 40) return "Medium";
  return "Low";
}

function priorityRank(priority: TransferRow["priority"]): number {
  return { Critical: 4, High: 3, Medium: 2, Low: 1 }[priority];
}

function coverChange(before: number | null, after: number | null): string {
  if (before === null || after === null) return "Unavailable";
  return `${formatNumber(before)}d → ${formatNumber(after)}d`;
}

function formatNumber(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "Unavailable";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: value < 10 ? 1 : 0 }).format(value);
}

function finiteOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isDemoMode(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return (
      sessionStorage.getItem("skubase_demo") === "1" ||
      new URLSearchParams(window.location.search).get("demo") === "1"
    );
  } catch {
    return false;
  }
}
