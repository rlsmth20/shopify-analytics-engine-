"use client";

import { useState, type FormEvent } from "react";

import { EmptyState } from "@/components/empty-state";
import { KpiCard } from "@/components/kpi-card";
import { SectionCard } from "@/components/section-card";
import { SyncStatusCard } from "@/components/sync-status-card";
import type { ShopifyIngestionResponse } from "@/lib/api";
import { triggerShopifyIngestion } from "@/lib/api";
import { useStoredShopDomain } from "@/lib/use-stored-shop-domain";
import { useSyncStatus } from "@/lib/use-sync-status";

export default function StoreSyncPage() {
  const { shopifyDomain, setShopifyDomain } = useStoredShopDomain();
  const {
    latestSyncStatus,
    isLoadingSyncStatus,
    syncStatusError,
    reloadLatestSyncStatus
  } = useSyncStatus(shopifyDomain);
  const [accessToken, setAccessToken] = useState("");
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestionError, setIngestionError] = useState<string | null>(null);
  const [ingestionResult, setIngestionResult] =
    useState<ShopifyIngestionResponse | null>(null);

  async function handleIngestionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedDomain = shopifyDomain.trim();
    const normalizedAccessToken = accessToken.trim();

    if (!normalizedDomain || !normalizedAccessToken) {
      setIngestionError("Enter both a Shopify domain and access token first.");
      setIngestionResult(null);
      return;
    }

    setIsIngesting(true);
    setIngestionError(null);
    setIngestionResult(null);

    try {
      const result = await triggerShopifyIngestion({
        shopify_domain: normalizedDomain,
        access_token: normalizedAccessToken
      });
      setIngestionResult(result);
      await reloadLatestSyncStatus(normalizedDomain);
    } catch (error) {
      setIngestionError(
        error instanceof Error
          ? error.message
          : "The Shopify ingestion request failed."
      );
    } finally {
      setIsIngesting(false);
    }
  }

  return (
    <div className="page-stack">
      <div className="kpi-grid kpi-grid-tight">
        <KpiCard
          label="Connected domain"
          value={shopifyDomain.trim() || "Not set"}
          note="Stored locally for the current workspace"
        />
        <KpiCard
          label="Latest sync"
          value={latestSyncStatus?.latest_run?.status ?? (isLoadingSyncStatus ? "..." : "None")}
          note="Most recent manual ingest run"
        />
      </div>

      <div className="content-grid content-grid-2-1">
        <SectionCard>
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">Connection</p>
              <h2 className="section-title">Manual Shopify ingest</h2>
            </div>
            <p className="section-copy">
              Trigger a one-shop ingest into the backend database. Actions will
              prefer DB-backed data when usable.
            </p>
          </div>

          <form className="stack-form" onSubmit={handleIngestionSubmit}>
            <label className="field-label">
              <span>Shopify domain</span>
              <input
                className="input-control"
                type="text"
                name="shopify_domain"
                placeholder="store-name.myshopify.com"
                value={shopifyDomain}
                onChange={(event) => setShopifyDomain(event.target.value)}
                autoComplete="off"
              />
            </label>

            <label className="field-label">
              <span>Access token</span>
              <input
                className="input-control"
                type="password"
                name="access_token"
                placeholder="shpat_..."
                value={accessToken}
                onChange={(event) => setAccessToken(event.target.value)}
                autoComplete="off"
              />
            </label>

            <div className="button-row">
              <button type="submit" className="button button-primary" disabled={isIngesting}>
                {isIngesting ? "Running ingest..." : "Run Shopify ingest"}
              </button>
            </div>
          </form>

          {ingestionError ? (
            <div className="inline-message inline-message-error" role="alert">
              <p className="inline-message-title">Ingest failed</p>
              <p className="inline-message-copy">{ingestionError}</p>
            </div>
          ) : null}
        </SectionCard>

        <SyncStatusCard
          isLoading={isLoadingSyncStatus}
          errorMessage={syncStatusError}
          status={latestSyncStatus}
        />
      </div>

      {ingestionResult ? (
        <SectionCard>
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">Result</p>
              <h2 className="section-title section-title-small">Latest ingest output</h2>
            </div>
          </div>
          <div className="kpi-grid kpi-grid-tight">
            <ProcessedCountCard label="Shops" value={ingestionResult.shops.processed} />
            <ProcessedCountCard label="Products" value={ingestionResult.products.processed} />
            <ProcessedCountCard
              label="Inventory rows"
              value={ingestionResult.inventory_rows.processed}
            />
            <ProcessedCountCard
              label="Order line items"
              value={ingestionResult.order_line_items.processed}
            />
          </div>
        </SectionCard>
      ) : (
        <EmptyState
          title="No ingest result yet"
          description="Run a manual Shopify ingest to populate the store catalog and sync history."
        />
      )}
    </div>
  );
}

function ProcessedCountCard({ label, value }: { label: string; value: number }) {
  return <KpiCard label={label} value={value} note="Processed in the latest run" />;
}
