"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { SectionCard } from "@/components/section-card";
import { BrowserHealthCheckOption } from "@/components/browser-health-check-option";
import {
  getSyncNotice,
  isSyncResult,
  isSyncRunActive,
  isSyncRunStatus,
  unmatchedSyncItems,
  type SyncResult,
  type SyncRunStatus,
} from "@/lib/sync-summary";
import {
  authenticatedFetch,
  getEmbeddedShopifyContext,
  reconnectShopify,
} from "@/lib/shopify-embedded";

const API_BASE = APP_API_BASE_URL;
const POLL_INTERVAL_MS = 2_500;
// A very large store can take longer than this; the run keeps going on the
// server and the last-sync time updates when it finishes.
const POLL_LIMIT_MS = 20 * 60 * 1_000;
const STILL_RUNNING_MESSAGE =
  "This sync is still running in the background. The last sync time updates when it finishes.";
const UNCONFIRMED_MESSAGE =
  "Shopify's sync result could not be confirmed. Check the last sync time, then try again.";

type Connection = {
  connected: boolean;
  shopify_domain: string | null;
  last_sync_at: string | null;
  scope: string | null;
};

function formatRelative(iso: string | null): string {
  if (!iso) return "never";
  try {
    const dt = new Date(iso);
    return dt.toLocaleString();
  } catch {
    return iso;
  }
}

async function fetchSyncRun(runId?: number, signal?: AbortSignal): Promise<SyncRunStatus | null> {
  const query = runId ? `?run_id=${runId}` : "";
  const res = await authenticatedFetch(`${API_BASE}/integrations/shopify/sync/status${query}`, {
    credentials: "include",
    signal,
  });
  if (res.status === 404) return null;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(typeof body?.detail === "string" ? body.detail : `Could not read the sync status (${res.status}).`);
  }
  if (!isSyncRunStatus(body)) throw new Error("Could not read the sync status. Please try again.");
  return body;
}

