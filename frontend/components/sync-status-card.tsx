import { EmptyState } from "@/components/empty-state";
import { SectionCard } from "@/components/section-card";
import type { LatestShopifySyncStatusResponse } from "@/lib/api";
import {
  buildSyncRunSummary,
  formatSyncTimestamp
} from "@/lib/app-helpers";

export function SyncStatusCard({
  title = "Latest Sync Status",
  isLoading,
  errorMessage,
  status
}: {
  title?: string;
  isLoading: boolean;
  errorMessage: string | null;
  status: LatestShopifySyncStatusResponse | null;
}) {
  if (isLoading) {
    return (
      <EmptyState
        title="Loading sync status"
        description="Checking the most recent Shopify ingest run for this shop."
      />
    );
  }

  if (errorMessage) {
    return (
      <EmptyState
        title="Sync status unavailable"
        description={errorMessage}
        tone="error"
      />
    );
  }

  if (!status) {
    return (
      <EmptyState
        title="No store selected"
        description="Add a Shopify domain on the Store Sync page to track the latest ingestion run."
      />
    );
  }

  if (!status.latest_run) {
    return (
      <EmptyState
        title={title}
        description={`No Shopify sync runs have been recorded yet for ${status.shopify_domain}.`}
      />
    );
  }

  return (
    <SectionCard>
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">Operations</p>
          <h2 className="section-title section-title-small">{title}</h2>
        </div>
        <span className={`status-badge status-${status.latest_run.status}`}>
          {status.latest_run.status}
        </span>
      </div>

      <p className="section-copy sync-summary">
        {buildSyncRunSummary(status.latest_run)} for{" "}
        <span className="inline-code">{status.shopify_domain}</span>.
      </p>

      <div className="stats-grid">
        <div className="stat-item">
          <span className="stat-label">Started</span>
          <strong>{formatSyncTimestamp(status.latest_run.started_at)}</strong>
        </div>
        <div className="stat-item">
          <span className="stat-label">Products</span>
          <strong>{status.latest_run.products_count}</strong>
        </div>
        <div className="stat-item">
          <span className="stat-label">Inventory rows</span>
          <strong>{status.latest_run.inventory_rows_count}</strong>
        </div>
        <div className="stat-item">
          <span className="stat-label">Order lines</span>
          <strong>{status.latest_run.order_line_items_count}</strong>
        </div>
      </div>

      <div className="meta-stack">
        {status.latest_run.finished_at ? (
          <p className="meta-copy">
            Finished {formatSyncTimestamp(status.latest_run.finished_at)}
          </p>
        ) : null}
        {status.latest_run.error_message ? (
          <p className="meta-copy meta-copy-error">
            {status.latest_run.error_message}
          </p>
        ) : null}
      </div>
    </SectionCard>
  );
}
