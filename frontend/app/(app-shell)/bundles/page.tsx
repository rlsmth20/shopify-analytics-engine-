"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

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
import {
  currency,
  fetchBundles,
  type BundleHealth,
  type BundleOpportunity,
} from "@/lib/api-v2";
import { exportReportRowsCsv } from "@/lib/report-export";

type BundleTab = "opportunities" | "mappings" | "requirements";
type QuickView = "all" | "bundle" | "cross-sell" | "promo" | "high-confidence";
type SortDirection = "asc" | "desc";

export default function BundlesPage() {
  return (
    <GatedFeature
      capability="bundleOpportunities"
      title="Find products customers buy together"
      description="Upgrade to Growth to use order history for bundle, kit, cross-sell, and promo opportunities."
    >
      <BundlesContent />
    </GatedFeature>
  );
}

function BundlesContent() {
  const [bundles, setBundles] = useState<BundleHealth[]>([]);
  const [opportunities, setOpportunities] = useState<BundleOpportunity[]>([]);
  const [ordersAnalyzed, setOrdersAnalyzed] = useState(0);
  const [activeTab, setActiveTab] = useState<BundleTab>("opportunities");
  const [quickView, setQuickView] = useState<QuickView>("all");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [sortKey, setSortKey] = useState("co_purchase_count");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchBundles(controller.signal)
      .then((r) => {
        setBundles(r.bundles ?? []);
        setOpportunities(r.opportunities ?? []);
        setOrdersAnalyzed(r.orders_analyzed ?? 0);
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
  const columns = useMemo(() => buildColumns(), []);
  const filterConfig = useMemo(() => buildFilterConfig(opportunities), [opportunities]);
  const visibleOpportunities = useMemo(
    () =>
      sortRows(
        filterOpportunities(opportunities, search, filters, quickView),
        columns,
        sortKey,
        sortDirection,
      ),
    [opportunities, search, filters, quickView, columns, sortKey, sortDirection],
  );
  const metrics = useMemo(
    () => buildMetrics(opportunities, visibleOpportunities, ordersAnalyzed),
    [opportunities, visibleOpportunities, ordersAnalyzed],
  );

  function updateSort(key: string) {
    if (sortKey === key) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDirection(key === "bundleIdea" ? "asc" : "desc");
  }

  function exportOpportunities() {
    exportReportRowsCsv({
      filename: `skubase-bundle-opportunities-${new Date().toISOString().slice(0, 10)}.csv`,
      rows: visibleOpportunities,
      columns: [
        { label: "Bundle idea", value: (row) => bundleIdea(row) },
        { label: "Product A", value: (row) => row.product_a_name },
        { label: "Product B", value: (row) => row.product_b_name },
        { label: "Co-purchase count", value: (row) => row.co_purchase_count },
        { label: "Confidence A to B", value: (row) => percent(row.confidence_a_to_b) },
        { label: "Confidence B to A", value: (row) => percent(row.confidence_b_to_a) },
        { label: "Lift", value: (row) => row.lift ?? "" },
        { label: "Combined revenue", value: (row) => row.combined_revenue },
        { label: "Suggested action", value: (row) => row.suggested_action },
        { label: "Opportunity type", value: (row) => row.opportunity_type },
        { label: "Explanation", value: (row) => row.explanation },
      ],
    });
  }

  if (loading && opportunities.length === 0 && bundles.length === 0) {
    return <div className="page-loading">Analyzing bundle opportunities...</div>;
  }
  if (error) return <p className="page-error-copy">{error}</p>;

  return (
    <div className="bundles-page page-stack">
      <section className="section-card bundle-hero">
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Bundle planning</p>
            <h1 className="section-title section-title-small">
              Find products customers already buy together
            </h1>
            <p className="section-copy">
              Skubase looks at historical orders to suggest bundle, kit, and
              cross-sell opportunities. Bundle inventory tracking still requires
              component mappings.
            </p>
          </div>
          {isDemo ? <ReportStatusBadge tone="demo">Sample data</ReportStatusBadge> : null}
        </div>
      </section>

      <ReportMetricCards metrics={metrics} />

      <div className="bundle-tabs" role="tablist" aria-label="Bundle sections">
        <TabButton active={activeTab === "opportunities"} onClick={() => setActiveTab("opportunities")}>
          Bundle Opportunities
        </TabButton>
        <TabButton active={activeTab === "mappings"} onClick={() => setActiveTab("mappings")}>
          Bundle Inventory Requirements
        </TabButton>
        <TabButton active={activeTab === "requirements"} onClick={() => setActiveTab("requirements")}>
          Data Requirements
        </TabButton>
      </div>

      {activeTab === "opportunities" ? (
        <section className="section-card bundle-opportunity-card">
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">Frequently bought together</p>
              <h2 className="section-title section-title-small">Bundle opportunity report</h2>
              <p className="section-copy">
                Ranked by co-purchase count, confidence, lift, and combined revenue.
                Use these as bundle, cross-sell, or promo-test candidates.
              </p>
            </div>
            <button
              type="button"
              className="button button-primary"
              onClick={exportOpportunities}
              disabled={visibleOpportunities.length === 0}
            >
              Export filtered CSV
            </button>
          </div>

          <div className="quick-filter-row" aria-label="Quick filters">
            {[
              ["all", "All"],
              ["bundle", "Bundle opportunity"],
              ["cross-sell", "Cross-sell"],
              ["promo", "Promo test"],
              ["high-confidence", "High confidence"],
            ].map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={`quick-filter-chip${quickView === key ? " quick-filter-chip-active" : ""}`}
                onClick={() => setQuickView(key as QuickView)}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="report-control-panel">
            <ReportSearchInput value={search} onChange={setSearch} />
            <ReportFilters
              filters={filterConfig}
              values={filters}
              onChange={(key, value) =>
                setFilters((current) => ({ ...current, [key]: value }))
              }
              onReset={() => {
                setSearch("");
                setFilters({});
                setQuickView("all");
              }}
            />
          </div>

          {opportunities.length === 0 ? (
            <ReportEmptyState
              title="Bundle recommendations require order-line history"
              description="Skubase needs enough completed orders to find products that are frequently bought together."
              actions={<a className="button button-secondary" href="/store-sync">Check store sync</a>}
            />
          ) : (
            <ReportTable
              columns={columns}
              rows={visibleOpportunities}
              rowKey={(row) => row.id}
              selectedRowKey={selectedRowId}
              onRowClick={(row) => setSelectedRowId((current) => (current === row.id ? null : row.id))}
              renderRowDetails={(row) => <BundleOpportunityDetails row={row} />}
              sortKey={sortKey}
              sortDirection={sortDirection}
              onSort={updateSort}
              loading={loading}
              emptyState={
                <ReportEmptyState
                  title="No bundle opportunities match"
                  description="Clear filters or search for another product, SKU, category, or opportunity type."
                />
              }
            />
          )}
        </section>
      ) : null}

      {activeTab === "mappings" ? <BundleMappings bundles={bundles} /> : null}
      {activeTab === "requirements" ? <BundleRequirements ordersAnalyzed={ordersAnalyzed} /> : null}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      className={`bundle-tab${active ? " bundle-tab-active" : ""}`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function BundleOpportunityDetails({ row }: { row: BundleOpportunity }) {
  return (
    <div className="bundle-opportunity-detail">
      <div>
        <p className="report-detail-eyebrow">Why this opportunity matters</p>
        <h3>{bundleIdea(row)}</h3>
        <p>{row.explanation}</p>
      </div>
      <dl className="report-detail-grid">
        <Detail label="Co-purchase count" value={String(row.co_purchase_count)} />
        <Detail label="Support" value={percent(row.support)} />
        <Detail label="Confidence A to B" value={percent(row.confidence_a_to_b)} />
        <Detail label="Confidence B to A" value={percent(row.confidence_b_to_a)} />
        <Detail label="Lift" value={row.lift === null ? "Unavailable" : `${row.lift.toFixed(2)}x`} />
        <Detail label="Combined revenue" value={currency(row.combined_revenue)} />
        <Detail
          label="Avg order impact"
          value={
            row.average_order_value_impact === null
              ? "Unavailable"
              : currency(row.average_order_value_impact)
          }
        />
        <Detail label="Suggested action" value={row.suggested_action} />
      </dl>
      <div className="bundle-action-note">
        This does not create a Shopify bundle automatically. Use it to test a bundle,
        cross-sell, or promotion in your merchandising workflow.
      </div>
    </div>
  );
}

function BundleMappings({ bundles }: { bundles: BundleHealth[] }) {
  if (bundles.length === 0) {
    return (
      <DataQualityNote title="Bundle inventory tracking requires component mappings">
        <p>
          Bundle Opportunities can identify products worth packaging or cross-selling,
          but inventory tracking requires parent bundle and component SKU mappings.
          No live bundle mappings are configured yet.
        </p>
      </DataQualityNote>
    );
  }

  return (
    <section className="bundle-mapping-grid">
      {bundles.map((b) => (
        <article
          key={b.bundle_sku_id}
          className={`bundle-card${b.max_bundles_sellable === 0 ? " bundle-card-broken" : ""}`}
        >
          <div className="bundle-head">
            <div>
              <h4 className="bundle-name">{b.bundle_name}</h4>
              <p className="muted small">{b.bundle_sku_id}</p>
            </div>
            <div className="bundle-capacity">
              <p className="bundle-capacity-value">{b.max_bundles_sellable}</p>
              <p className="bundle-capacity-label">sellable now</p>
            </div>
          </div>
          <div className="bundle-limiting">
            <span className="muted small">Bottleneck component</span>
            <p>{b.limiting_component_name}</p>
          </div>
          <ul className="bundle-components">
            {b.component_status.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
          {b.total_component_value_at_risk > 0 ? (
            <p className="bundle-risk">
              {currency(b.total_component_value_at_risk)} in component inventory is
              stranded behind this bottleneck.
            </p>
          ) : null}
          <p className="bundle-recommendation">{b.recommended_action}</p>
        </article>
      ))}
    </section>
  );
}

function BundleRequirements({ ordersAnalyzed }: { ordersAnalyzed: number }) {
  return (
    <DataQualityNote title="What Skubase needs for bundle recommendations">
      <p>
        Bundle Opportunities use completed order-line history. Skubase analyzed{" "}
        {ordersAnalyzed.toLocaleString()} orders for this view. Bundle inventory
        health requires separate bundle/component mappings before Skubase can
        calculate bottlenecks or max buildable bundles.
      </p>
    </DataQualityNote>
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

function buildColumns(): ReportColumn<BundleOpportunity>[] {
  return [
    textColumn("bundleIdea", "Bundle idea", bundleIdea),
    textColumn("product_a_name", "Product A", (row) => row.product_a_name),
    textColumn("product_b_name", "Product B", (row) => row.product_b_name),
    numberColumn("co_purchase_count", "Co-purchase count", (row) => row.co_purchase_count),
    percentColumn("confidence_a_to_b", "Confidence", (row) => row.confidence_a_to_b),
    numberColumn("lift", "Lift", (row) => row.lift),
    moneyColumn("combined_revenue", "Combined revenue", (row) => row.combined_revenue),
    badgeColumn("suggested_action", "Suggested action", (row) => row.suggested_action),
  ];
}

function buildMetrics(
  allRows: BundleOpportunity[],
  visibleRows: BundleOpportunity[],
  ordersAnalyzed: number,
): ReportMetric[] {
  const topConfidence = Math.max(
    0,
    ...visibleRows.map((row) => Math.max(row.confidence_a_to_b, row.confidence_b_to_a)),
  );
  return [
    metric("Bundle opportunities", visibleRows.length, "warning"),
    metric("Estimated bundle revenue", currency(sumMoney(visibleRows)), "positive"),
    metric("Top co-purchase confidence", percent(topConfidence), "positive"),
    metric("Orders analyzed", ordersAnalyzed || allRows.reduce((max, row) => Math.max(max, row.co_purchase_count), 0), "neutral"),
  ];
}

function buildFilterConfig(rows: BundleOpportunity[]): ReportFilterConfig[] {
  return [
    selectFilter("category", "Category", uniqueCategories(rows)),
    selectFilter("confidenceBucket", "Minimum confidence", ["10%+", "20%+", "30%+"]),
    selectFilter("countBucket", "Co-purchase count", ["3+", "10+", "25+", "50+"]),
    selectFilter("opportunity_type", "Opportunity type", uniqueValues(rows, "opportunity_type")),
  ];
}

function filterOpportunities(
  rows: BundleOpportunity[],
  search: string,
  filters: Record<string, string>,
  quickView: QuickView,
): BundleOpportunity[] {
  const needle = search.trim().toLowerCase();
  return rows.filter((row) => {
    if (
      needle &&
      ![
        row.product_a_name,
        row.product_a_sku,
        row.product_a_category,
        row.product_b_name,
        row.product_b_sku,
        row.product_b_category,
        row.opportunity_type,
        row.suggested_action,
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle)
    ) {
      return false;
    }
    if (quickView === "bundle" && row.opportunity_type !== "Bundle") return false;
    if (quickView === "cross-sell" && row.opportunity_type !== "Cross-sell") return false;
    if (quickView === "promo" && row.opportunity_type !== "Promo test") return false;
    if (quickView === "high-confidence" && maxConfidence(row) < 0.25) return false;

    return Object.entries(filters).every(([key, value]) => {
      if (!value) return true;
      if (key === "category") {
        return row.product_a_category === value || row.product_b_category === value;
      }
      if (key === "confidenceBucket") return maxConfidence(row) >= Number(value.replace(/[^0-9]/g, "")) / 100;
      if (key === "countBucket") return row.co_purchase_count >= Number(value.replace(/[^0-9]/g, ""));
      if (key in row) return String(row[key as keyof BundleOpportunity]) === value;
      return true;
    });
  });
}

function sortRows(
  rows: BundleOpportunity[],
  columns: ReportColumn<BundleOpportunity>[],
  sortKey: string,
  direction: SortDirection,
): BundleOpportunity[] {
  const multiplier = direction === "asc" ? 1 : -1;
  return [...rows].sort((left, right) => {
    const a = columns.find((item) => item.key === sortKey)?.sortValue?.(left) ?? "";
    const b = columns.find((item) => item.key === sortKey)?.sortValue?.(right) ?? "";
    if (typeof a === "number" && typeof b === "number") return (a - b) * multiplier;
    return String(a).localeCompare(String(b)) * multiplier;
  });
}

function textColumn(
  key: string,
  label: string,
  value: (row: BundleOpportunity) => string,
): ReportColumn<BundleOpportunity> {
  return { key, label, render: value, sortValue: value };
}

function numberColumn(
  key: string,
  label: string,
  value: (row: BundleOpportunity) => number | null,
): ReportColumn<BundleOpportunity> {
  return {
    key,
    label,
    align: "right",
    render: (row) => formatNumber(value(row)),
    sortValue: (row) => value(row) ?? -1,
  };
}

function percentColumn(
  key: string,
  label: string,
  value: (row: BundleOpportunity) => number,
): ReportColumn<BundleOpportunity> {
  return {
    key,
    label,
    align: "right",
    render: (row) => percent(value(row)),
    sortValue: value,
  };
}

function moneyColumn(
  key: string,
  label: string,
  value: (row: BundleOpportunity) => number,
): ReportColumn<BundleOpportunity> {
  return {
    key,
    label,
    align: "right",
    render: (row) => currency(value(row)),
    sortValue: value,
  };
}

function badgeColumn(
  key: string,
  label: string,
  value: (row: BundleOpportunity) => string,
): ReportColumn<BundleOpportunity> {
  return {
    key,
    label,
    render: (row) => (
      <ReportStatusBadge tone={value(row) === "Create bundle" ? "positive" : value(row) === "Watch" ? "neutral" : "warning"}>
        {value(row)}
      </ReportStatusBadge>
    ),
    sortValue: value,
  };
}

function selectFilter(key: string, label: string, values: string[]): ReportFilterConfig {
  return {
    key,
    label,
    options: values.filter(Boolean).map((value) => ({ label: value, value })),
  };
}

function uniqueValues(rows: BundleOpportunity[], key: keyof BundleOpportunity): string[] {
  return [...new Set(rows.map((row) => String(row[key] ?? "")).filter(Boolean))].sort();
}

function uniqueCategories(rows: BundleOpportunity[]): string[] {
  return [
    ...new Set(
      rows
        .flatMap((row) => [row.product_a_category, row.product_b_category])
        .filter((value): value is string => Boolean(value)),
    ),
  ].sort();
}

function metric(label: string, value: string | number, tone: ReportMetric["tone"]): ReportMetric {
  return { label, value, tone };
}

function bundleIdea(row: BundleOpportunity): string {
  return `${row.product_a_name} + ${row.product_b_name}`;
}

function maxConfidence(row: BundleOpportunity): number {
  return Math.max(row.confidence_a_to_b, row.confidence_b_to_a);
}

function sumMoney(rows: BundleOpportunity[]): number {
  return rows.reduce((sum, row) => sum + row.combined_revenue, 0);
}

function percent(value: number): string {
  if (!Number.isFinite(value)) return "Unavailable";
  return `${Math.round(value * 100)}%`;
}

function formatNumber(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "Unavailable";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: value < 10 ? 2 : 0 }).format(value);
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