export default function StoreSyncPage() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [connectionLoading, setConnectionLoading] = useState(true);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [embeddedShop, setEmbeddedShop] = useState<string | null>(null);
  const [installLoading, setInstallLoading] = useState(false);
  const [installError, setInstallError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncInfo, setSyncInfo] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const pollController = useRef<AbortController | null>(null);

  const syncNotice = syncResult ? getSyncNotice(syncResult) : null;

  async function loadConnection(): Promise<Connection | null> {
    setConnectionLoading(true);
    setConnectionError(null);
    try {
      const res = await authenticatedFetch(`${API_BASE}/integrations/shopify/connection`, {
        credentials: "include",
        signal: AbortSignal.timeout(15_000),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(typeof body?.detail === "string" ? body.detail : `Could not check your Shopify connection (${res.status}).`);
      }
      if (typeof body?.connected !== "boolean") throw new Error("Could not read your Shopify connection. Please try again.");
      setConnection(body);
      return body as Connection;
    } catch (error) {
      setConnectionError(error instanceof Error ? error.message : "Could not load your Shopify connection.");
      return null;
    } finally {
      setConnectionLoading(false);
    }
  }

  // The sync runs on the server after POST /sync returns; poll its run until
  // it finishes so the page can show the stored result or the failure.
  async function followSyncRun(runId: number, signal: AbortSignal) {
    const startedAt = Date.now();
    setSyncing(true);
    try {
      while (!signal.aborted) {
        const run = await fetchSyncRun(runId, signal);
        if (!run) throw new Error("The sync run could not be found. Check the last sync time, then try again.");
        if (!isSyncRunActive(run)) {
          if (run.status === "failed") {
            setSyncError(run.error_message || "Sync failed. Please try again.");
          } else if (isSyncResult(run.result)) {
            setSyncResult(run.result);
          } else {
            setSyncError(UNCONFIRMED_MESSAGE);
          }
          void loadConnection();
          return;
        }
        if (Date.now() - startedAt > POLL_LIMIT_MS) {
          setSyncInfo(STILL_RUNNING_MESSAGE);
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
      }
    } catch (error) {
      if (signal.aborted) return;
      setSyncError(error instanceof Error ? error.message : UNCONFIRMED_MESSAGE);
      void loadConnection();
    } finally {
      if (!signal.aborted) setSyncing(false);
    }
  }

  function startFollowing(runId: number) {
    pollController.current?.abort();
    const controller = new AbortController();
    pollController.current = controller;
    void followSyncRun(runId, controller.signal);
  }

  useEffect(() => {
    setEmbeddedShop(getEmbeddedShopifyContext()?.shop || null);
    const controller = new AbortController();
    void loadConnection()
      .then((loaded) => {
        if (!loaded?.connected || controller.signal.aborted) return null;
        // A run started from another tab is shown in progress here too.
        return fetchSyncRun(undefined, controller.signal);
      })
      .then((run) => {
        if (run && !controller.signal.aborted && isSyncRunActive(run)) startFollowing(run.run_id);
      })
      .catch(() => undefined);
    return () => {
      controller.abort();
      pollController.current?.abort();
    };
  }, []);

  async function handleSyncNow() {
    setSyncError(null);
    setSyncInfo(null);
    setSyncResult(null);
    setSyncing(true);
    try {
      const res = await authenticatedFetch(`${API_BASE}/integrations/shopify/sync`, {
        method: "POST",
        credentials: "include",
      });
      const body = await res.json().catch(() => null);
      if (res.status === 409) {
        // Another run owns this store right now; follow it instead.
        const latest = await fetchSyncRun();
        if (latest && isSyncRunActive(latest)) {
          startFollowing(latest.run_id);
          return;
        }
        setSyncError(typeof body?.detail === "string" ? body.detail : "A sync is already running. Please wait for it to finish.");
        setSyncing(false);
        return;
      }
      if (!res.ok) {
        setSyncError(typeof body?.detail === "string" ? body.detail : `Sync failed (${res.status}).`);
        setSyncing(false);
        return;
      }
      if (!isSyncRunStatus(body)) {
        setSyncError("The sync could not be started. Please try again.");
        setSyncing(false);
        return;
      }
      startFollowing(body.run_id);
    } catch {
      setSyncError("The connection was interrupted before sync could be started. Check the last sync time, then try again.");
      setSyncing(false);
    }
  }

  async function handleReconnect() {
    setInstallError(null);
    setInstallLoading(true);
    try {
      await reconnectShopify(connection?.shopify_domain || undefined);
    } catch (error) {
      setInstallError(error instanceof Error ? error.message : "Could not reconnect Shopify. Please try again.");
    } finally {
      setInstallLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Shopify connection</p>
            <h2 className="section-title">
              {connectionLoading ? "Checking Shopify connection…" : connectionError ? "Connection unavailable" : connection?.connected ? "Connected" : "Connect your Shopify store"}
            </h2>
          </div>
          {connectionLoading || connectionError ? null : connection?.connected ? (
            <span className="status-badge status-succeeded">Active</span>
          ) : (
            <span className="status-badge status-failed">Not connected</span>
          )}
        </div>

        {connectionLoading ? (
          <p className="section-copy" role="status">Loading your Shopify connection…</p>
        ) : connectionError ? (
          <div>
            <p className="auth-error" role="alert">{connectionError}</p>
            <button type="button" className="button button-primary" onClick={() => void loadConnection()}>Try again</button>
            <Link href="/billing" className="button button-ghost">View billing</Link>
          </div>
        ) : connection?.connected ? (
          <>
            <p className="section-copy">
              Connected to <strong>{connection.shopify_domain}</strong>. Last
              sync: {formatRelative(connection.last_sync_at)}.
            </p>
            <p className="section-copy" style={{ margin: "10px 0 18px" }}>Read-only sync · your Shopify stock and orders stay unchanged.</p>
            <div className="button-row">
              <button
                type="button"
                className="button button-primary"
                onClick={handleSyncNow}
                disabled={syncing}
              >
                {syncing ? "Syncing…" : "Sync now"}
              </button>
              <button
                type="button"
                className="button button-ghost"
                onClick={() => void handleReconnect()}
                disabled={installLoading || syncing}
              >
                {installLoading ? "Connecting…" : "Reconnect"}
              </button>
            </div>
            {installError ? <p className="auth-error" role="alert">{installError}</p> : null}
            {syncing ? (
              <p className="section-copy" role="status" style={{ marginTop: "16px" }}>
                Syncing products, inventory, and recent orders. You can leave this page; the sync keeps running.
              </p>
            ) : null}
            {syncError ? (
              <p className="auth-error" style={{ marginTop: "16px" }}>
                {syncError}
              </p>
            ) : null}
            {syncInfo ? (
              <p className="section-copy" role="status" style={{ marginTop: "16px" }}>
                {syncInfo}
              </p>
            ) : null}
            {syncResult ? (
              <div className="sync-safety-note" role="status" style={{ marginTop: "16px" }}>
                <strong>{syncResult.status === "partial" ? "Inventory refreshed; order import incomplete" : "Sync complete"}</strong>
                <p className="section-copy" style={{ margin: 0 }}>
                  Synced{" "}
                  <strong>{(syncResult.variants_imported ?? syncResult.products_count ?? 0).toLocaleString()}</strong>{" "}
                  product variants and{" "}
                  <strong>{(syncResult.order_line_items_count ?? 0).toLocaleString()}</strong>{" "}
                  new order line items.
                </p>
                {typeof syncResult.inventory_variants_active === "number" ? (
                  <p className="section-copy" style={{ margin: "8px 0 0" }}>
                    <strong>{syncResult.inventory_variants_active.toLocaleString()}</strong> active, stock-tracked variants included in inventory planning.
                    {(syncResult.inventory_variants_excluded ?? 0) > 0 ? ` ${syncResult.inventory_variants_excluded!.toLocaleString()} draft, archived, gift card, or untracked variants excluded.` : ""}
                    {(syncResult.inventory_rows_retired ?? 0) > 0 ? " Outdated inventory records were removed from current totals; product and order history is retained." : ""}
                  </p>
                ) : null}
                <p className="section-copy" style={{ margin: "8px 0 0" }}>
                  Products scanned:{" "}
                  <strong>{(syncResult.products_scanned ?? 0).toLocaleString()}</strong>.
                  Orders scanned:{" "}
                  <strong>{(syncResult.orders_scanned ?? 0).toLocaleString()}</strong>.
                  Line items scanned:{" "}
                  <strong>{(syncResult.line_items_scanned ?? 0).toLocaleString()}</strong>.
                  Already imported:{" "}
                  <strong>{(syncResult.line_item_skip_reasons?.already_imported ?? 0).toLocaleString()}</strong>.
                  Unmatched items:{" "}
                  <strong>{unmatchedSyncItems(syncResult).toLocaleString()}</strong>.
                </p>
                {syncResult.top_skip_reason && syncResult.top_skip_reason !== "already_imported" ? (
                  <p className="section-copy" style={{ margin: "8px 0 0" }}>
                    Top skip reason: <strong>{syncResult.top_skip_reason}</strong>.
                  </p>
                ) : null}
              </div>
            ) : null}
            {syncNotice ? (
              <div className={syncNotice.warning ? "import-error" : "sync-safety-note"} role={syncNotice.warning ? "alert" : "status"} style={{ marginTop: "12px" }}>
                <strong>{syncNotice.title}</strong>
                <p className="section-copy" style={{ margin: "8px 0 0" }}>
                  {syncNotice.message}
                </p>
              </div>
            ) : null}
            {syncResult ? (
              <div className="button-row" style={{ marginTop: "16px" }}>
                <Link href="/analytics" className="button button-ghost">Review inventory</Link>
                <Link href="/actions" className="button button-ghost">Review actions</Link>
              </div>
            ) : null}
          </>
        ) : (
          <>
            <p className="section-copy">
              Skubase is in Shopify App Store review and is not listed yet.
              You can start with CSV imports below or try the free inventory
              health check while Shopify access is being arranged.
            </p>
            <div className="sync-safety-note" role="status">
              <strong>Safe by default.</strong> Initial Shopify access is
              read-only for planning. Any future write-back flow should require
              a preview and explicit approval before touching Shopify stock.
            </div>
            <p className="section-copy">If Skubase is already installed for your store, open it from the Apps section of Shopify Admin to connect that store.</p>
            {embeddedShop ? (
              <button type="button" className="button button-primary" disabled={installLoading} onClick={() => void handleReconnect()}>
                {installLoading ? "Connecting…" : "Reconnect this store"}
              </button>
            ) : (
              <div className="button-row">
                <a className="button button-ghost" href="mailto:info@skubase.io?subject=Skubase%20Shopify%20access">Ask about Shopify access</a>
                <a className="button button-ghost" href="https://admin.shopify.com" target="_top">Open Shopify Admin if already installed</a>
              </div>
            )}
            {installError ? <p className="auth-error" role="alert">{installError}</p> : null}
          </>
        )}
        <BrowserHealthCheckOption />
      </SectionCard>

      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Start with your existing exports</p>
            <h2 className="section-title section-title-small">CSV imports work too</h2>
          </div>
        </div>
        <p className="section-copy">Bring your existing exports into Skubase. No Shopify app installation required.</p>
        <div className="import-options">
          <div className="import-option"><div><h3>Stocky</h3><p>Catalog and stock for CSV workspaces. Supported costs and lead times for connected Shopify catalogs.</p></div><Link href="/import-stocky" className="button button-secondary">Import Stocky CSV</Link></div>
          <div className="import-option"><div><h3>ShipStation</h3><p>Non-Shopify shipment history. Add current inventory separately for reorder planning.</p></div><Link href="/import-shipstation" className="button button-secondary">Import ShipStation CSV</Link></div>
        </div>
        <details className="workspace-disclosure"><summary>How imports affect your inventory</summary>
        <p className="section-copy">
          In a CSV-only workspace, Stocky imports supply catalog details and a stock snapshot.
          When Shopify is connected or its catalog is already synced, Shopify remains the stock source:
          Stocky CSVs can update supported costs and lead times for unambiguous Shopify variants, but do not add inventory quantities.
          ShipStation imports supply non-Shopify shipment history. Reorder planning needs
          both current inventory and recent sales for matching SKUs, plus supplier
          lead times. Shipment history alone does not tell us how much stock you have.
          These CSV imports do not require a Shopify app installation.
        </p>
        </details>
        <p className="section-copy">After importing, <Link href="/lead-time-settings">check your supplier lead times</Link> and <Link href="/actions">review your action queue</Link>. Add missing history before relying on demand estimates.</p>
      </SectionCard>
    </div>
  );
}
